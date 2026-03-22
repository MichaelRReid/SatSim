"""OMS MiddleWare Adapter (MWA) and central message bus."""

import json
import logging
import os
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime, timezone
from lxml import etree

from satsim.uci.validator import UCIValidator, UCIValidationError
from satsim.uci.messages import (
    UCIMessage, FaultReport, Header, HeartbeatMessage, PowerModeCommand,
    UCI_NS, MESSAGE_TYPES, parse_message,
)

logger = logging.getLogger("satsim.bus")


class BaseService(ABC):
    """Abstract base class for all OMS bus services."""

    def __init__(self, service_id: str, env=None):
        self.service_id = service_id
        self.env = env
        self.mwa = None  # Set when registered on bus
        self._running = False
        self._start_met = 0.0

    @abstractmethod
    def start(self):
        """Start the service."""
        self._running = True
        if self.env:
            self._start_met = self.env.clock.met()

    @abstractmethod
    def stop(self):
        """Stop the service."""
        self._running = False

    @abstractmethod
    def handle_message(self, message: UCIMessage):
        """Handle an incoming UCI message."""
        pass

    @abstractmethod
    def get_status(self) -> UCIMessage:
        """Return a status report message for this service."""
        pass

    def send_heartbeat(self):
        """Publish a heartbeat message."""
        if self.env:
            uptime = int(self.env.clock.met() - self._start_met)
        else:
            uptime = 0
        hb = HeartbeatMessage(
            header=Header(SenderID=self.service_id),
            ServiceID=self.service_id,
            ServiceState="NOMINAL" if self._running else "FAULT",
            UptimeSeconds=uptime,
        )
        if self.mwa:
            self.mwa.send(hb)

    def _publish(self, message: UCIMessage):
        """Convenience method to publish via MWA."""
        if self.mwa:
            self.mwa.send(message)


class MiddleWareAdapter:
    """Per-service middleware adapter for UCI message validation and routing."""

    def __init__(self, service: BaseService, bus: 'OMSBus'):
        self.service = service
        self.bus = bus
        self._subscriptions = set()
        self._validator = UCIValidator()

    def send(self, message: UCIMessage):
        """Validate and publish a message to the bus."""
        try:
            xml_str = message.to_xml()
        except UCIValidationError:
            # Message failed validation during to_xml
            fault = FaultReport(
                header=Header(SenderID="MWA"),
                FaultCode="VALIDATION_ERROR",
                FaultSeverity="WARNING",
                AffectedServiceID=self.service.service_id,
                FaultDescription="Outgoing message failed XSD validation",
                RecommendedAction="Check message field values",
            )
            self.bus._route_message(fault, fault.to_xml())
            return
        self.bus._route_message(message, xml_str)

    def receive(self, message: UCIMessage, xml_str: str):
        """Validate incoming message and pass to service handler."""
        try:
            is_valid, errors = self._validator.validate(xml_str)
            if not is_valid:
                fault = FaultReport(
                    header=Header(SenderID="MWA"),
                    FaultCode="INCOMING_VALIDATION_ERROR",
                    FaultSeverity="WARNING",
                    AffectedServiceID=self.service.service_id,
                    FaultDescription=f"Incoming message failed validation: {'; '.join(errors[:3])}",
                    RecommendedAction="Check sender message format",
                )
                self.bus._route_message(fault, fault.to_xml())
                return
        except Exception:
            pass
        self.service.handle_message(message)

    def subscribe(self, message_class: type):
        """Subscribe this service to a message type."""
        self._subscriptions.add(message_class)
        self.bus._add_subscription(self.service.service_id, message_class)

    def get_subscriptions(self) -> set:
        """Return set of subscribed message types."""
        return self._subscriptions


