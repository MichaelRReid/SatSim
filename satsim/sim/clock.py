"""Simulation clock providing deterministic time for all services."""

import threading
from datetime import datetime, timezone, timedelta

# Global clock singleton
_global_clock = None


def get_global_clock():
    """Return the global simulation clock, or None if not set."""
    return _global_clock


def set_global_clock(clock):
    """Set the global simulation clock."""
    global _global_clock
    _global_clock = clock


class SimulationClock:
    """Simulated mission elapsed time (MET) clock.

    Maintains simulated time with configurable acceleration factor.
    All services must use this clock for timestamps.
    """

    def __init__(self, epoch: datetime = None, time_acceleration: float = 60.0):
        """Initialize the simulation clock.

        Args:
            epoch: Starting UTC datetime. Defaults to 2026-01-15T12:00:00Z.
            time_acceleration: Ratio of simulated seconds per wall-clock second.
        """
        if epoch is None:
            epoch = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        self._epoch = epoch
        self._current_time = epoch
        self._met_seconds = 0.0
        self._time_acceleration = time_acceleration
        self._running = False
        self._timers = []  # List of (interval_sec, callback, last_fired_met)
        self._lock = threading.Lock()

    def now(self) -> datetime:
        """Return current simulated UTC datetime."""
        with self._lock:
            return self._current_time

    def met(self) -> float:
        """Return mission elapsed time in seconds."""
        with self._lock:
            return self._met_seconds

    def advance(self, seconds: float):
        """Advance simulated time by the given number of seconds.

        Fires any registered timers whose intervals have elapsed.
        """
        with self._lock:
            self._met_seconds += seconds
            self._current_time = self._epoch + timedelta(seconds=self._met_seconds)

        # Fire timers
        self._check_timers()

    def _check_timers(self):
        """Check and fire any timers that are due."""
        fired = []
        for i, (interval, callback, last_met) in enumerate(self._timers):
            while self._met_seconds >= last_met + interval:
                last_met += interval
                fired.append((callback, last_met))
                self._timers[i] = (interval, callback, last_met)
        for callback, _ in fired:
            try:
                callback()
            except Exception:
                pass

    def register_timer(self, callback, interval_sec: float):
        """Register a periodic timer callback.

        Args:
            callback: Function to call when timer fires.
            interval_sec: Interval in simulated seconds between firings.
        """
        self._timers.append((interval_sec, callback, self._met_seconds))

    def set_acceleration(self, factor: float):
        """Change the time acceleration factor."""
        self._time_acceleration = factor

    @property
    def time_acceleration(self) -> float:
        return self._time_acceleration

    @property
    def epoch(self) -> datetime:
        return self._epoch

    def reset(self):
        """Reset the clock to the epoch."""
        with self._lock:
            self._met_seconds = 0.0
            self._current_time = self._epoch
            self._timers.clear()
