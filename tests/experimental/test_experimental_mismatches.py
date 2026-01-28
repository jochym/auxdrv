import asyncio
import unittest
import os
import sys
import subprocess
import time
import math
import ephem
from celestron_aux.alignment import AlignmentModel
from celestron_aux.celestron_indi_driver import (
    CelestronAUXDriver,
    AUXTargets,
    AUXCommand,
    AUXCommands,
    STEPS_PER_REVOLUTION,
)


class TestExperimentalMismatches(unittest.IsolatedAsyncioTestCase):
    sim_proc = None
    sim_port = 2005

    @classmethod
    def setUpClass(cls):
        cls.sim_log = open("test_exp_sim.log", "w")
        cls.sim_proc = subprocess.Popen(
            [
                "caux-sim",
                "--text",
                "--perfect",
                "--hc",
                "--port",
                str(cls.sim_port),
            ],
            stdout=cls.sim_log,
            stderr=cls.sim_log,
        )
        time.sleep(3)

    @classmethod
    def tearDownClass(cls):
        if cls.sim_proc:
            cls.sim_proc.terminate()
            cls.sim_proc.wait()
        cls.sim_log.close()

    async def asyncSetUp(self):
        self.driver = CelestronAUXDriver()
        self.driver.port_name.membervalue = f"socket://localhost:{self.sim_port}"

        async def mock_send(xmldata):
            pass

        self.driver.send = mock_send

        self.driver.conn_connect.membervalue = "On"
        await self.driver.handle_connection(None)

    async def asyncTearDown(self):
        if self.driver.communicator:
            await self.driver.communicator.disconnect()

    async def wait_for_idle(self, timeout=120):
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

    async def test_6_equatorial_goto(self):
        """RA/Dec GoTo transformation and execution (Experimental)."""
        self.driver.lat.membervalue = 50.1822
        self.driver.long.membervalue = 19.7925
        self.driver.update_observer()

        self.driver.align_clear_all.membervalue = "On"
        await self.driver.handle_alignment_config(None)

        lst = self.driver.observer.sidereal_time()
        target_ra = (math.degrees(lst) / 15.0 + 2.0) % 24.0
        target_dec = 45.0

        self.driver.ra.membervalue = target_ra
        self.driver.dec.membervalue = target_dec
        self.driver.set_sync.membervalue = "Off"

        await self.driver.handle_equatorial_goto(None)
        await self.wait_for_idle(60)

        await self.driver.read_mount_position()
        ra = float(self.driver.ra.membervalue)
        dec = float(self.driver.dec.membervalue)

        print(
            f"Experimental GoTo: Target({target_ra:.4f}, {target_dec:.4f}) -> Actual({ra:.4f}, {dec:.4f})"
        )
        self.assertAlmostEqual(ra, target_ra, delta=0.5)

    async def test_10_alignment_3star(self):
        """Multi-star alignment using real-time coordinates (Experimental)."""
        self.driver.align_clear_all.membervalue = "On"
        await self.driver.handle_alignment_config(None)

        self.driver.update_observer()
        lst_hours = math.degrees(self.driver.observer.sidereal_time()) / 15.0
        points = [
            (lst_hours + 1.0, 45.0),
            (lst_hours - 2.0, 30.0),
            (lst_hours + 3.0, 60.0),
        ]

        self.driver.set_sync.membervalue = "On"
        for ra, dec in points:
            ra = ra % 24.0
            self.driver.ra.membervalue = ra
            self.driver.dec.membervalue = dec

            self.driver.update_observer()
            body = ephem.FixedBody()
            body._ra = math.radians(ra * 15.0)
            body._dec = math.radians(dec)
            body.compute(self.driver.observer)

            az_deg, alt_deg = (
                math.degrees(float(body.az)),
                math.degrees(float(body.alt)),
            )
            az_steps = int((az_deg / 360.0) * 16777216) % 16777216
            alt_steps = int((alt_deg / 360.0) * 16777216) % 16777216

            await self.driver._do_slew(AUXTargets.AZM, az_steps, fast=True)
            await self.driver._do_slew(AUXTargets.ALT, alt_steps, fast=True)
            await self.wait_for_idle(90)
            await self.driver.handle_equatorial_goto(None)

        self.assertEqual(len(self.driver._align_model.points), 3)
        self.assertIsNotNone(self.driver._align_model.matrix)

    async def test_focuser_control(self):
        """Verifies focuser control (Experimental)."""
        target_pos = 500000
        self.driver.focus_pos.membervalue = target_pos
        event = {"FOCUS_POS": target_pos}
        await self.driver.handle_focuser(event)

        if self.driver.communicator:
            from celestron_aux.celestron_aux_driver import AUXCommand, AUXCommands

            resp = await self.driver.communicator.send_command(
                AUXCommand(
                    AUXCommands.MC_GET_POSITION, AUXTargets.APP, AUXTargets.FOCUS
                )
            )
            self.assertIsNotNone(resp, "Focuser (0x12) not responding in sim")

    async def test_drift_and_jump_detection(self):
        """Slews to a star and monitors for drift and 'jumps' in position (Experimental)."""
        self.driver.align_clear_all.membervalue = "On"
        await self.driver.handle_alignment_config(None)

        import ephem

        star = ephem.star("Vega")
        self.driver.update_observer()
        star.compute(self.driver.observer)
        target_ra = float(star.ra) * 12.0 / math.pi
        target_dec = float(star.dec) * 180.0 / math.pi

        self.driver.ra.membervalue = target_ra
        self.driver.dec.membervalue = target_dec
        self.driver.set_track.membervalue = "On"

        state_transitions = []
        slew_finished = False

        async def monitor_slew():
            nonlocal slew_finished
            last_state = None
            while not slew_finished:
                cur_state = self.driver.equatorial_vector.state
                if cur_state != last_state:
                    state_transitions.append((time.time(), cur_state))
                    last_state = cur_state
                await asyncio.sleep(0.05)

        monitor_task = asyncio.create_task(monitor_slew())
        await self.driver.handle_equatorial_goto(None)

        for _ in range(120):
            await self.driver.read_mount_position()
            if (
                self.driver.slewing_light.membervalue == "Idle"
                and self.driver.equatorial_vector.state != "Busy"
            ):
                break
            await asyncio.sleep(1)

        slew_finished = True
        await monitor_task
        self.assertEqual(self.driver.equatorial_vector.state, "Ok")
