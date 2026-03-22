# UCI Message Reference

All messages use the XML namespace `urn:uci:messages:v6.0` and carry a mandatory `Header` element.

---

## Common Header

Every UCI message begins with a `Header` element containing the following fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| MessageID | string (UUID) | Required | Unique identifier for this message instance |
| Timestamp | string (ISO 8601 UTC, trailing `Z`) | Required | Time the message was created |
| SenderID | string | Required | Identifier of the originating service |
| Version | string | Required | Protocol version; always `UCI-6.0` |
| Priority | enum | Required | `ROUTINE`, `PRIORITY`, `IMMEDIATE`, or `FLASH` |

---

## Request Messages

### ImageryCapabilityCommand

**Purpose:** Commands the satellite to configure and execute an imagery collection against a geographic target.

**Category:** Request

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Header | Header | Required | Standard UCI header |
| CapabilityID | string | Required | Identifier of the imaging capability (e.g. `EOIR_CAP_01`) |
| CommandState | string | Required | Command action; typically `CHANGE_SETTING` |
| SensorMode | string | Required | Imaging mode: `VISIBLE`, `INFRARED_SHORT_WAVE`, `INFRARED_LONG_WAVE`, or `MULTISPECTRAL` |
| Resolution_m | float | Required | Requested ground resolution in meters |
| CollectionDuration_sec | int | Required | Duration of the collection in seconds |
| Target | PointTarget | Required | Geographic target with sub-elements (see below) |

**Target / PointTarget sub-elements:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Latitude | float | Required | WGS-84 latitude in decimal degrees |
| Longitude | float | Required | WGS-84 longitude in decimal degrees |
| Altitude_m | float | Optional | Target altitude in meters (default `0.0`) |
| CoordSystem | string | Optional | Coordinate reference system (default `WGS84`) |

```xml
<?xml version='1.0' encoding='UTF-8'?>
<ImageryCapabilityCommand xmlns="urn:uci:messages:v6.0">
  <Header>
    <MessageID>a1b2c3d4-e5f6-7890-abcd-ef1234567890</MessageID>
    <Timestamp>2026-01-15T12:00:00.000Z</Timestamp>
    <SenderID>GROUND_C2</SenderID>
    <Version>UCI-6.0</Version>
    <Priority>PRIORITY</Priority>
  </Header>
  <CapabilityID>EOIR_CAP_01</CapabilityID>
  <CommandState>CHANGE_SETTING</CommandState>
  <SensorMode>VISIBLE</SensorMode>
  <Resolution_m>1.0</Resolution_m>
  <CollectionDuration_sec>30</CollectionDuration_sec>
  <Target>
    <PointTarget>
      <Latitude>39.7392</Latitude>
      <Longitude>-104.9903</Longitude>
      <Altitude_m>0.0</Altitude_m>
      <CoordSystem>WGS84</CoordSystem>
    </PointTarget>
  </Target>
</ImageryCapabilityCommand>
```

---

### SlewCommand

**Purpose:** Commands GNC to slew the spacecraft attitude to a target pointing vector.

**Category:** Request

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Header | Header | Required | Standard UCI header |
| TargetPointingVector / Azimuth_deg | float | Required | Desired azimuth angle in degrees |
| TargetPointingVector / Elevation_deg | float | Required | Desired elevation angle in degrees |
| TargetPointingVector / Stabilization_ms | int | Required | Time to allow for stabilization after slew, in milliseconds |

```xml
<?xml version='1.0' encoding='UTF-8'?>
<SlewCommand xmlns="urn:uci:messages:v6.0">
  <Header>
    <MessageID>b2c3d4e5-f6a7-8901-bcde-f12345678901</MessageID>
    <Timestamp>2026-01-15T12:00:05.000Z</Timestamp>
    <SenderID>MISSION_MGR</SenderID>
    <Version>UCI-6.0</Version>
    <Priority>PRIORITY</Priority>
  </Header>
  <TargetPointingVector>
    <Azimuth_deg>255.01</Azimuth_deg>
    <Elevation_deg>50.26</Elevation_deg>
    <Stabilization_ms>500</Stabilization_ms>
  </TargetPointingVector>
</SlewCommand>
```

