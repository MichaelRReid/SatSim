"""Mission Manager service - the primary orchestrator."""

import logging
import math
from satsim.bus.middleware import BaseService
from satsim.uci.messages import (
    Header, UCIMessage,
    ImageryCapabilityCommand, MissionPlan, StatusRequest, PowerModeCommand,
    AttitudeStatusReport, NavigationStatusReport, ImageryReport,
    SensorStatusReport, FaultReport, SlewCommand, SensorActivateCommand,
    SensorCalibrationCommand, PlanStatusReport, HeartbeatMessage,
    TargetDetectionReport,
)

logger = logging.getLogger("satsim.mission_manager")


class MissionManagerService(BaseService):
    """Orchestrates mission execution across all spacecraft services."""

    def __init__(self, service_id: str = "MISSION_MGR", env=None):
        super().__init__(service_id, env)
        self._mission_log = []
        self._pending_commands = {}  # message_id -> command context
        self._current_plan = None
        self._plan_step = 0
        self._plan_state = "WAITING"
        self._last_attitude = None
        self._last_nav = None
        self._last_imagery_report = None
        self._awaiting_attitude = False
        self._awaiting_imagery = False
        self._current_imagery_cmd = None
        self._power_state = "ON"

    def start(self):
        super().start()
        if self.mwa:
            self.mwa.subscribe(ImageryCapabilityCommand)
            self.mwa.subscribe(MissionPlan)
            self.mwa.subscribe(StatusRequest)
            self.mwa.subscribe(PowerModeCommand)
            self.mwa.subscribe(AttitudeStatusReport)
            self.mwa.subscribe(NavigationStatusReport)
            self.mwa.subscribe(ImageryReport)
            self.mwa.subscribe(SensorStatusReport)
            self.mwa.subscribe(FaultReport)
            self.mwa.subscribe(TargetDetectionReport)
        if self.env:
            self.env.clock.register_timer(self.send_heartbeat, 30)

    def stop(self):
        super().stop()

    def handle_message(self, message: UCIMessage):
        if isinstance(message, ImageryCapabilityCommand):
            self._handle_imagery_command(message)
        elif isinstance(message, MissionPlan):
            self._handle_mission_plan(message)
        elif isinstance(message, StatusRequest):
            if message.TargetServiceID == self.service_id:
                self._publish(self.get_status())
        elif isinstance(message, PowerModeCommand):
            if message.TargetServiceID == self.service_id:
                self._power_state = message.PowerState
        elif isinstance(message, AttitudeStatusReport):
            self._handle_attitude_report(message)
        elif isinstance(message, NavigationStatusReport):
            self._last_nav = message
        elif isinstance(message, ImageryReport):
            self._handle_imagery_report(message)
        elif isinstance(message, SensorStatusReport):
            pass  # logged
        elif isinstance(message, FaultReport):
            self._handle_fault(message)
        elif isinstance(message, TargetDetectionReport):
            self._log_event("ATR_DETECTION", {
                "reference_image": message.ReferenceImageID,
                "detection_count": message.DetectionCount,
            })

    def _handle_imagery_command(self, cmd: ImageryCapabilityCommand):
        self._log_event("IMAGERY_CMD_RECEIVED", {
            "capability_id": cmd.CapabilityID,
            "sensor_mode": cmd.SensorMode,
            "target_lat": cmd.Target.Latitude,
            "target_lon": cmd.Target.Longitude,
        })

        self._current_imagery_cmd = cmd

        # Query NAV for orbit state
        self._publish(StatusRequest(
            header=Header(SenderID=self.service_id),
            TargetServiceID="GNC_01",
        ))

        # Compute pointing vector to target (simplified)
        az = cmd.Target.Longitude % 360
        el = 90.0 - abs(cmd.Target.Latitude)

        # Set state BEFORE publishing (synchronous routing)
        self._awaiting_attitude = True
        self._awaiting_imagery = False

        # Send slew command
        self._publish(SlewCommand(
            header=Header(SenderID=self.service_id, Priority=cmd.header.Priority),
            Azimuth_deg=az,
            Elevation_deg=el,
            Stabilization_ms=500,
        ))

    def _handle_attitude_report(self, report: AttitudeStatusReport):
        self._last_attitude = report

        if self._awaiting_attitude and report.PointingError_deg < 0.05:
            self._awaiting_attitude = False
            cmd = self._current_imagery_cmd
            if cmd:
                self._log_event("POINTING_SETTLED", {
                    "error_deg": report.PointingError_deg,
                })
                # Activate sensor
                self._publish(SensorActivateCommand(
                    header=Header(SenderID=self.service_id),
                    CapabilityID=cmd.CapabilityID,
                    IntegrationTime_ms=int(cmd.CollectionDuration_sec * 1000 / 10),
                    GainMode="AUTO",
                ))
                self._awaiting_imagery = True

    def _handle_imagery_report(self, report: ImageryReport):
        self._last_imagery_report = report
        self._awaiting_imagery = False

        self._log_event("IMAGERY_REPORT", {
            "status": report.ImageryStatus,
            "completion": report.CompletionCode,
            "quality": report.ImageMetadata.QualityRating if report.ImageMetadata else None,
            "gsd_m": report.ImageMetadata.GSD_m if report.ImageMetadata else None,
        })

        # If executing a plan, advance to next step
        if self._current_plan and self._plan_state == "EXECUTING":
            self._advance_plan()

    def _handle_fault(self, fault: FaultReport):
        self._log_event("FAULT_RECEIVED", {
            "code": fault.FaultCode,
            "severity": fault.FaultSeverity,
            "affected": fault.AffectedServiceID,
            "description": fault.FaultDescription,
        })

        if fault.FaultSeverity in ("ERROR", "CRITICAL"):
            if fault.AffectedServiceID == "EOIR_SENSOR_01":
                self._publish(SensorCalibrationCommand(
                    header=Header(SenderID=self.service_id),
                    CapabilityID="EOIR_CAP_01",
                    CalibrationMode="DARK",
                ))
                self._log_event("CALIBRATION_INITIATED", {
                    "reason": fault.FaultCode,
                })
            elif fault.AffectedServiceID == "GNC_01":
                self._publish(PowerModeCommand(
                    header=Header(SenderID=self.service_id),
                    TargetServiceID="GNC_01",
                    PowerState="SAFE_MODE",
                ))
                self._log_event("SAFE_HOLD_COMMANDED", {
                    "reason": fault.FaultCode,
                })

            # If executing a plan, check ContinueOnFault
            if self._current_plan and self._plan_state == "EXECUTING":
                steps = self._current_plan.Steps
                if self._plan_step < len(steps):
                    step = steps[self._plan_step]
                    if not step.ContinueOnFault:
                        self._plan_state = "ABORTED"
                        self._publish_plan_status()

    def _handle_mission_plan(self, plan: MissionPlan):
        self._current_plan = plan
        self._plan_step = 0
        self._plan_state = "EXECUTING"
        self._log_event("PLAN_STARTED", {
            "plan_id": plan.PlanID,
            "plan_name": plan.PlanName,
            "total_steps": len(plan.Steps),
        })
        self._publish_plan_status()
        self._execute_current_step()

    def _execute_current_step(self):
        if not self._current_plan or self._plan_step >= len(self._current_plan.Steps):
            self._plan_state = "COMPLETED"
            self._publish_plan_status()
            return

        step = self._current_plan.Steps[self._plan_step]
        self._log_event("PLAN_STEP_EXECUTING", {
            "step": step.StepNumber,
            "offset_sec": step.ExecutionOffset_sec,
        })

        # Parse the command reference and publish it
        cmd_ref = step.CommandRef
        try:
            from satsim.uci.messages import parse_message
            msg = parse_message(cmd_ref)
            msg.header.SenderID = self.service_id

            if isinstance(msg, ImageryCapabilityCommand):
                # Imagery commands: handle locally (won't route back to self)
                # and publish to other services (EOIR receives sensor config)
                self._publish(msg)
                self._handle_imagery_command(msg)
                # Don't auto-advance; wait for ImageryReport
            else:
                self._publish(msg)
                # Auto-advance for non-imagery commands
                self._advance_plan()
        except Exception as e:
            # Command ref might be a simple identifier; handle known types
            self._log_event("PLAN_STEP_CMD_REF", {"ref": cmd_ref})
            # Auto-advance for non-parseable commands
            self._advance_plan()

    def _advance_plan(self):
        if not self._current_plan:
            return
        self._plan_step += 1
        self._publish_plan_status()
        if self._plan_step >= len(self._current_plan.Steps):
            self._plan_state = "COMPLETED"
            self._publish_plan_status()
        else:
            self._execute_current_step()

    def _publish_plan_status(self):
        plan = self._current_plan
        if not plan:
            return
        self._publish(PlanStatusReport(
            header=Header(SenderID=self.service_id),
            PlanID=plan.PlanID,
            CurrentStepNumber=self._plan_step + 1,
            PlanState=self._plan_state,
            CompletedSteps=min(self._plan_step, len(plan.Steps)),
            TotalSteps=len(plan.Steps),
        ))

    def execute_imagery_task(self, cmd: ImageryCapabilityCommand):
        """Execute a full imagery task synchronously (for scenarios)."""
        self._handle_imagery_command(cmd)

        # Simulate the flow by stepping the environment
        if self.env:
            # Give time for slew
            self.env.step(5)
            # Give time for collection
            self.env.step(cmd.CollectionDuration_sec)
            # Give time for ATR
            self.env.step(15)

        return self._last_imagery_report

    def execute_plan_sync(self, plan: MissionPlan):
        """Execute a plan synchronously (for scenarios)."""
        self._handle_mission_plan(plan)

        # Step through plan execution
        if self.env:
            for step in plan.Steps:
                self.env.step(max(step.ExecutionOffset_sec, 5))
                self.env.step(60)  # time for step execution

        return self._plan_state

    def _log_event(self, event_type: str, details: dict):
        ts = ""
        if self.env:
            ts = self.env.clock.now().isoformat()
        entry = {
            "event": event_type,
            "timestamp": ts,
            **details,
        }
        self._mission_log.append(entry)
        logger.info(f"[{event_type}] {details}")

    def get_mission_log(self) -> list:
        return list(self._mission_log)

    def get_status(self) -> PlanStatusReport:
        if self._current_plan:
            return PlanStatusReport(
                header=Header(SenderID=self.service_id),
                PlanID=self._current_plan.PlanID,
                CurrentStepNumber=self._plan_step + 1,
                PlanState=self._plan_state,
                CompletedSteps=min(self._plan_step, len(self._current_plan.Steps)),
                TotalSteps=len(self._current_plan.Steps),
            )
        return HeartbeatMessage(
            header=Header(SenderID=self.service_id),
            ServiceID=self.service_id,
            ServiceState="NOMINAL",
            UptimeSeconds=int(self.env.clock.met() - self._start_met) if self.env else 0,
        )
