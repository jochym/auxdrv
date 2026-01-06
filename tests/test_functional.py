import asyncio
import unittest
import os
import signal
import subprocess
import time
import math
import ephem
from celestron_indi_driver import (
    CelestronAUXDriver,
    AUXTargets,
    AUXCommand,
    AUXCommands,
)


class TestCelestronAUXFunctional(unittest.IsolatedAsyncioTestCase):
    sim_proc = None
    sim_port = 2001
    external_sim = False  # Set to True to use an already running simulator

    @classmethod
    def setUpClass(cls):
        # Allow override via environment variable
        if os.environ.get("EXTERNAL_SIM"):
            cls.external_sim = True
            cls.sim_port = int(os.environ.get("SIM_PORT", 2000))
            return

        # Start simulator and capture output (unbuffered)
        cls.sim_log = open("test_sim.log", "w")
        cls.sim_proc = subprocess.Popen(
            [
                "./venv/bin/python",
                "-u",
                "simulator/nse_simulator.py",
                "-t",
                "-d",
                "-p",
                str(cls.sim_port),
            ],
            stdout=cls.sim_log,
            stderr=cls.sim_log,
        )
        time.sleep(2)

    @classmethod
    def tearDownClass(cls):
        if cls.external_sim:
            return
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
        # Connect
        self.driver.conn_connect.membervalue = "On"
        await self.driver.handle_connection(None)
        self.assertTrue(self.driver.communicator and self.driver.communicator.connected)

    async def asyncTearDown(self):
        if self.driver.communicator:
            await self.driver.communicator.disconnect()

    async def wait_for_idle(self, timeout=120):
        """Polls hardware until slewing is finished."""
        if not self.driver.communicator:
            return False
        for _ in range(timeout):
            r_azm = await self.driver.communicator.send_command(
                AUXCommand(AUXCommands.MC_SLEW_DONE, AUXTargets.APP, AUXTargets.AZM)
            )
            r_alt = await self.driver.communicator.send_command(
                AUXCommand(AUXCommands.MC_SLEW_DONE, AUXTargets.APP, AUXTargets.ALT)
            )
            if r_azm and r_alt and r_azm.data[0] == 0xFF and r_alt.data[0] == 0xFF:
                return True
            await asyncio.sleep(1)
        return False

    async def test_1_firmware_info(self):
        """Test if firmware info is correctly retrieved."""
        await self.driver.get_firmware_info()
        self.assertNotEqual(self.driver.model.membervalue, "Unknown")
        self.assertIn("7.11", self.driver.azm_ver.membervalue)
        self.assertIn("7.11", self.driver.alt_ver.membervalue)

    async def test_2_goto_precision(self):
        """Test GoTo movement precision in both axes."""
        target_azm = 10000
        target_alt = 5000

        await self.driver.slew_to(AUXTargets.AZM, target_azm)
        await self.driver.slew_to(AUXTargets.ALT, target_alt)

        success = await self.wait_for_idle(30)
        self.assertTrue(success, "Slew timed out")

        await self.driver.read_mount_position()
        azm = int(self.driver.azm_steps.membervalue)
        alt = int(self.driver.alt_steps.membervalue)

        self.assertAlmostEqual(azm, target_azm, delta=100)
        self.assertAlmostEqual(alt, target_alt, delta=100)

    async def test_3_tracking_logic(self):
        """Test if tracking (Guide Rate) actually moves the mount."""
        await self.driver.slew_by_rate(AUXTargets.AZM, 0, 1)
        await self.driver.slew_by_rate(AUXTargets.ALT, 0, 1)
        await asyncio.sleep(1)

        await self.driver.read_mount_position()
        p1_azm = int(self.driver.azm_steps.membervalue)

        # Use a larger guide rate to be sure we see movement
        self.driver.guide_azm.membervalue = 1000
        await self.driver.handle_guide_rate(None)
        self.assertEqual(self.driver.tracking_light.membervalue, "Ok")

        await asyncio.sleep(3)
        await self.driver.read_mount_position()
        p2_azm = int(self.driver.azm_steps.membervalue)

        self.assertGreater(p2_azm, p1_azm)

        self.driver.guide_azm.membervalue = 0
        await self.driver.handle_guide_rate(None)

    async def test_4_park_unpark(self):
        """Test Park and Unpark functionality."""
        await self.driver.slew_to(AUXTargets.AZM, 10000)
        await asyncio.sleep(1)

        self.driver.park_switch.membervalue = "On"
        await self.driver.handle_park(None)

        success = await self.wait_for_idle(30)
        self.assertTrue(success)

        await self.driver.read_mount_position()
        azm = int(self.driver.azm_steps.membervalue)
        alt = int(self.driver.alt_steps.membervalue)

        dist_azm = min(azm, 16777216 - azm)
        dist_alt = min(alt, 16777216 - alt)

        self.assertLess(dist_azm, 500)
        self.assertEqual(self.driver.parked_light.membervalue, "Ok")

        self.driver.unpark_switch.membervalue = "On"
        await self.driver.handle_unpark(None)
        self.assertEqual(self.driver.parked_light.membervalue, "Idle")

    async def test_5_connection_robustness(self):
        """Test disconnecting and reconnecting multiple times."""
        for i in range(3):
            self.driver.conn_connect.membervalue = "Off"
            self.driver.conn_disconnect.membervalue = "On"
            await self.driver.handle_connection(None)
            self.assertTrue(
                self.driver.communicator is None
                or not self.driver.communicator.connected
            )

            self.driver.conn_connect.membervalue = "On"
            self.driver.conn_disconnect.membervalue = "Off"
            await self.driver.handle_connection(None)
            self.assertTrue(
                self.driver.communicator and self.driver.communicator.connected
            )

    async def test_6_equatorial_goto(self):
        """Test GoTo movement using RA/Dec coordinates."""
        import yaml

        with open("config.yaml", "r") as f:
            cfg = yaml.safe_load(f).get("observer", {})

        self.driver.lat.membervalue = cfg.get("latitude", 50.1822)
        self.driver.long.membervalue = cfg.get("longitude", 19.7925)
        self.driver.update_observer()

        # Fixed point far from pole
        target_ra = 14.0
        target_dec = 30.0
        self.driver.ra.membervalue = target_ra
        self.driver.dec.membervalue = target_dec

        await self.driver.handle_equatorial_goto(None)
        await self.wait_for_idle(40)

        await self.driver.read_mount_position()
        ra = float(self.driver.ra.membervalue)
        dec = float(self.driver.dec.membervalue)

        self.assertAlmostEqual(ra, target_ra, delta=0.5)
        self.assertAlmostEqual(dec, target_dec, delta=0.5)

    async def test_6b_robustness_pole(self):
        """Test if the driver handles exactly 90 deg Dec without crashing."""
        self.driver.ra.membervalue = 0.0
        self.driver.dec.membervalue = 90.0
        await self.driver.handle_equatorial_goto(None)
        await self.driver.read_mount_position()

    async def test_7_approach_logic(self):
        """Test anti-backlash approach logic."""
        self.driver.approach_disabled.membervalue = "Off"
        self.driver.approach_fixed.membervalue = "On"
        self.driver.approach_azm_offset.membervalue = 5000
        self.driver.approach_alt_offset.membervalue = 5000

        target_azm = 20000
        target_alt = 10000

        # Monitor slew calls
        slew_calls = []
        original_do_slew = self.driver._do_slew

        async def mock_do_slew(axis, steps, fast=True):
            slew_calls.append((axis, steps, fast))
            return await original_do_slew(axis, steps, fast)

        self.driver._do_slew = mock_do_slew

        await self.driver.goto_position(target_azm, target_alt)
        await self.wait_for_idle(20)

        self.assertEqual(len(slew_calls), 4)
        self.assertEqual(slew_calls[0][1], target_azm - 5000)
        self.assertTrue(slew_calls[0][2])
        self.assertEqual(slew_calls[2][1], target_azm)
        self.assertFalse(slew_calls[2][2])

    async def test_8_approach_tracking_direction(self):
        """Test anti-backlash approach in tracking direction."""
        ra, dec = 2.5, 60.0
        self.driver.approach_disabled.membervalue = "Off"
        self.driver.approach_tracking.membervalue = "On"

        slew_calls = []
        original_do_slew = self.driver._do_slew

        async def mock_do_slew(axis, steps, fast=True):
            slew_calls.append((axis, steps, fast))
            return await original_do_slew(axis, steps, fast)

        self.driver._do_slew = mock_do_slew

        target_azm, target_alt = await self.driver.equatorial_to_steps(ra, dec)
        await self.driver.goto_position(target_azm, target_alt, ra=ra, dec=dec)
        await self.wait_for_idle(20)

        self.assertEqual(len(slew_calls), 4)

    async def test_9_predictive_tracking(self):
        """Test 2nd order predictive tracking loop."""
        self.driver.ra.membervalue = 12.0
        self.driver.dec.membervalue = 45.0
        self.driver.track_none.membervalue = "Off"
        self.driver.track_sidereal.membervalue = "On"

        await self.driver.handle_track_mode(None)

        recorded_cmds = []
        if self.driver.communicator:
            original_send = self.driver.communicator.send_command

            async def mock_send(command):
                if command.command in (
                    AUXCommands.MC_SET_POS_GUIDERATE,
                    AUXCommands.MC_SET_NEG_GUIDERATE,
                ):
                    recorded_cmds.append(command)
                return await original_send(command)

            self.driver.communicator.send_command = mock_send

        await asyncio.sleep(2.5)
        self.assertGreaterEqual(len(recorded_cmds), 2)

        self.driver.track_none.membervalue = "On"
        await self.driver.handle_track_mode(None)

    async def test_10_alignment_3star(self):
        """Test 3-star alignment system."""
        self.driver.track_none.membervalue = "On"
        self.driver.track_sidereal.membervalue = "Off"
        await self.driver.handle_track_mode(None)
        await self.driver.handle_clear_alignment(None)

        fixed_date = ephem.Date("2026/1/6 12:00:00")
        self.driver.observer.date = fixed_date
        self.driver.observer.epoch = fixed_date

        original_update = self.driver.update_observer

        def patched_update(time_offset: float = 0):
            self.driver.observer.date = ephem.Date(fixed_date + time_offset / 86400.0)
            self.driver.observer.epoch = self.driver.observer.date

        self.driver.update_observer = patched_update

        points = [(2.0, 45.0), (10.0, 30.0), (18.0, 60.0)]
        self.driver.set_sync.membervalue = "On"

        for ra, dec in points:
            self.driver.ra.membervalue = ra
            self.driver.dec.membervalue = dec
            body = ephem.FixedBody()
            body._ra = math.radians(ra * 15.0)
            body._dec = math.radians(dec)
            body._epoch = fixed_date
            body.compute(self.driver.observer)

            az_steps = int((math.degrees(float(body.az)) / 360.0) * 16777216) % 16777216
            alt_steps = (
                int((math.degrees(float(body.alt)) / 360.0) * 16777216) % 16777216
            )

            await self.driver._do_slew(AUXTargets.AZM, az_steps, fast=False)
            await self.driver._do_slew(AUXTargets.ALT, alt_steps, fast=False)
            await self.wait_for_idle(30)
            await self.driver.handle_equatorial_goto(None)

        self.assertEqual(len(self.driver._align_model.points), 3)
        self.assertIsNotNone(self.driver._align_model.matrix)

        self.driver.set_sync.membervalue = "Off"
        target_ra, target_dec = 6.0, 20.0
        self.driver.ra.membervalue = target_ra
        self.driver.dec.membervalue = target_dec
        await self.driver.handle_equatorial_goto(None)
        await self.wait_for_idle(30)

        await self.driver.read_mount_position()
        self.assertAlmostEqual(float(self.driver.ra.membervalue), target_ra, delta=0.1)
        self.assertAlmostEqual(
            float(self.driver.dec.membervalue), target_dec, delta=0.1
        )

        self.driver.update_observer = original_update


if __name__ == "__main__":
    unittest.main()