---

### SensorActivateCommand

**Purpose:** Commands the EO/IR sensor payload to begin an image collection with specific integration and gain parameters.

**Category:** Request

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Header | Header | Required | Standard UCI header |
| CapabilityID | string | Required | Capability identifier (e.g. `EOIR_CAP_01`) |
| IntegrationTime_ms | int | Required | Detector integration time in milliseconds |
| GainMode | string | Required | Gain control mode: `AUTO`, `HIGH`, `LOW` |

```xml
<?xml version='1.0' encoding='UTF-8'?>
<SensorActivateCommand xmlns="urn:uci:messages:v6.0">
  <Header>
    <MessageID>c3d4e5f6-a7b8-9012-cdef-123456789012</MessageID>
    <Timestamp>2026-01-15T12:00:10.000Z</Timestamp>
    <SenderID>MISSION_MGR</SenderID>
    <Version>UCI-6.0</Version>
    <Priority>ROUTINE</Priority>
  </Header>
  <CapabilityID>EOIR_CAP_01</CapabilityID>
  <IntegrationTime_ms>3000</IntegrationTime_ms>
  <GainMode>AUTO</GainMode>
</SensorActivateCommand>
```

---

### StatusRequest

**Purpose:** Requests a status report from a specific service on the bus.

**Category:** Request

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Header | Header | Required | Standard UCI header |
| TargetServiceID | string | Required | Service identifier to query (e.g. `GNC_01`, `EPS_01`) |

```xml
<?xml version='1.0' encoding='UTF-8'?>
<StatusRequest xmlns="urn:uci:messages:v6.0">
  <Header>
    <MessageID>d4e5f6a7-b8c9-0123-defa-234567890123</MessageID>
    <Timestamp>2026-01-15T12:01:00.000Z</Timestamp>
    <SenderID>MISSION_MGR</SenderID>
    <Version>UCI-6.0</Version>
    <Priority>ROUTINE</Priority>
  </Header>
  <TargetServiceID>GNC_01</TargetServiceID>
</StatusRequest>
```

---

### PowerModeCommand

**Purpose:** Commands a service to transition to a specified power state.

**Category:** Request

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Header | Header | Required | Standard UCI header |
| TargetServiceID | string | Required | Service to command (or `ALL` for broadcast) |
| PowerState | string | Required | Desired power state: `ON`, `OFF`, `SAFE_MODE` |

```xml
<?xml version='1.0' encoding='UTF-8'?>
<PowerModeCommand xmlns="urn:uci:messages:v6.0">
  <Header>
    <MessageID>e5f6a7b8-c9d0-1234-efab-345678901234</MessageID>
    <Timestamp>2026-01-15T12:02:00.000Z</Timestamp>
    <SenderID>MISSION_MGR</SenderID>
    <Version>UCI-6.0</Version>
    <Priority>IMMEDIATE</Priority>
  </Header>
  <TargetServiceID>GNC_01</TargetServiceID>
  <PowerState>SAFE_MODE</PowerState>
</PowerModeCommand>
```

---

### SensorCalibrationCommand

**Purpose:** Commands the EO/IR sensor to execute a calibration sequence.

**Category:** Request

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Header | Header | Required | Standard UCI header |
| CapabilityID | string | Required | Capability identifier (e.g. `EOIR_CAP_01`) |
| CalibrationMode | string | Required | Calibration type: `DARK`, `FLAT`, `FULL` |

```xml
<?xml version='1.0' encoding='UTF-8'?>
<SensorCalibrationCommand xmlns="urn:uci:messages:v6.0">
  <Header>
    <MessageID>f6a7b8c9-d0e1-2345-fabc-456789012345</MessageID>
    <Timestamp>2026-01-15T12:03:00.000Z</Timestamp>
    <SenderID>MISSION_MGR</SenderID>
    <Version>UCI-6.0</Version>
    <Priority>ROUTINE</Priority>
  </Header>
  <CapabilityID>EOIR_CAP_01</CapabilityID>
  <CalibrationMode>DARK</CalibrationMode>
</SensorCalibrationCommand>
```

