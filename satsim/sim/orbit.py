"""Simplified two-body orbital mechanics simulator."""

import math


# Constants
MU_EARTH = 3.986004418e14  # m^3/s^2, Earth gravitational parameter
R_EARTH = 6371000.0        # m, Earth mean radius
EARTH_ROT_RATE = 7.2921159e-5  # rad/s, Earth rotation rate


class OrbitSimulator:
    """Two-body Keplerian orbit propagator.

    Implements simplified orbital mechanics with no perturbations.
    Provides position/velocity in ECEF and geodetic coordinates.
    """

    def __init__(self, semi_major_axis_km: float = 6921.0,
                 eccentricity: float = 0.0,
                 inclination_deg: float = 45.0,
                 raan_deg: float = 0.0,
                 arg_perigee_deg: float = 0.0,
                 true_anomaly_deg: float = 0.0):
        """Initialize orbit with Keplerian elements.

        Default: circular LEO at 550km altitude, 45-degree inclination.
        """
        self.semi_major_axis = semi_major_axis_km * 1000.0  # convert to meters
        self.eccentricity = eccentricity
        self.inclination = math.radians(inclination_deg)
        self.raan = math.radians(raan_deg)
        self.arg_perigee = math.radians(arg_perigee_deg)
        self.true_anomaly = math.radians(true_anomaly_deg)

        # Derived quantities
        self.orbital_period = 2.0 * math.pi * math.sqrt(
            self.semi_major_axis ** 3 / MU_EARTH
        )
        self.mean_motion = 2.0 * math.pi / self.orbital_period

        self._elapsed_seconds = 0.0
        self._initial_true_anomaly = self.true_anomaly

    def advance(self, dt_seconds: float):
        """Advance the orbit by dt_seconds."""
        self._elapsed_seconds += dt_seconds
        # Compute mean anomaly
        M = self.mean_motion * self._elapsed_seconds + self._true_to_mean(self._initial_true_anomaly)
        M = M % (2.0 * math.pi)
        # Solve Kepler's equation for eccentric anomaly
        E = self._solve_kepler(M, self.eccentricity)
        # Convert to true anomaly
        self.true_anomaly = self._eccentric_to_true(E)

    def _true_to_mean(self, nu):
        """Convert true anomaly to mean anomaly."""
        e = self.eccentricity
        E = math.atan2(math.sqrt(1 - e * e) * math.sin(nu), e + math.cos(nu))
        M = E - e * math.sin(E)
        return M

    def _solve_kepler(self, M, e, tol=1e-10, max_iter=50):
        """Solve Kepler's equation M = E - e*sin(E) for E."""
        E = M
        for _ in range(max_iter):
            dE = (M - E + e * math.sin(E)) / (1.0 - e * math.cos(E))
            E += dE
            if abs(dE) < tol:
                break
        return E

    def _eccentric_to_true(self, E):
        """Convert eccentric anomaly to true anomaly."""
        e = self.eccentricity
        nu = math.atan2(math.sqrt(1 - e * e) * math.sin(E), math.cos(E) - e)
        return nu

    def _get_orbital_radius(self):
        """Get current orbital radius in meters."""
        e = self.eccentricity
        a = self.semi_major_axis
        nu = self.true_anomaly
        return a * (1 - e * e) / (1 + e * math.cos(nu))

    def get_position_eci(self):
        """Return position in ECI frame (x, y, z) in meters."""
        r = self._get_orbital_radius()
        nu = self.true_anomaly
        omega = self.arg_perigee
        RAAN = self.raan
        inc = self.inclination

        # Position in orbital plane
        u = omega + nu
        x_orb = r * math.cos(u)
        y_orb = r * math.sin(u)

        # Rotate to ECI
        cos_raan = math.cos(RAAN)
        sin_raan = math.sin(RAAN)
        cos_inc = math.cos(inc)
        sin_inc = math.sin(inc)

        x_eci = x_orb * cos_raan - y_orb * cos_inc * sin_raan
        y_eci = x_orb * sin_raan + y_orb * cos_inc * cos_raan
        z_eci = y_orb * sin_inc

        return x_eci, y_eci, z_eci

    def get_velocity_eci(self):
        """Return velocity in ECI frame (vx, vy, vz) in m/s."""
        r = self._get_orbital_radius()
        nu = self.true_anomaly
        e = self.eccentricity
        a = self.semi_major_axis
        omega = self.arg_perigee
        RAAN = self.raan
        inc = self.inclination

        p = a * (1 - e * e)
        h = math.sqrt(MU_EARTH * p)

        # Velocity components in orbital plane
        u = omega + nu
        vr = (MU_EARTH / h) * e * math.sin(nu)
        vu = (MU_EARTH / h) * (1 + e * math.cos(nu))

        vx_orb = vr * math.cos(u) - vu * math.sin(u)
        vy_orb = vr * math.sin(u) + vu * math.cos(u)

        cos_raan = math.cos(RAAN)
        sin_raan = math.sin(RAAN)
        cos_inc = math.cos(inc)
        sin_inc = math.sin(inc)

        vx = vx_orb * cos_raan - vy_orb * cos_inc * sin_raan
        vy = vx_orb * sin_raan + vy_orb * cos_inc * cos_raan
        vz = vy_orb * sin_inc

        return vx, vy, vz

    def get_position_ecef(self):
        """Return position in ECEF frame (x, y, z) in meters."""
        x_eci, y_eci, z_eci = self.get_position_eci()
        # Rotate from ECI to ECEF by Earth rotation angle
        theta = EARTH_ROT_RATE * self._elapsed_seconds
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        x_ecef = x_eci * cos_t + y_eci * sin_t
        y_ecef = -x_eci * sin_t + y_eci * cos_t
        z_ecef = z_eci
        return x_ecef, y_ecef, z_ecef

    def get_velocity_ecef(self):
        """Return velocity in ECEF frame (vx, vy, vz) in m/s."""
        vx_eci, vy_eci, vz_eci = self.get_velocity_eci()
        x_eci, y_eci, _ = self.get_position_eci()
        theta = EARTH_ROT_RATE * self._elapsed_seconds
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        # ECEF velocity includes Earth rotation correction
        vx = vx_eci * cos_t + vy_eci * sin_t + EARTH_ROT_RATE * (x_eci * sin_t - y_eci * cos_t)
        vy = -vx_eci * sin_t + vy_eci * cos_t + EARTH_ROT_RATE * (x_eci * cos_t + y_eci * sin_t)
        vz = vz_eci
        return vx, vy, vz

    def get_lat_lon_alt(self):
        """Return geodetic latitude (deg), longitude (deg), altitude (km)."""
        x, y, z = self.get_position_ecef()
        # Simplified spherical Earth model
        r = math.sqrt(x * x + y * y + z * z)
        lat = math.degrees(math.asin(z / r))
        lon = math.degrees(math.atan2(y, x))
        alt = (r - R_EARTH) / 1000.0  # km
        return lat, lon, alt

    def is_in_eclipse(self) -> bool:
        """Check if satellite is in Earth's shadow using cylindrical model."""
        x, y, z = self.get_position_eci()
        r = math.sqrt(x * x + y * y + z * z)

        # Sun direction: simplified, assume along +X ECI axis
        # In eclipse if satellite is behind Earth relative to Sun
        sun_x = 1.0  # normalized sun direction
        # Project satellite position onto sun direction
        dot = x / r  # cos(angle between sat and sun)
        # Distance from sun-Earth line
        perp_dist = math.sqrt(y * y + z * z)

        # In shadow if satellite is on the opposite side of Earth from Sun
        # and within the Earth's shadow cylinder
        if x < 0 and perp_dist < R_EARTH:
            return True
        return False

    def time_to_target_los(self, target_lat: float, target_lon: float,
                           half_angle_deg: float = 30.0) -> tuple:
        """Estimate time until target enters line of sight.

        Args:
            target_lat: Target latitude in degrees.
            target_lon: Target longitude in degrees.
            half_angle_deg: Half-angle of sensor field of regard in degrees.

        Returns:
            Tuple of (seconds_to_access, access_duration_sec).
            Returns (0, duration) if target is currently in view.
        """
        target_lat_rad = math.radians(target_lat)
        target_lon_rad = math.radians(target_lon)
        half_angle_rad = math.radians(half_angle_deg)

        # Target ECEF position on Earth surface
        tx = R_EARTH * math.cos(target_lat_rad) * math.cos(target_lon_rad)
        ty = R_EARTH * math.cos(target_lat_rad) * math.sin(target_lon_rad)
        tz = R_EARTH * math.sin(target_lat_rad)

        # Check current visibility
        sx, sy, sz = self.get_position_ecef()
        dx, dy, dz = sx - tx, sy - ty, sz - tz
        slant = math.sqrt(dx * dx + dy * dy + dz * dz)
        r_sat = math.sqrt(sx * sx + sy * sy + sz * sz)

        # Nadir angle
        nadir_cos = (sx * dx + sy * dy + sz * dz) / (r_sat * slant)
        if nadir_cos > 0:
            nadir_angle = math.acos(min(1.0, max(-1.0, nadir_cos)))
        else:
            nadir_angle = math.pi

        # Simplified: target is visible if the angle from nadir to target < half_angle
        earth_angle = self._central_angle(
            math.radians(self.get_lat_lon_alt()[0]),
            math.radians(self.get_lat_lon_alt()[1]),
            target_lat_rad, target_lon_rad
        )
        max_earth_angle = math.asin(min(1.0, math.sin(half_angle_rad) * r_sat / R_EARTH)) if r_sat > R_EARTH else half_angle_rad

        if earth_angle < max_earth_angle:
            # Currently in view, estimate how long
            # Rough estimate based on ground track velocity
            ground_speed = math.sqrt(sum(v ** 2 for v in self.get_velocity_ecef()[:2]))
            footprint_radius = R_EARTH * max_earth_angle
            duration = 2 * footprint_radius / max(ground_speed, 1.0)
            return 0.0, duration

        # Estimate time to next pass - simplified
        # Use orbital period and assume roughly uniform coverage
        ground_speed = 7500.0  # approximate LEO ground speed m/s
        dist = R_EARTH * earth_angle
        # Very rough: time proportional to how far around the orbit we need to go
        time_to = dist / ground_speed
        # Cap at orbital period
        time_to = min(time_to, self.orbital_period)
        duration = 2 * R_EARTH * max_earth_angle / ground_speed

        return time_to, duration

    def _central_angle(self, lat1, lon1, lat2, lon2):
        """Compute central angle between two points on a sphere."""
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        return 2 * math.asin(math.sqrt(min(1.0, a)))

    @property
    def altitude_km(self) -> float:
        """Current altitude in km."""
        return self.get_lat_lon_alt()[2]

    @property
    def elapsed_seconds(self) -> float:
        return self._elapsed_seconds
