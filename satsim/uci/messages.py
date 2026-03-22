"""UCI message type definitions with XML serialization and validation."""

import uuid
from dataclasses import dataclass, field
from typing import List, Optional
from lxml import etree

from satsim.uci.validator import UCIValidator

UCI_NS = "urn:uci:messages:v6.0"
_NSMAP = {None: UCI_NS}

# Lazy-initialized singleton validator
_validator_instance = None


def _get_validator():
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = UCIValidator()
    return _validator_instance


def _ts_now():
    """Get current simulation time as ISO 8601 UTC string.

    Tries to use the global simulation clock if available, otherwise
    falls back to a default timestamp for testing.
    """
    try:
        from satsim.sim.clock import get_global_clock
        clock = get_global_clock()
        if clock is not None:
            return clock.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    except ImportError:
        pass
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _sub(parent, tag, text=None):
    """Add a subelement with optional text in the UCI namespace."""
    el = etree.SubElement(parent, f"{{{UCI_NS}}}{tag}")
    if text is not None:
        el.text = str(text)
    return el


def _get_text(element, tag, ns=UCI_NS):
    """Get text content of a child element."""
    child = element.find(f"{{{ns}}}{tag}")
    if child is not None and child.text is not None:
        return child.text.strip()
    return None


def _get_float(element, tag, ns=UCI_NS):
    val = _get_text(element, tag, ns)
    return float(val) if val is not None else None


def _get_int(element, tag, ns=UCI_NS):
    val = _get_text(element, tag, ns)
    return int(val) if val is not None else None


def _get_bool(element, tag, ns=UCI_NS):
    val = _get_text(element, tag, ns)
    if val is None:
        return None
    return val.lower() in ('true', '1')


# ============================================================
# Header
# ============================================================

@dataclass
class Header:
    """UCI message header, mandatory on every message."""
    SenderID: str
    MessageID: str = field(default_factory=lambda: str(uuid.uuid4()))
    Timestamp: str = field(default_factory=_ts_now)
    Version: str = "UCI-6.0"
    Priority: str = "ROUTINE"

    def to_xml(self, parent):
        hdr = _sub(parent, "Header")
        _sub(hdr, "MessageID", self.MessageID)
        _sub(hdr, "Timestamp", self.Timestamp)
        _sub(hdr, "SenderID", self.SenderID)
        _sub(hdr, "Version", self.Version)
        _sub(hdr, "Priority", self.Priority)
        return hdr

    @classmethod
    def from_xml(cls, element):
        ns = UCI_NS
        return cls(
            MessageID=_get_text(element, "MessageID", ns),
            Timestamp=_get_text(element, "Timestamp", ns),
            SenderID=_get_text(element, "SenderID", ns),
            Version=_get_text(element, "Version", ns) or "UCI-6.0",
            Priority=_get_text(element, "Priority", ns) or "ROUTINE",
        )


# ============================================================
# Base UCI Message
# ============================================================

class UCIMessage:
    """Base class for all UCI messages."""
    message_type: str = "UCIMessage"

    def to_xml(self) -> str:
        raise NotImplementedError

    @classmethod
    def from_xml(cls, xml_string: str):
        raise NotImplementedError

    def _build_root(self, tag):
        return etree.Element(f"{{{UCI_NS}}}{tag}", nsmap=_NSMAP)

    def _serialize(self, root, validate=True) -> str:
        xml_bytes = etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)
        xml_str = xml_bytes.decode("utf-8")
        if validate:
            _get_validator().validate_or_raise(xml_str)
        return xml_str

    @staticmethod
    def _parse_root(xml_string: str, validate=True):
        if validate:
            _get_validator().validate_or_raise(xml_string)
        return etree.fromstring(xml_string.encode('utf-8') if isinstance(xml_string, str) else xml_string)


# ============================================================
# Point Target helper
# ============================================================

@dataclass
class PointTarget:
    Latitude: float
    Longitude: float
    Altitude_m: float = 0.0
    CoordSystem: str = "WGS84"

    def to_xml(self, parent):
        tgt = _sub(parent, "Target")
        pt = _sub(tgt, "PointTarget")
        _sub(pt, "Latitude", str(self.Latitude))
        _sub(pt, "Longitude", str(self.Longitude))
        _sub(pt, "Altitude_m", str(self.Altitude_m))
        _sub(pt, "CoordSystem", self.CoordSystem)
        return tgt

    @classmethod
    def from_xml(cls, target_el):
        ns = UCI_NS
        pt = target_el.find(f"{{{ns}}}PointTarget")
        return cls(
            Latitude=float(_get_text(pt, "Latitude", ns)),
            Longitude=float(_get_text(pt, "Longitude", ns)),
            Altitude_m=float(_get_text(pt, "Altitude_m", ns) or 0),
            CoordSystem=_get_text(pt, "CoordSystem", ns) or "WGS84",
        )


# ============================================================
# Request Messages
# ============================================================

