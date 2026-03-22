"""GNC (Guidance, Navigation, and Control) service."""

import random
import math
from satsim.bus.middleware import BaseService
from satsim.uci.messages import (
    Header, AttitudeStatusReport, NavigationStatusReport,
    HeartbeatMessage, FaultReport, SlewCommand, StatusRequest,
    PowerModeCommand, UCIMessage,
)


class GNCService(BaseService):
    """Simulates attitude determination and control, and orbit determination."""

    def __init__(self, service_id: str = "GNC_01", env=None):
        super().__init__(service_id, env)
        self.quaternion = [1.0, 0.0, 0.0, 0.0]  # w, x, y, z
        self.pointing_mode = "NADIR"
        self.pointing_error = 0.0
        self.angular_rate = 0.0
        self._power_state = "ON"
        self._slewing = False
        self._target_az = 0.0
        self._target_el = 0.0
        self._slew_remaining = 0.0

    def start(self):
        super().start()
        if self.mwa:
            self.mwa.subscribe(SlewCommand)
            self.mwa.subscribe(StatusRequest)
            self.mwa.subscribe(PowerModeCommand)
            self.mwa.subscribe(FaultReport)
        if self.env:
            self.env.clock.register_timer(self.send_heartbeat, 30)
            self.env.clock.register_timer(self._publish_nav_status, 10)

    def stop(self):
        super().stop()

    def handle_message(self, message: UCIMessage):
        if isinstance(message, SlewCommand):
            self._handle_slew(message)
        elif isinstance(message, StatusRequest):
            if message.TargetServiceID == self.service_id:
                self._publish(self.get_status())
                self._publish(self._make_nav_report())
        elif isinstance(message, PowerModeCommand):
            if message.TargetServiceID == self.service_id:
                self._power_state = message.PowerState
                if message.PowerState == "SAFE_MODE":
                    self.pointing_mode = "SAFE_HOLD"
                    self._slewing = False
        elif isinstance(message, FaultReport):
            if message.AffectedServiceID == self.service_id:
                self.pointing_mode = "SAFE_HOLD"
                self._slewing = False
                self._publish(self.get_status())

    def _handle_slew(self, cmd: SlewCommand):
        self._target_az = cmd.Azimuth_deg
        self._target_el = cmd.Elevation_deg
        self._slewing = True
        self.pointing_mode = "TARGET_TRACK"

        # Compute angular distance (simplified)
        angular_dist = math.sqrt(cmd.Azimuth_deg**2 + cmd.Elevation_deg**2) % 180
        slew_steps = max(1, int(angular_dist / 10))

        # Simulate slew convergence
        for i in range(slew_steps):
            error = max(0.001, angular_dist * (1.0 - (i + 1) / slew_steps))
            self.pointing_error = error
            self.angular_rate = error * 0.5
            if error > 0.05:
                self._publish(AttitudeStatusReport(
                    header=Header(SenderID=self.service_id),
                    PointingMode="TARGET_TRACK",
                    PointingError_deg=round(error, 4),
                    QuaternionW=self.quaternion[0],
                    QuaternionX=self.quaternion[1],
                    QuaternionY=self.quaternion[2],
                    QuaternionZ=self.quaternion[3],
                    AngularRate_degps=round(self.angular_rate, 4),
                ))

        # Final settled report
        self.pointing_error = round(random.uniform(0.001, 0.04), 4)
        self.angular_rate = round(random.uniform(0.0001, 0.005), 4)
        self._slewing = False
        self._publish(AttitudeStatusReport(
            header=Header(SenderID=self.service_id),
            PointingMode="TARGET_TRACK",
            PointingError_deg=self.pointing_error,
            QuaternionW=self.quaternion[0],
            QuaternionX=self.quaternion[1],
            QuaternionY=self.quaternion[2],
            QuaternionZ=self.quaternion[3],
            AngularRate_degps=self.angular_rate,
        ))

    def _publish_nav_status(self):
        if self._running and self._power_state != "OFF":
            self._publish(self._make_nav_report())

    def _make_nav_report(self) -> NavigationStatusReport:
        if self.env:
            x, y, z = self.env.orbit.get_position_ecef()
            vx, vy, vz = self.env.orbit.get_velocity_ecef()
            lat, lon, alt = self.env.orbit.get_lat_lon_alt()
            period = self.env.orbit.orbital_period
        else:
            x, y, z = 6921000.0, 0.0, 0.0
            vx, vy, vz = 0.0, 7500.0, 0.0
            lat, lon, alt = 0.0, 0.0, 550.0
            period = 5790.0

        return NavigationStatusReport(
            header=Header(SenderID=self.service_id),
            PositionECEF_x_m=x,
            PositionECEF_y_m=y,
            PositionECEF_z_m=z,
            VelocityECEF_x_ms=vx,
            VelocityECEF_y_ms=vy,
            VelocityECEF_z_ms=vz,
            Latitude_deg=lat,
            Longitude_deg=lon,
            Altitude_m=alt * 1000,  # convert km to m
            OrbitalPeriod_sec=period,
            EphemerisAge_sec=self.env.clock.met() if self.env else 0.0,
        )

    def get_status(self) -> AttitudeStatusReport:
        return AttitudeStatusReport(
            header=Header(SenderID=self.service_id),
            PointingMode=self.pointing_mode,
            PointingError_deg=self.pointing_error,
            QuaternionW=self.quaternion[0],
            QuaternionX=self.quaternion[1],
            QuaternionY=self.quaternion[2],
            QuaternionZ=self.quaternion[3],
            AngularRate_degps=self.angular_rate,
        )
