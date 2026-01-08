import asyncio
import unittest
import math
import ephem
import os
from celestron_aux.celestron_indi_driver import CelestronAUXDriver


class TestVisualStars(unittest.IsolatedAsyncioTestCase):
    """
    Test suite for visual verification of sky display.
    Points to 3 bright stars visible at the current time.
    """

    sim_port = 2000

    async def asyncSetUp(self):
        self.driver = CelestronAUXDriver()
        self.driver.port_name.membervalue = f"socket://localhost:{self.sim_port}"

        async def mock_send(xmldata):
            pass

        self.driver.send = mock_send

        self.driver.conn_connect.membervalue = "On"
        await self.driver.handle_connection(None)

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

            # Set GoTo mode
            for name in self.driver.coord_set_vector:
                self.driver.coord_set_vector[name] = "Off"
            self.driver.set_slew.membervalue = "On"

            # Trigger GoTo
            await self.driver.handle_equatorial_goto(None)

            # Wait for completion (poll status)
            for _ in range(60):
                await self.driver.read_mount_position()
                if self.driver.slewing_light.membervalue == "Idle":
                    break
                await asyncio.sleep(1)

            print(f"Reached {star_name}. Observing for 5 seconds...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    unittest.main()
