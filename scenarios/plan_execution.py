"""Plan execution scenario with 4 steps."""

from satsim.sim.setup import create_simulation
from satsim.uci.messages import (
    SensorCalibrationCommand, ImageryCapabilityCommand, StatusRequest,
    Header, PointTarget, PlanStep,
)


def run(env=None, ground=None, bus=None, services=None):
    """Execute a 4-step mission plan.

    Step 1: Calibrate sensor (DARK)
    Step 2: Image Denver, CO
    Step 3: Image Colorado Springs, CO
    Step 4: Request status from all services
    """
    if env is None:
        env, bus, ground, services = create_simulation()

    result = {"scenario": "plan_execution", "success": False}

    # Build command XMLs for each step
    cal_cmd = SensorCalibrationCommand(
        header=Header(SenderID="MISSION_MGR"),
        CapabilityID="EOIR_CAP_01",
        CalibrationMode="DARK",
    )

    img_cmd_1 = ImageryCapabilityCommand(
        header=Header(SenderID="MISSION_MGR"),
        CapabilityID="EOIR_CAP_01",
        CommandState="CHANGE_SETTING",
        SensorMode="VISIBLE",
        Resolution_m=0.3,
        CollectionDuration_sec=30,
        Target=PointTarget(Latitude=39.7392, Longitude=-104.9903),
    )

    img_cmd_2 = ImageryCapabilityCommand(
        header=Header(SenderID="MISSION_MGR"),
        CapabilityID="EOIR_CAP_01",
        CommandState="CHANGE_SETTING",
        SensorMode="VISIBLE",
        Resolution_m=0.3,
        CollectionDuration_sec=30,
        Target=PointTarget(Latitude=38.8339, Longitude=-104.8214),
    )

    status_cmd = StatusRequest(
        header=Header(SenderID="MISSION_MGR"),
        TargetServiceID="EOIR_SENSOR_01",
    )

    steps = [
        PlanStep(StepNumber=1, CommandRef=cal_cmd.to_xml(), ExecutionOffset_sec=0, ContinueOnFault=True),
        PlanStep(StepNumber=2, CommandRef=img_cmd_1.to_xml(), ExecutionOffset_sec=5, ContinueOnFault=True),
        PlanStep(StepNumber=3, CommandRef=img_cmd_2.to_xml(), ExecutionOffset_sec=5, ContinueOnFault=True),
        PlanStep(StepNumber=4, CommandRef=status_cmd.to_xml(), ExecutionOffset_sec=0, ContinueOnFault=True),
    ]

    plan = ground.send_mission_plan("Multi-Target Collection", steps)
    result["plan_id"] = plan.PlanID

    # Run the simulation for enough time
    env.step(600)

    # Check plan status
    mission_mgr = services["MISSION_MGR"]
    plan_state = mission_mgr._plan_state

    result["plan_state"] = plan_state
    result["completed_steps"] = mission_mgr._plan_step
    result["total_steps"] = len(steps)

    # Check PlanStatusReport messages
    plan_reports = [e for e in bus.get_message_log() if e["MessageType"] == "PlanStatusReport"]
    result["plan_status_reports"] = len(plan_reports)

    result["success"] = (plan_state == "COMPLETED" and mission_mgr._plan_step >= len(steps))
    result["mission_log"] = mission_mgr.get_mission_log()

    return result


if __name__ == "__main__":
    import json
    result = run()
    print(json.dumps(result, indent=2, default=str))
