"""Command and Data Handling (CDH) service."""

import struct
from collections import deque
from satsim.bus.middleware import BaseService
from satsim.uci.messages import (
    Header, FaultReport, HeartbeatMessage, UCIMessage,
    StatusRequest, PowerModeCommand,
)


class CCSDSPacket:
    """Simplified CCSDS Space Packet structure."""

    def __init__(self, apid: int, packet_type: int = 0, data: bytes = b""):
        self.version = 0  # 3 bits
        self.packet_type = packet_type  # 1 bit: 0=TM, 1=TC
        self.sec_hdr_flag = 0  # 1 bit
        self.apid = apid  # 11 bits
        self.sequence_flags = 3  # 2 bits (standalone)
        self.sequence_count = 0  # 14 bits
        self.data = data

    @property
    def data_length(self) -> int:
        return len(self.data) - 1 if len(self.data) > 0 else 0

    def to_bytes(self) -> bytes:
        # Primary header: 6 bytes
        word1 = (self.version << 13) | (self.packet_type << 12) | (self.sec_hdr_flag << 11) | self.apid
        word2 = (self.sequence_flags << 14) | (self.sequence_count & 0x3FFF)
        word3 = self.data_length
        header = struct.pack(">HHH", word1, word2, word3)
        return header + self.data

    def __repr__(self):
        return (f"CCSDSPacket(APID={self.apid}, Type={'TC' if self.packet_type else 'TM'}, "
                f"SeqCount={self.sequence_count}, DataLen={len(self.data)})")


class CDHService(BaseService):
    """Command and Data Handling service.

    Acts as relay and logger for all bus messages.
    Wraps telemetry in CCSDS packets for ground downlink.
    """

    def __init__(self, service_id: str = "CDH_01", env=None):
        super().__init__(service_id, env)
        self._message_store = deque(maxlen=1000)
        self._downlink_queue = deque()
        self._sequence_counters = {}  # sender_id -> last sequence count
        self._ccsds_seq_count = 0
        self._apid_map = {}  # service_id -> APID
        self._next_apid = 100
        self._power_state = "ON"

    def start(self):
        super().start()
        if self.mwa:
            # CDH subscribes to all message types
            from satsim.uci.messages import MESSAGE_TYPES
            for msg_cls in MESSAGE_TYPES.values():
                self.mwa.subscribe(msg_cls)
        if self.env:
            self.env.clock.register_timer(self.send_heartbeat, 30)

    def stop(self):
        super().stop()

    def handle_message(self, message: UCIMessage):
        if self._power_state == "OFF":
            return

        # Store message
        self._message_store.append(message)

        # Queue for downlink
        self._downlink_queue.append(message)

        # Handle power commands directed at us
        if isinstance(message, PowerModeCommand):
            if message.TargetServiceID == self.service_id:
                self._power_state = message.PowerState

        if isinstance(message, StatusRequest):
            if message.TargetServiceID == self.service_id:
                self._publish(self.get_status())

    def get_stored_messages(self, count: int = 10, message_type: str = None) -> list:
        """Query stored messages from the onboard store."""
        msgs = list(self._message_store)
        if message_type:
            msgs = [m for m in msgs if getattr(m, 'message_type', '') == message_type]
        return msgs[-count:]

    def wrap_as_ccsds(self, message: UCIMessage) -> CCSDSPacket:
        """Wrap a UCI message in a CCSDS Space Packet."""
        sender = message.header.SenderID if hasattr(message, 'header') and message.header else "UNKNOWN"
        if sender not in self._apid_map:
            self._apid_map[sender] = self._next_apid
            self._next_apid += 1

        apid = self._apid_map[sender]
        try:
            data = message.to_xml().encode('utf-8')
        except Exception:
            data = b"<error/>"

        pkt = CCSDSPacket(apid=apid, packet_type=0, data=data)
        pkt.sequence_count = self._ccsds_seq_count
        self._ccsds_seq_count = (self._ccsds_seq_count + 1) & 0x3FFF
        return pkt

    def flush_downlink_queue(self) -> list:
        """Flush the downlink queue, returning CCSDS packets."""
        packets = []
        while self._downlink_queue:
            msg = self._downlink_queue.popleft()
            pkt = self.wrap_as_ccsds(msg)
            packets.append(pkt)
        return packets

    def get_downlink_queue_size(self) -> int:
        return len(self._downlink_queue)

    def get_status(self) -> HeartbeatMessage:
        return HeartbeatMessage(
            header=Header(SenderID=self.service_id),
            ServiceID=self.service_id,
            ServiceState="NOMINAL" if self._power_state != "OFF" else "FAULT",
            UptimeSeconds=int(self.env.clock.met() - self._start_met) if self.env else 0,
        )
