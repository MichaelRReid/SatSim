# SatSim Scenario Guide

Scenarios are self-contained test sequences that exercise specific simulation capabilities. Each scenario resets the simulation to a clean state, executes a defined sequence of operations, and returns a JSON result with a `success` boolean.

## Running Scenarios

**Interactive mode:**

```
satsim> scenario run basic_imagery_tasking
```

**Non-interactive mode:**

```
python -m satsim --run basic_imagery_tasking
```

**Directly as a Python module:**

```
python -m scenarios.basic_imagery_tasking
```

---

## Built-in Scenarios

### 1. basic_imagery_tasking

A single INFRARED_LONG_WAVE imagery collection targeting Denver, CO.

**What it does:**

1. Sends an `ImageryCapabilityCommand` with:
   - Target: Denver, CO (lat 39.7392, lon -104.9903)
   - Sensor mode: `INFRARED_LONG_WAVE`
   - Resolution: 1.0 m
   - Duration: 45 seconds
   - Priority: `ROUTINE`
2. Advances the simulation by 120 seconds to allow the full command-to-report flow.
3. Checks for `ImageryReport` and `TargetDetectionReport` messages on the bus.

**Success criteria:** An `ImageryReport` message is found in the bus log.

**Result fields:**

| Field                  | Type     | Description                                |
|------------------------|----------|--------------------------------------------|
| `scenario`             | string   | `"basic_imagery_tasking"`                  |
| `success`              | boolean  | True if an ImageryReport was received      |
| `message_sequence`     | string[] | Ordered list of all message types on the bus |
| `total_messages`       | int      | Total number of bus messages                |
| `imagery_report_found` | boolean  | Whether an ImageryReport was published     |
| `atr_detections_found` | boolean  | Whether a TargetDetectionReport was found  |
| `mission_log`          | object[] | Full mission manager event log             |

---

### 2. sensor_fault_injection

Injects a sensor fault and verifies automatic recovery.

**What it does:**

1. Sends a VISIBLE-mode imagery command (lat 39.7392, lon -104.9903, res 0.3 m, dur 30 s).
2. Injects a `FOCAL_PLANE_OVERHEAT` fault into the `EOIR_SENSOR_01` service.
3. Verifies that a `FaultReport` is published and a `SensorCalibrationCommand` is issued in response.
4. Waits for calibration to complete (~70 seconds).
5. Retries the imagery command and verifies successful collection.

**Success criteria:** All of the following must be true:
- A `FaultReport` was published.
- A `SensorCalibrationCommand` was issued.
- The EO/IR sensor returns to `NOMINAL` or `DEGRADED` state.
- The retry imagery command produces an `ImageryReport`.

**Result fields:**

| Field                    | Type     | Description                                  |
|--------------------------|----------|----------------------------------------------|
| `scenario`               | string   | `"sensor_fault_injection"`                   |
| `success`                | boolean  | True if all recovery criteria are met        |
| `transitions`            | object[] | State transitions at each step               |
| `fault_report_published` | boolean  | Whether a FaultReport appeared on the bus    |
| `calibration_commanded`  | boolean  | Whether a calibration was automatically sent |
| `retry_imagery_found`    | boolean  | Whether the retry produced an ImageryReport  |

Each entry in `transitions` contains:

| Field        | Type   | Description                                   |
|--------------|--------|-----------------------------------------------|
| `step`       | string | Step label (initial_command, fault_injected, after_calibration, after_retry) |
| `eoir_state` | string | Operational state of EOIR_SENSOR_01 at that point |

---

### 3. plan_execution

Executes a 4-step mission plan through the Mission Manager.

**What it does:**

1. **Step 1 -- Calibrate:** Sends a `SensorCalibrationCommand` with mode `DARK` to `EOIR_CAP_01`.
2. **Step 2 -- Image Denver:** Sends an `ImageryCapabilityCommand` targeting Denver, CO (lat 39.7392, lon -104.9903) in VISIBLE mode at 0.3 m resolution for 30 seconds.
3. **Step 3 -- Image Colorado Springs:** Sends an `ImageryCapabilityCommand` targeting Colorado Springs, CO (lat 38.8339, lon -104.8214) with the same parameters.
4. **Step 4 -- Status request:** Sends a `StatusRequest` to `EOIR_SENSOR_01`.

All steps have `ContinueOnFault` set to True, so the plan continues even if individual steps encounter faults.

The plan is submitted via `ground.send_mission_plan()` and the simulation advances 600 seconds to allow full execution.

**Success criteria:** Plan state reaches `COMPLETED` and all 4 steps are executed.

**Result fields:**

| Field                 | Type     | Description                                |
|-----------------------|----------|--------------------------------------------|
| `scenario`            | string   | `"plan_execution"`                         |
| `success`             | boolean  | True if plan completed all steps           |
| `plan_id`             | string   | UUID of the submitted plan                 |
| `plan_state`          | string   | Final plan state (COMPLETED, EXECUTING, etc.) |
| `completed_steps`     | int      | Number of steps executed                   |
| `total_steps`         | int      | Total steps in the plan (4)                |
| `plan_status_reports` | int      | Number of PlanStatusReport messages        |
| `mission_log`         | object[] | Full mission manager event log             |

---

### 4. constellation_handoff

Demonstrates store-and-forward behavior during ground contact gaps.

**What it does:**