@dataclass
class ImageryCapabilityCommand(UCIMessage):
    message_type = "ImageryCapabilityCommand"
    header: Header = None
    CapabilityID: str = "EOIR_CAP_01"
    CommandState: str = "CHANGE_SETTING"
    SensorMode: str = "VISIBLE"
    Resolution_m: float = 1.0
    CollectionDuration_sec: int = 30
    Target: PointTarget = None

    def __post_init__(self):
        if self.header is None:
            self.header = Header(SenderID="GROUND_C2")
        if self.Target is None:
            self.Target = PointTarget(Latitude=0.0, Longitude=0.0)

    def to_xml(self) -> str:
        root = self._build_root("ImageryCapabilityCommand")
        self.header.to_xml(root)
        _sub(root, "CapabilityID", self.CapabilityID)
        _sub(root, "CommandState", self.CommandState)
        _sub(root, "SensorMode", self.SensorMode)
        _sub(root, "Resolution_m", str(self.Resolution_m))
        _sub(root, "CollectionDuration_sec", str(self.CollectionDuration_sec))
        self.Target.to_xml(root)
        return self._serialize(root)

    @classmethod
    def from_xml(cls, xml_string: str):
        root = cls._parse_root(xml_string)
        ns = UCI_NS
        hdr = Header.from_xml(root.find(f"{{{ns}}}Header"))
        target_el = root.find(f"{{{ns}}}Target")
        return cls(
            header=hdr,
            CapabilityID=_get_text(root, "CapabilityID", ns),
            CommandState=_get_text(root, "CommandState", ns),
            SensorMode=_get_text(root, "SensorMode", ns),
            Resolution_m=_get_float(root, "Resolution_m", ns),
            CollectionDuration_sec=_get_int(root, "CollectionDuration_sec", ns),
            Target=PointTarget.from_xml(target_el),
        )


@dataclass
class SlewCommand(UCIMessage):
    message_type = "SlewCommand"
    header: Header = None
    Azimuth_deg: float = 0.0
    Elevation_deg: float = 0.0
    Stabilization_ms: int = 500

    def __post_init__(self):
        if self.header is None:
            self.header = Header(SenderID="MISSION_MGR")

    def to_xml(self) -> str:
        root = self._build_root("SlewCommand")
        self.header.to_xml(root)
        tpv = _sub(root, "TargetPointingVector")
        _sub(tpv, "Azimuth_deg", str(self.Azimuth_deg))
        _sub(tpv, "Elevation_deg", str(self.Elevation_deg))
        _sub(tpv, "Stabilization_ms", str(self.Stabilization_ms))
        return self._serialize(root)

    @classmethod
    def from_xml(cls, xml_string: str):
        root = cls._parse_root(xml_string)
        ns = UCI_NS
        hdr = Header.from_xml(root.find(f"{{{ns}}}Header"))
        tpv = root.find(f"{{{ns}}}TargetPointingVector")
        return cls(
            header=hdr,
            Azimuth_deg=_get_float(tpv, "Azimuth_deg", ns),
            Elevation_deg=_get_float(tpv, "Elevation_deg", ns),
            Stabilization_ms=_get_int(tpv, "Stabilization_ms", ns),
        )


@dataclass
class SensorActivateCommand(UCIMessage):
    message_type = "SensorActivateCommand"
    header: Header = None
    CapabilityID: str = "EOIR_CAP_01"
    IntegrationTime_ms: int = 100
    GainMode: str = "AUTO"

    def __post_init__(self):
        if self.header is None:
            self.header = Header(SenderID="MISSION_MGR")

    def to_xml(self) -> str:
        root = self._build_root("SensorActivateCommand")
        self.header.to_xml(root)
        _sub(root, "CapabilityID", self.CapabilityID)
        _sub(root, "IntegrationTime_ms", str(self.IntegrationTime_ms))
        _sub(root, "GainMode", self.GainMode)
        return self._serialize(root)

    @classmethod
    def from_xml(cls, xml_string: str):
        root = cls._parse_root(xml_string)
        ns = UCI_NS
        hdr = Header.from_xml(root.find(f"{{{ns}}}Header"))
        return cls(
            header=hdr,
            CapabilityID=_get_text(root, "CapabilityID", ns),
            IntegrationTime_ms=_get_int(root, "IntegrationTime_ms", ns),
            GainMode=_get_text(root, "GainMode", ns),
        )


@dataclass
class StatusRequest(UCIMessage):
    message_type = "StatusRequest"
    header: Header = None
    TargetServiceID: str = ""

    def __post_init__(self):
        if self.header is None:
            self.header = Header(SenderID="MISSION_MGR")

    def to_xml(self) -> str:
        root = self._build_root("StatusRequest")
        self.header.to_xml(root)
        _sub(root, "TargetServiceID", self.TargetServiceID)
        return self._serialize(root)

    @classmethod
    def from_xml(cls, xml_string: str):
        root = cls._parse_root(xml_string)
        ns = UCI_NS
        hdr = Header.from_xml(root.find(f"{{{ns}}}Header"))
        return cls(
            header=hdr,
            TargetServiceID=_get_text(root, "TargetServiceID", ns),
        )


