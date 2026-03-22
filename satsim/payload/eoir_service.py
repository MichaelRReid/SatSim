"""EO/IR imaging payload sensor service."""

import random
from satsim.bus.middleware import BaseService
from satsim.uci.messages import (
    Header, UCIMessage,
    SensorActivateCommand, SensorCalibrationCommand, StatusRequest,
    PowerModeCommand, ImageryCapabilityCommand,
    ImageryReport, SensorStatusReport, HeartbeatMessage, FaultReport,
    ImageMetadata,
)


class EOIRService(BaseService):
    """Simulates the EO/IR imaging payload sensor."""

    def __init__(self, service_id: str = "EOIR_SENSOR_01", env=None):
        super().__init__(service_id, env)
        self.operational_state = "NOMINAL"
        self.focal_plane_temp = -20.0
        self.last_calibration_time = ""
        self.sensor_mode = "VISIBLE"
        self.gain_mode = "AUTO"
        self._power_state = "ON"
        self._image_sequence = 0
        self._collections_since_cal = 0
        self._collection_duration = 30
        self._current_capability_id = "EOIR_CAP_01"
        self._last_pointing_error = 0.01
        self._fault_code = None

    def start(self):
        super().start()
        if self.env:
            self.last_calibration_time = self.env.clock.now().strftime("%Y-%m-%dT%H:%M:%S.000Z")
        if self.mwa:
            self.mwa.subscribe(SensorActivateCommand)
            self.mwa.subscribe(SensorCalibrationCommand)
            self.mwa.subscribe(StatusRequest)
            self.mwa.subscribe(PowerModeCommand)
            self.mwa.subscribe(ImageryCapabilityCommand)
        if self.env:
            self.env.clock.register_timer(self.send_heartbeat, 30)

    def stop(self):
        super().stop()

    def handle_message(self, message: UCIMessage):
        if isinstance(message, SensorActivateCommand):
            self._handle_activate(message)
        elif isinstance(message, SensorCalibrationCommand):
            self._handle_calibration(message)
        elif isinstance(message, StatusRequest):
            if message.TargetServiceID == self.service_id:
                self._publish(self.get_status())
        elif isinstance(message, PowerModeCommand):
            if message.TargetServiceID == self.service_id:
                self._power_state = message.PowerState
                if message.PowerState == "OFF":
                    self.operational_state = "OFFLINE"
        elif isinstance(message, ImageryCapabilityCommand):
            self._current_capability_id = message.CapabilityID
            self.sensor_mode = message.SensorMode
            self._collection_duration = message.CollectionDuration_sec

    def _handle_activate(self, cmd: SensorActivateCommand):
        if self.operational_state in ("FAULT", "OFFLINE", "CALIBRATING"):
            self._publish(ImageryReport(
                header=Header(SenderID=self.service_id),
                ImageryStatus="FAILED",
                CompletionCode="SENSOR_FAULT",
            ))
            return

        self._current_capability_id = cmd.CapabilityID
        self.gain_mode = cmd.GainMode

        # Record collection timestamps from current sim clock
        start_time = self.env.clock.now().strftime("%Y-%m-%dT%H:%M:%S.000Z") if self.env else "2026-01-15T12:00:00.000Z"
        # End time offset by collection duration (clock is advanced externally)
        if self.env:
            from datetime import timedelta
            end_dt = self.env.clock.now() + timedelta(seconds=self._collection_duration)
            end_time = end_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        else:
            end_time = "2026-01-15T12:01:00.000Z"

        self._image_sequence += 1
        self._collections_since_cal += 1

        # Compute GSD based on sensor mode and altitude
        alt_km = 550.0
        if self.env:
            _, _, alt_km = self.env.orbit.get_lat_lon_alt()

        gsd = self._compute_gsd(self.sensor_mode, alt_km)
        quality = self._compute_niirs(gsd)
        cloud_cover = round(random.uniform(0, 40), 1)

        report = ImageryReport(
            header=Header(SenderID=self.service_id),
            ImageryStatus="COMPLETED",
            CompletionCode="SUCCESS",
            ImageMetadata=ImageMetadata(
                FileLocation=f"S3://NSS-ARCHIVE/IMG_{self._image_sequence:05d}.NITF",
                FileFormat="NITF_2.1",
                CloudCoverPercentage=cloud_cover,
                QualityRating=quality,
                GSD_m=round(gsd, 2),
                CollectionStartTime=start_time,
                CollectionEndTime=end_time,
            ),
        )
        self._publish(report)

        # Publish sensor status
        self._publish(self.get_status())

        # Check if degraded due to lack of calibration
        if self._collections_since_cal >= 3:
            self.operational_state = "DEGRADED"
            self._publish(SensorStatusReport(
                header=Header(SenderID=self.service_id),
                ServiceID=self.service_id,
                OperationalState="DEGRADED",
                TemperatureC=25.0,
                FocalPlaneTemp_C=self.focal_plane_temp,
                LastCalibrationTime=self.last_calibration_time,
                FaultCode="CALIBRATION_OVERDUE",
            ))

    def _handle_calibration(self, cmd: SensorCalibrationCommand):
        prev_state = self.operational_state
        self.operational_state = "CALIBRATING"
        self._publish(self.get_status())

        # Calibration completes immediately in the simulation model
        # (time advancement happens externally via env.step)
        self.operational_state = "NOMINAL"
        self._collections_since_cal = 0
        self.last_calibration_time = self.env.clock.now().strftime("%Y-%m-%dT%H:%M:%S.000Z") if self.env else "2026-01-15T12:01:00.000Z"
        self._fault_code = None
        self._publish(self.get_status())

    def _compute_gsd(self, sensor_mode: str, altitude_km: float) -> float:
        """Compute ground sample distance based on mode and altitude."""
        ref_alt = 500.0
        scale = altitude_km / ref_alt

        base_gsd = {
            "VISIBLE": 0.3,
            "INFRARED_SHORT_WAVE": 0.6,
            "INFRARED_LONG_WAVE": 1.0,
            "MULTISPECTRAL": 0.8,
        }
        return base_gsd.get(sensor_mode, 1.0) * scale

    @staticmethod
    def _compute_niirs(gsd_m: float) -> str:
        """Compute NIIRS rating from GSD."""
        if gsd_m < 0.3:
            return "NIIRS_7"
        elif gsd_m < 0.5:
            return "NIIRS_6"
        elif gsd_m < 1.0:
            return "NIIRS_5"
        elif gsd_m < 2.0:
            return "NIIRS_4"
        else:
            return "NIIRS_3"

    def inject_fault(self, fault_code: str):
        """Inject a fault into the sensor service."""
        self.operational_state = "FAULT"
        self._fault_code = fault_code
        self._publish(FaultReport(
            header=Header(SenderID=self.service_id),
            FaultCode=fault_code,
            FaultSeverity="ERROR",
            AffectedServiceID=self.service_id,
            FaultDescription=f"Injected fault: {fault_code}",
            RecommendedAction="Initiate sensor calibration",
        ))

    def get_status(self) -> SensorStatusReport:
        return SensorStatusReport(
            header=Header(SenderID=self.service_id),
            ServiceID=self.service_id,
            OperationalState=self.operational_state,
            TemperatureC=25.0,
            FocalPlaneTemp_C=self.focal_plane_temp,
            LastCalibrationTime=self.last_calibration_time,
            FaultCode=self._fault_code,
        )
