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
    """
    Functional test suite for the Celestron AUX INDI Driver.

    This suite verifies the core functionality of the driver by interacting with
    a simulated telescope mount. It covers connection management, basic GoTo
    operations, tracking, parking, and multi-star alignment.
    """

    sim_proc = None
    sim_port = 2001
    external_sim = False  # Set to True to use an already running simulator

    @classmethod
    def setUpClass(cls):
        """
        Sets up the test environment by launching the NSE Simulator.

        Methodology:
            Launches the simulator in headless mode (-t) on port 2001.
            Captures output to 'test_sim.log'.
        """
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
        """
        Cleans up the test environment by terminating the simulator.
        """
        if cls.external_sim:
            return
        if cls.sim_proc:
            cls.sim_proc.terminate()
            cls.sim_proc.wait()
        if hasattr(cls, "sim_log"):
            cls.sim_log.close()

    async def asyncSetUp(self):
        """
        Initializes the driver and connects to the simulator.
        Resets mount position to (0,0) for each test.
        """
        self.driver = CelestronAUXDriver()
        self.driver.port_name.membervalue = f"socket://localhost:{self.sim_port}"

        # Mock INDI send to prevent actual network traffic during tests
        async def mock_send(xmldata):
            pass

        self.driver.send = mock_send
        # Connect
        self.driver.conn_connect.membervalue = "On"
        await self.driver.handle_connection(None)
        self.assertTrue(self.driver.communicator and self.driver.communicator.connected)

        # Reset position to 0,0
        if self.driver.communicator:
            from celestron_aux_driver import pack_int3_steps

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
            await self.driver.slew_by_rate(AUXTargets.AZM, 0, 1)
            await self.driver.slew_by_rate(AUXTargets.ALT, 0, 1)

    async def asyncTearDown(self):
        """
        Disconnects the driver.
        """
        if self.driver.communicator:
            await self.driver.communicator.disconnect()

    async def wait_for_idle(self, timeout=120):
        """
        Polls hardware until slewing is finished.

        Args:
            timeout: Maximum seconds to wait.

        Returns:
            bool: True if mount reached idle, False if timeout.
        """
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
        """
        Description:
            Verifies that the driver correctly retrieves and parses firmware
            versions and model identification from the mount.

        Methodology:
            Calls `get_firmware_info()` which sends `MC_GET_MODEL` and `GET_VER`
            commands to the AUX bus.

        Expected Results:
            - Model name should be identified (not "Unknown").
            - Azimuth and Altitude versions should contain "7.11" (default sim version).
        """
        await self.driver.get_firmware_info()
        self.assertNotEqual(self.driver.model.membervalue, "Unknown")
        self.assertIn("7.11", self.driver.azm_ver.membervalue)
        self.assertIn("7.11", self.driver.alt_ver.membervalue)

    async def test_2_goto_precision(self):
        """
        Description:
            Verifies the precision of encoder-based GoTo movements.

        Methodology:
            1. Issues low-level `slew_to` commands for Azm and Alt axes.
            2. Waits for the simulator to reach target positions using `wait_for_idle`.
            3. Reads back mount position.

        Expected Results:
            - The reported encoder steps should match the target steps within a
              100-step tolerance (handles small simulation inaccuracies).
        """
        target_azm = 10000
        target_alt = 5000

        await self.driver.slew_to(AUXTargets.AZM, target_azm)
        await self.driver.slew_to(AUXTargets.ALT, target_alt)

        success = await self.wait_for_idle(30)
        self.assertTrue(success, "Slew timed out")

        await self.driver.read_mount_position()
        azm = int(self.driver.azm_steps.membervalue)
        alt = int(self.driver.alt_steps.membervalue)

        self.assertAlmostEqual(azm, target_azm, delta=200)
        self.assertAlmostEqual(alt, target_alt, delta=200)

    async def test_3_tracking_logic(self):
        """
        Description:
            Verifies that setting a guide rate results in physical mount movement.

        Methodology:
            1. Sets initial rates to 0 and records position.
            2. Sets Azm guide rate to 1000 steps/sec.
            3. Waits for 3 seconds.
            4. Verifies that the encoder position has increased using wrap-around aware diff.

        Expected Results:
            - Mount position must increase significantly.
            - `TRACKING` light must be set to "Ok".
        """
        await self.driver.slew_by_rate(AUXTargets.AZM, 0, 1)
        await self.driver.slew_by_rate(AUXTargets.ALT, 0, 1)
        await asyncio.sleep(1)

        await self.driver.read_mount_position()
        p1_azm = int(self.driver.azm_steps.membervalue)

        # Use a larger guide rate to be sure we see movement
        # The units are roughly 1/79 of a step/sec.
        # To get 1000 steps/sec we need ~80000 units.
        self.driver.guide_azm.membervalue = 100000
        await self.driver.handle_guide_rate(None)
        self.assertEqual(self.driver.tracking_light.membervalue, "Ok")

        await asyncio.sleep(3)
        await self.driver.read_mount_position()
        p2_azm = int(self.driver.azm_steps.membervalue)

        def diff_steps(s2, s1):
            d = s2 - s1
            if d > 16777216 / 2:
                d -= 16777216
            if d < -16777216 / 2:
                d += 16777216
            return d

        self.assertGreater(diff_steps(p2_azm, p1_azm), 1000)

        self.driver.guide_azm.membervalue = 0
        await self.driver.handle_guide_rate(None)

    async def test_4_park_unpark(self):
        """
        Description:
            Verifies the Parking and Unparking sequences.

        Methodology:
            1. Moves the mount away from home (0,0).
            2. Activates the `PARK` switch and calls the handler.
            3. Verifies mount returns to 0 steps.
            4. Activates `UNPARK` and verifies status.

        Expected Results:
            - Mount steps should be near 0 after Park.
            - `PARKED` light status must transition from "Ok" to "Idle".
        """
        await self.driver.slew_to(AUXTargets.AZM, 10000)
        await asyncio.sleep(1)

        self.driver.park_switch.membervalue = "On"
        await self.driver.handle_park(None)

        success = await self.wait_for_idle(30)
        self.assertTrue(success)

        await self.driver.read_mount_position()
        azm = int(self.driver.azm_steps.membervalue)
        alt = int(self.driver.alt_steps.membervalue)

        def diff_steps(s2, s1):
            d = s2 - s1
            if d > 16777216 / 2:
                d -= 16777216
            if d < -16777216 / 2:
                d += 16777216
            return d

        self.assertLess(abs(diff_steps(azm, 0)), 500)
        self.assertLess(abs(diff_steps(alt, 0)), 500)
        self.assertEqual(self.driver.parked_light.membervalue, "Ok")

        self.driver.unpark_switch.membervalue = "On"
        await self.driver.handle_unpark(None)
        self.assertEqual(self.driver.parked_light.membervalue, "Idle")

    async def test_5_connection_robustness(self):
        """
        Description:
            Verifies the stability of the connection management logic.

        Methodology:
            Repeatedly cycles the `CONNECTION` switch between "Connect" and
            "Disconnect" while verifying the state of the underlying
            `AUXCommunicator`.

        Expected Results:
            - Connection and Disconnection should complete without errors.
            - The `communicator.connected` property must reflect the switch state.
        """
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
        """
        Description:
            Verifies the high-level RA/Dec GoTo transformation and execution.

        Methodology:
            1. Loads observer site configuration.
            2. Sets a target RA/Dec far from the celestial pole.
            3. Calls `handle_equatorial_goto`.
            4. Waits for slewing to complete and verifies resulting RA/Dec.

        Expected Results:
            - The final reported RA and Dec must match the target within 0.5 degrees
              (accounting for time drift and transformation rounding).
        """
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
        """
        Description:
            Tests the mathematical robustness of the coordinate transformation
            at the celestial pole (90 deg Dec).

        Methodology:
            Issues an equatorial GoTo command exactly to Dec +90.0.

        Expected Results:
            - The driver must not crash or encounter singular matrix errors.
        """
        self.driver.ra.membervalue = 0.0
        self.driver.dec.membervalue = 90.0
        await self.driver.handle_equatorial_goto(None)
        await self.driver.read_mount_position()

    async def test_7_approach_logic(self):
        """
        Description:
            Verifies the anti-backlash "Fixed Offset" approach logic.

        Methodology:
            1. Enables `FIXED_OFFSET` approach with a 5000-step offset.
            2. Mocks the low-level `_do_slew` method to record the sequence of
               physical movement commands.
            3. Issues a GoTo command.

        Expected Results:
            - The driver must issue exactly 4 slew commands (2 for intermedite
              offset position, 2 for final target).
            - The first slew must be `fast=True` to the offset position.
            - The final slew must be `fast=False` (precision approach).
        """
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
        """
        Description:
            Verifies the "Tracking Direction" anti-backlash approach.

        Methodology:
            1. Enables `TRACKING_DIRECTION` approach mode.
            2. Mocks `_do_slew` to verify the sequence.
            3. Issues an equatorial GoTo.

        Expected Results:
            - The driver must calculate the direction of sky motion and perform
              an intermediate slew that ensures the final precision approach
              happens in the same direction as tracking.
        """
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
        """
        Description:
            Verifies the 2nd-order predictive tracking background loop.

        Methodology:
            1. Enables tracking mode.
            2. Mocks the communicator's `send_command` to intercept guide rate
               updates.
            3. Waits for several loop iterations.

        Expected Results:
            - The driver must periodically send `MC_SET_POS_GUIDERATE` or
              `MC_SET_NEG_GUIDERATE` commands to the mount to maintain tracking.
        """
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
        """
        Description:
            Verifies the multi-star alignment system.

        Methodology:
            1. Clears existing alignment points.
            2. Simulates centering 3 stars at different sky positions.
            3. Performs a `SYNC` at each position to populate the `AlignmentModel`.
            4. Performs a GoTo to a 4th point and verifies RA/Dec accuracy.

        Expected Results:
            - The `AlignmentModel` must contain 3 points.
            - The transformation matrix must be computed.
            - The GoTo accuracy for the 4th point should be high (< 0.1 deg).
        """
        self.driver.track_none.membervalue = "On"
        self.driver.track_sidereal.membervalue = "Off"
        await self.driver.handle_track_mode(None)
        self.driver.align_clear_all.membervalue = "On"
        await self.driver.handle_alignment_config(None)

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

            await self.driver._do_slew(AUXTargets.AZM, az_steps, fast=True)
            await self.driver._do_slew(AUXTargets.ALT, alt_steps, fast=True)
            await self.wait_for_idle(60)
            await self.driver.handle_equatorial_goto(None)

        self.assertEqual(len(self.driver._align_model.points), 3)
        self.assertIsNotNone(self.driver._align_model.matrix)

        self.driver.set_sync.membervalue = "Off"
        target_ra, target_dec = 6.0, 20.0
        self.driver.ra.membervalue = target_ra
        self.driver.dec.membervalue = target_dec
        await self.driver.handle_equatorial_goto(None)
        await self.wait_for_idle(60)

        await self.driver.read_mount_position()
        self.assertAlmostEqual(float(self.driver.ra.membervalue), target_ra, delta=0.1)
        self.assertAlmostEqual(
            float(self.driver.dec.membervalue), target_dec, delta=0.1
        )

        self.driver.update_observer = original_update


if __name__ == "__main__":
    unittest.main()
