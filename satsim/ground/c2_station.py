"""Ground Command and Control station."""

import uuid
from satsim.uci.messages import (
    Header, ImageryCapabilityCommand, MissionPlan, StatusRequest,
    PowerModeCommand, PlanStep, PointTarget, UCIMessage,
)


class GroundC2Station:
    """Simulates the ground command and control station.

    Not an OMS service - communicates by publishing to the bus.
    """

    def __init__(self, bus, env=None):
        self._bus = bus
        self._env = env
        self._sender_id = "GROUND_C2"
        self._received_reports = []
        self._mission_log = []
        self._command_seq = 0

    def send_imagery_command(self, lat: float, lon: float, alt: float = 0.0,
                             sensor_mode: str = "VISIBLE",
                             resolution_m: float = 1.0,
                             duration_sec: int = 30,
                             priority: str = "ROUTINE") -> ImageryCapabilityCommand:
        """Build and send an ImageryCapabilityCommand."""
        cmd = ImageryCapabilityCommand(
            header=Header(SenderID=self._sender_id, Priority=priority),
            CapabilityID="EOIR_CAP_01",
            CommandState="CHANGE_SETTING",
            SensorMode=sensor_mode,
            Resolution_m=resolution_m,
            CollectionDuration_sec=duration_sec,
            Target=PointTarget(Latitude=lat, Longitude=lon, Altitude_m=alt),
        )
        self._command_seq += 1
        ts = self._env.clock.now().isoformat() if self._env else ""
        self._mission_log.append({
            "seq": self._command_seq,
            "type": "ImageryCapabilityCommand",
            "timestamp": ts,
            "target": f"{lat}, {lon}",
            "mode": sensor_mode,
        })
        self._bus.publish(cmd)
        return cmd

    def send_mission_plan(self, plan_name: str, steps: list) -> MissionPlan:
        """Build and send a MissionPlan.

        Args:
            plan_name: Human-readable plan name.
            steps: List of PlanStep objects or dicts with step info.
        """
        plan_steps = []
        for i, step in enumerate(steps):
            if isinstance(step, PlanStep):
                plan_steps.append(step)
            elif isinstance(step, dict):
                plan_steps.append(PlanStep(
                    StepNumber=step.get("step_number", i + 1),
                    CommandRef=step.get("command_ref", ""),
                    ExecutionOffset_sec=step.get("offset_sec", 0),
                    ContinueOnFault=step.get("continue_on_fault", True),
                ))

        ts = self._env.clock.now().strftime("%Y-%m-%dT%H:%M:%S.000Z") if self._env else "2026-01-15T12:00:00.000Z"
        plan = MissionPlan(
            header=Header(SenderID=self._sender_id),
            PlanID=str(uuid.uuid4()),
            PlanName=plan_name,
            ScheduledStartTime=ts,
            Steps=plan_steps,
        )
        self._command_seq += 1
        self._mission_log.append({
            "seq": self._command_seq,
            "type": "MissionPlan",
            "timestamp": ts,
            "plan_name": plan_name,
            "steps": len(plan_steps),
        })
        self._bus.publish(plan)
        return plan

    def send_status_request(self, target_service_id: str) -> StatusRequest:
        """Send a StatusRequest to a service."""
        req = StatusRequest(
            header=Header(SenderID=self._sender_id),
            TargetServiceID=target_service_id,
        )
        self._bus.publish(req)
        return req

    def send_power_command(self, target_service_id: str,
                           power_state: str) -> PowerModeCommand:
        """Send a PowerModeCommand."""
        cmd = PowerModeCommand(
            header=Header(SenderID=self._sender_id),
            TargetServiceID=target_service_id,
            PowerState=power_state,
        )
        self._bus.publish(cmd)
        return cmd

    def request_telemetry_dump(self) -> list:
        """Request CDH to flush its downlink queue."""
        # Find CDH service on the bus
        services = self._bus.get_registered_services()
        for sid, info in services.items():
            if "CDH" in sid.upper():
                service = self._bus._services.get(sid)
                if service and hasattr(service, 'flush_downlink_queue'):
                    return service.flush_downlink_queue()
        return []

    def get_received_reports(self) -> list:
        """Return all reports received from the bus."""
        return list(self._received_reports)

    def get_mission_log(self) -> list:
        """Return structured log of commands and responses."""
        return list(self._mission_log)

    def add_report(self, report: UCIMessage):
        """Add a received report (called by bus routing)."""
        self._received_reports.append(report)
