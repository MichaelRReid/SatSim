# Bus Services

All bus services extend `BaseService` and communicate over the OMS message bus via per-service MiddleWare Adapters (MWA). Each service validates outgoing and incoming messages against the UCI v6.0 XSD schema. Services publish heartbeat messages every 30 seconds.

---

## MissionManager

**Service ID:** `MISSION_MGR`

**Purpose:** Primary orchestrator for the spacecraft. Receives ground commands and mission plans, coordinates slew maneuvers, sensor activation, imagery collection, and fault response across all subsystems.

### State Machine

| State | Description |
|-------|-------------|
| `WAITING` | No active plan; ready to accept commands or plans |
| `EXECUTING` | A mission plan is actively being stepped through |
| `COMPLETED` | All plan steps have finished successfully |
| `ABORTED` | Plan execution halted due to an unrecoverable fault on a step with `ContinueOnFault=false` |

State transitions:
- `WAITING` -> `EXECUTING`: On receipt of a `MissionPlan`
- `EXECUTING` -> `COMPLETED`: When all plan steps finish
- `EXECUTING` -> `ABORTED`: When a fault occurs on a step where `ContinueOnFault` is `false` and `FaultSeverity` is `ERROR` or `CRITICAL`

### Subscriptions

| Message Type | Handling |
|--------------|----------|
| `ImageryCapabilityCommand` | Initiates the slew-collect-report pipeline: queries GNC, computes pointing vector, sends `SlewCommand`, waits for attitude convergence |
| `MissionPlan` | Begins sequential plan execution from step 1 |
| `StatusRequest` | Responds with `PlanStatusReport` or `HeartbeatMessage` if no plan is active |
| `PowerModeCommand` | Updates internal power state when targeted at this service |
| `AttitudeStatusReport` | Checks pointing error; when < 0.05 deg, sends `SensorActivateCommand` to begin collection |
| `NavigationStatusReport` | Caches latest navigation state |
| `ImageryReport` | Logs collection results; advances plan if executing |
| `SensorStatusReport` | Logged for telemetry |
| `FaultReport` | Triggers corrective actions (calibration for sensor faults, safe-hold for GNC faults); may abort plan |
| `TargetDetectionReport` | Logs ATR detection summary |

### Publications

| Message Type | Trigger |
|--------------|---------|
| `StatusRequest` | Sent to GNC on imagery command receipt |
| `SlewCommand` | Sent to GNC to point at the computed target vector |
| `SensorActivateCommand` | Sent when attitude settles (pointing error < 0.05 deg) |
| `SensorCalibrationCommand` | Sent on sensor `ERROR`/`CRITICAL` faults |
| `PowerModeCommand` | Sent to GNC on GNC `ERROR`/`CRITICAL` faults (commands `SAFE_MODE`) |
| `PlanStatusReport` | Published on plan start, each step transition, and plan completion/abort |
| `HeartbeatMessage` | Published every 30 seconds |

### Fault Behaviors

- **Sensor fault (ERROR/CRITICAL):** Initiates `DARK` calibration on `EOIR_CAP_01`.
- **GNC fault (ERROR/CRITICAL):** Commands GNC to `SAFE_MODE` via `PowerModeCommand`.
- **Plan fault handling:** If the faulting step has `ContinueOnFault=false`, transitions plan to `ABORTED`.

---

## GNC (Guidance, Navigation, and Control)

**Service ID:** `GNC_01`

**Purpose:** Manages spacecraft attitude determination and control (ADCS) and orbit determination. Executes slew maneuvers and publishes periodic navigation state.

### State Machine

| State | Description |
|-------|-------------|
| `NADIR` | Default Earth-pointing mode |
| `TARGET_TRACK` | Actively tracking a commanded target vector |
| `SAFE_HOLD` | Minimum-torque safe orientation after fault or `SAFE_MODE` power command |

State transitions:
- `NADIR` -> `TARGET_TRACK`: On receipt of `SlewCommand`
- `TARGET_TRACK` -> `SAFE_HOLD`: On receipt of `FaultReport` affecting this service, or `PowerModeCommand` with `SAFE_MODE`
- Any -> `SAFE_HOLD`: On `PowerModeCommand` with `PowerState=SAFE_MODE`

### Subscriptions

