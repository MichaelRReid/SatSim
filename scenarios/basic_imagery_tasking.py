"""Basic imagery tasking scenario targeting Denver, CO."""

from satsim.sim.setup import create_simulation


def run(env=None, ground=None, bus=None, services=None):
    """Execute basic imagery tasking scenario.

    Sends a single ImageryCapabilityCommand targeting Denver, CO.
    Mode: INFRARED_LONG_WAVE, Resolution: 1.0m, Duration: 45 sec.
    """
    if env is None:
        env, bus, ground, services = create_simulation()

    result = {"scenario": "basic_imagery_tasking", "success": False}

    # Send imagery command
    cmd = ground.send_imagery_command(
        lat=39.7392, lon=-104.9903, alt=0.0,
        sensor_mode="INFRARED_LONG_WAVE",
        resolution_m=1.0,
        duration_sec=45,
        priority="ROUTINE",
    )

    # Allow time for the full flow
    env.step(120)

    # Check results
    bus_log = bus.get_message_log()
    message_types = [e["MessageType"] for e in bus_log]

    result["message_sequence"] = message_types
    result["total_messages"] = len(bus_log)

    # Check for ImageryReport
    imagery_reports = [e for e in bus_log if e["MessageType"] == "ImageryReport"]
    if imagery_reports:
        result["imagery_report_found"] = True
        result["success"] = True
    else:
        result["imagery_report_found"] = False

    # Check for TargetDetectionReport
    atr_reports = [e for e in bus_log if e["MessageType"] == "TargetDetectionReport"]
    result["atr_detections_found"] = len(atr_reports) > 0

    # Get mission log
    mission_mgr = services["MISSION_MGR"]
    result["mission_log"] = mission_mgr.get_mission_log()

    return result


if __name__ == "__main__":
    import json
    result = run()
    print(json.dumps(result, indent=2, default=str))
