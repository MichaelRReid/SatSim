# Payload Services

---

## EOIRService

**Service ID:** `EOIR_SENSOR_01`

**Purpose:** Simulates the Electro-Optical / Infrared (EO/IR) imaging payload sensor. Handles sensor activation, image collection, calibration, and quality assessment. Computes NIIRS ratings from ground sample distance.

### State Machine

| State | Description |
|-------|-------------|
| `NOMINAL` | Sensor healthy, calibrated, and ready for tasking |
| `DEGRADED` | Sensor operational but calibration is overdue (3+ collections since last calibration) |
| `CALIBRATING` | Calibration sequence in progress |
| `FAULT` | Sensor has an injected or detected fault; collections will be rejected |
| `OFFLINE` | Power state is `OFF` |

State transitions:
- `NOMINAL` -> `DEGRADED`: After 3 collections without calibration
- `NOMINAL` / `DEGRADED` -> `CALIBRATING`: On receipt of `SensorCalibrationCommand`
- `CALIBRATING` -> `NOMINAL`: When calibration completes (collections-since-cal counter resets to 0)
- Any -> `FAULT`: When `inject_fault()` is called
- `FAULT` -> `NOMINAL`: After successful calibration clears the fault code
- Any -> `OFFLINE`: On `PowerModeCommand` with `PowerState=OFF`

### Subscriptions

| Message Type | Handling |
|--------------|----------|
| `SensorActivateCommand` | Begins image collection if sensor is in a valid state |
| `SensorCalibrationCommand` | Initiates calibration sequence |
| `StatusRequest` | Responds with `SensorStatusReport` |
| `PowerModeCommand` | Updates power state; `OFF` transitions to `OFFLINE` |
| `ImageryCapabilityCommand` | Caches capability ID, sensor mode, and collection duration for subsequent activation |

### Publications

| Message Type | Trigger |
|--------------|---------|
| `ImageryReport` | After each collection (with `COMPLETED`/`SUCCESS` or `FAILED`/`SENSOR_FAULT`) |
| `SensorStatusReport` | After each collection and calibration; also on `StatusRequest`. Includes `CALIBRATION_OVERDUE` fault code when degraded. |
| `HeartbeatMessage` | Published every 30 seconds |
| `FaultReport` | Published via `inject_fault()` with severity `ERROR` |

### NIIRS Computation

The NIIRS quality rating is derived from the computed Ground Sample Distance (GSD). GSD is determined by sensor mode and orbital altitude:

**GSD calculation:**

```
GSD = base_gsd[sensor_mode] * (altitude_km / 500.0)
```

Base GSD values by sensor mode:

| Sensor Mode | Base GSD (m) at 500 km |
|-------------|------------------------|
| `VISIBLE` | 0.3 |
| `INFRARED_SHORT_WAVE` | 0.6 |
| `INFRARED_LONG_WAVE` | 1.0 |
| `MULTISPECTRAL` | 0.8 |

**NIIRS rating thresholds:**

| GSD Range | NIIRS Rating |
|-----------|-------------|
| GSD < 0.3 m | `NIIRS_7` |
| 0.3 m <= GSD < 0.5 m | `NIIRS_6` |
| 0.5 m <= GSD < 1.0 m | `NIIRS_5` |
| 1.0 m <= GSD < 2.0 m | `NIIRS_4` |
| GSD >= 2.0 m | `NIIRS_3` |

### Calibration Sequence

1. **Trigger:** A `SensorCalibrationCommand` is received specifying a `CalibrationMode` (e.g. `DARK`, `FLAT`, `FULL`).
2. **Enter calibrating state:** The sensor transitions to `CALIBRATING` and publishes an updated `SensorStatusReport`.
3. **Execute calibration:** In the simulation model, calibration completes synchronously. The external environment clock (`env.step()`) advances time externally.
4. **Reset counters:** The `_collections_since_cal` counter resets to 0. The `last_calibration_time` is updated to the current simulation clock time.
5. **Clear faults:** Any active `_fault_code` is set to `None`.
6. **Return to nominal:** The sensor transitions to `NOMINAL` and publishes a final `SensorStatusReport`.

Calibration is also triggered autonomously by:
- The **Thermal** service when focal plane temperature exceeds 0 C (sends `DARK` calibration).
- The **MissionManager** when a sensor `ERROR` or `CRITICAL` fault is received (sends `DARK` calibration).

### Fault Injection API

The `inject_fault(fault_code)` method allows test scenarios to inject faults into the sensor:

