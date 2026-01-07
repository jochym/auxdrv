import asyncio
import sys
import os
import subprocess
import time
import math
from datetime import datetime


class PPTAccuracy:
    """
    Photography & Pointing Test (PPT) for Celestron AUX Mount.
    Automates accuracy measurement using INDI and ASTAP.
    """

    def __init__(
        self,
        host="localhost",
        port=7624,
        mount_device="Celestron AUX",
        camera_device="CCD Simulator",
    ):
        self.host = host
        self.port = port
        self.mount_device = mount_device
        self.camera_device = camera_device
        self.reader = None
        self.writer = None
        self.results = []  # List of (target_ra, target_dec, solved_ra, solved_dec, error)

    async def connect(self):
        print(f"Connecting to INDI at {self.host}:{self.port}...")
        try:
            self.reader, self.writer = await asyncio.open_connection(
                self.host, self.port
            )
            self.writer.write(b'<getProperties version="1.7" />\n')
            await self.writer.drain()
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    async def send_xml(self, xml):
        self.writer.write(xml.encode())
        await self.writer.drain()

    async def slew_to(self, ra, dec):
        print(f"Slewing to RA {ra:.2f}, Dec {dec:.2f}...")
        xml = f'''<newNumberVector device="{self.mount_device}" name="EQUATORIAL_EOD_COORD">
            <oneNumber name="RA">{ra}</oneNumber>
            <oneNumber name="DEC">{dec}</oneNumber>
        </newNumberVector>\n'''
        await self.send_xml(xml)
        # Wait for idle (simplistic wait for this script)
        await asyncio.sleep(10)

    async def capture_image(self, exposure=2.0):
        print(f"Capturing {exposure}s exposure...")
        filename = f"ppt_capture_{int(time.time())}.fits"
        # 1. Set local path
        xml_path = f'''<newTextVector device="{self.camera_device}" name="UPLOAD_SETTINGS">
            <oneText name="UPLOAD_DIR">{os.getcwd()}</oneText>
            <oneText name="UPLOAD_PREFIX">ppt_capture</oneText>
        </newTextVector>\n'''
        # 2. Trigger exposure
        xml_exp = f'''<newNumberVector device="{self.camera_device}" name="CCD_EXPOSURE">
            <oneNumber name="EXPOSURE">{exposure}</oneNumber>
        </newNumberVector>\n'''

        await self.send_xml(xml_path)
        await asyncio.sleep(0.5)
        await self.send_xml(xml_exp)

        # Wait for capture
        await asyncio.sleep(exposure + 5)

        # Find latest fits
        files = [
            f
            for f in os.listdir(".")
            if f.startswith("ppt_capture") and f.endswith(".fits")
        ]
        if not files:
            return None
        return sorted(files)[-1]

    def solve_image(self, filepath):
        print(f"Solving {filepath} with ASTAP...")
        try:
            # -solve: standard solve, -v: verbose
            res = subprocess.run(
                ["astap", "-f", filepath, "-solve"], capture_output=True, text=True
            )
            # ASTAP creates a .wcs file or outputs to stdout
            # For simplicity in this routine, we look for the .wcs or parse stdout
            # Real ASTAP output: "Solution found: RA=..., Dec=..."
            if "Solution found" in res.stdout:
                # Extract RA/Dec from stdout
                # Solution found: 10:20:30, 45:00:00
                import re

                match = re.search(r"Solution found: ([\d:]+), ([\d\-:]+)", res.stdout)
                if match:
                    ra_str, dec_str = match.groups()
                    return self.hms_to_float(ra_str), self.dms_to_float(dec_str)
            return None, None
        except Exception as e:
            print(f"ASTAP failed: {e}")
            return None, None

    def hms_to_float(self, hms):
        h, m, s = map(float, hms.split(":"))
        return h + m / 60.0 + s / 3600.0

    def dms_to_float(self, dms):
        parts = dms.split(":")
        d = float(parts[0])
        m = float(parts[1]) if len(parts) > 1 else 0
        s = float(parts[2]) if len(parts) > 2 else 0
        sign = 1 if d >= 0 else -1
        return d + sign * (m / 60.0 + s / 3600.0)

    async def run_ppt(self):
        if not await self.connect():
            return

        print("\n--- Photography & Pointing Test (PPT) ---")
        targets = [(2.0, 45.0), (10.0, 30.0), (18.0, 60.0)]

        for ra, dec in targets:
            print(f"\nTarget: RA={ra}, Dec={dec}")
            input("Press Enter to slew, or Ctrl+C to abort...")
            await self.slew_to(ra, dec)

            filepath = await self.capture_image()
            if not filepath:
                print("Capture failed.")
                continue

            s_ra, s_dec = self.solve_image(filepath)
            if s_ra is not None:
                error = (
                    math.sqrt(
                        ((ra - s_ra) * 15 * math.cos(math.radians(dec))) ** 2
                        + (dec - s_dec) ** 2
                    )
                    * 3600
                )
                print(f"Solved: RA={s_ra:.4f}, Dec={s_dec:.4f}")
                print(f"Error: {error:.2f} arcsec")
                self.results.append((ra, dec, s_ra, s_dec, error))
            else:
                print("Plate solve failed.")

        print("\n--- PPT Report ---")
        if self.results:
            avg_err = sum(r[4] for r in self.results) / len(self.results)
            print(f"Processed {len(self.results)} points.")
            print(f"Average Pointing Error: {avg_err:.2f} arcsec")
        else:
            print("No valid results.")


if __name__ == "__main__":
    ppt = PPTAccuracy()
    try:
        asyncio.run(ppt.run_ppt())
    except KeyboardInterrupt:
        pass
