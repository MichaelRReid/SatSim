"""Tests for scenario execution."""

import pytest
from satsim.bus.middleware import OMSBus
from satsim.sim.clock import set_global_clock
from satsim.sim.setup import create_simulation


@pytest.fixture(autouse=True)
def reset():
    OMSBus.reset()
    yield
    OMSBus.reset()
    set_global_clock(None)


class TestScenarios:

    def test_basic_imagery_tasking(self):
        """Basic imagery tasking scenario produces COMPLETED ImageryReport."""
        from scenarios.basic_imagery_tasking import run
        env, bus, ground, services = create_simulation()
        result = run(env, ground, bus, services)
        assert result["imagery_report_found"] is True
        assert result["success"] is True

    def test_sensor_fault_injection(self):
        """Sensor fault injection scenario completes with all transitions."""
        from scenarios.sensor_fault_injection import run
        env, bus, ground, services = create_simulation()
        result = run(env, ground, bus, services)
        assert result["fault_report_published"] is True
        assert result["calibration_commanded"] is True
        assert result["success"] is True

    def test_plan_execution(self):
        """Plan execution scenario completes 4/4 steps."""
        from scenarios.plan_execution import run
        env, bus, ground, services = create_simulation()
        result = run(env, ground, bus, services)
        assert result["plan_state"] == "COMPLETED"
        assert result["success"] is True

    def test_constellation_handoff(self):
        """Constellation handoff scenario stores and forwards data."""
        from scenarios.constellation_handoff import run
        env, bus, ground, services = create_simulation()
        result = run(env, ground, bus, services)
        assert result["packets_flushed"] > 0
        assert result["queue_size_after_flush"] == 0
        assert result["success"] is True