| Message Type | Handling |
|--------------|----------|
| `SlewCommand` | Computes angular distance, simulates convergence, publishes intermediate and final `AttitudeStatusReport` |
| `StatusRequest` | Responds with `AttitudeStatusReport` and `NavigationStatusReport` |
| `PowerModeCommand` | Sets power state; `SAFE_MODE` transitions pointing to `SAFE_HOLD` and cancels any active slew |
| `FaultReport` | If this service is affected, enters `SAFE_HOLD` |

### Publications

| Message Type | Trigger |
|--------------|---------|
| `AttitudeStatusReport` | During slew convergence (intermediate reports at error > 0.05 deg) and final settled report |
| `NavigationStatusReport` | Published every 10 seconds with ECEF position/velocity from orbit propagator |
| `HeartbeatMessage` | Published every 30 seconds |

### Fault Behaviors

- On receipt of a `FaultReport` targeting `GNC_01`, immediately enters `SAFE_HOLD`, cancels active slew, and publishes updated `AttitudeStatusReport`.
- On `SAFE_MODE` power command, enters `SAFE_HOLD` mode.

---

## CDH (Command and Data Handling)

**Service ID:** `CDH_01`

**Purpose:** Acts as the onboard data recorder and telemetry relay. Subscribes to all message types on the bus, stores them in a bounded circular buffer, and wraps messages in CCSDS Space Packets for ground downlink.

### State Machine

| State | Description |
|-------|-------------|
| `ON` | Normal operation: storing and relaying messages |
| `OFF` | All message handling disabled; no storage or downlink |

State transitions:
- `ON` -> `OFF`: On receipt of `PowerModeCommand` with `PowerState=OFF` targeting this service
- `OFF` -> `ON`: On receipt of `PowerModeCommand` with `PowerState=ON` targeting this service

### Subscriptions

| Message Type | Handling |
|--------------|----------|
| All message types | Stores each message in circular buffer (max 1000); queues for CCSDS downlink |
| `PowerModeCommand` | Updates internal power state when targeted |
| `StatusRequest` | Responds with `HeartbeatMessage` |

### Publications

| Message Type | Trigger |
|--------------|---------|
| `HeartbeatMessage` | Published every 30 seconds |

### CCSDS Packaging

- Each service is assigned a unique Application Process Identifier (APID) starting at 100.
- Messages are serialized to XML, wrapped in a 6-byte CCSDS primary header, and queued for downlink.
- Sequence counts are maintained per-packet (14-bit rollover).

### Fault Behaviors

- When `OFF`, silently drops all incoming messages.
- No autonomous fault generation; CDH is a passive recorder.

---

## EPS (Electrical Power System)

**Service ID:** `EPS_01`

**Purpose:** Simulates the spacecraft power system including solar array generation, battery state of charge, and power bus management. Monitors battery thresholds and initiates autonomous load shedding.

### State Machine

| State | Description |
|-------|-------------|
| `NOMINAL` | Solar arrays illuminated, battery charging or charged |
| `ECLIPSE` | Spacecraft in Earth shadow, running on battery |
| `DEGRADED` | Battery SOC below 20%; load shedding initiated |
| `EMERGENCY_LOAD_SHED` | Battery SOC below 10%; all services commanded to `SAFE_MODE` |

State transitions:
- `NOMINAL` -> `ECLIPSE`: When orbit model reports eclipse entry
- `ECLIPSE` -> `NOMINAL`: When orbit model reports eclipse exit (and SOC > 30%)
- `NOMINAL` / `ECLIPSE` -> `DEGRADED`: When battery SOC falls below 20%
- `DEGRADED` -> `EMERGENCY_LOAD_SHED`: When battery SOC falls below 10%
- `DEGRADED` / `EMERGENCY_LOAD_SHED` -> `NOMINAL`: When battery SOC recovers above 30%

### Subscriptions

| Message Type | Handling |
|--------------|----------|
| `PowerModeCommand` | Updates internal power state when targeted |
| `StatusRequest` | Responds with `PowerStatusReport` |

### Publications

| Message Type | Trigger |
|--------------|---------|
| `PowerStatusReport` | On `StatusRequest` |
| `FaultReport` | `BATTERY_LOW` (WARNING) at SOC < 20%; `BATTERY_CRITICAL` (CRITICAL) at SOC < 10% |
| `PowerModeCommand` | Broadcasts `SAFE_MODE` to `ALL` services at SOC < 10% |
| `HeartbeatMessage` | Published every 30 seconds |

### Power Model

- Solar array output: 200 W when illuminated, 0 W in eclipse.
- Battery drain in eclipse: approximately 0.25% SOC per second (simplified model).
- Battery charge: +0.01% SOC per second when net power is positive.
- Bus voltage: fixed at 28 V.

