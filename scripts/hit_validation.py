import asyncio
import sys
import os
import termios
import tty
import argparse
import yaml
from datetime import datetime

# Simple INDI XML templates
GET_PROPS = '<getProperties version="1.7" />\n'


def load_config(config_path):
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    return {}


class HITValidation:
    """
    Hardware Interaction Test (HIT) for Celestron AUX Mount.
    Safety-first interactive validation routine.
    """

    def __init__(
        self, host="localhost", port=7624, device="Celestron AUX", config=None
    ):
        self.host = host
        self.port = port
        self.device = device
        self.config = config or {}
        self.reader = None
        self.writer = None
        self.abort_event = asyncio.Event()

    async def connect(self):
        print(f"Connecting to INDI server at {self.host}:{self.port}...")
        try:
            self.reader, self.writer = await asyncio.open_connection(
                self.host, self.port
            )
            if self.writer:
                self.writer.write(GET_PROPS.encode())
                await self.writer.drain()
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    async def send_prop(self, property_name, members):
        """Sends a newProperty or switch command."""
        if not self.writer:
            return

        if property_name == "CONNECTION":
            xml = f'<newSwitchVector device="{self.device}" name="CONNECTION">\n'
            for k, v in members.items():
                xml += f'  <oneSwitch name="{k}">{v}</oneSwitch>\n'
            xml += "</newSwitchVector>\n"
        elif property_name == "TELESCOPE_ABORT_MOTION":
            xml = f'<newSwitchVector device="{self.device}" name="TELESCOPE_ABORT_MOTION">\n'
            xml += f'  <oneSwitch name="ABORT">On</oneSwitch>\n'
            xml += "</newSwitchVector>\n"
        elif property_name == "TELESCOPE_MOTION_NS":
            xml = (
                f'<newSwitchVector device="{self.device}" name="TELESCOPE_MOTION_NS">\n'
            )
            for k, v in members.items():
                xml += f'  <oneSwitch name="{k}">{v}</oneSwitch>\n'
            xml += "</newSwitchVector>\n"
        elif property_name == "TELESCOPE_MOTION_WE":
            xml = (
                f'<newSwitchVector device="{self.device}" name="TELESCOPE_MOTION_WE">\n'
            )
            for k, v in members.items():
                xml += f'  <oneSwitch name="{k}">{v}</oneSwitch>\n'
            xml += "</newSwitchVector>\n"
        elif property_name == "SLEW_RATE":
            xml = f'<newNumberVector device="{self.device}" name="SLEW_RATE">\n'
            xml += f'  <oneNumber name="RATE">{members["RATE"]}</oneNumber>\n'
            xml += "</newNumberVector>\n"
        elif property_name == "TELESCOPE_ABSOLUTE_COORD":
            xml = f'<newNumberVector device="{self.device}" name="TELESCOPE_ABSOLUTE_COORD">\n'
            xml += f'  <oneNumber name="AZM_STEPS">{members["AZM_STEPS"]}</oneNumber>\n'
            xml += f'  <oneNumber name="ALT_STEPS">{members["ALT_STEPS"]}</oneNumber>\n'
            xml += "</newNumberVector>\n"
        else:
            print(f"Unknown property: {property_name}")
            return

        self.writer.write(xml.encode())
        await self.writer.drain()

    async def abort(self):
        print("\n!!! EMERGENCY STOP TRIGGERED !!!")
        await self.send_prop("TELESCOPE_ABORT_MOTION", {"ABORT": "On"})
        self.abort_event.set()

    async def monitor_abort(self):
        """Background task to watch for Space key."""
        while not self.abort_event.is_set():
            loop = asyncio.get_event_loop()
            key = await loop.run_in_executor(None, self._get_char_raw)
            if key == " " or key == "\x03":  # Space or Ctrl+C
                await self.abort()
                break

    async def confirm(self, message):
        """Waits for user Enter to proceed or Space to abort."""
        print(f"\n{message}")
        print("Press [Enter] to proceed, [Space] to ABORT and EXIT.")

        while True:
            loop = asyncio.get_event_loop()
            ch = await loop.run_in_executor(None, self._get_char_raw)

            if ch in ("\r", "\n"):
                return True
            if ch == " ":
                await self.abort()
                return False

    def _get_char_raw(self):
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

    async def run_test(self):
        if not await self.connect():
            return

        print("\n--- Hardware Interaction Test (HIT) ---")
        print("Safety: Press SPACE at any time to STOP all motion.")

        abort_task = asyncio.create_task(self.monitor_abort())

        try:
            # 1. Initialization
            print("\nPhase 1: Connection Audit")
            await self.send_prop("CONNECTION", {"CONNECT": "On", "DISCONNECT": "Off"})
            await asyncio.sleep(2)
            if not await self.confirm("Connection established?"):
                return

            slew_rate = self.config.get("slew_rate", 2)
            # 2. Pulse Test N
            print(f"\nPhase 2: Directional Pulse (North) at Rate {slew_rate}")
            await self.send_prop("SLEW_RATE", {"RATE": slew_rate})
            await self.send_prop(
                "TELESCOPE_MOTION_NS", {"SLEW_NORTH": "On", "SLEW_SOUTH": "Off"}
            )
            await asyncio.sleep(2)
            await self.send_prop(
                "TELESCOPE_MOTION_NS", {"SLEW_NORTH": "Off", "SLEW_SOUTH": "Off"}
            )
            if not await self.confirm("Did the mount move NORTH?"):
                return

            # 3. Pulse Test S
            print(f"\nPhase 3: Directional Pulse (South) at Rate {slew_rate}")
            await self.send_prop(
                "TELESCOPE_MOTION_NS", {"SLEW_NORTH": "Off", "SLEW_SOUTH": "On"}
            )
            await asyncio.sleep(2)
            await self.send_prop(
                "TELESCOPE_MOTION_NS", {"SLEW_NORTH": "Off", "SLEW_SOUTH": "Off"}
            )
            if not await self.confirm("Did the mount move SOUTH?"):
                return

            fast_slew_rate = self.config.get("fast_slew_rate", 9)
            # 4. High Speed Audit
            print(f"\nPhase 4: Slew Speed Audit (Rate {fast_slew_rate})")
            if not await self.confirm("Ready for fast movement? Check cables!"):
                return
            await self.send_prop("SLEW_RATE", {"RATE": fast_slew_rate})
            await self.send_prop(
                "TELESCOPE_MOTION_WE", {"SLEW_WEST": "Off", "SLEW_EAST": "On"}
            )
            await asyncio.sleep(1)
            await self.send_prop(
                "TELESCOPE_MOTION_WE", {"SLEW_WEST": "Off", "SLEW_EAST": "Off"}
            )
            if not await self.confirm(f"Was that Rate {fast_slew_rate} movement?"):
                return

            goto_dist = self.config.get("goto_test_distance_deg", 5.0)
            # 5. GoTo Safety
            print(f"\nPhase 5: Safe GoTo ({goto_dist} degrees)")
            goto_steps = int((goto_dist / 360.0) * 16777216)
            await self.send_prop(
                "TELESCOPE_ABSOLUTE_COORD", {"AZM_STEPS": goto_steps, "ALT_STEPS": 0}
            )
            if not await self.confirm("GoTo in progress. Everything safe?"):
                return

            print("\nValidation Complete.")
            print("Results: PASSED (Manual verification)")

        except Exception as e:
            print(f"\nTest Error: {e}")
            await self.abort()
        finally:
            abort_task.cancel()
            if self.writer:
                self.writer.close()
                await self.writer.wait_closed()


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_config_path = os.path.join(base_dir, "config.yaml")

    parser = argparse.ArgumentParser(description="HIT Validation Script")
    parser.add_argument(
        "--config", default=default_config_path, help="Path to config.yaml"
    )
    parser.add_argument("--host", help="INDI server host")
    parser.add_argument("--port", type=int, help="INDI server port")
    parser.add_argument("--device", help="Mount device name")
    args = parser.parse_args()

    full_config = load_config(args.config)
    hit_config = full_config.get("validation_hit", {})

    host = args.host or hit_config.get("host", "localhost")
    port = args.port or hit_config.get("port", 7624)
    device = args.device or hit_config.get("device", "Celestron AUX")

    hit = HITValidation(host=host, port=port, device=device, config=hit_config)
    try:
        asyncio.run(hit.run_test())
    except KeyboardInterrupt:
        pass
