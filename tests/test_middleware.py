"""Tests for the OMS middleware bus."""

import json
import os
import tempfile
import pytest
from satsim.bus.middleware import OMSBus, BaseService
from satsim.uci.messages import (
    Header, StatusRequest, FaultReport, HeartbeatMessage,
    PowerModeCommand, UCIMessage,
)
from satsim.sim.clock import SimulationClock, set_global_clock


@pytest.fixture(autouse=True)
def setup_clock():
    clock = SimulationClock()
    set_global_clock(clock)
    yield
    set_global_clock(None)


@pytest.fixture(autouse=True)
def reset_bus():
    OMSBus.reset()
    yield
    OMSBus.reset()


class MockService(BaseService):
    def __init__(self, service_id):
        super().__init__(service_id)
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


class TestMiddleware:

    def test_service_registration(self):
        """A service can register on the bus."""
        bus = OMSBus()
        svc = MockService("SVC_01")
        bus.register_service("SVC_01", svc)
        services = bus.get_registered_services()
        assert "SVC_01" in services

    def test_message_routing_to_subscribers(self):
        """Published message is received by subscribed services."""
        bus = OMSBus()
        sub_svc = MockService("SUB_01")
        unsub_svc = MockService("UNSUB_01")

        bus.register_service("SUB_01", sub_svc)
        bus.register_service("UNSUB_01", unsub_svc)

        sub_svc.mwa.subscribe(StatusRequest)
        sub_svc.start()
        unsub_svc.start()

        req = StatusRequest(
            header=Header(SenderID="EXTERNAL"),
            TargetServiceID="SUB_01",
        )
        bus.publish(req)

        assert len(sub_svc.received) == 1
        assert len(unsub_svc.received) == 0

    def test_invalid_message_rejected_with_fault(self):
        """Invalid message (fails XSD) is rejected and FaultReport published."""
        bus = OMSBus()
        fault_catcher = MockService("FAULT_CATCHER")
        bus.register_service("FAULT_CATCHER", fault_catcher)
        fault_catcher.mwa.subscribe(FaultReport)
        fault_catcher.start()

        # Attempt to publish something that will fail validation
        # by creating an object with bad enum value
        # The to_xml() call in publish will raise UCIValidationError
        # which should produce a FaultReport
        class BadMessage(UCIMessage):
            message_type = "StatusRequest"
            def __init__(self):
                self.header = Header(SenderID="BAD")
            def to_xml(self):
                from satsim.uci.validator import UCIValidationError
                raise UCIValidationError(["test error"])

        bus.publish(BadMessage())
        assert len(fault_catcher.received) > 0
        assert isinstance(fault_catcher.received[0], FaultReport)

    def test_replay_log(self):
        """replay_log replays messages in correct order."""
        bus = OMSBus()

        # Create a temp log file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            entries = [
                {"MessageID": "aaa", "MessageType": "StatusRequest", "SenderID": "A", "Timestamp": "t1", "Destinations": []},
                {"MessageID": "bbb", "MessageType": "FaultReport", "SenderID": "B", "Timestamp": "t2", "Destinations": []},
            ]
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
            tmp_path = f.name

        try:
            bus.clear_log()
            bus.replay_log(tmp_path)
            log = bus.get_message_log()
            assert len(log) == 2
            assert log[0]["MessageID"] == "aaa"
            assert log[1]["MessageID"] == "bbb"
        finally:
            os.unlink(tmp_path)
