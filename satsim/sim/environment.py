"""Simulation environment aggregating clock and orbit simulator."""

import math
from satsim.sim.clock import SimulationClock, set_global_clock
from satsim.sim.orbit import OrbitSimulator, R_EARTH


class SimEnvironment:
    """Aggregates simulation clock and orbit simulator.

    Provides coordinated time advancement and environmental queries.
    """

    def __init__(self, clock: SimulationClock = None, orbit: OrbitSimulator = None):
        self.clock = clock or SimulationClock()
        self.orbit = orbit or OrbitSimulator()
        self._running = False
        set_global_clock(self.clock)

    def start(self):
        """Start the simulation environment."""
        self._running = True

    def stop(self):
        """Stop the simulation environment."""
        self._running = False

    def step(self, seconds: float = 1.0):
        """Advance simulation by the given number of seconds.

        Updates both the clock and the orbit propagator.
        """
        self.clock.advance(seconds)
        self.orbit.advance(seconds)

    def get_solar_flux_W_m2(self) -> float:
        """Return solar flux scaled by eclipse state.

        Returns ~1361 W/m^2 in sunlight, 0 in eclipse.
        """
        if self.orbit.is_in_eclipse():
            return 0.0
        return 1361.0

    def get_atmospheric_density_kg_m3(self) -> float:
        """Return atmospheric density at current altitude.

        Uses simplified exponential model.
        """
        alt_km = self.orbit.altitude_km
        # Scale height model: rho = rho0 * exp(-alt/H)
        rho0 = 1.225  # sea level density kg/m^3
        H = 8.5  # scale height km
        if alt_km < 0:
            return rho0
        return rho0 * math.exp(-alt_km / H)

    @property
    def is_running(self) -> bool:
        return self._running
