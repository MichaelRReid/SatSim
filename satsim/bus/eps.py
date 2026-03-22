"""Electrical Power System (EPS) service."""

from satsim.bus.middleware import BaseService
from satsim.uci.messages import (
    Header, PowerStatusReport, PowerModeCommand, FaultReport,
    HeartbeatMessage, StatusRequest, UCIMessage,
)


class EPSService(BaseService):
    """Simulates the Electrical Power System."""

    def __init__(self, service_id: str = "EPS_01", env=None):
        super().__init__(service_id, env)
        self.battery_soc = 85.0
        self.solar_array_power = 200.0
        self.total_bus_power = 150.0
        self.bus_voltage = 28.0
        self.power_mode = "NOMINAL"
        self._power_state = "ON"
        self._load_shed = False

    def start(self):
        super().start()
        if self.mwa:
            self.mwa.subscribe(PowerModeCommand)
            self.mwa.subscribe(StatusRequest)
        if self.env:
            self.env.clock.register_timer(self.send_heartbeat, 30)
            self.env.clock.register_timer(self._update_power, 1)

    def stop(self):
        super().stop()

    def handle_message(self, message: UCIMessage):
        if isinstance(message, PowerModeCommand):
            if message.TargetServiceID == self.service_id:
                self._power_state = message.PowerState
        elif isinstance(message, StatusRequest):
            if message.TargetServiceID == self.service_id:
                self._publish(self.get_status())

    def _update_power(self):
        if not self._running or self._power_state == "OFF":
            return

        # Check eclipse state
        if self.env and self.env.orbit.is_in_eclipse():
            self.solar_array_power = 0.0
            self.power_mode = "ECLIPSE"
            # Deplete battery: 15W per minute = 0.25W per second
            self.battery_soc -= (15.0 / 60.0) / 100.0  # crude percentage drain
        else:
            self.solar_array_power = 200.0
            if not self._load_shed:
                self.power_mode = "NOMINAL"
            # Charge battery
            net_power = self.solar_array_power - self.total_bus_power
            if net_power > 0:
                self.battery_soc = min(100.0, self.battery_soc + 0.01)

        # Check SOC thresholds
        if self.battery_soc < 10.0:
            self.power_mode = "EMERGENCY_LOAD_SHED"
            self._load_shed = True
            self._publish(FaultReport(
                header=Header(SenderID=self.service_id),
                FaultCode="BATTERY_CRITICAL",
                FaultSeverity="CRITICAL",
                AffectedServiceID=self.service_id,
                FaultDescription=f"Battery SOC critically low: {self.battery_soc:.1f}%",
                RecommendedAction="Immediate load shedding required",
            ))
            self._publish(PowerModeCommand(
                header=Header(SenderID=self.service_id),
                TargetServiceID="ALL",
                PowerState="SAFE_MODE",
            ))
        elif self.battery_soc < 20.0 and not self._load_shed:
            self.power_mode = "DEGRADED"
            self._load_shed = True
            self._publish(FaultReport(
                header=Header(SenderID=self.service_id),
                FaultCode="BATTERY_LOW",
                FaultSeverity="WARNING",
                AffectedServiceID=self.service_id,
                FaultDescription=f"Battery SOC low: {self.battery_soc:.1f}%",
                RecommendedAction="Shed non-essential loads",
            ))

        if self.battery_soc > 30.0:
            self._load_shed = False

    def get_status(self) -> PowerStatusReport:
        return PowerStatusReport(
            header=Header(SenderID=self.service_id),
            BatterySOC_pct=round(self.battery_soc, 1),
            SolarArrayPower_W=self.solar_array_power,
            TotalBusPower_W=self.total_bus_power,
            BusVoltage_V=self.bus_voltage,
            PowerMode=self.power_mode,
        )