---

## Plan Messages

### MissionPlan

**Purpose:** Defines an ordered sequence of commands (steps) to be executed by the Mission Manager as an autonomous plan.

**Category:** Plan

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Header | Header | Required | Standard UCI header |
| PlanID | string (UUID) | Required | Unique plan identifier |
| PlanName | string | Required | Human-readable plan name |
| ScheduledStartTime | string (ISO 8601 UTC) | Required | Planned execution start time |
| Steps | list of Step | Required | Ordered list of plan steps |

**Step sub-elements:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| StepNumber | int | Required | 1-based ordinal position |
| CommandRef | string | Required | XML string of the UCI command to execute |
| ExecutionOffset_sec | int | Optional | Delay in seconds from plan start (default `0`) |
| ContinueOnFault | bool | Optional | Whether to continue the plan if this step faults (default `true`) |

```xml
<?xml version='1.0' encoding='UTF-8'?>
<MissionPlan xmlns="urn:uci:messages:v6.0">
  <Header>
    <MessageID>a7b8c9d0-e1f2-3456-abcd-567890123456</MessageID>
    <Timestamp>2026-01-15T11:55:00.000Z</Timestamp>
    <SenderID>GROUND_C2</SenderID>
    <Version>UCI-6.0</Version>
    <Priority>PRIORITY</Priority>
  </Header>
  <PlanID>plan-001-denver</PlanID>
  <PlanName>Denver Overpass Collection</PlanName>
  <ScheduledStartTime>2026-01-15T12:00:00.000Z</ScheduledStartTime>
  <Steps>
    <Step>
      <StepNumber>1</StepNumber>
      <CommandRef>&lt;ImageryCapabilityCommand xmlns="urn:uci:messages:v6.0"&gt;...&lt;/ImageryCapabilityCommand&gt;</CommandRef>
      <ExecutionOffset_sec>0</ExecutionOffset_sec>
      <ContinueOnFault>true</ContinueOnFault>
    </Step>
    <Step>
      <StepNumber>2</StepNumber>
      <CommandRef>&lt;ImageryCapabilityCommand xmlns="urn:uci:messages:v6.0"&gt;...&lt;/ImageryCapabilityCommand&gt;</CommandRef>
      <ExecutionOffset_sec>120</ExecutionOffset_sec>
      <ContinueOnFault>false</ContinueOnFault>
    </Step>
  </Steps>
</MissionPlan>
```

---

## Report Messages

### ImageryReport

**Purpose:** Reports the outcome of an imagery collection, including metadata about the captured image.

**Category:** Report

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Header | Header | Required | Standard UCI header |
| ImageryStatus | string | Required | `COMPLETED` or `FAILED` |
| CompletionCode | string | Required | Result code: `SUCCESS`, `SENSOR_FAULT`, etc. |
| ImageMetadata | ImageMetadata | Optional | Present when status is `COMPLETED` |

**ImageMetadata sub-elements:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| FileLocation | string | Required | Storage URI (e.g. `S3://NSS-ARCHIVE/IMG_00001.NITF`) |
| FileFormat | string | Required | Image format (e.g. `NITF_2.1`) |
| CloudCoverPercentage | float | Required | Estimated cloud cover (0-100) |
| QualityRating | string | Required | NIIRS quality rating (`NIIRS_3` through `NIIRS_7`) |
| GSD_m | float | Required | Ground sample distance in meters |
| CollectionStartTime | string (ISO 8601 UTC) | Required | Start of collection window |
| CollectionEndTime | string (ISO 8601 UTC) | Required | End of collection window |

