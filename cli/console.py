"""Interactive and non-interactive CLI for SatSim."""

import argparse
import cmd
import json
import sys

from rich.console import Console
from rich.table import Table

from satsim.sim.setup import create_simulation

console = Console()


class SatSimConsole(cmd.Cmd):
    """Interactive command console for the satellite simulation."""

    intro = (
        "\n[SatSim] Satellite Bus & EO/IR Payload UCI Simulation\n"
        "Type 'help' for available commands. Type 'quit' to exit.\n"
    )
    prompt = "satsim> "

    def __init__(self):
        super().__init__()
        self.env, self.bus, self.ground, self.services = create_simulation()
        console.print("[green]Simulation initialized. All services running.[/green]")

    def do_status(self, arg):
        """Display status of all registered services."""
        table = Table(title="Service Status")
        table.add_column("Service ID", style="cyan")
        table.add_column("Type")
        table.add_column("State")
        table.add_column("Details")

        for sid, service in self.services.items():
            state = "RUNNING" if service._running else "STOPPED"
            detail = ""

            # Get service-specific details
            if hasattr(service, 'operational_state'):
                detail = f"OpState: {service.operational_state}"
            elif hasattr(service, 'pointing_mode'):
                detail = f"Mode: {service.pointing_mode}, Err: {service.pointing_error:.4f}deg"
            elif hasattr(service, 'battery_soc'):
                detail = f"SOC: {service.battery_soc:.1f}%, Mode: {service.power_mode}"
            elif hasattr(service, 'focal_plane_temp') and hasattr(service, 'thermal_mode'):
                detail = f"FP: {service.focal_plane_temp:.1f}C, Mode: {service.thermal_mode}"
            elif hasattr(service, '_downlink_available'):
                detail = f"Downlink: {'YES' if service._downlink_available else 'NO'}"

            color = "green" if state == "RUNNING" else "red"
            if hasattr(service, 'operational_state') and service.operational_state == "FAULT":
                color = "red"
            elif hasattr(service, 'operational_state') and service.operational_state == "DEGRADED":
                color = "yellow"

            table.add_row(sid, type(service).__name__, f"[{color}]{state}[/{color}]", detail)

        console.print(table)

    def do_task(self, arg):
        """Send an imagery command. Usage: task <lat> <lon> [--mode MODE] [--res M] [--dur SEC] [--priority PRI]"""
        parts = arg.split()
        if len(parts) < 2:
            console.print("[red]Usage: task <lat> <lon> [--mode MODE] [--res M] [--dur SEC][/red]")
            return

        lat = float(parts[0])
        lon = float(parts[1])
        mode = "VISIBLE"
        res = 1.0
        dur = 30
        priority = "ROUTINE"

        i = 2
        while i < len(parts):
            if parts[i] == "--mode" and i + 1 < len(parts):
                mode = parts[i + 1]
                i += 2
            elif parts[i] == "--res" and i + 1 < len(parts):
                res = float(parts[i + 1])
                i += 2
            elif parts[i] == "--dur" and i + 1 < len(parts):
                dur = int(parts[i + 1])
                i += 2
            elif parts[i] == "--priority" and i + 1 < len(parts):
                priority = parts[i + 1]
                i += 2
            else:
                i += 1

        console.print(f"[cyan]Sending imagery command: lat={lat}, lon={lon}, mode={mode}, res={res}m, dur={dur}s[/cyan]")
        self.ground.send_imagery_command(lat, lon, 0.0, mode, res, dur, priority)
        self.env.step(dur + 60)

        # Show results
        log = self.bus.get_message_log(last_n=5)
        for entry in log:
            if entry["MessageType"] == "ImageryReport":
                console.print(f"[green]ImageryReport received![/green]")
            elif entry["MessageType"] == "TargetDetectionReport":
                console.print(f"[green]ATR TargetDetectionReport received![/green]")

    def do_plan(self, arg):
        """Plan commands. Usage: plan load <file> | plan status"""
        parts = arg.split()
        if not parts:
            console.print("[red]Usage: plan load <file> | plan status[/red]")
            return

        if parts[0] == "status":
            mgr = self.services["MISSION_MGR"]
            console.print(f"Plan State: {mgr._plan_state}")
            console.print(f"Current Step: {mgr._plan_step}")
            if mgr._current_plan:
                console.print(f"Total Steps: {len(mgr._current_plan.Steps)}")

        elif parts[0] == "load" and len(parts) > 1:
            scenario_name = parts[1]
            self._run_scenario(scenario_name)

    def do_service(self, arg):
        """Service commands. Usage: service status <id> | service fault <id> <code> | service power <id> <state> | service calibrate <id> <mode>"""
        parts = arg.split()
        if len(parts) < 2:
            console.print("[red]Usage: service status|fault|power|calibrate <id> [args][/red]")
            return

        subcmd = parts[0]
        sid = parts[1]

        if subcmd == "status":
            service = self.services.get(sid)
            if service:
                try:
                    status = service.get_status()
                    console.print(f"[cyan]{sid} Status:[/cyan]")
                    console.print(status.to_xml())
                except Exception as e:
                    console.print(f"[red]Error getting status: {e}[/red]")
            else:
                console.print(f"[red]Unknown service: {sid}[/red]")

        elif subcmd == "fault" and len(parts) > 2:
            fault_code = parts[2]
            service = self.services.get(sid)
            if service and hasattr(service, 'inject_fault'):
                service.inject_fault(fault_code)
                console.print(f"[yellow]Fault {fault_code} injected into {sid}[/yellow]")
            else:
                console.print(f"[red]Service {sid} does not support fault injection[/red]")

        elif subcmd == "power" and len(parts) > 2:
            state = parts[2]
            self.ground.send_power_command(sid, state)
            console.print(f"[cyan]PowerModeCommand sent: {sid} -> {state}[/cyan]")

        elif subcmd == "calibrate" and len(parts) > 2:
            cal_mode = parts[2]
            from satsim.uci.messages import SensorCalibrationCommand, Header
            cmd = SensorCalibrationCommand(
                header=Header(SenderID="GROUND_C2"),
                CapabilityID=sid,
                CalibrationMode=cal_mode,
            )
            self.bus.publish(cmd)
            self.env.step(65)
            console.print(f"[cyan]Calibration {cal_mode} sent to {sid}[/cyan]")

    def do_telemetry(self, arg):
        """Telemetry commands. Usage: telemetry dump"""
        if arg.strip() == "dump":
            packets = self.ground.request_telemetry_dump()
            table = Table(title="CCSDS Telemetry Packets")
            table.add_column("Seq")
            table.add_column("APID")
            table.add_column("Type")
            table.add_column("Data Len")
            for pkt in packets[:20]:
                table.add_row(
                    str(pkt.sequence_count),
                    str(pkt.apid),
                    "TM" if pkt.packet_type == 0 else "TC",
                    str(len(pkt.data)),
                )
            console.print(table)
            console.print(f"Total packets: {len(packets)}")

    def do_log(self, arg):
        """Log commands. Usage: log messages [--last N] [--type TYPE] | log mission"""
        parts = arg.split()
        if not parts:
            console.print("[red]Usage: log messages [--last N] [--type TYPE] | log mission[/red]")
            return

        if parts[0] == "messages":
            last_n = 20
            msg_type = None
            i = 1
            while i < len(parts):
                if parts[i] == "--last" and i + 1 < len(parts):
                    last_n = int(parts[i + 1])
                    i += 2
                elif parts[i] == "--type" and i + 1 < len(parts):
                    msg_type = parts[i + 1]
                    i += 2
                else:
                    i += 1

            entries = self.bus.get_message_log(last_n=last_n, message_type=msg_type)
            table = Table(title=f"Bus Messages (last {last_n})")
            table.add_column("MessageID", max_width=12)
            table.add_column("Type", style="cyan")
            table.add_column("Sender")
            table.add_column("Timestamp", max_width=24)
            table.add_column("Destinations")

            for entry in entries:
                table.add_row(
                    entry["MessageID"][:12] + "..." if len(entry.get("MessageID", "")) > 12 else entry.get("MessageID", ""),
                    entry["MessageType"],
                    entry["SenderID"],
                    entry.get("Timestamp", "")[:24],
                    ", ".join(entry.get("Destinations", [])),
                )
            console.print(table)

        elif parts[0] == "mission":
            mgr = self.services["MISSION_MGR"]
            log = mgr.get_mission_log()
            table = Table(title="Mission Log")
            table.add_column("Event", style="cyan")
            table.add_column("Timestamp")
            table.add_column("Details")
            for entry in log[-20:]:
                event = entry.pop("event", "")
                ts = entry.pop("timestamp", "")
                table.add_row(event, str(ts)[:24], json.dumps(entry, default=str)[:80])
                entry["event"] = event
                entry["timestamp"] = ts
            console.print(table)

    def do_orbit(self, arg):
        """Display current orbit state."""
        if arg.strip() == "info" or not arg.strip():
            lat, lon, alt = self.env.orbit.get_lat_lon_alt()
            x, y, z = self.env.orbit.get_position_ecef()
            eclipse = self.env.orbit.is_in_eclipse()
            period = self.env.orbit.orbital_period

            comms = self.services.get("COMMS_01")
            contact = comms.get_contact_window_status() if comms else {}

            table = Table(title="Orbit State")
            table.add_column("Parameter", style="cyan")
            table.add_column("Value")
            table.add_row("Latitude", f"{lat:.4f} deg")
            table.add_row("Longitude", f"{lon:.4f} deg")
            table.add_row("Altitude", f"{alt:.2f} km")
            table.add_row("ECEF X", f"{x:.0f} m")
            table.add_row("ECEF Y", f"{y:.0f} m")
            table.add_row("ECEF Z", f"{z:.0f} m")
            table.add_row("Eclipse", "[red]YES[/red]" if eclipse else "[green]NO[/green]")
            table.add_row("Orbital Period", f"{period:.1f} sec")
            table.add_row("MET", f"{self.env.clock.met():.1f} sec")
            table.add_row("Sim Time", str(self.env.clock.now()))
            if contact:
                table.add_row("Downlink", "[green]AVAILABLE[/green]" if contact.get("downlink_available") else "[red]UNAVAILABLE[/red]")
                table.add_row("Next Contact", f"{contact.get('next_contact_start_sec', 0):.0f} sec")

            console.print(table)

    def do_sim(self, arg):
        """Simulation commands. Usage: sim speed <factor> | sim advance <seconds>"""
        parts = arg.split()
        if not parts:
            console.print("[red]Usage: sim speed <factor> | sim advance <seconds>[/red]")
            return

        if parts[0] == "speed" and len(parts) > 1:
            factor = float(parts[1])
            self.env.clock.set_acceleration(factor)
            console.print(f"[cyan]Time acceleration set to {factor}x[/cyan]")

        elif parts[0] == "advance" and len(parts) > 1:
            seconds = float(parts[1])
            self.env.step(seconds)
            console.print(f"[cyan]Advanced {seconds} simulated seconds. MET: {self.env.clock.met():.1f}s[/cyan]")

    def do_scenario(self, arg):
        """Scenario commands. Usage: scenario list | scenario run <name>"""
        parts = arg.split()
        if not parts:
            console.print("[red]Usage: scenario list | scenario run <name>[/red]")
            return

        if parts[0] == "list":
            scenarios = [
                "basic_imagery_tasking",
                "sensor_fault_injection",
                "plan_execution",
                "constellation_handoff",
            ]
            table = Table(title="Available Scenarios")
            table.add_column("Name", style="cyan")
            for s in scenarios:
                table.add_row(s)
            console.print(table)

        elif parts[0] == "run" and len(parts) > 1:
            self._run_scenario(parts[1])

    def _run_scenario(self, name):
        """Run a named scenario."""
        scenario_map = {
            "basic_imagery_tasking": "scenarios.basic_imagery_tasking",
            "sensor_fault_injection": "scenarios.sensor_fault_injection",
            "plan_execution": "scenarios.plan_execution",
            "constellation_handoff": "scenarios.constellation_handoff",
        }
        mod_name = scenario_map.get(name)
        if not mod_name:
            console.print(f"[red]Unknown scenario: {name}[/red]")
            return

        import importlib
        mod = importlib.import_module(mod_name)

        # Re-create simulation for clean state
        self.env, self.bus, self.ground, self.services = create_simulation()
        console.print(f"[cyan]Running scenario: {name}...[/cyan]")

        result = mod.run(self.env, self.ground, self.bus, self.services)
        console.print(f"[green]Scenario complete. Success: {result.get('success', False)}[/green]")
        console.print(json.dumps(result, indent=2, default=str))

    def do_help(self, arg):
        """Show available commands."""
        if arg:
            super().do_help(arg)
            return

        table = Table(title="Available Commands")
        table.add_column("Command", style="cyan")
        table.add_column("Description")
        commands = [
            ("status", "Display all service states"),
            ("task <lat> <lon> [opts]", "Send imagery command (--mode, --res, --dur, --priority)"),
            ("plan load <file>", "Load and execute a scenario"),
            ("plan status", "Show plan execution state"),
            ("service status <id>", "Show service details"),
            ("service fault <id> <code>", "Inject fault"),
            ("service power <id> <state>", "Send power command"),
            ("service calibrate <id> <mode>", "Send calibration command"),
            ("telemetry dump", "Request CDH telemetry dump"),
            ("log messages [--last N] [--type T]", "Show bus message log"),
            ("log mission", "Show mission manager log"),
            ("orbit info", "Show orbit state"),
            ("sim speed <factor>", "Set time acceleration"),
            ("sim advance <seconds>", "Advance simulation time"),
            ("scenario list", "List available scenarios"),
            ("scenario run <name>", "Run a scenario"),
            ("quit / exit", "Exit simulation"),
        ]
        for cmd_name, desc in commands:
            table.add_row(cmd_name, desc)
        console.print(table)

    def do_quit(self, arg):
        """Exit the simulation."""
        console.print("[yellow]Shutting down simulation...[/yellow]")
        self.env.stop()
        return True

    def do_exit(self, arg):
        """Exit the simulation."""
        return self.do_quit(arg)

    def do_EOF(self, arg):
        """Handle Ctrl+D."""
        print()
        return self.do_quit(arg)