@dataclass
class PowerModeCommand(UCIMessage):
    message_type = "PowerModeCommand"
    header: Header = None
    TargetServiceID: str = ""
    PowerState: str = "ON"

    def __post_init__(self):
        if self.header is None:
            self.header = Header(SenderID="MISSION_MGR")

    def to_xml(self) -> str:
        root = self._build_root("PowerModeCommand")
        self.header.to_xml(root)
        _sub(root, "TargetServiceID", self.TargetServiceID)
        _sub(root, "PowerState", self.PowerState)
        return self._serialize(root)

    @classmethod
    def from_xml(cls, xml_string: str):
        root = cls._parse_root(xml_string)
        ns = UCI_NS
        hdr = Header.from_xml(root.find(f"{{{ns}}}Header"))
        return cls(
            header=hdr,
            TargetServiceID=_get_text(root, "TargetServiceID", ns),
            PowerState=_get_text(root, "PowerState", ns),
        )


@dataclass
class SensorCalibrationCommand(UCIMessage):
    message_type = "SensorCalibrationCommand"
    header: Header = None
    CapabilityID: str = "EOIR_CAP_01"
    CalibrationMode: str = "DARK"

    def __post_init__(self):
        if self.header is None:
            self.header = Header(SenderID="MISSION_MGR")

    def to_xml(self) -> str:
        root = self._build_root("SensorCalibrationCommand")
        self.header.to_xml(root)
        _sub(root, "CapabilityID", self.CapabilityID)
        _sub(root, "CalibrationMode", self.CalibrationMode)
        return self._serialize(root)

    @classmethod
    def from_xml(cls, xml_string: str):
        root = cls._parse_root(xml_string)
        ns = UCI_NS
        hdr = Header.from_xml(root.find(f"{{{ns}}}Header"))
        return cls(
            header=hdr,
            CapabilityID=_get_text(root, "CapabilityID", ns),
            CalibrationMode=_get_text(root, "CalibrationMode", ns),
        )


# ============================================================
# Plan Messages
# ============================================================

@dataclass
class PlanStep:
    StepNumber: int
    CommandRef: str  # XML string of the UCI command
    ExecutionOffset_sec: int = 0
    ContinueOnFault: bool = True

    def to_xml(self, parent):
        step = _sub(parent, "Step")
        _sub(step, "StepNumber", str(self.StepNumber))
        _sub(step, "CommandRef", self.CommandRef)
        _sub(step, "ExecutionOffset_sec", str(self.ExecutionOffset_sec))
        _sub(step, "ContinueOnFault", str(self.ContinueOnFault).lower())
        return step

    @classmethod
    def from_xml(cls, element):
        ns = UCI_NS
        return cls(
            StepNumber=_get_int(element, "StepNumber", ns),
            CommandRef=_get_text(element, "CommandRef", ns) or "",
            ExecutionOffset_sec=_get_int(element, "ExecutionOffset_sec", ns) or 0,
            ContinueOnFault=_get_bool(element, "ContinueOnFault", ns),
        )


@dataclass
class MissionPlan(UCIMessage):
    message_type = "MissionPlan"
    header: Header = None
    PlanID: str = field(default_factory=lambda: str(uuid.uuid4()))
    PlanName: str = ""
    ScheduledStartTime: str = field(default_factory=_ts_now)
    Steps: List[PlanStep] = field(default_factory=list)

    def __post_init__(self):
        if self.header is None:
            self.header = Header(SenderID="GROUND_C2")

    def to_xml(self) -> str:
        root = self._build_root("MissionPlan")
        self.header.to_xml(root)
        _sub(root, "PlanID", self.PlanID)
        _sub(root, "PlanName", self.PlanName)
        _sub(root, "ScheduledStartTime", self.ScheduledStartTime)
        steps_el = _sub(root, "Steps")
        for step in self.Steps:
            step.to_xml(steps_el)
        return self._serialize(root)

    @classmethod
    def from_xml(cls, xml_string: str):
        root = cls._parse_root(xml_string)
        ns = UCI_NS
        hdr = Header.from_xml(root.find(f"{{{ns}}}Header"))
        steps_el = root.find(f"{{{ns}}}Steps")
        steps = []
        if steps_el is not None:
            for step_el in steps_el.findall(f"{{{ns}}}Step"):
                steps.append(PlanStep.from_xml(step_el))
        return cls(
            header=hdr,
            PlanID=_get_text(root, "PlanID", ns),
            PlanName=_get_text(root, "PlanName", ns),
            ScheduledStartTime=_get_text(root, "ScheduledStartTime", ns),
            Steps=steps,
        )


# ============================================================
# Report / Status Messages
# ============================================================

@dataclass
class ImageMetadata:
    FileLocation: str = ""
    FileFormat: str = "NITF_2.1"
    CloudCoverPercentage: float = 0.0
    QualityRating: str = "NIIRS_5"
    GSD_m: float = 1.0
    CollectionStartTime: str = ""
    CollectionEndTime: str = ""

    def to_xml(self, parent):
        md = _sub(parent, "ImageMetadata")
        _sub(md, "FileLocation", self.FileLocation)
        _sub(md, "FileFormat", self.FileFormat)
        _sub(md, "CloudCoverPercentage", str(self.CloudCoverPercentage))
        _sub(md, "QualityRating", self.QualityRating)
        _sub(md, "GSD_m", str(self.GSD_m))
        _sub(md, "CollectionStartTime", self.CollectionStartTime)
        _sub(md, "CollectionEndTime", self.CollectionEndTime)
        return md

    @classmethod
    def from_xml(cls, element):
        ns = UCI_NS
        return cls(
            FileLocation=_get_text(element, "FileLocation", ns) or "",
            FileFormat=_get_text(element, "FileFormat", ns) or "NITF_2.1",
            CloudCoverPercentage=_get_float(element, "CloudCoverPercentage", ns) or 0.0,
            QualityRating=_get_text(element, "QualityRating", ns) or "NIIRS_5",
            GSD_m=_get_float(element, "GSD_m", ns) or 1.0,
            CollectionStartTime=_get_text(element, "CollectionStartTime", ns) or "",
            CollectionEndTime=_get_text(element, "CollectionEndTime", ns) or "",
        )