```xml
<?xml version='1.0' encoding='UTF-8'?>
<ImageryReport xmlns="urn:uci:messages:v6.0">
  <Header>
    <MessageID>b8c9d0e1-f2a3-4567-bcde-678901234567</MessageID>
    <Timestamp>2026-01-15T12:01:00.000Z</Timestamp>
    <SenderID>EOIR_SENSOR_01</SenderID>
    <Version>UCI-6.0</Version>
    <Priority>ROUTINE</Priority>
  </Header>
  <ImageryStatus>COMPLETED</ImageryStatus>
  <CompletionCode>SUCCESS</CompletionCode>
  <ImageMetadata>
    <FileLocation>S3://NSS-ARCHIVE/IMG_00001.NITF</FileLocation>
    <FileFormat>NITF_2.1</FileFormat>
    <CloudCoverPercentage>12.5</CloudCoverPercentage>
    <QualityRating>NIIRS_6</QualityRating>
    <GSD_m>0.33</GSD_m>
    <CollectionStartTime>2026-01-15T12:00:10.000Z</CollectionStartTime>
    <CollectionEndTime>2026-01-15T12:00:40.000Z</CollectionEndTime>
  </ImageMetadata>
</ImageryReport>
```

---

### SensorStatusReport

**Purpose:** Reports the current operational state and health of the EO/IR sensor payload.

**Category:** Report

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Header | Header | Required | Standard UCI header |
| ServiceID | string | Required | Sensor service identifier (e.g. `EOIR_SENSOR_01`) |
| OperationalState | string | Required | `NOMINAL`, `DEGRADED`, `CALIBRATING`, `FAULT`, `OFFLINE` |
| TemperatureC | float | Required | Electronics temperature in degrees Celsius |
| FocalPlaneTemp_C | float | Required | Focal plane array temperature in degrees Celsius |
| LastCalibrationTime | string (ISO 8601 UTC) | Required | Timestamp of last completed calibration |
| FaultCode | string | Optional | Active fault code if in degraded or fault state |

```xml
<?xml version='1.0' encoding='UTF-8'?>
<SensorStatusReport xmlns="urn:uci:messages:v6.0">
  <Header>
    <MessageID>c9d0e1f2-a3b4-5678-cdef-789012345678</MessageID>
    <Timestamp>2026-01-15T12:01:05.000Z</Timestamp>
    <SenderID>EOIR_SENSOR_01</SenderID>
    <Version>UCI-6.0</Version>
    <Priority>ROUTINE</Priority>
  </Header>
  <ServiceID>EOIR_SENSOR_01</ServiceID>
  <OperationalState>DEGRADED</OperationalState>
  <TemperatureC>25.0</TemperatureC>
  <FocalPlaneTemp_C>-18.5</FocalPlaneTemp_C>
  <LastCalibrationTime>2026-01-15T11:30:00.000Z</LastCalibrationTime>
  <FaultCode>CALIBRATION_OVERDUE</FaultCode>
</SensorStatusReport>
```

---

### AttitudeStatusReport

**Purpose:** Reports the current spacecraft attitude, pointing error, and angular rates from the GNC subsystem.

**Category:** Report

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Header | Header | Required | Standard UCI header |
| PointingMode | string | Required | `NADIR`, `TARGET_TRACK`, `SAFE_HOLD` |
| PointingError_deg | float | Required | Current pointing error magnitude in degrees |
| QuaternionW | float | Required | Attitude quaternion scalar component |
| QuaternionX | float | Required | Attitude quaternion X component |
| QuaternionY | float | Required | Attitude quaternion Y component |
| QuaternionZ | float | Required | Attitude quaternion Z component |
| AngularRate_degps | float | Required | Body angular rate in degrees per second |