```python
eoir_service.inject_fault("FOCAL_PLANE_OVERHEAT")
```

**Behavior:**
1. Sets `operational_state` to `FAULT`.
2. Stores the fault code internally.
3. Publishes a `FaultReport` with:
   - `FaultCode`: The provided fault code string
   - `FaultSeverity`: `ERROR`
   - `AffectedServiceID`: This sensor's service ID (`EOIR_SENSOR_01`)
   - `FaultDescription`: `Injected fault: <fault_code>`
   - `RecommendedAction`: `Initiate sensor calibration`

**Recovery:** The fault is cleared by performing a calibration (`SensorCalibrationCommand`), which resets the state to `NOMINAL` and clears the fault code.

**Effect on collections:** While in `FAULT` state, any `SensorActivateCommand` will be rejected with an `ImageryReport` having `ImageryStatus=FAILED` and `CompletionCode=SENSOR_FAULT`.

Common injectable fault codes used in test scenarios:
- `FOCAL_PLANE_OVERHEAT`
- `DETECTOR_ANOMALY`
- `CALIBRATION_FAILURE`

---

## ATRService

**Service ID:** `ATR_01`

**Purpose:** Simulates Automatic Target Recognition (ATR) processing on collected imagery. Receives completed imagery reports, performs quality gating, runs a simulated detection algorithm, and publishes target detection reports.

### State Machine

| State | Description |
|-------|-------------|
| `NOMINAL` | Service powered on and processing imagery |
| `FAULT` | Service powered off |

The ATR service does not maintain complex internal states beyond power status.

### Subscriptions

| Message Type | Handling |
|--------------|----------|
| `ImageryReport` | Triggers the ATR processing pipeline |

### Publications

| Message Type | Trigger |
|--------------|---------|
| `TargetDetectionReport` | After successful ATR processing of a completed image |
| `FaultReport` | When imagery quality is insufficient for ATR (NIIRS < 4) |
| `HeartbeatMessage` | Published every 30 seconds |

### ATR Processing Pipeline

The ATR pipeline executes the following steps when an `ImageryReport` is received:

```
ImageryReport received
        |
        v
  [1] Status Check ---- ImageryStatus != COMPLETED ----> discard
        |
        v
  [2] Quality Gate ---- NIIRS < 4 ----> publish FaultReport (LOW_QUALITY_IMAGERY, WARNING)
        |                                 and stop processing
        v
  [3] Processing Delay
        |  (5-15 seconds simulated time via env.step)
        v
  [4] Detection Generation
        |  (0-5 random detections)
        v
  [5] Publish TargetDetectionReport
```

**Step 1 -- Status check:** Only imagery reports with `ImageryStatus=COMPLETED` are processed. Failed collections are silently discarded.

**Step 2 -- Quality gate:** The NIIRS value is extracted from the `ImageMetadata.QualityRating` field. If the numeric NIIRS level is less than 4 (i.e. `NIIRS_3` or lower), a `FaultReport` is published with:
- `FaultCode`: `LOW_QUALITY_IMAGERY`
- `FaultSeverity`: `WARNING`
- `FaultDescription`: Includes the actual quality rating
- `RecommendedAction`: `Re-collect imagery with better conditions`

Processing stops; no detections are generated.

**Step 3 -- Processing delay:** A randomized processing time of 5 to 15 seconds is simulated by advancing the environment clock.

**Step 4 -- Detection generation:** A random number of detections (0 to 5) is generated. Each detection includes:
- **TargetClass:** Randomly selected from `VEHICLE`, `BUILDING`, `VESSEL`, `AIRCRAFT`, `UNKNOWN`
- **Confidence_pct:** Random value between 30% and 99%
- **Latitude_deg / Longitude_deg:** Base coordinates (39.7, -104.9) with small random offsets (within +/-0.01 degrees)
- **BoundingBox:** Random pixel coordinates within a 1920x1080 frame, with random width and height (10-200 pixels)

**Step 5 -- Publish results:** A `TargetDetectionReport` is published containing:
- `ReferenceImageID`: The `MessageID` from the triggering `ImageryReport`'s header
- `DetectionCount`: Number of detections generated
- `Detections`: List of individual `Detection` elements

### Fault Injection

The ATR service does not expose a dedicated `inject_fault()` method. Faults can be simulated by:
- Sending imagery with low NIIRS quality to trigger the quality gate fault path.
- Setting the service power state to `OFF` via `PowerModeCommand`, which causes `get_status()` to report `ServiceState=FAULT`.