@dataclass
class ImageryReport(UCIMessage):
    message_type = "ImageryReport"
    header: Header = None
    ImageryStatus: str = "COMPLETED"
    CompletionCode: str = "SUCCESS"
    ImageMetadata: Optional[ImageMetadata] = None

    def __post_init__(self):
        if self.header is None:
            self.header = Header(SenderID="EOIR_SENSOR_01")

    def to_xml(self) -> str:
        root = self._build_root("ImageryReport")
        self.header.to_xml(root)
        _sub(root, "ImageryStatus", self.ImageryStatus)
        _sub(root, "CompletionCode", self.CompletionCode)
        if self.ImageMetadata is not None:
            self.ImageMetadata.to_xml(root)
        return self._serialize(root)

    @classmethod
    def from_xml(cls, xml_string: str):
        root = cls._parse_root(xml_string)
        ns = UCI_NS
        hdr = Header.from_xml(root.find(f"{{{ns}}}Header"))
        md_el = root.find(f"{{{ns}}}ImageMetadata")
        md = ImageMetadata.from_xml(md_el) if md_el is not None else None
        return cls(
            header=hdr,
            ImageryStatus=_get_text(root, "ImageryStatus", ns),
            CompletionCode=_get_text(root, "CompletionCode", ns),
            ImageMetadata=md,
        )


@dataclass
class SensorStatusReport(UCIMessage):
    message_type = "SensorStatusReport"
    header: Header = None
    ServiceID: str = "EOIR_SENSOR_01"
    OperationalState: str = "NOMINAL"
    TemperatureC: float = 25.0
    FocalPlaneTemp_C: float = -20.0
    LastCalibrationTime: str = ""
    FaultCode: Optional[str] = None

    def __post_init__(self):
        if self.header is None:
            self.header = Header(SenderID="EOIR_SENSOR_01")
        if not self.LastCalibrationTime:
            self.LastCalibrationTime = _ts_now()

    def to_xml(self) -> str:
        root = self._build_root("SensorStatusReport")
        self.header.to_xml(root)
        _sub(root, "ServiceID", self.ServiceID)
        _sub(root, "OperationalState", self.OperationalState)
        _sub(root, "TemperatureC", str(self.TemperatureC))
        _sub(root, "FocalPlaneTemp_C", str(self.FocalPlaneTemp_C))
        _sub(root, "LastCalibrationTime", self.LastCalibrationTime)
        if self.FaultCode is not None:
            _sub(root, "FaultCode", self.FaultCode)
        return self._serialize(root)

    @classmethod
    def from_xml(cls, xml_string: str):
        root = cls._parse_root(xml_string)
        ns = UCI_NS
        hdr = Header.from_xml(root.find(f"{{{ns}}}Header"))
        return cls(
            header=hdr,
            ServiceID=_get_text(root, "ServiceID", ns),
            OperationalState=_get_text(root, "OperationalState", ns),
            TemperatureC=_get_float(root, "TemperatureC", ns),
            FocalPlaneTemp_C=_get_float(root, "FocalPlaneTemp_C", ns),
            LastCalibrationTime=_get_text(root, "LastCalibrationTime", ns),
            FaultCode=_get_text(root, "FaultCode", ns),
        )


@dataclass
class AttitudeStatusReport(UCIMessage):
    message_type = "AttitudeStatusReport"
    header: Header = None
    PointingMode: str = "NADIR"
    PointingError_deg: float = 0.0
    QuaternionW: float = 1.0
    QuaternionX: float = 0.0
    QuaternionY: float = 0.0
    QuaternionZ: float = 0.0
    AngularRate_degps: float = 0.0

    def __post_init__(self):
        if self.header is None:
            self.header = Header(SenderID="GNC_01")

    def to_xml(self) -> str:
        root = self._build_root("AttitudeStatusReport")
        self.header.to_xml(root)
        _sub(root, "PointingMode", self.PointingMode)
        _sub(root, "PointingError_deg", str(self.PointingError_deg))
        _sub(root, "QuaternionW", str(self.QuaternionW))
        _sub(root, "QuaternionX", str(self.QuaternionX))
        _sub(root, "QuaternionY", str(self.QuaternionY))
        _sub(root, "QuaternionZ", str(self.QuaternionZ))
        _sub(root, "AngularRate_degps", str(self.AngularRate_degps))
        return self._serialize(root)

    @classmethod
    def from_xml(cls, xml_string: str):
        root = cls._parse_root(xml_string)
        ns = UCI_NS
        hdr = Header.from_xml(root.find(f"{{{ns}}}Header"))
        return cls(
            header=hdr,
            PointingMode=_get_text(root, "PointingMode", ns),
            PointingError_deg=_get_float(root, "PointingError_deg", ns),
            QuaternionW=_get_float(root, "QuaternionW", ns),
            QuaternionX=_get_float(root, "QuaternionX", ns),
            QuaternionY=_get_float(root, "QuaternionY", ns),
            QuaternionZ=_get_float(root, "QuaternionZ", ns),
            AngularRate_degps=_get_float(root, "AngularRate_degps", ns),
        )


