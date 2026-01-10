#!/usr/bin/env python3
import asyncio
import math
import ephem
import numpy as np
import time
import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent / "src"))

from celestron_aux.celestron_indi_driver import CelestronAUXDriver, STEPS_PER_REVOLUTION
from celestron_aux.celestron_aux_driver import (
    AUXCommand,
    AUXCommands,
    AUXTargets,
    unpack_int3_steps,
)


class AlignmentAnalyzer:
    def __init__(self, host="localhost", port=2000):
        self.host = host
        self.port = port
        self.driver = CelestronAUXDriver()
        self.driver.port_name.membervalue = f"socket://{host}:{port}"

        async def mock_send(xmldata):
            pass

        self.driver.send = mock_send

    async def setup(self):
        self.driver.conn_connect.membervalue = "On"
        await self.driver.handle_connection(None)
        if not self.driver.communicator or not self.driver.communicator.connected:
            return False
        return True

    async def reset(self):
        self.driver.align_clear_all.membervalue = "On"
        await self.driver.handle_alignment_config(None)
        self.driver.refraction_on.membervalue = "Off"

    async def get_truth(self):
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

        ra_rad, dec_rad = self.driver.observer.radec_of(
            math.radians(true_az_deg), math.radians(true_alt_deg)
        )
        return (ra_rad / (2 * math.pi)) * 24.0, (dec_rad / (2 * math.pi)) * 360.0

    async def perform_sync(self, ra, dec):
        # We simulate centering the star.
        # To do this correctly in simulation analysis:
        # 1. We know the star is at (ra, dec).
        # 2. We ask the mount where it is PHYSICALLY (encoders).
        # 3. We ask the mount where it is LOOKING (truth).
        # 4. We map the physical encoders to the sky (ra, dec).

        await self.driver.read_mount_position()
        raw_az_deg = (self.driver.current_azm_steps / 16777216.0) * 360.0
        raw_alt_deg = (self.driver.current_alt_steps / 16777216.0) * 360.0
        if raw_alt_deg > 180:
            raw_alt_deg -= 360.0

        # Truth backdoor
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

        from celestron_aux.alignment import vector_from_altaz

        sky_vec = vector_from_altaz(true_az_deg, true_alt_deg)
        mount_vec = vector_from_altaz(raw_az_deg, raw_alt_deg)

        self.driver._align_model.add_point(sky_vec, mount_vec)
        await self.driver.update_alignment_status()

    async def wait_for_idle(self):
        for _ in range(60):
            await self.driver.read_mount_position()
            if self.driver.slewing_light.membervalue == "Idle":
                return True
            await asyncio.sleep(0.5)
        return False

    async def check_accuracy(self, ra, dec):
        self.driver.ra.membervalue = ra % 24.0
        self.driver.dec.membervalue = dec
        await self.driver.handle_equatorial_goto(None)
        await self.wait_for_idle()

        truth = await self.get_truth()
        true_ra, true_dec = truth

        ra_diff = true_ra - (ra % 24.0)
        if ra_diff > 12:
            ra_diff -= 24
        if ra_diff < -12:
            ra_diff += 24

        ra_err = ra_diff * 3600.0 * 15.0 * math.cos(math.radians(dec))
        dec_err = (true_dec - dec) * 3600.0
        return math.sqrt(ra_err**2 + dec_err**2)

    async def run_suite(self):
        if not await self.setup():
            return

        target_center_ra = 18.0
        target_center_dec = 40.0

        print(f"{'Points':<10} | {'Local Err':<12} | {'Global Err':<12} | {'RMS':<10}")
        print("-" * 55)

        # Scenarios: 1, 2, 3, 6, 12
        point_counts = [1, 2, 3, 6, 12]

        # Pre-generate points
        all_stars = []
        for i in range(15):
            # Spiral outward
            r = 5.0 + i * 3.0
            angle = i * 137.5
            d_ra = (r * math.cos(math.radians(angle))) / (
                15.0 * math.cos(math.radians(target_center_dec))
            )
            d_dec = r * math.sin(math.radians(angle))
            all_stars.append((target_center_ra + d_ra, target_center_dec + d_dec))

        for count in point_counts:
            await self.reset()
            # Perform alignment
            for i in range(count):
                ra, dec = all_stars[i]
                self.driver.ra.membervalue = ra % 24.0
                self.driver.dec.membervalue = dec
                await self.driver.handle_equatorial_goto(None)
                await self.wait_for_idle()
                await self.perform_sync(ra, dec)

            # Measure local accuracy
            local_errs = []
            for i in range(1):
                ra = target_center_ra + 0.5
                dec = target_center_dec + 2.0
                err = await self.check_accuracy(ra, dec)
                local_errs.append(err)

            # Measure global accuracy
            global_errs = []
            for i in range(1):
                ra = (target_center_ra + 10) % 24.0
                dec = target_center_dec - 30
                err = await self.check_accuracy(ra, dec)
                global_errs.append(err)

            rms = float(self.driver.align_rms_error.membervalue)
            print(
                f'{count:<10} | {np.mean(local_errs):>10.1f}" | {np.mean(global_errs):>11.1f}" | {rms:>8.1f}"'
            )


if __name__ == "__main__":
    analyzer = AlignmentAnalyzer()
    asyncio.run(analyzer.run_suite())
