"""Automatic Target Recognition (ATR) service."""

import random
from satsim.bus.middleware import BaseService
from satsim.uci.messages import (
    Header, UCIMessage, ImageryReport, FaultReport, HeartbeatMessage,
    TargetDetectionReport, Detection, BoundingBox,
)


class ATRService(BaseService):
    """Simulates ATR processing on collected imagery."""

    def __init__(self, service_id: str = "ATR_01", env=None):
        super().__init__(service_id, env)
        self._power_state = "ON"

    def start(self):
        super().start()
        if self.mwa:
            self.mwa.subscribe(ImageryReport)
        if self.env:
            self.env.clock.register_timer(self.send_heartbeat, 30)

    def stop(self):
        super().stop()

    def handle_message(self, message: UCIMessage):
        if isinstance(message, ImageryReport):
            self._process_imagery(message)

    def _process_imagery(self, report: ImageryReport):
        if report.ImageryStatus != "COMPLETED":
            return

        # Check quality
        if report.ImageMetadata:
            niirs_val = int(report.ImageMetadata.QualityRating.split("_")[1])
            if niirs_val < 4:
                self._publish(FaultReport(
                    header=Header(SenderID=self.service_id),
                    FaultCode="LOW_QUALITY_IMAGERY",
                    FaultSeverity="WARNING",
                    AffectedServiceID=self.service_id,
                    FaultDescription=f"Imagery quality {report.ImageMetadata.QualityRating} insufficient for ATR",
                    RecommendedAction="Re-collect imagery with better conditions",
                ))
                return

        # Simulate ATR processing time (5-15 seconds)
        processing_time = random.randint(5, 15)
        if self.env:
            self.env.step(processing_time)

        # Generate detections
        num_detections = random.randint(0, 5)
        target_classes = ["VEHICLE", "BUILDING", "VESSEL", "AIRCRAFT", "UNKNOWN"]
        detections = []

        base_lat = 39.7
        base_lon = -104.9
        if report.ImageMetadata and report.ImageMetadata.GSD_m > 0:
            pass  # Use default base coords

        for _ in range(num_detections):
            det = Detection(
                TargetClass=random.choice(target_classes),
                Confidence_pct=round(random.uniform(30, 99), 1),
                Latitude_deg=round(base_lat + random.uniform(-0.01, 0.01), 6),
                Longitude_deg=round(base_lon + random.uniform(-0.01, 0.01), 6),
                BoundingBox=BoundingBox(
                    PixelX=random.randint(0, 1920),
                    PixelY=random.randint(0, 1080),
                    WidthPx=random.randint(10, 200),
                    HeightPx=random.randint(10, 200),
                ),
            )
            detections.append(det)

        self._publish(TargetDetectionReport(
            header=Header(SenderID=self.service_id),
            ReferenceImageID=report.header.MessageID,
            DetectionCount=num_detections,
            Detections=detections,
        ))

    def get_status(self) -> HeartbeatMessage:
        return HeartbeatMessage(
            header=Header(SenderID=self.service_id),
            ServiceID=self.service_id,
            ServiceState="NOMINAL" if self._power_state != "OFF" else "FAULT",
            UptimeSeconds=int(self.env.clock.met() - self._start_met) if self.env else 0,
        )