@dataclass
class PowerStatusReport(UCIMessage):
    message_type = "PowerStatusReport"
    header: Header = None
    BatterySOC_pct: float = 85.0
    SolarArrayPower_W: float = 200.0
    TotalBusPower_W: float = 150.0
    BusVoltage_V: float = 28.0
    PowerMode: str = "NOMINAL"

    def __post_init__(self):
        if self.header is None:
            self.header = Header(SenderID="EPS_01")

    def to_xml(self) -> str:
        root = self._build_root("PowerStatusReport")
        self.header.to_xml(root)
        _sub(root, "BatterySOC_pct", str(self.BatterySOC_pct))
        _sub(root, "SolarArrayPower_W", str(self.SolarArrayPower_W))
        _sub(root, "TotalBusPower_W", str(self.TotalBusPower_W))
        _sub(root, "BusVoltage_V", str(self.BusVoltage_V))
        _sub(root, "PowerMode", self.PowerMode)
        return self._serialize(root)

    @classmethod
    def from_xml(cls, xml_string: str):
        root = cls._parse_root(xml_string)
        ns = UCI_NS
        hdr = Header.from_xml(root.find(f"{{{ns}}}Header"))
        return cls(
            header=hdr,
            BatterySOC_pct=_get_float(root, "BatterySOC_pct", ns),
            SolarArrayPower_W=_get_float(root, "SolarArrayPower_W", ns),
            TotalBusPower_W=_get_float(root, "TotalBusPower_W", ns),
            BusVoltage_V=_get_float(root, "BusVoltage_V", ns),
            PowerMode=_get_text(root, "PowerMode", ns),
        )


@dataclass
class ThermalStatusReport(UCIMessage):
    message_type = "ThermalStatusReport"
    header: Header = None
    ServiceID: str = "THERMAL_01"
    FocalPlaneTemp_C: float = -20.0
    ElectronicsTemp_C: float = 25.0
    StructureTemp_C: float = 15.0
    ThermalMode: str = "NOMINAL"

    def __post_init__(self):
        if self.header is None:
            self.header = Header(SenderID="THERMAL_01")

    def to_xml(self) -> str:
        root = self._build_root("ThermalStatusReport")
        self.header.to_xml(root)
        _sub(root, "ServiceID", self.ServiceID)
        _sub(root, "FocalPlaneTemp_C", str(self.FocalPlaneTemp_C))
        _sub(root, "ElectronicsTemp_C", str(self.ElectronicsTemp_C))
        _sub(root, "StructureTemp_C", str(self.StructureTemp_C))
        _sub(root, "ThermalMode", self.ThermalMode)
        return self._serialize(root)

    @classmethod
    def from_xml(cls, xml_string: str):
        root = cls._parse_root(xml_string)
        ns = UCI_NS
        hdr = Header.from_xml(root.find(f"{{{ns}}}Header"))
        return cls(
            header=hdr,
            ServiceID=_get_text(root, "ServiceID", ns),
            FocalPlaneTemp_C=_get_float(root, "FocalPlaneTemp_C", ns),
            ElectronicsTemp_C=_get_float(root, "ElectronicsTemp_C", ns),
            StructureTemp_C=_get_float(root, "StructureTemp_C", ns),
            ThermalMode=_get_text(root, "ThermalMode", ns),
        )


@dataclass
class FaultReport(UCIMessage):
    message_type = "FaultReport"
    header: Header = None
    FaultCode: str = "UNKNOWN"
    FaultSeverity: str = "WARNING"
    AffectedServiceID: str = ""
    FaultDescription: str = ""
    RecommendedAction: str = ""

    def __post_init__(self):
        if self.header is None:
            self.header = Header(SenderID="SYSTEM")

    def to_xml(self) -> str:
        root = self._build_root("FaultReport")
        self.header.to_xml(root)
        _sub(root, "FaultCode", self.FaultCode)
        _sub(root, "FaultSeverity", self.FaultSeverity)
        _sub(root, "AffectedServiceID", self.AffectedServiceID)
        _sub(root, "FaultDescription", self.FaultDescription)
        _sub(root, "RecommendedAction", self.RecommendedAction)
        return self._serialize(root)

    @classmethod
    def from_xml(cls, xml_string: str):
        root = cls._parse_root(xml_string)
        ns = UCI_NS
        hdr = Header.from_xml(root.find(f"{{{ns}}}Header"))
        return cls(
            header=hdr,
            FaultCode=_get_text(root, "FaultCode", ns),
            FaultSeverity=_get_text(root, "FaultSeverity", ns),
            AffectedServiceID=_get_text(root, "AffectedServiceID", ns),
            FaultDescription=_get_text(root, "FaultDescription", ns),
            RecommendedAction=_get_text(root, "RecommendedAction", ns),
        )