```xml
<?xml version='1.0' encoding='UTF-8'?>
<AttitudeStatusReport xmlns="urn:uci:messages:v6.0">
  <Header>
    <MessageID>d0e1f2a3-b4c5-6789-defa-890123456789</MessageID>
    <Timestamp>2026-01-15T12:00:08.000Z</Timestamp>
    <SenderID>GNC_01</SenderID>
    <Version>UCI-6.0</Version>
    <Priority>ROUTINE</Priority>
  </Header>
  <PointingMode>TARGET_TRACK</PointingMode>
  <PointingError_deg>0.0234</PointingError_deg>
  <QuaternionW>1.0</QuaternionW>
  <QuaternionX>0.0</QuaternionX>
  <QuaternionY>0.0</QuaternionY>
  <QuaternionZ>0.0</QuaternionZ>
  <AngularRate_degps>0.0032</AngularRate_degps>
</AttitudeStatusReport>
```

---

### PowerStatusReport

**Purpose:** Reports the current state of the Electrical Power System including battery, solar array, and bus power.

**Category:** Report

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Header | Header | Required | Standard UCI header |
| BatterySOC_pct | float | Required | Battery state of charge as a percentage (0-100) |
| SolarArrayPower_W | float | Required | Current solar array output in watts |
| TotalBusPower_W | float | Required | Total spacecraft bus power consumption in watts |
| BusVoltage_V | float | Required | Main power bus voltage in volts |
| PowerMode | string | Required | `NOMINAL`, `ECLIPSE`, `DEGRADED`, `EMERGENCY_LOAD_SHED` |

```xml
<?xml version='1.0' encoding='UTF-8'?>
<PowerStatusReport xmlns="urn:uci:messages:v6.0">
  <Header>
    <MessageID>e1f2a3b4-c5d6-7890-efab-901234567890</MessageID>
    <Timestamp>2026-01-15T12:01:30.000Z</Timestamp>
    <SenderID>EPS_01</SenderID>
    <Version>UCI-6.0</Version>
    <Priority>ROUTINE</Priority>
  </Header>
  <BatterySOC_pct>82.3</BatterySOC_pct>
  <SolarArrayPower_W>200.0</SolarArrayPower_W>
  <TotalBusPower_W>150.0</TotalBusPower_W>
  <BusVoltage_V>28.0</BusVoltage_V>
  <PowerMode>NOMINAL</PowerMode>
</PowerStatusReport>
```

---

### ThermalStatusReport

**Purpose:** Reports thermal environment readings for the spacecraft focal plane, electronics, and structure.

**Category:** Report

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Header | Header | Required | Standard UCI header |
| ServiceID | string | Required | Thermal service identifier (e.g. `THERMAL_01`) |
| FocalPlaneTemp_C | float | Required | Focal plane array temperature in degrees Celsius |
| ElectronicsTemp_C | float | Required | Electronics bay temperature in degrees Celsius |
| StructureTemp_C | float | Required | Structural temperature in degrees Celsius |
| ThermalMode | string | Required | `NOMINAL`, `OVER_TEMP_WARNING`, `OVER_TEMP_CRITICAL` |

```xml
<?xml version='1.0' encoding='UTF-8'?>
<ThermalStatusReport xmlns="urn:uci:messages:v6.0">
  <Header>
    <MessageID>f2a3b4c5-d6e7-8901-fabc-012345678901</MessageID>
    <Timestamp>2026-01-15T12:02:00.000Z</Timestamp>
    <SenderID>THERMAL_01</SenderID>
    <Version>UCI-6.0</Version>
    <Priority>ROUTINE</Priority>
  </Header>
  <ServiceID>THERMAL_01</ServiceID>
  <FocalPlaneTemp_C>-19.5</FocalPlaneTemp_C>
  <ElectronicsTemp_C>25.0</ElectronicsTemp_C>
  <StructureTemp_C>15.0</StructureTemp_C>
  <ThermalMode>NOMINAL</ThermalMode>
</ThermalStatusReport>
```

---

### FaultReport

**Purpose:** Reports a fault condition detected by any service on the bus, including severity and recommended corrective action.

**Category:** Report

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Header | Header | Required | Standard UCI header |
| FaultCode | string | Required | Machine-readable fault identifier (e.g. `BATTERY_CRITICAL`, `FOCAL_PLANE_OVERHEAT`) |
| FaultSeverity | string | Required | `WARNING`, `ERROR`, or `CRITICAL` |
| AffectedServiceID | string | Required | Identifier of the service experiencing the fault |
| FaultDescription | string | Required | Human-readable description of the fault condition |
| RecommendedAction | string | Required | Suggested corrective action |

