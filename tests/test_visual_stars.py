import asyncio
import math
import ephem
from base_test import CelestronAUXBaseTest


class TestVisualStars(CelestronAUXBaseTest):
    """
    Test suite for visual verification of sky display.
    """

    async def asyncSetUp(self):
        await super().asyncSetUp()
        # Reset position to 0,0
        if self.driver.communicator and self.driver.communicator.connected:
            from celestron_aux.celestron_aux_driver import pack_int3_steps
            from celestron_aux.celestron_indi_driver import (
                AUXCommand,
                AUXCommands,
                AUXTargets,
            )

            cmd_azm = AUXCommand(
                AUXCommands.MC_SET_POSITION,
                AUXTargets.APP,
                AUXTargets.AZM,
                pack_int3_steps(0),
            )
            cmd_alt = AUXCommand(
                AUXCommands.MC_SET_POSITION,
                AUXTargets.APP,
                AUXTargets.ALT,
                pack_int3_steps(0),
            )
            await self.driver.communicator.send_command(cmd_azm)
            await self.driver.communicator.send_command(cmd_alt)

    async def asyncTearDown(self):
        if self.driver.communicator:
            await self.driver.communicator.disconnect()

    async def test_slew_to_bright_stars(self):
        """Slew to Capella, Castor, and Betelgeuse for visual verification."""
        # 1. Enable Anti-backlash (Fixed Offset)
        self.driver.approach_disabled.membervalue = "Off"
        self.driver.approach_fixed.membervalue = "On"
        self.driver.approach_azm_offset.membervalue = 10000
        self.driver.approach_alt_offset.membervalue = 10000

        # 2. Set Coord Set Mode to TRACK
        for name in self.driver.coord_set_vector:
            self.driver.coord_set_vector[name] = "Off"
        self.driver.set_track.membervalue = "On"

        stars_to_test = ["Capella", "Castor", "Betelgeuse"]
        self.driver.update_observer()

        for star_name in stars_to_test:
            print(f"\nTargeting star: {star_name}")
            star = ephem.star(star_name)
            star.compute(self.driver.observer)

            ra_hours = float(star.ra) * 12.0 / math.pi
            dec_deg = float(star.dec) * 180.0 / math.pi

            print(
                f"Slewing to {star_name} (RA: {ra_hours:.4f}h, Dec: {dec_deg:.4f}deg)"
            )

            self.driver.ra.membervalue = ra_hours
            self.driver.dec.membervalue = dec_deg

            # Trigger GoTo (via handle_equatorial_goto because set_track is On)
            await self.driver.handle_equatorial_goto(None)

            # Wait for slew completion
            for _ in range(120):
                await self.driver.read_mount_position()
                if self.driver.slewing_light.membervalue == "Idle":
                    break
                await asyncio.sleep(1)

            print(f"Reached {star_name}. Tracking for 15 seconds...")
            # Re-verify tracking light is set correctly by the driver
            await asyncio.sleep(15)

            # Stop motion
            print("Stopping motion...")
            for name in self.driver.track_mode_vector:
                self.driver.track_mode_vector[name] = "Off"
            self.driver.track_none.membervalue = "On"
            await self.driver.handle_track_mode(None)
            await asyncio.sleep(2)


if __name__ == "__main__":
    unittest.main()
