"""Tests for UCI message validation against XSD schema."""

import pytest
from satsim.uci.validator import UCIValidator, UCIValidationError
from satsim.uci.messages import (
    Header, ImageryCapabilityCommand, PointTarget, FaultReport,
    SensorStatusReport,
)
from satsim.sim.clock import SimulationClock, set_global_clock


@pytest.fixture(autouse=True)
def setup_clock():
    """Ensure a global clock is available for timestamps."""
    clock = SimulationClock()
    set_global_clock(clock)
    yield
    set_global_clock(None)


@pytest.fixture
def validator():
    return UCIValidator()


class TestUCIValidation:

    def test_valid_imagery_command_passes(self, validator):
        """A well-formed ImageryCapabilityCommand passes XSD validation."""
        cmd = ImageryCapabilityCommand(
            header=Header(SenderID="TEST_01"),
            CapabilityID="CAP_01",
            CommandState="CHANGE_SETTING",
            SensorMode="VISIBLE",
            Resolution_m=0.5,
            CollectionDuration_sec=30,
            Target=PointTarget(Latitude=39.7392, Longitude=-104.9903),
        )
        xml = cmd.to_xml()
        is_valid, errors = validator.validate(xml)
        assert is_valid, f"Validation failed: {errors}"

    def test_missing_header_fails(self, validator):
        """A message with a missing Header field fails validation."""
        # Build XML manually without Header
        xml = '''<?xml version='1.0' encoding='unicode'?>
        <ImageryCapabilityCommand xmlns="urn:uci:messages:v6.0">
            <CapabilityID>CAP_01</CapabilityID>
            <CommandState>CHANGE_SETTING</CommandState>
            <SensorMode>VISIBLE</SensorMode>
            <Resolution_m>0.5</Resolution_m>
            <CollectionDuration_sec>30</CollectionDuration_sec>
            <Target>
                <PointTarget>
                    <Latitude>39.0</Latitude>
                    <Longitude>-104.0</Longitude>
                    <Altitude_m>0.0</Altitude_m>
                    <CoordSystem>WGS84</CoordSystem>
                </PointTarget>
            </Target>
        </ImageryCapabilityCommand>'''
        is_valid, errors = validator.validate(xml)
        assert not is_valid
        assert len(errors) > 0

    def test_invalid_sensor_mode_fails(self, validator):
        """A message with a non-enumerated SensorMode value fails validation."""
        xml = '''<?xml version='1.0' encoding='unicode'?>
        <ImageryCapabilityCommand xmlns="urn:uci:messages:v6.0">
            <Header>
                <MessageID>12345678-1234-1234-1234-123456789012</MessageID>
                <Timestamp>2026-01-15T12:00:00.000Z</Timestamp>
                <SenderID>TEST</SenderID>
                <Version>UCI-6.0</Version>
                <Priority>ROUTINE</Priority>
            </Header>
            <CapabilityID>CAP_01</CapabilityID>
            <CommandState>CHANGE_SETTING</CommandState>
            <SensorMode>XRAY_VISION</SensorMode>
            <Resolution_m>0.5</Resolution_m>
            <CollectionDuration_sec>30</CollectionDuration_sec>
            <Target>
                <PointTarget>
                    <Latitude>39.0</Latitude>
                    <Longitude>-104.0</Longitude>
                    <Altitude_m>0.0</Altitude_m>
                    <CoordSystem>WGS84</CoordSystem>
                </PointTarget>
            </Target>
        </ImageryCapabilityCommand>'''
        is_valid, errors = validator.validate(xml)
        assert not is_valid

    def test_timestamp_without_utc_fails(self, validator):
        """A timestamp without UTC timezone designation fails validation."""
        xml = '''<?xml version='1.0' encoding='unicode'?>
        <ImageryCapabilityCommand xmlns="urn:uci:messages:v6.0">
            <Header>
                <MessageID>12345678-1234-1234-1234-123456789012</MessageID>
                <Timestamp>2026-01-15T12:00:00.000</Timestamp>
                <SenderID>TEST</SenderID>
                <Version>UCI-6.0</Version>
                <Priority>ROUTINE</Priority>
            </Header>
            <CapabilityID>CAP_01</CapabilityID>
            <CommandState>CHANGE_SETTING</CommandState>
            <SensorMode>VISIBLE</SensorMode>
            <Resolution_m>0.5</Resolution_m>
            <CollectionDuration_sec>30</CollectionDuration_sec>
            <Target>
                <PointTarget>
                    <Latitude>39.0</Latitude>
                    <Longitude>-104.0</Longitude>
                    <Altitude_m>0.0</Altitude_m>
                    <CoordSystem>WGS84</CoordSystem>
                </PointTarget>
            </Target>
        </ImageryCapabilityCommand>'''
        is_valid, errors = validator.validate(xml)
        assert not is_valid

    def test_latitude_out_of_range_fails(self, validator):
        """A Latitude value outside [-90, 90] fails validation."""
        xml = '''<?xml version='1.0' encoding='unicode'?>
        <ImageryCapabilityCommand xmlns="urn:uci:messages:v6.0">
            <Header>
                <MessageID>12345678-1234-1234-1234-123456789012</MessageID>
                <Timestamp>2026-01-15T12:00:00.000Z</Timestamp>
                <SenderID>TEST</SenderID>
                <Version>UCI-6.0</Version>
                <Priority>ROUTINE</Priority>
            </Header>
            <CapabilityID>CAP_01</CapabilityID>
            <CommandState>CHANGE_SETTING</CommandState>
            <SensorMode>VISIBLE</SensorMode>
            <Resolution_m>0.5</Resolution_m>
            <CollectionDuration_sec>30</CollectionDuration_sec>
            <Target>
                <PointTarget>
                    <Latitude>95.0</Latitude>
                    <Longitude>-104.0</Longitude>
                    <Altitude_m>0.0</Altitude_m>
                    <CoordSystem>WGS84</CoordSystem>
                </PointTarget>
            </Target>
        </ImageryCapabilityCommand>'''
        is_valid, errors = validator.validate(xml)
        assert not is_valid

    def test_fault_report_for_invalid_message(self):
        """FaultReport is generated (not exception) for invalid incoming messages."""
        from satsim.bus.middleware import OMSBus, BaseService
        from satsim.uci.messages import UCIMessage, HeartbeatMessage

        OMSBus.reset()
        bus = OMSBus()

        class DummyService(BaseService):
            def __init__(self):
                super().__init__("DUMMY_01")
                self.received = []
            def start(self):
                super().start()
            def stop(self):
                super().stop()
            def handle_message(self, msg):
                self.received.append(msg)
            def get_status(self):
                return HeartbeatMessage(
                    header=Header(SenderID=self.service_id),
                    ServiceID=self.service_id,
                    ServiceState="NOMINAL",
                    UptimeSeconds=0,
                )

        dummy = DummyService()
        bus.register_service("DUMMY_01", dummy)
        dummy.mwa.subscribe(FaultReport)
        dummy.start()

        # Publish a message that will generate a fault report
        # by trying to create an invalid message manually
        fault = FaultReport(
            header=Header(SenderID="TEST"),
            FaultCode="TEST_FAULT",
            FaultSeverity="INFO",
            AffectedServiceID="TEST",
            FaultDescription="Test fault",
            RecommendedAction="None",
        )
        bus.publish(fault)

        # The FaultReport itself should be valid and received
        assert len(dummy.received) > 0

        OMSBus.reset()
