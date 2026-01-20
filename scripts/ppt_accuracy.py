import asyncio
import sys
import os
import subprocess
import time
import math
import argparse
import re
import tomllib
from datetime import datetime


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merges two dictionaries."""
    for key, value in override.items():
        if isinstance(value, dict) and key in base and isinstance(base[key], dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def load_config(config_path=None):
    config = {}
    # 1. Load config.default.toml
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_dir = os.path.join(base_dir, "src", "celestron_aux")
    default_path = os.path.join(config_dir, "config.default.toml")

    if os.path.exists(default_path):
        with open(default_path, "rb") as f:
            config = tomllib.load(f)

    # 2. Load config.toml if it exists in the same dir
    user_path = os.path.join(config_dir, "config.toml")
    if os.path.exists(user_path):
        with open(user_path, "rb") as f:
            deep_merge(config, tomllib.load(f))

    # 3. Load --config if provided and different from above
    if config_path and os.path.exists(config_path):
        abs_config = os.path.abspath(config_path)
        if abs_config != os.path.abspath(
            default_path
        ) and abs_config != os.path.abspath(user_path):
            with open(config_path, "rb") as f:
                deep_merge(config, tomllib.load(f))

    return config


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
        config=None,
    ):
        self.host = host
        self.port = port
        self.mount_device = mount_device
        self.camera_device = camera_device
        self.config = config or {}
        self.reader = None
        self.writer = None
        self.results = []  # List of (target_ra, target_dec, solved_ra, solved_dec, error)

    async def connect(self):
        print(f"Connecting to INDI at {self.host}:{self.port}...")
        try:
            self.reader, self.writer = await asyncio.open_connection(
                self.host, self.port
            )
            if self.writer:
                self.writer.write(b'<getProperties version="1.7" />\n')
                await self.writer.drain()
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    async def send_xml(self, xml):
        if self.writer:
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
        upload_prefix = self.config.get("upload_prefix", "ppt_capture")
        # 1. Set local path
        xml_path = f'''<newTextVector device="{self.camera_device}" name="UPLOAD_SETTINGS">
            <oneText name="UPLOAD_DIR">{os.getcwd()}</oneText>
            <oneText name="UPLOAD_PREFIX">{upload_prefix}</oneText>
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
            if f.startswith(upload_prefix) and f.endswith(".fits")
        ]
        if not files:
            return None
        return sorted(files)[-1]

    def solve_image(self, filepath):
        print(f"Solving {filepath} with ASTAP...")
        try:
            # -solve: standard solve
            res = subprocess.run(
                ["astap", "-f", filepath, "-solve"], capture_output=True, text=True
            )
            # ASTAP output: "Solution found: RA=..., Dec=..."
            if "Solution found" in res.stdout:
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
        targets = self.config.get("targets", [(2.0, 45.0), (10.0, 30.0), (18.0, 60.0)])
        exposure = self.config.get("exposure", 2.0)

        for ra, dec in targets:
            print(f"\nTarget: RA={ra}, Dec={dec}")
            print("Press Enter to slew, or Ctrl+C to abort...")
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, sys.stdin.readline)

            await self.slew_to(ra, dec)

            filepath = await self.capture_image(exposure=exposure)
            if not filepath:
                print("Capture failed.")
                continue

            s_ra, s_dec = self.solve_image(filepath)
            if s_ra is not None and s_dec is not None:
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

        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_config_path = os.path.join(
        base_dir, "src", "celestron_aux", "config.default.toml"
    )

    parser = argparse.ArgumentParser(description="PPT Accuracy Script")
    parser.add_argument(
        "--config", default=default_config_path, help="Path to config.toml"
    )
    parser.add_argument("--host", help="INDI server host")
    parser.add_argument("--port", type=int, help="INDI server port")
    parser.add_argument("--mount", help="Mount device name")
    parser.add_argument("--camera", help="Camera device name")
    args = parser.parse_args()

    full_config = load_config(args.config)
    ppt_config = full_config.get("validation_ppt", {})

    host = args.host or ppt_config.get("host", "localhost")
    port = args.port or ppt_config.get("port", 7624)
    mount = args.mount or ppt_config.get("mount_device", "Celestron AUX")
    camera = args.camera or ppt_config.get("camera_device", "CCD Simulator")

    ppt = PPTAccuracy(
        host=host,
        port=port,
        mount_device=mount,
        camera_device=camera,
        config=ppt_config,
    )
    try:
        asyncio.run(ppt.run_ppt())
    except KeyboardInterrupt:
        pass