@dataclass
class NavigationStatusReport(UCIMessage):
    message_type = "NavigationStatusReport"
    header: Header = None
    PositionECEF_x_m: float = 0.0
    PositionECEF_y_m: float = 0.0
    PositionECEF_z_m: float = 0.0
    VelocityECEF_x_ms: float = 0.0
    VelocityECEF_y_ms: float = 0.0
    VelocityECEF_z_ms: float = 0.0
    Latitude_deg: float = 0.0
    Longitude_deg: float = 0.0
    Altitude_m: float = 550000.0
    OrbitalPeriod_sec: float = 5790.0
    EphemerisAge_sec: float = 0.0

    def __post_init__(self):
        if self.header is None:
            self.header = Header(SenderID="GNC_01")

    def to_xml(self) -> str:
        root = self._build_root("NavigationStatusReport")
        self.header.to_xml(root)
        _sub(root, "PositionECEF_x_m", str(self.PositionECEF_x_m))
        _sub(root, "PositionECEF_y_m", str(self.PositionECEF_y_m))
        _sub(root, "PositionECEF_z_m", str(self.PositionECEF_z_m))
        _sub(root, "VelocityECEF_x_ms", str(self.VelocityECEF_x_ms))
        _sub(root, "VelocityECEF_y_ms", str(self.VelocityECEF_y_ms))
        _sub(root, "VelocityECEF_z_ms", str(self.VelocityECEF_z_ms))
        _sub(root, "Latitude_deg", str(self.Latitude_deg))
        _sub(root, "Longitude_deg", str(self.Longitude_deg))
        _sub(root, "Altitude_m", str(self.Altitude_m))
        _sub(root, "OrbitalPeriod_sec", str(self.OrbitalPeriod_sec))
        _sub(root, "EphemerisAge_sec", str(self.EphemerisAge_sec))
        return self._serialize(root)

    @classmethod
    def from_xml(cls, xml_string: str):
        root = cls._parse_root(xml_string)
        ns = UCI_NS
        hdr = Header.from_xml(root.find(f"{{{ns}}}Header"))
        return cls(
            header=hdr,
            PositionECEF_x_m=_get_float(root, "PositionECEF_x_m", ns),
            PositionECEF_y_m=_get_float(root, "PositionECEF_y_m", ns),
            PositionECEF_z_m=_get_float(root, "PositionECEF_z_m", ns),
            VelocityECEF_x_ms=_get_float(root, "VelocityECEF_x_ms", ns),
            VelocityECEF_y_ms=_get_float(root, "VelocityECEF_y_ms", ns),
            VelocityECEF_z_ms=_get_float(root, "VelocityECEF_z_ms", ns),
            Latitude_deg=_get_float(root, "Latitude_deg", ns),
            Longitude_deg=_get_float(root, "Longitude_deg", ns),
            Altitude_m=_get_float(root, "Altitude_m", ns),
            OrbitalPeriod_sec=_get_float(root, "OrbitalPeriod_sec", ns),
            EphemerisAge_sec=_get_float(root, "EphemerisAge_sec", ns),
        )


@dataclass
class PlanStatusReport(UCIMessage):
    message_type = "PlanStatusReport"
    header: Header = None
    PlanID: str = ""
    CurrentStepNumber: int = 0
    PlanState: str = "WAITING"
    CompletedSteps: int = 0
    TotalSteps: int = 0

    def __post_init__(self):
        if self.header is None:
            self.header = Header(SenderID="MISSION_MGR")

    def to_xml(self) -> str:
        root = self._build_root("PlanStatusReport")
        self.header.to_xml(root)
        _sub(root, "PlanID", self.PlanID)
        _sub(root, "CurrentStepNumber", str(self.CurrentStepNumber))
        _sub(root, "PlanState", self.PlanState)
        _sub(root, "CompletedSteps", str(self.CompletedSteps))
        _sub(root, "TotalSteps", str(self.TotalSteps))
        return self._serialize(root)

    @classmethod
    def from_xml(cls, xml_string: str):
        root = cls._parse_root(xml_string)
        ns = UCI_NS
        hdr = Header.from_xml(root.find(f"{{{ns}}}Header"))
        return cls(
            header=hdr,
            PlanID=_get_text(root, "PlanID", ns),
            CurrentStepNumber=_get_int(root, "CurrentStepNumber", ns),
            PlanState=_get_text(root, "PlanState", ns),
            CompletedSteps=_get_int(root, "CompletedSteps", ns),
            TotalSteps=_get_int(root, "TotalSteps", ns),
        )


@dataclass
class HeartbeatMessage(UCIMessage):
    message_type = "HeartbeatMessage"
    header: Header = None
    ServiceID: str = ""
    ServiceState: str = "NOMINAL"
    UptimeSeconds: int = 0

    def __post_init__(self):
        if self.header is None:
            self.header = Header(SenderID=self.ServiceID or "SYSTEM")

    def to_xml(self) -> str:
        root = self._build_root("HeartbeatMessage")
        self.header.to_xml(root)
        _sub(root, "ServiceID", self.ServiceID)
        _sub(root, "ServiceState", self.ServiceState)
        _sub(root, "UptimeSeconds", str(self.UptimeSeconds))
        return self._serialize(root)

    @classmethod
    def from_xml(cls, xml_string: str):
        root = cls._parse_root(xml_string)
        ns = UCI_NS
        hdr = Header.from_xml(root.find(f"{{{ns}}}Header"))
        return cls(
            header=hdr,
            ServiceID=_get_text(root, "ServiceID", ns),
            ServiceState=_get_text(root, "ServiceState", ns),
            UptimeSeconds=_get_int(root, "UptimeSeconds", ns),
        )


