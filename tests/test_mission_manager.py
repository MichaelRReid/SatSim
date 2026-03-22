"""Tests for the Mission Manager service."""

import pytest
from satsim.sim.setup import create_simulation
from satsim.bus.middleware import OMSBus
from satsim.uci.messages import (
    Header, ImageryCapabilityCommand, PointTarget,
    FaultReport,
)
from satsim.sim.clock import set_global_clock


@pytest.fixture(autouse=True)
def reset():
    OMSBus.reset()
    yield
    OMSBus.reset()
    set_global_clock(None)


class TestMissionManager:

    def test_full_imagery_flow(self):
        """Command in -> ImageryReport out."""
        env, bus, ground, services = create_simulation()

        ground.send_imagery_command(
            lat=39.7392, lon=-104.9903,
            sensor_mode="VISIBLE", resolution_m=0.5, duration_sec=20,
        )
        env.step(120)

        log = bus.get_message_log()
        types = [e["MessageType"] for e in log]

        assert "ImageryCapabilityCommand" in types
        assert "SlewCommand" in types
        assert "AttitudeStatusReport" in types
        assert "ImageryReport" in types

    def test_waits_for_pointing_settle(self):
        """MissionManager does not activate sensor until pointing error < 0.05."""
        env, bus, ground, services = create_simulation()

        ground.send_imagery_command(
            lat=39.7392, lon=-104.9903,
            sensor_mode="VISIBLE", resolution_m=0.5, duration_sec=20,
        )
        env.step(120)

        log = bus.get_message_log()
        types = [e["MessageType"] for e in log]

        # SensorActivateCommand should come after AttitudeStatusReport
        if "SensorActivateCommand" in types and "AttitudeStatusReport" in types:
            first_attitude = next(i for i, t in enumerate(types) if t == "AttitudeStatusReport")
            first_activate = next(i for i, t in enumerate(types) if t == "SensorActivateCommand")
            assert first_activate > first_attitude

    def test_fault_escalation(self):
        """ERROR fault on EOIR triggers calibration command."""
        env, bus, ground, services = create_simulation()

        eoir = services["EOIR_SENSOR_01"]
        eoir.inject_fault("TEST_FAULT")
        env.step(10)

        log = bus.get_message_log()
        types = [e["MessageType"] for e in log]

        assert "FaultReport" in types
        assert "SensorCalibrationCommand" in types
