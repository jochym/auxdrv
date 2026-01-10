#!/usr/bin/env python3
"""
Real-World Validation Script for Celestron AUX INDI Driver.

Scenario:
1. Non-perfect mount (PE, Backlash, Cone, Non-Perp, Jitter, Refraction).
2. Local multi-star alignment around a target region.
3. Comparative accuracy analysis (Inside vs Outside alignment area).
4. Long-term tracking stability measurement.
"""

import asyncio
import math
import ephem
import numpy as np
import time
import argparse
import sys
from pathlib import Path

# Add src to path to import driver components if needed
sys.path.append(str(Path(__file__).parent.parent / "src"))

from celestron_aux.celestron_indi_driver import CelestronAUXDriver, STEPS_PER_REVOLUTION
from celestron_aux.celestron_aux_driver import (
    AUXCommand,
    AUXCommands,
    AUXTargets,
    unpack_int3_steps,
)


class RealWorldValidator:
    def __init__(self, host="localhost", port=2000):
        self.host = host
        self.port = port
        self.driver = CelestronAUXDriver()
        self.driver.port_name.membervalue = f"socket://{host}:{port}"

        # Mock the XML send to avoid network overhead, we talk directly to driver logic
        async def mock_send(xmldata):
            pass

        self.driver.send = mock_send

    async def setup(self):
        print(f"Connecting to simulator at {self.host}:{self.port}...")
        self.driver.conn_connect.membervalue = "On"
        await self.driver.handle_connection(None)

        if not self.driver.communicator or not self.driver.communicator.connected:
            print("Failed to connect to simulator!")
            return False

        print("Resetting alignment model...")
        self.driver.align_clear_all.membervalue = "On"
        await self.driver.handle_alignment_config(None)

        # IMPORTANT: We disable refraction in the driver during this validation
        # because the validation script queries the 'Apparent' position
        # from the simulator truth backdoor.
        self.driver.refraction_on.membervalue = "Off"
        self.driver.set_track.membervalue = "On"
        return True

    async def wait_for_idle(self, timeout=120):
        start = time.time()
        while time.time() - start < timeout:
            await self.driver.read_mount_position()
            if self.driver.slewing_light.membervalue == "Idle":
                return True
            await asyncio.sleep(1)
        return False

    async def get_true_sky_radec(self):
        """Queries the simulator for the absolute TRUTH (actual sky position)."""
        if not self.driver.communicator:
            return None

        # AZM
        resp = await self.driver.communicator.send_command(
            AUXCommand(AUXCommands.SIM_GET_SKY_POSITION, AUXTargets.APP, AUXTargets.AZM)
        )
        true_az_steps = unpack_int3_steps(resp.data)

        # ALT
        resp = await self.driver.communicator.send_command(
            AUXCommand(AUXCommands.SIM_GET_SKY_POSITION, AUXTargets.APP, AUXTargets.ALT)
        )
        true_alt_steps = unpack_int3_steps(resp.data)

        # Convert steps to degrees
        true_az_deg = (true_az_steps / 16777216.0) * 360.0
        true_alt_deg = (true_alt_steps / 16777216.0) * 360.0
        if true_alt_deg > 180:
            true_alt_deg -= 360.0

        # Convert Alt/Az truth to RA/Dec truth
        # Note: We use the driver's observer for time/location
        ra_rad, dec_rad = self.driver.observer.radec_of(
            math.radians(true_az_deg), math.radians(true_alt_deg)
        )
        return (ra_rad / (2 * math.pi)) * 24.0, (dec_rad / (2 * math.pi)) * 360.0

    async def measure_accuracy(self, ra, dec, label="Point"):
        """Slews to a target and measures the difference between target and ACTUAL sky truth."""
        ra = ra % 24.0
        print(f"  Measuring {label} (RA: {ra:.4f}h, Dec: {dec:.4f}deg)...")
        self.driver.ra.membervalue = ra
        self.driver.dec.membervalue = dec

        # Trigger GoTo
        await self.driver.handle_equatorial_goto(None)
        if not await self.wait_for_idle():
            print(f"    TIMEOUT reaching {label}")
            return None

        # Get "Truth" from simulator
        truth = await self.get_true_sky_radec()
        if not truth:
            return None
        true_ra, true_dec = truth

        # Calculate error between Target and Truth in arcsec
        ra_diff = true_ra - ra
        if ra_diff > 12.0:
            ra_diff -= 24.0
        if ra_diff < -12.0:
            ra_diff += 24.0

        ra_err = ra_diff * 3600.0 * 15.0 * math.cos(math.radians(dec))
        dec_err = (true_dec - dec) * 3600.0
        total_err = math.sqrt(ra_err**2 + dec_err**2)

        print(
            f'    True Sky Error: {total_err:.2f}" (RA: {ra_err:.2f}", Dec: {dec_err:.2f}")'
        )
        return total_err, ra_err, dec_err

    async def perform_sync(self, ra, dec):
        """Programmatically adds a perfect alignment point by reading simulator truth."""
        ra = ra % 24.0

        # Get the ACTUAL encoders from the simulator at this moment
        # (Assuming the 'user' has centered the star perfectly)
        await self.driver.read_mount_position()
        raw_az_deg = (self.driver.current_azm_steps / 16777216.0) * 360.0
        raw_alt_deg = (self.driver.current_alt_steps / 16777216.0) * 360.0
        if raw_alt_deg > 180:
            raw_alt_deg -= 360.0

        # Get the TRUE sky position from the simulator (where the mount is REALLY pointing)
        resp_az = await self.driver.communicator.send_command(
            AUXCommand(AUXCommands.SIM_GET_SKY_POSITION, AUXTargets.APP, AUXTargets.AZM)
        )
        true_az_deg = (unpack_int3_steps(resp_az.data) / 16777216.0) * 360.0
        resp_alt = await self.driver.communicator.send_command(
            AUXCommand(AUXCommands.SIM_GET_SKY_POSITION, AUXTargets.APP, AUXTargets.ALT)
        )
        true_alt_deg = (unpack_int3_steps(resp_alt.data) / 16777216.0) * 360.0
        if true_alt_deg > 180:
            true_alt_deg -= 360.0

        # THE CORE TRUTH:
        # These ENCODER positions (raw_az_deg, raw_alt_deg)
        # map to this SKY position (true_az_deg, true_alt_deg).
        from celestron_aux.alignment import vector_from_altaz

        sky_vec = vector_from_altaz(true_az_deg, true_alt_deg)
        mount_vec = vector_from_altaz(raw_az_deg, raw_alt_deg)

        self.driver._align_model.add_point(sky_vec, mount_vec)
        await self.driver.update_alignment_status()

    async def run_validation(self):
        if not await self.setup():
            return

        # Target Region: Summer Triangle
        target_center_ra = 18.61
        target_center_dec = 38.78

        print(f"\n--- PHASE 1: Baseline Accuracy (No Alignment) ---")
        res = await self.measure_accuracy(
            target_center_ra, target_center_dec, "Center Baseline"
        )
        baseline_err = res[0] if res else 0.0

        print(f"\n--- PHASE 2: Local 12-Star Alignment ---")
        # Stars scattered around the target box
        alignment_points = [
            (target_center_ra, target_center_dec + 10),
            (target_center_ra, target_center_dec - 10),
            (target_center_ra + 2, target_center_dec),
            (target_center_ra - 2, target_center_dec),
            (target_center_ra + 1, target_center_dec + 5),
            (target_center_ra - 1, target_center_dec - 5),
            (target_center_ra + 6, target_center_dec + 30),
            (target_center_ra - 6, target_center_dec - 30),
            (target_center_ra + 10, target_center_dec),
            (target_center_ra - 10, target_center_dec),
        ]

        for ra, dec in alignment_points:
            # Slew NEAR
            self.driver.ra.membervalue = ra % 24.0
            self.driver.dec.membervalue = dec
            await self.driver.handle_equatorial_goto(None)
            await self.wait_for_idle()
            # Then SYNC using truth
            await self.perform_sync(ra, dec)

        # Log Model Status
        await self.driver.update_alignment_status()
        print(
            f'\nAlignment Model: {int(self.driver.align_point_count.membervalue)} points, RMS: {float(self.driver.align_rms_error.membervalue):.2f}"'
        )
        print(
            f"Computed Params: ID={float(self.driver.cal_alt_offset.membervalue):.2f}', CH={float(self.driver.cal_cone.membervalue):.2f}', NP={float(self.driver.cal_nonperp.membervalue):.2f}'"
        )

        print(f"\n--- PHASE 3: Accuracy Test (Inside Box) ---")
        test_points_inside = [
            (target_center_ra, target_center_dec),
            (target_center_ra + 0.2, target_center_dec + 2.0),
            (target_center_ra - 0.2, target_center_dec - 2.0),
        ]
        results_inside = []
        for ra, dec in test_points_inside:
            res = await self.measure_accuracy(ra, dec, "Inside Point")
            if res:
                results_inside.append(res[0])

        print(f"\n--- PHASE 4: Accuracy Test (Outside Box) ---")
        test_points_outside = [
            (target_center_ra + 6.0, target_center_dec),
            (target_center_ra, target_center_dec + 40.0),
            (target_center_ra - 8.0, target_center_dec - 30.0),
        ]
        results_outside = []
        for ra, dec in test_points_outside:
            res = await self.measure_accuracy(ra, dec, "Outside Point")
            if res:
                results_outside.append(res[0])

        print(f"\n--- PHASE 5: Tracking Stability (60s) ---")
        await self.measure_accuracy(
            target_center_ra, target_center_dec, "Tracking Center"
        )

        tracking_data = []
        print("  Monitoring drift...")
        for i in range(60):
            await self.driver.read_mount_position()
            ra = float(self.driver.ra.membervalue)
            dec = float(self.driver.dec.membervalue)
            tracking_data.append((ra, dec))
            await asyncio.sleep(1)

        ra_vals = [d[0] for d in tracking_data]
        dec_vals = [d[1] for d in tracking_data]

        ra_diff = ra_vals[-1] - ra_vals[0]
        if ra_diff > 12.0:
            ra_diff -= 24.0
        if ra_diff < -12.0:
            ra_diff += 24.0

        ra_drift = ra_diff * 3600.0 * 15.0 * math.cos(math.radians(target_center_dec))
        dec_drift = (dec_vals[-1] - dec_vals[0]) * 3600.0
        total_drift = math.sqrt(ra_drift**2 + dec_drift**2)

        print(f"\n--- FINAL SUMMARY ---")
        print(f'Baseline Error: {baseline_err:.2f}"')
        if results_inside:
            print(f'Avg Error Inside Box: {np.mean(results_inside):.2f}"')
        if results_outside:
            print(f'Avg Error Outside Box: {np.mean(results_outside):.2f}"')
        print(f'Tracking Drift (60s): {total_drift:.2f}"')
        print(f"Status: {'SUCCESS' if np.mean(results_inside) < 30.0 else 'FAILED'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Real-world accuracy validation.")
    parser.add_argument("--host", default="localhost", help="Simulator host")
    parser.add_argument("--port", type=int, default=2000, help="Simulator port")
    args = parser.parse_args()

    validator = RealWorldValidator(args.host, args.port)
    asyncio.run(validator.run_validation())