# ============================================================
# Metadata Messages
# ============================================================

@dataclass
class CollectionGeometry:
    OffNadirAngle_deg: float = 0.0
    SunElevation_deg: float = 45.0

    def to_xml(self, parent):
        cg = _sub(parent, "CollectionGeometry")
        _sub(cg, "OffNadirAngle_deg", str(self.OffNadirAngle_deg))
        _sub(cg, "SunElevation_deg", str(self.SunElevation_deg))
        return cg

    @classmethod
    def from_xml(cls, element):
        ns = UCI_NS
        return cls(
            OffNadirAngle_deg=_get_float(element, "OffNadirAngle_deg", ns) or 0.0,
            SunElevation_deg=_get_float(element, "SunElevation_deg", ns) or 45.0,
        )


@dataclass
class GroundCoverBounds:
    NorthLat: float = 0.0
    SouthLat: float = 0.0
    EastLon: float = 0.0
    WestLon: float = 0.0

    def to_xml(self, parent):
        gcb = _sub(parent, "GroundCoverBounds")
        _sub(gcb, "NorthLat", str(self.NorthLat))
        _sub(gcb, "SouthLat", str(self.SouthLat))
        _sub(gcb, "EastLon", str(self.EastLon))
        _sub(gcb, "WestLon", str(self.WestLon))
        return gcb

    @classmethod
    def from_xml(cls, element):
        ns = UCI_NS
        return cls(
            NorthLat=_get_float(element, "NorthLat", ns) or 0.0,
            SouthLat=_get_float(element, "SouthLat", ns) or 0.0,
            EastLon=_get_float(element, "EastLon", ns) or 0.0,
            WestLon=_get_float(element, "WestLon", ns) or 0.0,
        )


@dataclass
class ImageMetadataRecord(UCIMessage):
    message_type = "ImageMetadataRecord"
    header: Header = None
    SensorID: str = "EOIR_SENSOR_01"
    FileLocation: str = ""
    FileFormat: str = "NITF_2.1"
    CloudCoverPercentage: float = 0.0
    QualityRating: str = "NIIRS_5"
    GSD_m: float = 1.0
    CollectionStartTime: str = ""
    CollectionEndTime: str = ""
    CollectionGeometry: CollectionGeometry = None
    GroundCoverBounds: GroundCoverBounds = None

    def __post_init__(self):
        if self.header is None:
            self.header = Header(SenderID="EOIR_SENSOR_01")
        if self.CollectionGeometry is None:
            self.CollectionGeometry = CollectionGeometry()
        if self.GroundCoverBounds is None:
            self.GroundCoverBounds = GroundCoverBounds()

    def to_xml(self) -> str:
        root = self._build_root("ImageMetadataRecord")
        self.header.to_xml(root)
        _sub(root, "SensorID", self.SensorID)
        _sub(root, "FileLocation", self.FileLocation)
        _sub(root, "FileFormat", self.FileFormat)
        _sub(root, "CloudCoverPercentage", str(self.CloudCoverPercentage))
        _sub(root, "QualityRating", self.QualityRating)
        _sub(root, "GSD_m", str(self.GSD_m))
        _sub(root, "CollectionStartTime", self.CollectionStartTime)
        _sub(root, "CollectionEndTime", self.CollectionEndTime)
        self.CollectionGeometry.to_xml(root)
        self.GroundCoverBounds.to_xml(root)
        return self._serialize(root)

    @classmethod
    def from_xml(cls, xml_string: str):
        root = cls._parse_root(xml_string)
        ns = UCI_NS
        hdr = Header.from_xml(root.find(f"{{{ns}}}Header"))
        cg_el = root.find(f"{{{ns}}}CollectionGeometry")
        gcb_el = root.find(f"{{{ns}}}GroundCoverBounds")
        return cls(
            header=hdr,
            SensorID=_get_text(root, "SensorID", ns),
            FileLocation=_get_text(root, "FileLocation", ns),
            FileFormat=_get_text(root, "FileFormat", ns) or "NITF_2.1",
            CloudCoverPercentage=_get_float(root, "CloudCoverPercentage", ns),
            QualityRating=_get_text(root, "QualityRating", ns),
            GSD_m=_get_float(root, "GSD_m", ns),
            CollectionStartTime=_get_text(root, "CollectionStartTime", ns),
            CollectionEndTime=_get_text(root, "CollectionEndTime", ns),
            CollectionGeometry=CollectionGeometry.from_xml(cg_el) if cg_el is not None else CollectionGeometry(),
            GroundCoverBounds=GroundCoverBounds.from_xml(gcb_el) if gcb_el is not None else GroundCoverBounds(),
        )


# ============================================================
# ATR Target Detection Report
# ============================================================

