# SatSim CLI Reference

SatSim provides both an interactive console and non-interactive (batch) mode for controlling the satellite bus and EO/IR payload simulation.

## Starting the CLI

```
python -m satsim
```

This launches the interactive console. The prompt displays as:

```
[SatSim] Satellite Bus & EO/IR Payload UCI Simulation
Type 'help' for available commands. Type 'quit' to exit.

satsim>
```

---

## Interactive Commands

### status

Display a table of all registered services with their current state.

**Syntax:**

```
status
```

**Example output:**

```
                     Service Status
+-----------------+------------------+---------+----------------------------+
| Service ID      | Type             | State   | Details                    |
+-----------------+------------------+---------+----------------------------+
| EOIR_SENSOR_01  | EOIRService      | RUNNING | OpState: NOMINAL           |
| GNC_01          | GNCService       | RUNNING | Mode: NADIR, Err: 0.0010deg|
| EPS_01          | EPSService       | RUNNING | SOC: 85.0%, Mode: NOMINAL  |
| THERMAL_01      | ThermalService   | RUNNING | FP: -150.0C, Mode: NOMINAL |
| COMMS_01        | CommsService     | RUNNING | Downlink: YES              |
| CDH_01          | CDHService       | RUNNING |                            |
| MISSION_MGR     | MissionManager   | RUNNING |                            |
+-----------------+------------------+---------+----------------------------+
```

State colors: green = RUNNING, red = STOPPED or FAULT, yellow = DEGRADED.

---

### task

Send an imagery capability command to the EO/IR sensor.

**Syntax:**

```
task <lat> <lon> [--mode MODE] [--res M] [--dur SEC] [--priority PRI]
```

**Parameters:**

| Parameter    | Required | Default   | Description                                  |
|--------------|----------|-----------|----------------------------------------------|
| `<lat>`      | Yes      | --        | Target latitude in decimal degrees            |
| `<lon>`      | Yes      | --        | Target longitude in decimal degrees           |
| `--mode`     | No       | VISIBLE   | Sensor mode (VISIBLE, INFRARED_LONG_WAVE, etc.) |
| `--res`      | No       | 1.0       | Ground sample distance in meters              |
| `--dur`      | No       | 30        | Collection duration in seconds                |
| `--priority` | No       | ROUTINE   | Task priority level                           |

**Example:**

```
satsim> task 39.7392 -104.9903 --mode INFRARED_LONG_WAVE --res 0.5 --dur 45
Sending imagery command: lat=39.7392, lon=-104.9903, mode=INFRARED_LONG_WAVE, res=0.5m, dur=45s
ImageryReport received!
ATR TargetDetectionReport received!
```

After sending the command, the simulation advances by `dur + 60` seconds and prints any ImageryReport or TargetDetectionReport messages received on the bus.

---

### plan

Load and execute a scenario or check plan execution status.

**Syntax:**

```
plan load <scenario_file>
plan status
```

**Subcommands:**

| Subcommand            | Description                                      |
|-----------------------|--------------------------------------------------|
| `plan load <name>`    | Load and run a named scenario (resets simulation) |
| `plan status`         | Display current plan state, step, and total steps |

**Example:**

```
satsim> plan status
Plan State: COMPLETED
Current Step: 4
Total Steps: 4
```

---

### service

Inspect or control individual services.

**Syntax:**

```
service status <id>
service fault <id> <code>
service power <id> <state>
service calibrate <id> <mode>
```

**Subcommands:**

| Subcommand                      | Description                                      |
|---------------------------------|--------------------------------------------------|
| `service status <id>`           | Print the UCI XML status of a service             |
| `service fault <id> <code>`     | Inject a named fault into a service               |
| `service power <id> <state>`    | Send a PowerModeCommand to a service              |
| `service calibrate <id> <mode>` | Send a SensorCalibrationCommand to a service      |

**Known service IDs:** `EOIR_SENSOR_01`, `GNC_01`, `EPS_01`, `THERMAL_01`, `COMMS_01`, `CDH_01`, `MISSION_MGR`

**Known fault codes:** `FOCAL_PLANE_OVERHEAT`

**Known calibration modes:** `DARK`

**Examples:**

```
satsim> service status EOIR_SENSOR_01
EOIR_SENSOR_01 Status:
<StatusReport> ... </StatusReport>

satsim> service fault EOIR_SENSOR_01 FOCAL_PLANE_OVERHEAT
Fault FOCAL_PLANE_OVERHEAT injected into EOIR_SENSOR_01

satsim> service power EPS_01 LOW_POWER
PowerModeCommand sent: EPS_01 -> LOW_POWER

satsim> service calibrate EOIR_SENSOR_01 DARK
Calibration DARK sent to EOIR_SENSOR_01
```

---

### telemetry dump

Request a CCSDS telemetry dump from the CDH subsystem.

**Syntax:**

```
telemetry dump
```

**Example output:**

```
              CCSDS Telemetry Packets
+-----+------+------+----------+
| Seq | APID | Type | Data Len |
+-----+------+------+----------+
| 0   | 100  | TM   | 256      |
| 1   | 100  | TM   | 128      |
| 2   | 101  | TM   | 64       |
+-----+------+------+----------+
Total packets: 3
```

Displays up to 20 packets per dump.

---

### log

View bus message history or mission manager event log.

**Syntax:**

```
log messages [--last N] [--type TYPE]
log mission
```

**Parameters for `log messages`:**

