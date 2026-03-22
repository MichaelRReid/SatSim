"""Sensor fault injection scenario."""

from satsim.sim.setup import create_simulation


def run(env=None, ground=None, bus=None, services=None):
    """Execute sensor fault injection scenario.

    1. Start a normal imagery task.
    2. Inject FOCAL_PLANE_OVERHEAT fault.
    3. Verify fault handling and recovery.
    4. Retry imagery command.
    """
    if env is None:
        env, bus, ground, services = create_simulation()

    result = {"scenario": "sensor_fault_injection", "success": False, "transitions": []}

    eoir = services["EOIR_SENSOR_01"]

    # Step 1: Start imagery task
    ground.send_imagery_command(
        lat=39.7392, lon=-104.9903,
        sensor_mode="VISIBLE", resolution_m=0.3, duration_sec=30,
    )
    env.step(10)

    result["transitions"].append({
        "step": "initial_command",
        "eoir_state": eoir.operational_state,
    })

    # Step 2: Inject fault
    eoir.inject_fault("FOCAL_PLANE_OVERHEAT")
    env.step(5)

    result["transitions"].append({
        "step": "fault_injected",
        "eoir_state": eoir.operational_state,
    })

    # Check FaultReport was published
    fault_reports = [e for e in bus.get_message_log() if e["MessageType"] == "FaultReport"]
    result["fault_report_published"] = len(fault_reports) > 0

    # Step 3: Verify calibration response
    env.step(5)

    cal_commands = [e for e in bus.get_message_log() if e["MessageType"] == "SensorCalibrationCommand"]
    result["calibration_commanded"] = len(cal_commands) > 0

    # Wait for calibration to complete
    env.step(70)

    result["transitions"].append({
        "step": "after_calibration",
        "eoir_state": eoir.operational_state,
    })

    # Step 4: Retry imagery
    bus.clear_log()
    ground.send_imagery_command(
        lat=39.7392, lon=-104.9903,
        sensor_mode="VISIBLE", resolution_m=0.3, duration_sec=30,
    )
    env.step(120)

    retry_reports = [e for e in bus.get_message_log() if e["MessageType"] == "ImageryReport"]
    result["retry_imagery_found"] = len(retry_reports) > 0

    result["transitions"].append({
        "step": "after_retry",
        "eoir_state": eoir.operational_state,
    })

    # Verify success
    result["success"] = (
        result["fault_report_published"]
        and result["calibration_commanded"]
        and eoir.operational_state in ("NOMINAL", "DEGRADED")
        and result["retry_imagery_found"]
    )

    return result


if __name__ == "__main__":
    import json
    result = run()
    print(json.dumps(result, indent=2, default=str))
