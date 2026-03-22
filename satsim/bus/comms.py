"""Communications subsystem service."""

import math
from satsim.bus.middleware import BaseService
from satsim.uci.messages import (
    Header, HeartbeatMessage, FaultReport, StatusRequest,
    PowerModeCommand, UCIMessage,
)


class CommsService(BaseService):
    """Simulates spacecraft communications and ground contact management."""

    def __init__(self, service_id: str = "COMMS_01", env=None,
                 ground_lat: float = 38.8, ground_lon: float = -104.7):
        super().__init__(service_id, env)
        self._power_state = "ON"
        self._link_margin_db = 10.0
        self._ground_lat = ground_lat
        self._ground_lon = ground_lon
        self._downlink_available = False
        self._contact_start = None
        self._contact_duration = 0.0
        self._contact_elevation = 0.0
        self._bit_error_rate = 1e-9

    def start(self):
        super().start()
        if self.mwa:
            self.mwa.subscribe(StatusRequest)
            self.mwa.subscribe(PowerModeCommand)
        if self.env:
            self.env.clock.register_timer(self.send_heartbeat, 30)
            self.env.clock.register_timer(self._update_contact, 5)

    def stop(self):
        super().stop()

    def handle_message(self, message: UCIMessage):
        if isinstance(message, StatusRequest):
            if message.TargetServiceID == self.service_id:
                self._publish(self.get_status())
        elif isinstance(message, PowerModeCommand):
            if message.TargetServiceID == self.service_id:
                self._power_state = message.PowerState

    def _update_contact(self):
        if not self._running or not self.env:
            return

        time_to, duration = self.env.orbit.time_to_target_los(
            self._ground_lat, self._ground_lon, half_angle_deg=70.0
        )
        if time_to == 0.0:
            self._downlink_available = True
            self._contact_duration = duration
            self._contact_elevation = 45.0  # simplified
            self._contact_start = self.env.clock.now()
        else:
            self._downlink_available = False
            self._contact_duration = duration

        # BER as function of elevation
        if self._downlink_available:
            self._bit_error_rate = 1e-9 * (1 + 10 / max(self._contact_elevation, 5.0))
        else:
            self._bit_error_rate = 1.0

    def is_downlink_available(self) -> bool:
        return self._downlink_available and self._power_state != "OFF"

    def get_contact_window_status(self) -> dict:
        """Return contact window information."""
        if self.env:
            time_to, duration = self.env.orbit.time_to_target_los(
                self._ground_lat, self._ground_lon, half_angle_deg=70.0
            )
        else:
            time_to, duration = 0.0, 600.0

        return {
            "downlink_available": self._downlink_available,
            "next_contact_start_sec": time_to,
            "contact_duration_sec": duration,
            "elevation_deg": self._contact_elevation,
            "bit_error_rate": self._bit_error_rate,
            "link_margin_db": self._link_margin_db,
        }

    def get_status(self) -> HeartbeatMessage:
        return HeartbeatMessage(
            header=Header(SenderID=self.service_id),
            ServiceID=self.service_id,
            ServiceState="NOMINAL" if self._power_state != "OFF" else "FAULT",
            UptimeSeconds=int(self.env.clock.met() - self._start_met) if self.env else 0,
        )