```xml
<?xml version='1.0' encoding='UTF-8'?>
<FaultReport xmlns="urn:uci:messages:v6.0">
  <Header>
    <MessageID>a3b4c5d6-e7f8-9012-abcd-123456789012</MessageID>
    <Timestamp>2026-01-15T12:05:00.000Z</Timestamp>
    <SenderID>EPS_01</SenderID>
    <Version>UCI-6.0</Version>
    <Priority>IMMEDIATE</Priority>
  </Header>
  <FaultCode>BATTERY_CRITICAL</FaultCode>
  <FaultSeverity>CRITICAL</FaultSeverity>
  <AffectedServiceID>EPS_01</AffectedServiceID>
  <FaultDescription>Battery SOC critically low: 8.2%</FaultDescription>
  <RecommendedAction>Immediate load shedding required</RecommendedAction>
</FaultReport>
```

---

### NavigationStatusReport

**Purpose:** Reports the spacecraft orbit state including ECEF position and velocity, geodetic coordinates, and ephemeris age.

**Category:** Report

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Header | Header | Required | Standard UCI header |
| PositionECEF_x_m | float | Required | ECEF X position in meters |
| PositionECEF_y_m | float | Required | ECEF Y position in meters |
| PositionECEF_z_m | float | Required | ECEF Z position in meters |
| VelocityECEF_x_ms | float | Required | ECEF X velocity in meters per second |
| VelocityECEF_y_ms | float | Required | ECEF Y velocity in meters per second |
| VelocityECEF_z_ms | float | Required | ECEF Z velocity in meters per second |
| Latitude_deg | float | Required | Sub-satellite geodetic latitude in degrees |
| Longitude_deg | float | Required | Sub-satellite longitude in degrees |
| Altitude_m | float | Required | Altitude above WGS-84 ellipsoid in meters |
| OrbitalPeriod_sec | float | Required | Current orbital period in seconds |
| EphemerisAge_sec | float | Required | Age of the ephemeris data in seconds |

```xml
<?xml version='1.0' encoding='UTF-8'?>
<NavigationStatusReport xmlns="urn:uci:messages:v6.0">
  <Header>
    <MessageID>b4c5d6e7-f8a9-0123-bcde-234567890123</MessageID>
    <Timestamp>2026-01-15T12:00:10.000Z</Timestamp>
    <SenderID>GNC_01</SenderID>
    <Version>UCI-6.0</Version>
    <Priority>ROUTINE</Priority>
  </Header>
  <PositionECEF_x_m>6921000.0</PositionECEF_x_m>
  <PositionECEF_y_m>0.0</PositionECEF_y_m>
  <PositionECEF_z_m>0.0</PositionECEF_z_m>
  <VelocityECEF_x_ms>0.0</VelocityECEF_x_ms>
  <VelocityECEF_y_ms>7500.0</VelocityECEF_y_ms>
  <VelocityECEF_z_ms>0.0</VelocityECEF_z_ms>
  <Latitude_deg>39.7392</Latitude_deg>
  <Longitude_deg>-104.9903</Longitude_deg>
  <Altitude_m>550000.0</Altitude_m>
  <OrbitalPeriod_sec>5790.0</OrbitalPeriod_sec>
  <EphemerisAge_sec>120.0</EphemerisAge_sec>
</NavigationStatusReport>
```

---

### PlanStatusReport

**Purpose:** Reports the execution progress and state of a mission plan being managed by the Mission Manager.

**Category:** Report

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Header | Header | Required | Standard UCI header |
| PlanID | string | Required | Identifier of the plan being tracked |
| CurrentStepNumber | int | Required | 1-based index of the step currently executing |
| PlanState | string | Required | `WAITING`, `EXECUTING`, `COMPLETED`, or `ABORTED` |
| CompletedSteps | int | Required | Number of steps that have finished |
| TotalSteps | int | Required | Total number of steps in the plan |

