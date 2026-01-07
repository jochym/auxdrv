import asyncio
import unittest
import math
import ephem
import os
import subprocess
import time
from celestron_indi_driver import CelestronAUXDriver, AUXTargets


class TestMovingObjects(unittest.IsolatedAsyncioTestCase):
    sim_proc = None
    sim_port = 2002

    @classmethod
    def setUpClass(cls):
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
        if cls.sim_proc:
            cls.sim_proc.terminate()
            cls.sim_proc.wait()
        if hasattr(cls, "sim_log"):
            cls.sim_log.close()

    async def asyncSetUp(self):
        self.driver = CelestronAUXDriver()
        self.driver.port_name.membervalue = f"socket://localhost:{self.sim_port}"

        # Mock INDI send
        async def mock_send(xmldata):
            pass

        self.driver.send = mock_send

        # Connect (Assumes simulator is running on 2001)
        self.driver.conn_connect.membervalue = "On"
        await self.driver.handle_connection(None)

    async def asyncTearDown(self):
        if self.driver.communicator:
            await self.driver.communicator.disconnect()

    async def test_moon_goto(self):
        """Test GoTo Moon functionality."""
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

        # We need wait_for_idle from there or re-implement
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
        """Verify that Moon tracking rate differs from sidereal."""
        # Sidereal rate is approx 15 arcsec/sec in RA

        # 1. Set Sidereal tracking
        for name in self.driver.target_type_vector:
            self.driver.target_type_vector[name] = "Off"
        self.driver.target_type_vector["SIDEREAL"] = "On"

        for name in self.driver.track_mode_vector:
            self.driver.track_mode_vector[name] = "Off"
        self.driver.track_mode_vector["TRACK_SIDEREAL"] = "On"

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
        """Verify that Satellite tracking works with TLE."""
        # 1. Set Satellite TLE (ISS)
        # Using a date near the TLE epoch to ensure it's above horizon/calculable
        # ISS TLE from the code: epoch 26006.88541667 (Jan 6, 2026)

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
        self.driver.track_sidereal.membervalue = (
            "On"  # Any tracking mode except TRACK_OFF starts the loop
        )

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
        # Satellite rates should be much higher than sidereal
        # Sidereal is ~15"/s. ISS is ~1 deg/s = 3600"/s.

        # Stop tracking
        self.driver.track_none.membervalue = "On"
        await self.driver.handle_track_mode(None)


if __name__ == "__main__":
    unittest.main()
