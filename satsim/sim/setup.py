"""Simulation setup helper - creates and wires the full simulation."""

from satsim.sim.environment import SimEnvironment
from satsim.sim.clock import SimulationClock
from satsim.sim.orbit import OrbitSimulator
from satsim.bus.middleware import OMSBus
from satsim.bus.mission_manager import MissionManagerService
from satsim.bus.gnc import GNCService
from satsim.bus.cdh import CDHService
from satsim.bus.eps import EPSService
from satsim.bus.thermal import ThermalService
from satsim.bus.comms import CommsService
from satsim.payload.eoir_service import EOIRService
from satsim.payload.atr_service import ATRService
from satsim.ground.c2_station import GroundC2Station


def create_simulation(time_acceleration: float = 60.0):
    """Create a fully wired simulation environment.

    Returns:
        Tuple of (env, bus, ground_station, services_dict).
    """
    # Reset singleton bus
    OMSBus.reset()

    env = SimEnvironment(
        clock=SimulationClock(time_acceleration=time_acceleration),
        orbit=OrbitSimulator(),
    )
    bus = OMSBus()

    # Create services
    mission_mgr = MissionManagerService(env=env)
    gnc = GNCService(env=env)
    cdh = CDHService(env=env)
    eps = EPSService(env=env)
    thermal = ThermalService(env=env)
    comms = CommsService(env=env)
    eoir = EOIRService(env=env)
    atr = ATRService(env=env)

    # Register on bus
    bus.register_service("MISSION_MGR", mission_mgr)
    bus.register_service("GNC_01", gnc)
    bus.register_service("CDH_01", cdh)
    bus.register_service("EPS_01", eps)
    bus.register_service("THERMAL_01", thermal)
    bus.register_service("COMMS_01", comms)
    bus.register_service("EOIR_SENSOR_01", eoir)
    bus.register_service("ATR_01", atr)

    # Start all services
    mission_mgr.start()
    gnc.start()
    cdh.start()
    eps.start()
    thermal.start()
    comms.start()
    eoir.start()
    atr.start()

    # Start environment
    env.start()

    # Create ground station
    ground = GroundC2Station(bus, env)

    services = {
        "MISSION_MGR": mission_mgr,
        "GNC_01": gnc,
        "CDH_01": cdh,
        "EPS_01": eps,
        "THERMAL_01": thermal,
        "COMMS_01": comms,
        "EOIR_SENSOR_01": eoir,
        "ATR_01": atr,
    }

    return env, bus, ground, services
