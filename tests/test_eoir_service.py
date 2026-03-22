"""Tests for the EOIR sensor service."""

import pytest
from satsim.sim.setup import create_simulation
from satsim.bus.middleware import OMSBus
from satsim.payload.eoir_service import EOIRService
from satsim.sim.clock import set_global_clock


@pytest.fixture(autouse=True)
def reset():
    OMSBus.reset()
    yield
    OMSBus.reset()
    set_global_clock(None)


class TestEOIRService:

    def test_niirs_computation(self):
        """NIIRS rating computed correctly for different GSD values."""
        assert EOIRService._compute_niirs(0.2) == "NIIRS_7"
        assert EOIRService._compute_niirs(0.3) == "NIIRS_6"
        assert EOIRService._compute_niirs(0.4) == "NIIRS_6"
        assert EOIRService._compute_niirs(0.5) == "NIIRS_5"
        assert EOIRService._compute_niirs(0.8) == "NIIRS_5"
        assert EOIRService._compute_niirs(1.0) == "NIIRS_4"
        assert EOIRService._compute_niirs(1.5) == "NIIRS_4"
        assert EOIRService._compute_niirs(2.0) == "NIIRS_3"
        assert EOIRService._compute_niirs(5.0) == "NIIRS_3"

    def test_degraded_after_three_collections(self):
        """3 consecutive collections without calibration triggers DEGRADED."""
        env, bus, ground, services = create_simulation()
        eoir = services["EOIR_SENSOR_01"]

        for i in range(3):
            ground.send_imagery_command(
                lat=39.7392, lon=-104.9903,
                sensor_mode="VISIBLE", resolution_m=0.5, duration_sec=10,
            )
            env.step(60)

        assert eoir.operational_state == "DEGRADED"

    def test_fault_injection(self):
        """inject_fault publishes FaultReport and triggers auto-calibration recovery."""
        env, bus, ground, services = create_simulation()
        eoir = services["EOIR_SENSOR_01"]

        bus.clear_log()
        eoir.inject_fault("FOCAL_PLANE_OVERHEAT")

        log = bus.get_message_log()
        fault_reports = [e for e in log if e["MessageType"] == "FaultReport"]
        assert len(fault_reports) > 0

        # MissionManager auto-responds with calibration, restoring NOMINAL
        cal_commands = [e for e in log if e["MessageType"] == "SensorCalibrationCommand"]
        assert len(cal_commands) > 0
        assert eoir.operational_state == "NOMINAL"