### Fault Behaviors

- **SOC < 20%:** Publishes `BATTERY_LOW` FaultReport with WARNING severity. Sets load-shed flag.
- **SOC < 10%:** Publishes `BATTERY_CRITICAL` FaultReport with CRITICAL severity. Broadcasts `PowerModeCommand(SAFE_MODE)` to all services.
- **SOC > 30%:** Clears load-shed flag, returns to `NOMINAL` (if not in eclipse).

---

## Thermal

**Service ID:** `THERMAL_01`

**Purpose:** Simulates the spacecraft thermal environment, tracking focal plane, electronics, and structure temperatures. Monitors thermal limits and triggers autonomous protective actions when thresholds are exceeded.

### State Machine

| State | Description |
|-------|-------------|
| `NOMINAL` | Focal plane temperature at or below -10 C |
| `OVER_TEMP_WARNING` | Focal plane temperature above -10 C |
| `OVER_TEMP_CRITICAL` | Focal plane temperature above 0 C |

State transitions:
- `NOMINAL` -> `OVER_TEMP_WARNING`: When focal plane temp rises above -10 C
- `OVER_TEMP_WARNING` -> `OVER_TEMP_CRITICAL`: When focal plane temp rises above 0 C
- `OVER_TEMP_WARNING` / `OVER_TEMP_CRITICAL` -> `NOMINAL`: When focal plane temp recovers to -10 C or below

### Thermal Model

- When the sensor is active, focal plane temperature rises at 0.5 C per simulated minute.
- When the sensor is inactive, focal plane temperature recovers toward -20 C at 1.0 C per simulated minute.
- Electronics and structure temperatures are held constant in the current model.

### Subscriptions

| Message Type | Handling |
|--------------|----------|
| `StatusRequest` | Responds with `ThermalStatusReport` |
| `PowerModeCommand` | Updates internal power state when targeted |

### Publications

| Message Type | Trigger |
|--------------|---------|
| `ThermalStatusReport` | On `StatusRequest` |
| `FaultReport` | `FOCAL_PLANE_WARM` (WARNING) when temp > -10 C; `FOCAL_PLANE_OVERHEAT` (ERROR) when temp > 0 C |
| `SensorCalibrationCommand` | Automatically sent (`DARK` mode on `EOIR_CAP_01`) when focal plane exceeds 0 C |
| `HeartbeatMessage` | Published every 30 seconds |

### Fault Behaviors

- **Focal plane > -10 C:** Publishes `FOCAL_PLANE_WARM` WARNING targeting `EOIR_SENSOR_01`. Published once per warming event (resets when temp drops below -10 C).
- **Focal plane > 0 C:** Publishes `FOCAL_PLANE_OVERHEAT` ERROR targeting `EOIR_SENSOR_01` and autonomously commands a `DARK` calibration to force sensor cooldown. Published once per overheat event.

---

## Comms (Communications)

**Service ID:** `COMMS_01`

**Purpose:** Manages spacecraft-to-ground communication link, tracking ground station visibility windows and link quality.

### State Machine

| State | Description |
|-------|-------------|
| `ON` | Normal operation; actively tracking ground contact windows |
| `OFF` | Communications disabled |

Within `ON`, the link availability toggles based on line-of-sight geometry:

| Sub-state | Description |
|-----------|-------------|
| Downlink available | Ground station within 70-degree half-angle cone of visibility |
| Downlink unavailable | Ground station not visible |

### Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ground_lat` | 38.8 | Ground station geodetic latitude |
| `ground_lon` | -104.7 | Ground station geodetic longitude |
| Half-angle | 70 degrees | Visibility cone half-angle for contact window |

### Subscriptions

| Message Type | Handling |
|--------------|----------|
| `StatusRequest` | Responds with `HeartbeatMessage` |
| `PowerModeCommand` | Updates internal power state when targeted |

### Publications

| Message Type | Trigger |
|--------------|---------|
| `HeartbeatMessage` | Published every 30 seconds |

### Contact Window Model

- Ground contact is evaluated every 5 seconds using orbit propagator line-of-sight geometry.
- When in contact, bit error rate scales with elevation angle: `BER = 1e-9 * (1 + 10 / max(elevation, 5))`.
- When out of contact, BER is set to 1.0 (no usable link).
- Link margin is fixed at 10 dB.

### Fault Behaviors

- No autonomous fault generation in the current implementation.
- Returns `FAULT` service state if power state is `OFF`.