class OMSBus:
    """Singleton OMS message bus.

    Routes validated UCI messages between registered services.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._services = {}  # service_id -> BaseService
        self._subscriptions = defaultdict(set)  # message_type_name -> set of service_ids
        self._validator = UCIValidator()
        self._message_log = []
        self._log_file = None
        self._routing_depth = 0
        self._max_routing_depth = 20

    @classmethod
    def reset(cls):
        """Reset the singleton for testing."""
        cls._instance = None

    def register_service(self, service_id: str, service: BaseService):
        """Register a service on the bus."""
        self._services[service_id] = service
        mwa = MiddleWareAdapter(service, self)
        service.mwa = mwa
        return mwa

    def subscribe(self, service_id: str, message_class: type):
        """Subscribe a service to a message type."""
        type_name = getattr(message_class, 'message_type', message_class.__name__)
        self._subscriptions[type_name].add(service_id)

    def _add_subscription(self, service_id: str, message_class: type):
        """Internal: add subscription mapping."""
        type_name = getattr(message_class, 'message_type', message_class.__name__)
        self._subscriptions[type_name].add(service_id)

    def publish(self, message: UCIMessage):
        """Validate and route a message. Called externally (e.g., ground station)."""
        try:
            xml_str = message.to_xml()
        except UCIValidationError as e:
            fault = FaultReport(
                header=Header(SenderID="OMS_BUS"),
                FaultCode="VALIDATION_ERROR",
                FaultSeverity="WARNING",
                AffectedServiceID=getattr(message.header, 'SenderID', 'UNKNOWN'),
                FaultDescription=f"Message failed XSD validation: {str(e)[:200]}",
                RecommendedAction="Fix message format",
            )
            self._route_message(fault, fault.to_xml())
            return
        self._route_message(message, xml_str)

    def _route_message(self, message: UCIMessage, xml_str: str):
        """Route a validated message to subscribed services."""
        self._routing_depth += 1
        if self._routing_depth > self._max_routing_depth:
            self._routing_depth -= 1
            return

        try:
            msg_type = getattr(message, 'message_type', type(message).__name__)
            sender_id = message.header.SenderID if hasattr(message, 'header') and message.header else "UNKNOWN"
            timestamp = message.header.Timestamp if hasattr(message, 'header') and message.header else ""
            message_id = message.header.MessageID if hasattr(message, 'header') and message.header else ""

            # Find subscribers
            subscriber_ids = self._subscriptions.get(msg_type, set())
            destinations = [sid for sid in subscriber_ids if sid != sender_id]

            # Log
            log_entry = {
                "MessageID": message_id,
                "MessageType": msg_type,
                "SenderID": sender_id,
                "Timestamp": timestamp,
                "Destinations": destinations,
            }
            self._message_log.append(log_entry)

            if self._log_file:
                try:
                    with open(self._log_file, 'a') as f:
                        f.write(json.dumps(log_entry) + "\n")
                except Exception:
                    pass

            # Route to subscribers
            for sid in destinations:
                service = self._services.get(sid)
                if service and service.mwa:
                    service.mwa.receive(message, xml_str)
        finally:
            self._routing_depth -= 1

    def get_registered_services(self) -> dict:
        """Return dict of service_id to service state."""
        result = {}
        for sid, service in self._services.items():
            result[sid] = {
                "service_id": sid,
                "running": service._running,
                "type": type(service).__name__,
            }
        return result

    def get_message_log(self, last_n: int = None, message_type: str = None) -> list:
        """Return message log entries, optionally filtered."""
        log = self._message_log
        if message_type:
            log = [e for e in log if e["MessageType"] == message_type]
        if last_n:
            log = log[-last_n:]
        return log

    def set_log_file(self, path: str):
        """Set path for persistent JSON message log."""
        self._log_file = path

    def replay_log(self, log_file_path: str):
        """Replay a previously logged message sequence."""
        with open(log_file_path, 'r') as f:
            for line in f:
                entry = json.loads(line.strip())
                # Replay is informational - we log it
                self._message_log.append(entry)

    def clear_log(self):
        """Clear the in-memory message log."""
        self._message_log.clear()
