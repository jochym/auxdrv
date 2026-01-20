#!/usr/bin/env python3
"""
Periodic Error (PE) Measurement Script for Celestron AUX Mount.
Uses main camera and Plate Solving (ASTAP) to measure tracking residuals.

Procedure:
1. Slew to a star (ideally near the Celestial Equator and Meridian).
2. Take a sequence of images over 15-20 minutes (2+ worm cycles).
3. Solve images with ASTAP to get high-precision RA/Dec coordinates.
4. Analyze the drift and periodic oscillations.
"""

import sys
import asyncio
import math
import os
import subprocess
import time
import re
import argparse
import tomllib
import numpy as np
from datetime import datetime
from pathlib import Path

# Simple INDI XML templates
GET_PROPS = '<getProperties version="1.7" />\n'


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


class PECMeasurement:
    def __init__(
        self,
        host="localhost",
        port=7624,
        mount="Celestron AUX",
        camera="CCD Simulator",
        config=None,
    ):
        self.host = host
        self.port = port
        self.mount = mount
        self.camera = camera
        self.config = config or {}
        self.reader = None
        self.writer = None
        self.data = []  # List of (timestamp, ra, dec)

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

    async def send_xml(self, xml):
        if self.writer:
            self.writer.write(xml.encode())
            await self.writer.drain()

    async def capture_and_solve(self, exposure, upload_prefix):
        """Captures one image and returns solved (ra, dec)."""
        # 1. Set local path
        xml_path = f'''<newTextVector device="{self.camera}" name="UPLOAD_SETTINGS">
            <oneText name="UPLOAD_DIR">{os.getcwd()}</oneText>
            <oneText name="UPLOAD_PREFIX">{upload_prefix}</oneText>
        </newTextVector>\n'''
        # 2. Trigger exposure
        xml_exp = f'''<newNumberVector device="{self.camera}" name="CCD_EXPOSURE">
            <oneNumber name="EXPOSURE">{exposure}</oneNumber>
        </newNumberVector>\n'''

        await self.send_xml(xml_path)
        await asyncio.sleep(0.2)
        await self.send_xml(xml_exp)

        # Wait for capture (exposure + overhead)
        await asyncio.sleep(exposure + 5)

        # Find latest fits
        files = [
            f
            for f in os.listdir(".")
            if f.startswith(upload_prefix) and f.endswith(".fits")
        ]
        if not files:
            return None, None
        filepath = sorted(files)[-1]

        # Solve with ASTAP
        try:
            res = subprocess.run(
                ["astap", "-f", filepath, "-solve"], capture_output=True, text=True
            )
            if "Solution found" in res.stdout:
                # Solution found: 18:36:56.2, +38:47:01
                match = re.search(r"Solution found: ([\d:]+), ([\d\-:]+)", res.stdout)
                if match:
                    ra_str, dec_str = match.groups()
                    ra = self.hms_to_float(ra_str)
                    dec = self.dms_to_float(dec_str)
                    # Clean up file
                    os.remove(filepath)
                    if os.path.exists(filepath.replace(".fits", ".wcs")):
                        os.remove(filepath.replace(".fits", ".wcs"))
                    return ra, dec
            print(f"  Solve failed for {filepath}")
            return None, None
        except Exception as e:
            print(f"  ASTAP error: {e}")
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

    async def run(self, duration_min=20, interval_sec=20, exposure=1.0):
        if not await self.connect():
            return

        print(f"\n--- PEC Measurement Started ---")
        print(f"Mount: {self.mount}, Camera: {self.camera}")
        print(f"Duration: {duration_min} min, Interval: {interval_sec} s")
        print("Ensure the mount is tracking and a star is centered.")
        print("Press Enter to start sequence, or Ctrl+C to abort...")

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, sys.stdin.readline)

        start_time = time.time()
        end_time = start_time + (duration_min * 60)
        upload_prefix = f"pec_meas_{datetime.now().strftime('%H%M%S')}"

        try:
            while time.time() < end_time:
                now = time.time()
                t_rel = now - start_time
                print(f"[{t_rel:6.1f}s] Capturing...", end="", flush=True)

                ra, dec = await self.capture_and_solve(exposure, upload_prefix)
                if ra is not None:
                    print(f" Solved: RA={ra:.6f}h, Dec={dec:.6f}deg")
                    self.data.append((t_rel, ra, dec))

                # Wait for next interval
                elapsed = time.time() - now
                wait = max(0.1, interval_sec - elapsed)
                await asyncio.sleep(wait)

        except KeyboardInterrupt:
            print("\nAborted by user.")

        # Save results
        if self.data:
            self.save_report()
        else:
            print("No data collected.")

    def save_report(self):
        filename = f"pec_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(filename, "w") as f:
            f.write("time_sec,ra_hours,dec_deg\n")
            for t, r, d in self.data:
                f.write(f"{t:.2f},{r:.8f},{d:.6f}\n")

        print(f"\nMeasurement complete. Data saved to {filename}")

        # Simple analysis
        ts = np.array([d[0] for d in self.data])
        ras = np.array([d[1] for d in self.data]) * 15.0 * 3600.0  # to arcsec
        decs = np.array([d[2] for d in self.data]) * 3600.0  # to arcsec

        # Remove linear trend (drift)
        ra_p = np.polyfit(ts, ras, 1)
        ra_detrend = ras - np.polyval(ra_p, ts)

        dec_p = np.polyfit(ts, decs, 1)
        dec_detrend = decs - np.polyval(dec_p, ts)

        pe_pp = np.max(ra_detrend) - np.min(ra_detrend)
        rms = np.sqrt(np.mean(ra_detrend**2))

        print(f"--- Analysis ---")
        print(f"Total points: {len(self.data)}")
        print(f'RA Drift Rate: {ra_p[0]:.3f} "/s')
        print(f'RA Periodic Error (Peak-to-Peak): {pe_pp:.2f} "')
        print(f'RA Residual RMS: {rms:.2f} "')
        print(f'Dec Drift Rate: {dec_p[0]:.3f} "/s')


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_config_path = os.path.join(
        base_dir, "src", "celestron_aux", "config.default.toml"
    )

    parser = argparse.ArgumentParser(description="Measure Periodic Error using ASTAP")
    parser.add_argument(
        "--config", default=default_config_path, help="Path to config.toml"
    )
    parser.add_argument("--host", help="INDI host")
    parser.add_argument("--port", type=int, help="INDI port")
    parser.add_argument("--mount", help="Mount device name")
    parser.add_argument("--camera", help="Camera device name")
    parser.add_argument("--duration", type=int, help="Duration in minutes")
    parser.add_argument("--interval", type=int, help="Interval in seconds")
    parser.add_argument("--exposure", type=float, help="Exposure time in seconds")

    args = parser.parse_args()

    full_config = load_config(args.config)
    pec_config = full_config.get("validation_pec", {})

    host = args.host or pec_config.get("host", "localhost")
    port = args.port or pec_config.get("port", 7624)
    mount = args.mount or pec_config.get("mount_device", "Celestron AUX")
    camera = args.camera or pec_config.get("camera_device", "CCD Simulator")
    duration = args.duration or pec_config.get("duration", 20)
    interval = args.interval or pec_config.get("interval", 30)
    exposure = args.exposure or pec_config.get("exposure", 2.0)

    meas = PECMeasurement(
        host=host, port=port, mount=mount, camera=camera, config=pec_config
    )
    try:
        asyncio.run(
            meas.run(
                duration_min=duration,
                interval_sec=interval,
                exposure=exposure,
            )
        )
    except KeyboardInterrupt:
        pass