| Parameter  | Default | Description                                      |
|------------|---------|--------------------------------------------------|
| `--last`   | 20      | Number of recent messages to display              |
| `--type`   | (all)   | Filter by UCI message type (e.g., ImageryReport)  |

**Example:**

```
satsim> log messages --last 5 --type ImageryReport
           Bus Messages (last 5)
+--------------+---------------+-----------+--------------------------+--------------+
| MessageID    | Type          | Sender    | Timestamp                | Destinations |
+--------------+---------------+-----------+--------------------------+--------------+
| a1b2c3d4e... | ImageryReport | EOIR_SE...| 2026-01-01T00:02:00+00:00| GROUND_C2    |
+--------------+---------------+-----------+--------------------------+--------------+

satsim> log mission
                        Mission Log
+--------------------+--------------------------+-------------------------------+
| Event              | Timestamp                | Details                       |
+--------------------+--------------------------+-------------------------------+
| plan_loaded        | 2026-01-01T00:00:00+00:00| {"plan_id": "..."}            |
| step_started       | 2026-01-01T00:00:00+00:00| {"step": 1}                   |
| step_completed     | 2026-01-01T00:01:05+00:00| {"step": 1}                   |
+--------------------+--------------------------+-------------------------------+
```

The mission log displays the last 20 entries.

---

### orbit info

Display current orbital state and ground contact status.

**Syntax:**

```
orbit info
```

**Example output:**

```
              Orbit State
+----------------+--------------------+
| Parameter      | Value              |
+----------------+--------------------+
| Latitude       | 39.7392 deg        |
| Longitude      | -104.9903 deg      |
| Altitude       | 500.00 km          |
| ECEF X         | -1262078 m         |
| ECEF Y         | -4855012 m         |
| ECEF Z         | 4044830 m          |
| Eclipse        | NO                 |
| Orbital Period | 5676.8 sec         |
| MET            | 120.0 sec          |
| Sim Time       | 2026-01-01 00:02:00|
| Downlink       | AVAILABLE          |
| Next Contact   | 2400 sec           |
+----------------+--------------------+
```

---

### sim

Control simulation time progression.

**Syntax:**

```
sim speed <factor>
sim advance <seconds>
```

| Subcommand             | Description                                          |
|------------------------|------------------------------------------------------|
| `sim speed <factor>`   | Set the time acceleration multiplier                  |
| `sim advance <seconds>`| Advance simulation by the given number of seconds     |

**Examples:**

```
satsim> sim speed 10
Time acceleration set to 10.0x

satsim> sim advance 300
Advanced 300.0 simulated seconds. MET: 420.0s
```

---

### scenario

List or run predefined scenarios.

**Syntax:**

```
scenario list
scenario run <name>
```

**Example:**

```
satsim> scenario list
     Available Scenarios
+---------------------------+
| Name                      |
+---------------------------+
| basic_imagery_tasking     |
| sensor_fault_injection    |
| plan_execution            |
| constellation_handoff     |
+---------------------------+

satsim> scenario run basic_imagery_tasking
Running scenario: basic_imagery_tasking...
Scenario complete. Success: True
{
  "scenario": "basic_imagery_tasking",
  "success": true,
  "message_sequence": [...],
  "total_messages": 8,
  "imagery_report_found": true,
  "atr_detections_found": true,
  "mission_log": [...]
}
```

Running a scenario resets the simulation to a clean state before execution.

---

### help

Display a summary table of all available commands.

**Syntax:**

```
help
help <command>
```

Use `help` with no arguments for the full command list, or `help <command>` for detailed help on a specific command.

---

### quit / exit

Shut down the simulation and exit the console.

**Syntax:**

```
quit
exit
```

Ctrl+D (EOF) also exits.

---

## Non-Interactive Mode

Run SatSim from the command line without entering the interactive console.

### Single Imagery Task

```
python -m satsim --task --lat LAT --lon LON --mode MODE --res M --dur SEC
```

| Argument  | Required | Default  | Description                    |
|-----------|----------|----------|--------------------------------|
| `--task`  | Yes      | --       | Flag to run a single task      |
| `--lat`   | Yes      | --       | Target latitude                |
| `--lon`   | Yes      | --       | Target longitude               |
| `--mode`  | No       | VISIBLE  | Sensor mode                    |
| `--res`   | No       | 1.0      | Resolution in meters           |
| `--dur`   | No       | 30       | Duration in seconds            |

**Example:**

```
python -m satsim --task --lat 39.7392 --lon -104.9903 --mode INFRARED_LONG_WAVE --res 0.5 --dur 45
```

Output is a JSON object containing the last 10 bus messages and the mission log.

### Run a Scenario

```
python -m satsim --scenario --run NAME
```

or simply:

```
python -m satsim --run NAME
```

Runs a named scenario and prints its result as JSON to stdout.

**Example:**

```
python -m satsim --run basic_imagery_tasking
```

### JSON Status Dump

```
python -m satsim --json
```

Prints a JSON object mapping each service ID to its type and running state.

**Example output:**

```json
{
  "EOIR_SENSOR_01": {
    "type": "EOIRService",
    "running": true
  },
  "GNC_01": {
    "type": "GNCService",
    "running": true
  },
  "EPS_01": {
    "type": "EPSService",
    "running": true
  },
  "THERMAL_01": {
    "type": "ThermalService",
    "running": true
  },
  "COMMS_01": {
    "type": "CommsService",
    "running": true
  },
  "CDH_01": {
    "type": "CDHService",
    "running": true
  },
  "MISSION_MGR": {
    "type": "MissionManager",
    "running": true
  }
}
```