def main():
    """Entry point for CLI."""
    parser = argparse.ArgumentParser(description="SatSim - Satellite UCI Simulation")
    parser.add_argument("--task", action="store_true", help="Run a single imagery task")
    parser.add_argument("--lat", type=float, help="Target latitude")
    parser.add_argument("--lon", type=float, help="Target longitude")
    parser.add_argument("--mode", default="VISIBLE", help="Sensor mode")
    parser.add_argument("--res", type=float, default=1.0, help="Resolution in meters")
    parser.add_argument("--dur", type=int, default=30, help="Duration in seconds")
    parser.add_argument("--scenario", help="Run a named scenario")
    parser.add_argument("--run", help="Scenario name to run")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Check if any args were passed
    if len(sys.argv) > 1:
        args = parser.parse_args()

        if args.task and args.lat is not None and args.lon is not None:
            env, bus, ground, services = create_simulation()
            ground.send_imagery_command(
                args.lat, args.lon, 0.0, args.mode, args.res, args.dur,
            )
            env.step(args.dur + 60)
            log = bus.get_message_log()
            result = {
                "command": "task",
                "messages": log[-10:],
                "mission_log": services["MISSION_MGR"].get_mission_log(),
            }
            print(json.dumps(result, indent=2, default=str))
            return

        if args.scenario or args.run:
            name = args.scenario or args.run
            import importlib
            env, bus, ground, services = create_simulation()
            mod = importlib.import_module(f"scenarios.{name}")
            result = mod.run(env, ground, bus, services)
            print(json.dumps(result, indent=2, default=str))
            return

        if args.json:
            env, bus, ground, services = create_simulation()
            status = {}
            for sid, svc in services.items():
                status[sid] = {
                    "type": type(svc).__name__,
                    "running": svc._running,
                }
            print(json.dumps(status, indent=2))
            return

    # Interactive mode
    SatSimConsole().cmdloop()


if __name__ == "__main__":
    main()