```xml
<?xml version='1.0' encoding='UTF-8'?>
<PlanStatusReport xmlns="urn:uci:messages:v6.0">
  <Header>
    <MessageID>c5d6e7f8-a9b0-1234-cdef-345678901234</MessageID>
    <Timestamp>2026-01-15T12:02:30.000Z</Timestamp>
    <SenderID>MISSION_MGR</SenderID>
    <Version>UCI-6.0</Version>
    <Priority>ROUTINE</Priority>
  </Header>
  <PlanID>plan-001-denver</PlanID>
  <CurrentStepNumber>2</CurrentStepNumber>
  <PlanState>EXECUTING</PlanState>
  <CompletedSteps>1</CompletedSteps>
  <TotalSteps>3</TotalSteps>
</PlanStatusReport>
```

---

### HeartbeatMessage

**Purpose:** Periodic liveness signal published by every service to indicate operational status and uptime.

**Category:** Report

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Header | Header | Required | Standard UCI header |
| ServiceID | string | Required | Identifier of the reporting service |
| ServiceState | string | Required | `NOMINAL` or `FAULT` |
| UptimeSeconds | int | Required | Seconds since the service started |

```xml
<?xml version='1.0' encoding='UTF-8'?>
<HeartbeatMessage xmlns="urn:uci:messages:v6.0">
  <Header>
    <MessageID>d6e7f8a9-b0c1-2345-defa-456789012345</MessageID>
    <Timestamp>2026-01-15T12:03:00.000Z</Timestamp>
    <SenderID>GNC_01</SenderID>
    <Version>UCI-6.0</Version>
    <Priority>ROUTINE</Priority>
  </Header>
  <ServiceID>GNC_01</ServiceID>
  <ServiceState>NOMINAL</ServiceState>
  <UptimeSeconds>1800</UptimeSeconds>
</HeartbeatMessage>
```

---

## Metadata Messages

### ImageMetadataRecord

**Purpose:** Provides extended metadata for an archived image product, including collection geometry and ground coverage bounds.

**Category:** Metadata

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Header | Header | Required | Standard UCI header |
| SensorID | string | Required | Sensor that collected the image (e.g. `EOIR_SENSOR_01`) |
| FileLocation | string | Required | Storage URI for the image file |
| FileFormat | string | Required | Image format (e.g. `NITF_2.1`) |
| CloudCoverPercentage | float | Required | Estimated cloud cover (0-100) |
| QualityRating | string | Required | NIIRS quality rating |
| GSD_m | float | Required | Ground sample distance in meters |
| CollectionStartTime | string (ISO 8601 UTC) | Required | Start of collection window |
| CollectionEndTime | string (ISO 8601 UTC) | Required | End of collection window |
| CollectionGeometry | CollectionGeometry | Required | Geometry sub-element (see below) |
| GroundCoverBounds | GroundCoverBounds | Required | Geographic bounds sub-element (see below) |

**CollectionGeometry sub-elements:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| OffNadirAngle_deg | float | Required | Off-nadir look angle in degrees |
| SunElevation_deg | float | Required | Sun elevation angle in degrees |

**GroundCoverBounds sub-elements:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| NorthLat | float | Required | Northern latitude bound |
| SouthLat | float | Required | Southern latitude bound |
| EastLon | float | Required | Eastern longitude bound |
| WestLon | float | Required | Western longitude bound |

