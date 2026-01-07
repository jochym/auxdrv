import asyncio
import sys
import os
import termios
import tty
from datetime import datetime

# Simple INDI XML templates
GET_PROPS = '<getProperties version="1.7" />\n'
ENABLE_BLOB = '<enableBLOB device="Celestron AUX">Also</enableBLOB>\n'


class HITValidation:
    """
    Hardware Interaction Test (HIT) for Celestron AUX Mount.
    Safety-first interactive validation routine.
    """

    def __init__(self, host="localhost", port=7624):
        self.host = host
        self.port = port
        self.reader = None
        self.writer = None
        self.abort_event = asyncio.Event()
        self.device = "Celestron AUX"

    async def connect(self):
        print(f"Connecting to INDI server at {self.host}:{self.port}...")
        try:
            self.reader, self.writer = await asyncio.open_connection(
                self.host, self.port
            )
            self.writer.write(GET_PROPS.encode())
            await self.writer.drain()
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    async def send_prop(self, property_name, members, type="new"):
        """Sends a newProperty or switch command."""
        if not self.writer:
            return

        # Simple hacky XML generator for common cases
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

    async def get_key(self):
        """Reads a single key from stdin."""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

    async def monitor_abort(self):
        """Background task to watch for Space key."""
        while not self.abort_event.is_set():
            # Use run_in_executor for blocking read
            loop = asyncio.get_event_loop()
            key = await loop.run_in_executor(None, sys.stdin.read, 1)
            if key == " " or key == "\x03":  # Space or Ctrl+C
                await self.abort()
                break

    async def confirm(self, message):
        """Waits for user Enter to proceed or Space to abort."""
        print(f"\n{message}")
        print("Press [Enter] to proceed, [Space] to ABORT and EXIT.")

        while True:
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(sys.stdin.fileno())
                ch = sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

            if ch in ("\r", "\n"):
                return True
            if ch == " ":
                await self.abort()
                return False

    async def run_test(self):
        if not await self.connect():
            return

        print("\n--- Hardware Interaction Test (HIT) ---")
        print("Safety: Press SPACE at any time to STOP all motion.")

        asyncio.create_task(self.monitor_abort())

        try:
            # 1. Initialization
            print("\nPhase 1: Connection Audit")
            await self.send_prop("CONNECTION", {"CONNECT": "On", "DISCONNECT": "Off"})
            await asyncio.sleep(2)
            print("Check: Did the driver connect successfully? (Look at server output)")
            if not await self.confirm("Connection established?"):
                return

            # 2. Pulse Test N
            print("\nPhase 2: Directional Pulse (North)")
            await self.send_prop("SLEW_RATE", {"RATE": 2})
            await self.send_prop(
                "TELESCOPE_MOTION_NS", {"MOTION_N": "On", "MOTION_S": "Off"}
            )
            await asyncio.sleep(2)
            await self.send_prop(
                "TELESCOPE_MOTION_NS", {"MOTION_N": "Off", "MOTION_S": "Off"}
            )
            if not await self.confirm("Did the mount move NORTH?"):
                return

            # 3. Pulse Test S
            print("\nPhase 3: Directional Pulse (South)")
            await self.send_prop(
                "TELESCOPE_MOTION_NS", {"MOTION_N": "Off", "MOTION_S": "On"}
            )
            await asyncio.sleep(2)
            await self.send_prop(
                "TELESCOPE_MOTION_NS", {"MOTION_N": "Off", "MOTION_S": "Off"}
            )
            if not await self.confirm("Did the mount move SOUTH?"):
                return

            # 4. High Speed Audit
            print("\nPhase 4: Slew Speed Audit (Rate 9)")
            if not await self.confirm("Ready for fast movement? Check cables!"):
                return
            await self.send_prop("SLEW_RATE", {"RATE": 9})
            await self.send_prop(
                "TELESCOPE_MOTION_WE", {"MOTION_W": "Off", "MOTION_E": "On"}
            )
            await asyncio.sleep(1)
            await self.send_prop(
                "TELESCOPE_MOTION_WE", {"MOTION_W": "Off", "MOTION_E": "Off"}
            )
            if not await self.confirm("Was that Rate 9 movement?"):
                return

            # 5. GoTo Safety
            print("\nPhase 5: Safe GoTo (5 degrees)")
            # 5 degrees is ~233016 steps
            await self.send_prop(
                "TELESCOPE_ABSOLUTE_COORD", {"AZM_STEPS": 233016, "ALT_STEPS": 0}
            )
            if not await self.confirm("GoTo in progress. Everything safe?"):
                return

            print("\nValidation Complete.")
            print("Results: PASSED (Manual verification)")

        except Exception as e:
            print(f"\nTest Error: {e}")
            await self.abort()
        finally:
            if self.writer:
                self.writer.close()
                await self.writer.wait_closed()


if __name__ == "__main__":
    hit = HITValidation()
    try:
        asyncio.run(hit.run_test())
    except KeyboardInterrupt:
        pass
