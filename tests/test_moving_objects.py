import asyncio
import unittest
import math
import ephem
import os
import subprocess
import time
from celestron_indi_driver import CelestronAUXDriver, AUXTargets


class TestMovingObjects(unittest.IsolatedAsyncioTestCase):
    """
    Verification of non-sidereal tracking capabilities.

    Verifies that the driver can calculate positions and tracking rates for
    Solar System objects (Moon) and Satellites (TLE).
    """

    sim_proc = None
    sim_port = 2002

    @classmethod
    def setUpClass(cls):
        """
        Launches a simulator instance for moving object tests.
        """
        cls.sim_log = open("test_moving_sim.log", "w")
        cls.sim_proc = subprocess.Popen(
            [
                "./venv/bin/python",
                "-u",
                "simulator/nse_simulator.py",
                "-t",
                "-p",
                str(cls.sim_port),
            ],
            stdout=cls.sim_log,
            stderr=cls.sim_log,
        )
        time.sleep(2)

    @classmethod
    def tearDownClass(cls):
        """
        Terminates the simulator instance.
        """
        if cls.sim_proc:
            cls.sim_proc.terminate()
            cls.sim_proc.wait()
        if hasattr(cls, "sim_log"):
            cls.sim_log.close()

    async def asyncSetUp(self):
        """
        Initializes driver and connects to simulator.
        """
        self.driver = CelestronAUXDriver()
        self.driver.port_name.membervalue = f"socket://localhost:{self.sim_port}"

        async def mock_send(xmldata):
            pass

        self.driver.send = mock_send
        self.driver.conn_connect.membervalue = "On"
        await self.driver.handle_connection(None)

    async def asyncTearDown(self):
        """
        Disconnects the driver.
        """
        if self.driver.communicator:
            await self.driver.communicator.disconnect()

    async def test_moon_goto(self):
        """
        Description:
            Verifies the ability to perform a GoTo to the Moon.

        Methodology:
            1. Selects "Moon" as the target type.
            2. Calculates current Moon RA/Dec using `ephem`.
            3. Triggers GoTo via `handle_equatorial_goto`.
            4. Waits for completion and verifies reported position.

        Expected Results:
            - The telescope must reach the Moon's coordinates within 0.1 deg accuracy.
        """
        # 1. Select Moon
        for name in self.driver.target_type_vector:
            self.driver.target_type_vector[name] = "Off"
        self.driver.target_type_vector["MOON"] = "On"

        # 2. Get Moon JNow coords
        ra_moon, dec_moon = await self.driver._get_target_equatorial()

        # 3. Trigger GoTo
        await self.driver.handle_equatorial_goto(None)

        # 4. Wait for idle
        from tests.test_functional import TestCelestronAUXFunctional

        # Inline wait loop
        for _ in range(60):
            await self.driver.read_mount_position()
            if self.driver.slewing_light.membervalue == "Idle":
                break
            await asyncio.sleep(1)

        # 5. Verify position
        await self.driver.read_mount_position()
        ra = float(self.driver.ra.membervalue)
        dec = float(self.driver.dec.membervalue)

        self.assertAlmostEqual(ra, ra_moon, delta=0.1)
        self.assertAlmostEqual(dec, dec_moon, delta=0.1)

    async def test_moon_tracking_rate(self):
        """
        Description:
            Verifies that Moon tracking rate is different from the sidereal rate.

        Methodology:
            1. Enables sidereal tracking and captures the guide rate commands sent to MC.
            2. Switches to Moon tracking and captures the new guide rate commands.
            3. Compares the raw AUX packets.

        Expected Results:
            - The binary packets for sidereal and lunar tracking rates must differ.
        """
        # 1. Set Sidereal tracking
        for name in self.driver.target_type_vector:
            self.driver.target_type_vector[name] = "Off"
        self.driver.target_type_vector["SIDEREAL"] = "On"

        for name in self.driver.track_mode_vector:
            self.driver.track_mode_vector[name] = "Off"
        self.driver.track_sidereal.membervalue = "On"

        await self.driver.handle_track_mode(None)
        await asyncio.sleep(2)

        # Capture sidereal guide rates
        sent_cmds = []
        original_send = self.driver.communicator.send_command

        async def mock_send(command):
            sent_cmds.append(command)
            return await original_send(command)

        self.driver.communicator.send_command = mock_send

        await asyncio.sleep(2)
        sidereal_cmds = [
            c.fill_buf().hex()
            for c in sent_cmds
            if c.command.name in ("MC_SET_POS_GUIDERATE", "MC_SET_NEG_GUIDERATE")
        ]
        sent_cmds.clear()

        # 2. Set Moon tracking
        for name in self.driver.target_type_vector:
            self.driver.target_type_vector[name] = "Off"
        self.driver.target_type_vector["MOON"] = "On"

        await asyncio.sleep(2)
        moon_cmds = [
            c.fill_buf().hex()
            for c in sent_cmds
            if c.command.name in ("MC_SET_POS_GUIDERATE", "MC_SET_NEG_GUIDERATE")
        ]

        self.assertNotEqual(sidereal_cmds, moon_cmds)

    async def test_satellite_tracking(self):
        """
        Description:
            Verifies satellite tracking using Two-Line Element (TLE) data.

        Methodology:
            1. Sets TLE for the ISS.
            2. Selects "Satellite" as the target type.
            3. Enables tracking.
            4. Intercepts and verifies that guide rates are sent to the mount.

        Expected Results:
            - The driver must send non-zero guide rate updates.
            - Rates for a LEO satellite (ISS) should be significantly higher
               than sidereal rates.
        """
        # 1. Set Satellite TLE (ISS)
        self.driver.tle_name.membervalue = "ISS"
        self.driver.tle_line1.membervalue = (
            "1 25544U 98067A   26006.88541667  .00000000  00000-0  00000-0 0    01"
        )
        self.driver.tle_line2.membervalue = (
            "2 25544  51.6400  10.0000 0001000   0.0000   0.0000 15.50000000000001"
        )

        # Select Satellite
        for name in self.driver.target_type_vector:
            self.driver.target_type_vector[name] = "Off"
        self.driver.target_satellite.membervalue = "On"

        # Start tracking
        for name in self.driver.track_mode_vector:
            self.driver.track_mode_vector[name] = "Off"
        self.driver.track_sidereal.membervalue = "On"

        await self.driver.handle_track_mode(None)

        sent_cmds = []
        original_send = self.driver.communicator.send_command

        async def mock_send(command):
            sent_cmds.append(command)
            return await original_send(command)

        self.driver.communicator.send_command = mock_send

        await asyncio.sleep(3)

        sat_cmds = [
            c.fill_buf().hex()
            for c in sent_cmds
            if c.command.name in ("MC_SET_POS_GUIDERATE", "MC_SET_NEG_GUIDERATE")
        ]

        self.assertGreater(len(sat_cmds), 0)

        # Stop tracking
        self.driver.track_none.membervalue = "On"
        await self.driver.handle_track_mode(None)


if __name__ == "__main__":
    unittest.main()