```xml
<?xml version='1.0' encoding='UTF-8'?>
<ImageMetadataRecord xmlns="urn:uci:messages:v6.0">
  <Header>
    <MessageID>e7f8a9b0-c1d2-3456-efab-567890123456</MessageID>
    <Timestamp>2026-01-15T12:01:30.000Z</Timestamp>
    <SenderID>EOIR_SENSOR_01</SenderID>
    <Version>UCI-6.0</Version>
    <Priority>ROUTINE</Priority>
  </Header>
  <SensorID>EOIR_SENSOR_01</SensorID>
  <FileLocation>S3://NSS-ARCHIVE/IMG_00001.NITF</FileLocation>
  <FileFormat>NITF_2.1</FileFormat>
  <CloudCoverPercentage>12.5</CloudCoverPercentage>
  <QualityRating>NIIRS_6</QualityRating>
  <GSD_m>0.33</GSD_m>
  <CollectionStartTime>2026-01-15T12:00:10.000Z</CollectionStartTime>
  <CollectionEndTime>2026-01-15T12:00:40.000Z</CollectionEndTime>
  <CollectionGeometry>
    <OffNadirAngle_deg>15.3</OffNadirAngle_deg>
    <SunElevation_deg>52.7</SunElevation_deg>
  </CollectionGeometry>
  <GroundCoverBounds>
    <NorthLat>39.80</NorthLat>
    <SouthLat>39.68</SouthLat>
    <EastLon>-104.90</EastLon>
    <WestLon>-105.08</WestLon>
  </GroundCoverBounds>
</ImageMetadataRecord>
```

---

### TargetDetectionReport

**Purpose:** Reports ATR processing results including classified target detections with geo-locations and bounding boxes.

**Category:** Metadata

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Header | Header | Required | Standard UCI header |
| ReferenceImageID | string | Required | MessageID of the ImageryReport that was processed |
| DetectionCount | int | Required | Number of detections in this report |
| Detections | list of Detection | Required | List of individual detections |

**Detection sub-elements:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| TargetClass | string | Required | Classification: `VEHICLE`, `BUILDING`, `VESSEL`, `AIRCRAFT`, `UNKNOWN` |
| Confidence_pct | float | Required | Classification confidence as a percentage (0-100) |
| Latitude_deg | float | Required | Detection geodetic latitude in degrees |
| Longitude_deg | float | Required | Detection geodetic longitude in degrees |
| BoundingBox | BoundingBox | Required | Pixel-space bounding box (see below) |

**BoundingBox sub-elements:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| PixelX | int | Required | Top-left X coordinate in pixels |
| PixelY | int | Required | Top-left Y coordinate in pixels |
| WidthPx | int | Required | Box width in pixels |
| HeightPx | int | Required | Box height in pixels |

```xml
<?xml version='1.0' encoding='UTF-8'?>
<TargetDetectionReport xmlns="urn:uci:messages:v6.0">
  <Header>
    <MessageID>f8a9b0c1-d2e3-4567-fabc-678901234567</MessageID>
    <Timestamp>2026-01-15T12:01:45.000Z</Timestamp>
    <SenderID>ATR_01</SenderID>
    <Version>UCI-6.0</Version>
    <Priority>ROUTINE</Priority>
  </Header>
  <ReferenceImageID>b8c9d0e1-f2a3-4567-bcde-678901234567</ReferenceImageID>
  <DetectionCount>2</DetectionCount>
  <Detections>
    <Detection>
      <TargetClass>VEHICLE</TargetClass>
      <Confidence_pct>87.3</Confidence_pct>
      <Latitude_deg>39.7401</Latitude_deg>
      <Longitude_deg>-104.9892</Longitude_deg>
      <BoundingBox>
        <PixelX>450</PixelX>
        <PixelY>312</PixelY>
        <WidthPx>85</WidthPx>
        <HeightPx>42</HeightPx>
      </BoundingBox>
    </Detection>
    <Detection>
      <TargetClass>BUILDING</TargetClass>
      <Confidence_pct>94.1</Confidence_pct>
      <Latitude_deg>39.7385</Latitude_deg>
      <Longitude_deg>-104.9910</Longitude_deg>
      <BoundingBox>
        <PixelX>820</PixelX>
        <PixelY>540</PixelY>
        <WidthPx>150</WidthPx>
        <HeightPx>120</HeightPx>
      </BoundingBox>
    </Detection>
  </Detections>
</TargetDetectionReport>
```