@dataclass
class BoundingBox:
    PixelX: int = 0
    PixelY: int = 0
    WidthPx: int = 0
    HeightPx: int = 0

    def to_xml(self, parent):
        bb = _sub(parent, "BoundingBox")
        _sub(bb, "PixelX", str(self.PixelX))
        _sub(bb, "PixelY", str(self.PixelY))
        _sub(bb, "WidthPx", str(self.WidthPx))
        _sub(bb, "HeightPx", str(self.HeightPx))
        return bb

    @classmethod
    def from_xml(cls, element):
        ns = UCI_NS
        return cls(
            PixelX=_get_int(element, "PixelX", ns) or 0,
            PixelY=_get_int(element, "PixelY", ns) or 0,
            WidthPx=_get_int(element, "WidthPx", ns) or 0,
            HeightPx=_get_int(element, "HeightPx", ns) or 0,
        )


@dataclass
class Detection:
    TargetClass: str = "UNKNOWN"
    Confidence_pct: float = 50.0
    Latitude_deg: float = 0.0
    Longitude_deg: float = 0.0
    BoundingBox: BoundingBox = None

    def __post_init__(self):
        if self.BoundingBox is None:
            self.BoundingBox = BoundingBox()

    def to_xml(self, parent):
        det = _sub(parent, "Detection")
        _sub(det, "TargetClass", self.TargetClass)
        _sub(det, "Confidence_pct", str(self.Confidence_pct))
        _sub(det, "Latitude_deg", str(self.Latitude_deg))
        _sub(det, "Longitude_deg", str(self.Longitude_deg))
        self.BoundingBox.to_xml(det)
        return det

    @classmethod
    def from_xml(cls, element):
        ns = UCI_NS
        bb_el = element.find(f"{{{ns}}}BoundingBox")
        return cls(
            TargetClass=_get_text(element, "TargetClass", ns),
            Confidence_pct=_get_float(element, "Confidence_pct", ns),
            Latitude_deg=_get_float(element, "Latitude_deg", ns),
            Longitude_deg=_get_float(element, "Longitude_deg", ns),
            BoundingBox=BoundingBox.from_xml(bb_el) if bb_el is not None else BoundingBox(),
        )


@dataclass
class TargetDetectionReport(UCIMessage):
    message_type = "TargetDetectionReport"
    header: Header = None
    ReferenceImageID: str = ""
    DetectionCount: int = 0
    Detections: List[Detection] = field(default_factory=list)

    def __post_init__(self):
        if self.header is None:
            self.header = Header(SenderID="ATR_01")

    def to_xml(self) -> str:
        root = self._build_root("TargetDetectionReport")
        self.header.to_xml(root)
        _sub(root, "ReferenceImageID", self.ReferenceImageID)
        _sub(root, "DetectionCount", str(self.DetectionCount))
        dets_el = _sub(root, "Detections")
        for det in self.Detections:
            det.to_xml(dets_el)
        return self._serialize(root)

    @classmethod
    def from_xml(cls, xml_string: str):
        root = cls._parse_root(xml_string)
        ns = UCI_NS
        hdr = Header.from_xml(root.find(f"{{{ns}}}Header"))
        dets_el = root.find(f"{{{ns}}}Detections")
        detections = []
        if dets_el is not None:
            for det_el in dets_el.findall(f"{{{ns}}}Detection"):
                detections.append(Detection.from_xml(det_el))
        return cls(
            header=hdr,
            ReferenceImageID=_get_text(root, "ReferenceImageID", ns),
            DetectionCount=_get_int(root, "DetectionCount", ns),
            Detections=detections,
        )


# ============================================================
# Message type registry for routing
# ============================================================

MESSAGE_TYPES = {
    "ImageryCapabilityCommand": ImageryCapabilityCommand,
    "SlewCommand": SlewCommand,
    "SensorActivateCommand": SensorActivateCommand,
    "StatusRequest": StatusRequest,
    "PowerModeCommand": PowerModeCommand,
    "SensorCalibrationCommand": SensorCalibrationCommand,
    "MissionPlan": MissionPlan,
    "ImageryReport": ImageryReport,
    "SensorStatusReport": SensorStatusReport,
    "AttitudeStatusReport": AttitudeStatusReport,
    "PowerStatusReport": PowerStatusReport,
    "ThermalStatusReport": ThermalStatusReport,
    "FaultReport": FaultReport,
    "NavigationStatusReport": NavigationStatusReport,
    "PlanStatusReport": PlanStatusReport,
    "HeartbeatMessage": HeartbeatMessage,
    "ImageMetadataRecord": ImageMetadataRecord,
    "TargetDetectionReport": TargetDetectionReport,
}


def parse_message(xml_string: str) -> UCIMessage:
    """Parse an XML string and return the appropriate UCIMessage subclass."""
    root = etree.fromstring(xml_string.encode('utf-8') if isinstance(xml_string, str) else xml_string)
    # Extract local name from namespaced tag
    tag = root.tag
    if '}' in tag:
        tag = tag.split('}', 1)[1]
    msg_cls = MESSAGE_TYPES.get(tag)
    if msg_cls is None:
        raise ValueError(f"Unknown UCI message type: {tag}")
    return msg_cls.from_xml(xml_string)