1. Advances simulation by 10 seconds to initialize.
2. Sends a VISIBLE-mode imagery command (lat 39.7392, lon -104.9903, res 0.5 m, dur 20 s) and advances 120 seconds to generate data.
3. Records the CDH downlink queue size (should be > 0).
4. Checks the current ground contact window status from the COMMS service.
5. Flushes the CDH downlink queue (simulating a ground contact pass).
6. Verifies the queue is empty after the flush and inspects CCSDS packet structure.

**Success criteria:** All of the following must be true:
- The queue had data before the flush (`queue_size > 0`).
- At least one packet was flushed.
- The queue is empty after the flush (`queue_size == 0`).

**Result fields:**

| Field                    | Type     | Description                                |
|--------------------------|----------|--------------------------------------------|
| `scenario`               | string   | `"constellation_handoff"`                  |
| `success`                | boolean  | True if store-and-forward worked correctly |
| `queue_size_with_data`   | int      | CDH queue size before flush                |
| `contact_status`         | object   | COMMS contact window information           |
| `packets_flushed`        | int      | Number of CCSDS packets flushed            |
| `queue_size_after_flush` | int      | CDH queue size after flush (should be 0)   |
| `ccsds_sample`           | object   | Structure of the first flushed packet      |

The `ccsds_sample` object contains:

| Field         | Type   | Description                        |
|---------------|--------|------------------------------------|
| `apid`        | int    | Application Process Identifier     |
| `type`        | string | Packet type (`"TM"` or `"TC"`)     |
| `seq_count`   | int    | Sequence counter                   |
| `data_length` | int    | Length of the packet data in bytes  |

---

## Writing Custom Scenarios

Custom scenarios are Python modules placed in the `scenarios/` directory. Each module must define a `run()` function.

### Template

```python
"""Description of your scenario."""

from satsim.sim.setup import create_simulation


def run(env=None, ground=None, bus=None, services=None):
    """Execute the scenario.

    Parameters are provided when called from the CLI or another scenario.
    If called standalone, the function creates its own simulation.
    """
    if env is None:
        env, bus, ground, services = create_simulation()

    result = {"scenario": "my_custom_scenario", "success": False}

    # --- Your scenario logic here ---

    # Use ground.send_imagery_command() to task the sensor
    # Use env.step(seconds) to advance simulation time
    # Use bus.get_message_log() to inspect messages
    # Use services["SERVICE_ID"] to access individual services
    # Use services["SERVICE_ID"].inject_fault("CODE") for fault injection

    # --- Set success criteria ---
    result["success"] = True  # Set based on your checks

    return result


if __name__ == "__main__":
    import json
    result = run()
    print(json.dumps(result, indent=2, default=str))
```

### Available APIs

**Environment (`env`):**
- `env.step(seconds)` -- Advance the simulation clock by the given duration.
- `env.clock.met()` -- Get mission elapsed time in seconds.
- `env.clock.now()` -- Get current simulation datetime.
- `env.orbit.get_lat_lon_alt()` -- Get current subsatellite point.
- `env.stop()` -- Shut down the simulation.

**Ground station (`ground`):**
- `ground.send_imagery_command(lat, lon, alt, sensor_mode, resolution_m, duration_sec, priority)` -- Send an imagery tasking command.
- `ground.send_power_command(service_id, state)` -- Send a power mode command.
- `ground.send_mission_plan(name, steps)` -- Submit a multi-step mission plan.
- `ground.request_telemetry_dump()` -- Request CCSDS telemetry packets.

**Message bus (`bus`):**
- `bus.get_message_log(last_n=N, message_type=TYPE)` -- Retrieve bus message history.
- `bus.publish(message)` -- Publish a UCI message to the bus.
- `bus.clear_log()` -- Clear the message log.

**Services (`services` dict):**
- `services["EOIR_SENSOR_01"]` -- EO/IR sensor service (supports `inject_fault()`, `operational_state`)
- `services["GNC_01"]` -- Guidance, navigation, and control
- `services["EPS_01"]` -- Electrical power system
- `services["THERMAL_01"]` -- Thermal control
- `services["COMMS_01"]` -- Communications (supports `get_contact_window_status()`)
- `services["CDH_01"]` -- Command and data handling (supports `get_downlink_queue_size()`, `flush_downlink_queue()`)
- `services["MISSION_MGR"]` -- Mission manager (supports `get_mission_log()`)

**UCI Messages (from `satsim.uci.messages`):**
- `Header(SenderID=...)` -- Message header
- `ImageryCapabilityCommand(...)` -- Imagery tasking
- `SensorCalibrationCommand(...)` -- Sensor calibration
- `StatusRequest(...)` -- Request service status
- `PointTarget(Latitude=..., Longitude=...)` -- Geographic target
- `PlanStep(StepNumber=..., CommandRef=..., ExecutionOffset_sec=..., ContinueOnFault=...)` -- Mission plan step

### Registering a Custom Scenario

To make a custom scenario available in the interactive CLI, add its name to the `scenario_map` dictionary in `cli/console.py` inside the `_run_scenario` method, and to the list in `do_scenario`:

```python
# In _run_scenario:
scenario_map = {
    ...
    "my_custom_scenario": "scenarios.my_custom_scenario",
}

# In do_scenario, under "list":
scenarios = [
    ...
    "my_custom_scenario",
]
```

### Example Output Structure

All scenarios return a dictionary. The common fields are:

```json
{
  "scenario": "scenario_name",
  "success": true
}
```

Additional fields are scenario-specific (see the individual scenario sections above). All output is serializable to JSON via `json.dumps(result, indent=2, default=str)`.
