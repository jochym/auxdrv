import asyncio
import math
import ephem
import numpy as np
import os
from base_test import CelestronAUXBaseTest


class TestTrackingAccuracy(CelestronAUXBaseTest):
    """
    Automated verification of tracking accuracy, drift, and slew stability.
    """

    async def asyncSetUp(self):
        await super().asyncSetUp()
        # Reset position to 0,0
        if self.driver.communicator and self.driver.communicator.connected:
            from celestron_aux.celestron_indi_driver import (
                AUXCommand,
                AUXCommands,
                AUXTargets,
                pack_int3_steps,
            )

            await self.driver.communicator.send_command(
                AUXCommand(
                    AUXCommands.MC_SET_POSITION,
                    AUXTargets.APP,
                    AUXTargets.AZM,
                    pack_int3_steps(0),
                )
            )
            await self.driver.communicator.send_command(
                AUXCommand(
                    AUXCommands.MC_SET_POSITION,
                    AUXTargets.APP,
                    AUXTargets.ALT,
                    pack_int3_steps(0),
                )
            )

    async def test_tracking_stability(self):
        """
        Slews to a star and monitors for drift in position.
        """
        # 1. Setup Alignment (Perfect identity for sim)
        self.driver.align_clear_all.membervalue = "On"
        await self.driver.handle_alignment_config(None)

        # 2. Target a star (Vega)
        star = ephem.star("Vega")
        self.driver.update_observer()
        star.compute(self.driver.observer)

        target_ra = float(star.ra) * 12.0 / math.pi
        target_dec = float(star.dec) * 180.0 / math.pi

        print(f"Targeting Vega: RA={target_ra:.4f}h, Dec={target_dec:.4f}deg")
        self.driver.ra.membervalue = target_ra
        self.driver.dec.membervalue = target_dec
        self.driver.set_track.membervalue = "On"

        # Trigger GoTo
        await self.driver.handle_equatorial_goto(None)

        # Wait for slew done
        for _ in range(120):
            await self.driver.read_mount_position()
            if (
                self.driver.slewing_light.membervalue == "Idle"
                and self.driver.equatorial_vector.state != "Busy"
            ):
                break
            await asyncio.sleep(1)

        # 3. Monitor Tracking for Drift
        print("Slew finished. Monitoring tracking for 60 seconds...")
        tracking_data = []
        for i in range(60):
            await self.driver.read_mount_position()
            ra = float(self.driver.ra.membervalue)
            dec = float(self.driver.dec.membervalue)
            tracking_data.append((ra, dec))
            if i % 10 == 0:
                print(f" T+{i}s: RA={ra:.6f}h, Dec={dec:.6f}deg")
            await asyncio.sleep(1)

        ra_vals = [d[0] for d in tracking_data]
        dec_vals = [d[1] for d in tracking_data]

        # Calculate drift (difference between last and first)
        ra_drift = (ra_vals[-1] - ra_vals[0]) * 3600.0 * 15.0  # arcsec
        dec_drift = (dec_vals[-1] - dec_vals[0]) * 3600.0  # arcsec

        # Initial pointing error
        ra_init_err = (ra_vals[0] - target_ra) * 3600.0 * 15.0
        dec_init_err = (dec_vals[0] - target_dec) * 3600.0

        print(
            f"Initial Error: RA={ra_init_err:.2f} arcsec, Dec={dec_init_err:.2f} arcsec"
        )
        print(f"Drift over 60s: RA={ra_drift:.2f} arcsec, Dec={dec_drift:.2f} arcsec")

        # Standard deviation (jitter)
        ra_std = np.std(ra_vals) * 3600.0 * 15.0
        dec_std = np.std(dec_vals) * 3600.0

        print(f"Precision (std): RA={ra_std:.2f} arcsec, Dec={dec_std:.2f} arcsec")

        # Assertions
        # Initial pointing should be very good (< 20 arcsec with iterative GoTo)
        self.assertLess(
            abs(ra_init_err), 20.0, f"High initial RA error: {ra_init_err:.2f} arcsec"
        )
        self.assertLess(
            abs(dec_init_err),
            20.0,
            f"High initial Dec error: {dec_init_err:.2f} arcsec",
        )

        # Sidereal drift should be small (< 20.0 arcsec over 60s)
        # Note: Simulator has 15" amplitude PE, so end-to-start difference
        # can naturally be up to ~11" over a 60s window.
        self.assertLess(
            abs(ra_drift), 20.0, f"Significant RA drift: {ra_drift:.2f} arcsec"
        )
        self.assertLess(
            abs(dec_drift), 20.0, f"Significant Dec drift: {dec_drift:.2f} arcsec"
        )

        # Jitter should be small
        self.assertLess(ra_std, 15.0, f"High RA jitter: {ra_std:.2f} arcsec")
        self.assertLess(dec_std, 15.0, f"High Dec jitter: {dec_std:.2f} arcsec")


if __name__ == "__main__":
    unittest.main()
