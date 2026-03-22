"""Thermal subsystem service."""

from satsim.bus.middleware import BaseService
from satsim.uci.messages import (
    Header, ThermalStatusReport, FaultReport, HeartbeatMessage,
    SensorCalibrationCommand, StatusRequest, PowerModeCommand, UCIMessage,
)


class ThermalService(BaseService):
    """Simulates spacecraft thermal environment."""

    def __init__(self, service_id: str = "THERMAL_01", env=None):
        super().__init__(service_id, env)
        self.focal_plane_temp = -20.0  # nominal
        self.electronics_temp = 25.0
        self.structure_temp = 15.0
        self.thermal_mode = "NOMINAL"
        self._power_state = "ON"
        self._sensor_active = False
        self._warned_overtemp = False
        self._errored_overtemp = False

    def start(self):
        super().start()
        if self.mwa:
            self.mwa.subscribe(StatusRequest)
            self.mwa.subscribe(PowerModeCommand)
        if self.env:
            self.env.clock.register_timer(self.send_heartbeat, 30)
            self.env.clock.register_timer(self._update_thermal, 1)

    def stop(self):
        super().stop()

    def set_sensor_active(self, active: bool):
        """Called by environment to indicate sensor activity."""
        self._sensor_active = active

    def handle_message(self, message: UCIMessage):
        if isinstance(message, StatusRequest):
            if message.TargetServiceID == self.service_id:
                self._publish(self.get_status())
        elif isinstance(message, PowerModeCommand):
            if message.TargetServiceID == self.service_id:
                self._power_state = message.PowerState

    def _update_thermal(self):
        if not self._running or self._power_state == "OFF":
            return

        # Focal plane temperature dynamics
        if self._sensor_active:
            # Rises 0.5C per simulated minute = 0.00833 per second
            self.focal_plane_temp += 0.5 / 60.0
        else:
            # Recovers toward nominal (-20C)
            if self.focal_plane_temp > -20.0:
                self.focal_plane_temp -= 1.0 / 60.0
                self.focal_plane_temp = max(-20.0, self.focal_plane_temp)

        # Check thermal limits
        if self.focal_plane_temp > 0.0 and not self._errored_overtemp:
            self.thermal_mode = "OVER_TEMP_CRITICAL"
            self._errored_overtemp = True
            self._publish(FaultReport(
                header=Header(SenderID=self.service_id),
                FaultCode="FOCAL_PLANE_OVERHEAT",
                FaultSeverity="ERROR",
                AffectedServiceID="EOIR_SENSOR_01",
                FaultDescription=f"Focal plane temperature critical: {self.focal_plane_temp:.1f}C",
                RecommendedAction="Initiate sensor calibration and cooldown",
            ))
            self._publish(SensorCalibrationCommand(
                header=Header(SenderID=self.service_id),
                CapabilityID="EOIR_CAP_01",
                CalibrationMode="DARK",
            ))
        elif self.focal_plane_temp > -10.0 and not self._warned_overtemp:
            self.thermal_mode = "OVER_TEMP_WARNING"
            self._warned_overtemp = True
            self._publish(FaultReport(
                header=Header(SenderID=self.service_id),
                FaultCode="FOCAL_PLANE_WARM",
                FaultSeverity="WARNING",
                AffectedServiceID="EOIR_SENSOR_01",
                FaultDescription=f"Focal plane temperature elevated: {self.focal_plane_temp:.1f}C",
                RecommendedAction="Monitor temperature trend",
            ))
        elif self.focal_plane_temp <= -10.0:
            self.thermal_mode = "NOMINAL"
            self._warned_overtemp = False
            self._errored_overtemp = False

    def get_status(self) -> ThermalStatusReport:
        return ThermalStatusReport(
            header=Header(SenderID=self.service_id),
            ServiceID=self.service_id,
            FocalPlaneTemp_C=round(self.focal_plane_temp, 2),
            ElectronicsTemp_C=round(self.electronics_temp, 2),
            StructureTemp_C=round(self.structure_temp, 2),
            ThermalMode=self.thermal_mode,
        )
