# SatSim -- Satellite Bus & EO/IR Payload UCI Simulation

```
   ____        _   ____  _
  / ___|  __ _| |_/ ___|(_)_ __ ___
  \___ \ / _` | __\___ \| | '_ ` _ \
   ___) | (_| | |_ ___) | | | | | | |
  |____/ \__,_|\__|____/|_|_| |_| |_|
  UCI / OMS Spacecraft Simulation  v1.0
```

## Overview

SatSim is a software simulation of a satellite bus and electro-optical/infrared (EO/IR) payload that communicates using UCI (Unified C2 Interface) XML messages routed over an OMS (Open Mission Systems) middleware architecture. The simulation models eight spacecraft services -- Mission Manager, GNC, C&DH, EPS, Thermal, Comms, EO/IR Sensor, and ATR -- each exchanging strongly-typed, XSD-validated messages through a publish-subscribe message bus. This provides a realistic testbed for exploring how UCI message standards govern inter-service communication on a modern satellite bus.

The architecture follows the OMS MiddleWare Adapter (MWA) pattern, where each service is wrapped in a MiddleWareAdapter that handles XSD validation, subscription management, and message routing. Services never communicate directly; all messages flow through the central OMSBus singleton, which matches message types to subscriber lists and delivers validated XML payloads. This decoupled design mirrors real OMS deployments where services can be added, removed, or replaced without affecting the rest of the bus.

SatSim includes a simulation environment with a configurable clock, orbital mechanics model, and ground station interface. Four built-in scenarios exercise the full message flow -- from ground-commanded imagery tasking through attitude slewing, sensor activation, image capture, and automatic target recognition. An interactive CLI console built on Rich lets operators inspect service status, send commands, step the simulation clock, and review the message log in real time.

## Installation

**Requirements:** Python 3.9+

```bash
# Clone the repository
git clone <repository-url>
cd "UCI Example"

# Install in editable mode (includes all dependencies)
pip install -e .

# Or install dependencies directly
pip install -r requirements.txt

# Install with dev/test dependencies
pip install -e ".[dev]"
```

### Dependencies

| Package    | Version  | Purpose                        |
|------------|----------|--------------------------------|
| lxml       | >= 4.9.0 | XML parsing and XSD validation |
| rich       | >= 13.0  | CLI console formatting         |
| xmlschema  | >= 2.0.0 | UCI schema validation          |
| pytest     | >= 7.0.0 | Testing (dev)                  |
| pytest-cov | >= 4.0.0 | Coverage reporting (dev)       |

## Quick Start

```bash
# 1. Install the package
pip install -e .

# 2. Launch the interactive console
satsim-console

# 3. Run a scenario directly
python -m scenarios.basic_imagery_tasking

# 4. Run the test suite
pytest tests/ -v

# 5. Run with the Python module entry point
python -m satsim
```

### Interactive Console Commands

Once inside `satsim-console`, you can use commands like:

- `status` -- Show all service states
- `imagery <lat> <lon>` -- Send an imagery tasking command
- `step <seconds>` -- Advance the simulation clock
- `log [n]` -- Show recent message log entries
- `quit` -- Exit the console

## Architecture

```
                         +------------------+
                         |  Ground C2       |
                         |  Station         |
                         +--------+---------+
                                  |
                         publish  |  UCI XML
                                  v
+---------------------------------------------------------------+
|                        OMS Bus (Singleton)                    |
|  +------------------+  route   +------------------+           |
|  | Subscription Map |--------->| Message Log      |           |
|  +------------------+          +------------------+           |
+-------+-------+-------+-------+-------+-------+-------+------+
        |       |       |       |       |       |       |
       MWA    MWA     MWA     MWA     MWA     MWA     MWA
        |       |       |       |       |       |       |
   +----+--+ +--+---+ +-+--+ +-+--+ +--+---+ +-+----+ +--+---+
   |Mission | | GNC  | |C&DH| |EPS | |Therm | |Comms | |EO/IR |
   |Manager | |      | |    | |    | |      | |      | |Sensor|
   +--------+ +------+ +----+ +----+ +------+ +------+ +--+---+
                                                           |
                                                        +--+---+
                                                        | ATR  |
                                                        +------+
```

Each service communicates exclusively through its MiddleWare Adapter (MWA). The MWA validates outgoing messages against the UCI v6 XSD schema before publishing, and validates incoming messages before delivering to the service handler. The OMSBus routes messages based on type-to-subscriber mappings.

## Project Structure

```
UCI Example/
+-- setup.py                  # Package configuration
+-- requirements.txt          # Python dependencies
+-- schemas/
|   +-- uci_v6.xsd            # UCI message schema
+-- satsim/
|   +-- __main__.py            # python -m satsim entry point
|   +-- bus/
|   |   +-- middleware.py      # OMSBus, MWA, BaseService
|   |   +-- mission_manager.py # Mission orchestration
|   |   +-- gnc.py             # Guidance, Navigation & Control
|   |   +-- cdh.py             # Command & Data Handling
|   |   +-- eps.py             # Electrical Power System
|   |   +-- thermal.py         # Thermal management
|   |   +-- comms.py           # Communications
|   +-- payload/
|   |   +-- eoir_service.py    # EO/IR sensor service
|   |   +-- atr_service.py     # Automatic Target Recognition
|   +-- uci/
|   |   +-- messages.py        # UCI message dataclasses
|   |   +-- validator.py       # XSD validation
|   |   +-- schema_loader.py   # Schema file loading
|   +-- sim/
|   |   +-- setup.py           # Simulation wiring
|   |   +-- clock.py           # Simulation clock
|   |   +-- orbit.py           # Orbital mechanics
|   |   +-- environment.py     # SimEnvironment container
|   +-- ground/
|       +-- c2_station.py      # Ground station interface
+-- scenarios/
|   +-- basic_imagery_tasking.py
|   +-- sensor_fault_injection.py
|   +-- plan_execution.py
|   +-- constellation_handoff.py
+-- cli/
|   +-- console.py             # Interactive Rich console
+-- tests/
|   +-- test_middleware.py
|   +-- test_mission_manager.py
|   +-- test_uci_validation.py
|   +-- test_eoir_service.py
|   +-- test_scenarios.py
+-- docs/
    +-- architecture.md        # Architecture documentation
```

## Documentation

- [Architecture Guide](docs/architecture.md) -- OMS bus design, MWA pattern, service topology, and message flow diagrams

## Scenarios

| Scenario                  | Description                                          |
|---------------------------|------------------------------------------------------|
| `basic_imagery_tasking`   | Full imagery pipeline: command, slew, capture, ATR   |
| `sensor_fault_injection`  | Fault injection and recovery during sensor operation |
| `plan_execution`          | Multi-step mission plan execution                    |
| `constellation_handoff`   | Handoff coordination between constellation assets    |

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=satsim --cov-report=term-missing

# Run a specific test module
pytest tests/test_middleware.py -v
```

## License

See LICENSE file for details.
