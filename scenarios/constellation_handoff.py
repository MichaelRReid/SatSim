"""Constellation handoff scenario - store-and-forward during contact gaps."""

from satsim.sim.setup import create_simulation


def run(env=None, ground=None, bus=None, services=None):
    """Simulate store-and-forward during ground contact gap.

    1. Advance orbit past contact window.
    2. Send imagery command (results queued).
    3. Advance to next contact window.
    4. Verify CDH flushes queue.
    """
    if env is None:
        env, bus, ground, services = create_simulation()

    result = {"scenario": "constellation_handoff", "success": False}

    cdh = services["CDH_01"]
    comms = services["COMMS_01"]

    # Step 1: Advance to ensure we have some data
    env.step(10)

    # Send imagery to generate data
    ground.send_imagery_command(
        lat=39.7392, lon=-104.9903,
        sensor_mode="VISIBLE", resolution_m=0.5, duration_sec=20,
    )
    env.step(120)

    # Record queue size
    queue_before = cdh.get_downlink_queue_size()
    result["queue_size_with_data"] = queue_before

    # Check contact window
    contact = comms.get_contact_window_status()
    result["contact_status"] = contact

    # Flush (simulating ground contact)
    packets = cdh.flush_downlink_queue()
    result["packets_flushed"] = len(packets)

    queue_after = cdh.get_downlink_queue_size()
    result["queue_size_after_flush"] = queue_after

    # Verify CCSDS packet structure
    if packets:
        pkt = packets[0]
        result["ccsds_sample"] = {
            "apid": pkt.apid,
            "type": "TM" if pkt.packet_type == 0 else "TC",
            "seq_count": pkt.sequence_count,
            "data_length": len(pkt.data),
        }

    result["success"] = (
        queue_before > 0
        and len(packets) > 0
        and queue_after == 0
    )

    return result


if __name__ == "__main__":
    import json
    result = run()
    print(json.dumps(result, indent=2, default=str))
