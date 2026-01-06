
import asyncio
import unittest
import os
import signal
import subprocess
import time
from celestron_indi_driver import CelestronAUXDriver, AUXTargets

class TestCelestronAUXFunctional(unittest.IsolatedAsyncioTestCase):
    sim_proc = None
    sim_port = 2001 
    external_sim = False # Set to True to use an already running simulator

    @classmethod
    def setUpClass(cls):
        # Allow override via environment variable
        if os.environ.get('EXTERNAL_SIM'):
            cls.external_sim = True
            cls.sim_port = int(os.environ.get('SIM_PORT', 2000))
            return

        # Start simulator and capture output (unbuffered)
        cls.sim_log = open('test_sim.log', 'w')
        cls.sim_proc = subprocess.Popen(
            ['./venv/bin/python', '-u', 'simulator/nse_simulator.py', '-t', '-p', str(cls.sim_port)],
            stdout=cls.sim_log,
            stderr=cls.sim_log
        )
        time.sleep(2) 

    @classmethod
    def tearDownClass(cls):
        if cls.external_sim:
            return
        if cls.sim_proc:
            cls.sim_proc.terminate()
            cls.sim_proc.wait()
        if hasattr(cls, 'sim_log'):
            cls.sim_log.close()

    async def asyncSetUp(self):
        self.driver = CelestronAUXDriver()
        self.driver.port_name.membervalue = f"socket://localhost:{self.sim_port}"
        # Mock INDI send to avoid errors without a server
        self.driver.send = self.mock_send
        # Connect
        self.driver.conn_connect.membervalue = "On"
        await self.driver.handle_connection(None)
        self.assertTrue(self.driver.communicator and self.driver.communicator.connected)

    async def asyncTearDown(self):
        if self.driver.communicator:
            await self.driver.communicator.disconnect()

    async def mock_send(self, xmldata):
        pass

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
        
        # Wait for movement to complete
        reached = False
        for _ in range(15):
            await self.driver.read_mount_position()
            azm = int(self.driver.azm_steps.membervalue)
            alt = int(self.driver.alt_steps.membervalue)
            # Fast slew in simulator has some error margin
            if abs(azm - target_azm) < 500 and abs(alt - target_alt) < 500:
                reached = True
                break
            await asyncio.sleep(1)
        
        self.assertTrue(reached, f"Target not reached. Final pos: AZM={self.driver.azm_steps.membervalue}, ALT={self.driver.alt_steps.membervalue}")

    async def test_3_tracking_logic(self):
        """Test if tracking (Guide Rate) actually moves the mount."""
        # Stop any movement first
        await self.driver.slew_by_rate(AUXTargets.AZM, 0, 1)
        await self.driver.slew_by_rate(AUXTargets.ALT, 0, 1)
        await asyncio.sleep(1)
        
        await self.driver.read_mount_position()
        p1_azm = int(self.driver.azm_steps.membervalue)
        
        # Set guide rate
        self.driver.guide_azm.membervalue = 200
        await self.driver.handle_guide_rate(None)
        
        self.assertEqual(self.driver.tracking_light.membervalue, "Ok")
        
        await asyncio.sleep(3)
        await self.driver.read_mount_position()
        p2_azm = int(self.driver.azm_steps.membervalue)
        
        self.assertGreater(p2_azm, p1_azm, "Mount should move forward when tracking is on")
        
        # Stop tracking
        self.driver.guide_azm.membervalue = 0
        await self.driver.handle_guide_rate(None)
        self.assertEqual(self.driver.tracking_light.membervalue, "Idle")

    async def test_4_park_unpark(self):
        """Test Park and Unpark functionality."""
        # Move away from 0,0
        await self.driver.slew_to(AUXTargets.AZM, 10000)
        await asyncio.sleep(2)
        
        # Park
        self.driver.park_switch.membervalue = "On"
        await self.driver.handle_park(None)
        
        reached_home = False
        for i in range(20):
            await self.driver.read_mount_position()
            azm = int(self.driver.azm_steps.membervalue)
            alt = int(self.driver.alt_steps.membervalue)
            
            # Distance to 0 with wrap-around
            dist_azm = min(azm, 16777216 - azm)
            dist_alt = min(alt, 16777216 - alt)
            
            if dist_azm < 1000 and dist_alt < 1000: 
                reached_home = True
                break
            await asyncio.sleep(1)
            
        self.assertTrue(reached_home, f"Park failed to reach home. Current: AZM={self.driver.azm_steps.membervalue}")
        self.assertEqual(self.driver.parked_light.membervalue, "Ok")
        
        # Unpark
        self.driver.unpark_switch.membervalue = "On"
        await self.driver.handle_unpark(None)
        self.assertEqual(self.driver.parked_light.membervalue, "Idle")

    async def test_5_connection_robustness(self):
        """Test disconnecting and reconnecting multiple times."""
        for i in range(3):
            # Disconnect
            self.driver.conn_connect.membervalue = "Off"
            self.driver.conn_disconnect.membervalue = "On"
            await self.driver.handle_connection(None)
            self.assertTrue(self.driver.communicator is None or not self.driver.communicator.connected)
            
            # Reconnect
            self.driver.conn_connect.membervalue = "On"
            self.driver.conn_disconnect.membervalue = "Off"
            await self.driver.handle_connection(None)
            self.assertTrue(self.driver.communicator and self.driver.communicator.connected)

    async def test_6_equatorial_goto(self):
        """Test GoTo movement using RA/Dec coordinates."""
        # Location is loaded from config.yaml by default in the driver,
        # but we can set it explicitly to be sure.
        import yaml
        with open('config.yaml', 'r') as f:
            cfg = yaml.safe_load(f).get('observer', {})
        
        self.driver.lat.membervalue = cfg.get('latitude', 50.1822)
        self.driver.long.membervalue = cfg.get('longitude', 19.7925)
        self.driver.update_observer()
        
        # Target RA/Dec (Polaris approx)
        self.driver.ra.membervalue = 2.5
        self.driver.dec.membervalue = 89.2
        
        await self.driver.handle_equatorial_goto(None)
        
        # Wait for movement to complete
        reached = False
        for _ in range(15):
            await self.driver.read_mount_position()
            # Check if reported RA/Dec is near target
            ra = float(self.driver.ra.membervalue)
            dec = float(self.driver.dec.membervalue)
            # print(f"Eq GoTo progress: RA={ra:.3f}, DEC={dec:.3f}")
            if abs(ra - 2.5) < 0.1 and abs(dec - 89.2) < 0.5:
                reached = True
                break
            await asyncio.sleep(1)
            
        self.assertTrue(reached, f"RA/Dec target not reached. Final: RA={self.driver.ra.membervalue}, DEC={self.driver.dec.membervalue}")

    async def test_10_alignment_3star(self):
        """Test 3-star alignment system."""
        # 1. Clear existing alignment
        self.driver.clear_align.membervalue = "On"
        await self.driver.handle_clear_alignment(None)
        self.assertEqual(len(self.driver._align_model.points), 0)
        
        # 2. Add 3 alignment points
        points = [
            (2.0, 45.0), # RA, Dec
            (14.0, 20.0),
            (20.0, -10.0)
        ]
        
        # Turn on Sidereal Tracking to keep RA/Dec fixed in Alt/Az
        self.driver.track_sidereal.membervalue = "On"
        self.driver.track_none.membervalue = "Off"
        await self.driver.handle_track_mode(None)
        
        # Set to SYNC mode
        self.driver.set_slew.membervalue = "Off"
        self.driver.set_sync.membervalue = "On"
        
        for ra, dec in points:
            # Move to target (manually using goto_position or handle_equatorial_goto in SLEW mode)
            # To simulate a user centering a star, we'll just force the position
            self.driver.set_slew.membervalue = "On"
            self.driver.set_sync.membervalue = "Off"
            self.driver.ra.membervalue = ra
            self.driver.dec.membervalue = dec
            await self.driver.handle_equatorial_goto(None)
            
            # Now "Center" it and Sync
            self.driver.set_slew.membervalue = "Off"
            self.driver.set_sync.membervalue = "On"
            self.driver.ra.membervalue = ra # User confirms these are RA/Dec of currently centered star
            self.driver.dec.membervalue = dec
            await self.driver.handle_equatorial_goto(None)
            
        self.assertEqual(len(self.driver._align_model.points), 3)
        self.assertIsNotNone(self.driver._align_model.matrix)
        
        # 3. Test GoTo accuracy with alignment
        self.driver.set_slew.membervalue = "On"
        self.driver.set_sync.membervalue = "Off"
        
        target_ra, target_dec = 10.0, 10.0
        self.driver.ra.membervalue = target_ra
        self.driver.dec.membervalue = target_dec
        await self.driver.handle_equatorial_goto(None)
        
        await self.driver.read_mount_position()
        
        ra = float(self.driver.ra.membervalue)
        dec = float(self.driver.dec.membervalue)
        
        self.assertAlmostEqual(ra, target_ra, delta=0.1)
        self.assertAlmostEqual(dec, target_dec, delta=0.5)

    async def test_7_approach_logic(self):
        """Test anti-backlash approach logic (two-stage movement)."""
        # Enable FIXED_OFFSET approach
        self.driver.approach_disabled.membervalue = "Off"
        self.driver.approach_fixed.membervalue = "On"
        self.driver.approach_azm_offset.membervalue = 5000
        self.driver.approach_alt_offset.membervalue = 5000
        
        target_azm = 20000
        target_alt = 10000
        
        # Track calls to _do_slew
        slew_calls = []
        original_do_slew = self.driver._do_slew
        async def mock_do_slew(axis, steps, fast=True):
            slew_calls.append((axis, steps, fast))
            return await original_do_slew(axis, steps, fast)
        
        self.driver._do_slew = mock_do_slew
        
        await self.driver.goto_position(target_azm, target_alt)
        
        # Should have 4 calls (2 axes * 2 stages)
        self.assertEqual(len(slew_calls), 4)
        
        # Stage 1: Fast to intermediate
        self.assertEqual(slew_calls[0][1], target_azm - 5000)
        self.assertTrue(slew_calls[0][2])
        
        # Stage 2: Slow to final
        self.assertEqual(slew_calls[2][1], target_azm)
        self.assertFalse(slew_calls[2][2])

    async def test_8_approach_tracking_direction(self):
        """Test anti-backlash approach in tracking direction."""
        # Set location
        self.driver.lat.membervalue = 50.06
        self.driver.long.membervalue = 19.94
        self.driver.update_observer()
        
        ra, dec = 2.5, 80.0 # Use 80 deg Dec to ensure more measurable tracking rates
        
        # Enable TRACKING_DIRECTION approach
        self.driver.approach_disabled.membervalue = "Off"
        self.driver.approach_tracking.membervalue = "On"
        self.driver.approach_azm_offset.membervalue = 5000
        self.driver.approach_alt_offset.membervalue = 5000
        
        slew_calls = []
        original_do_slew = self.driver._do_slew
        async def mock_do_slew(axis, steps, fast=True):
            slew_calls.append((axis, steps, fast))
            return await original_do_slew(axis, steps, fast)
        self.driver._do_slew = mock_do_slew
        
        target_azm, target_alt = await self.driver.equatorial_to_steps(ra, dec)
        await self.driver.goto_position(target_azm, target_alt, ra=ra, dec=dec)
        
        self.assertEqual(len(slew_calls), 4)
        
        # Verify direction matches tracking rate
        rate_azm, rate_alt = await self.driver.get_tracking_rates(ra, dec)
        azm_sign = 1 if rate_azm >= 0 else -1
        alt_sign = 1 if rate_alt >= 0 else -1
        
        expected_inter_azm = (target_azm - azm_sign * 5000) % 16777216
        expected_inter_alt = (target_alt - alt_sign * 5000) % 16777216
        
        self.assertEqual(slew_calls[0][1], expected_inter_azm)
        self.assertEqual(slew_calls[1][1], expected_inter_alt)

    async def test_9_predictive_tracking(self):
        """Test 2nd order predictive tracking loop."""
        # Target some object
        self.driver.ra.membervalue = 12.0
        self.driver.dec.membervalue = 45.0
        
        # Enable tracking
        self.driver.track_none.membervalue = "Off"
        self.driver.track_sidereal.membervalue = "On"
        
        await self.driver.handle_track_mode(None)
        self.assertIsNotNone(self.driver._tracking_task)
        
        # Track guide rate commands
        recorded_cmds = []
        original_send = self.driver.communicator.send_command
        async def mock_send(cmd):
            from celestron_aux_driver import AUXCommands
            if cmd.command in (AUXCommands.MC_SET_POS_GUIDERATE, AUXCommands.MC_SET_NEG_GUIDERATE):
                recorded_cmds.append(cmd)
            return await original_send(cmd)
        
        self.driver.communicator.send_command = mock_send
        
        # Wait for loop to run
        await asyncio.sleep(2.5)
        
        # Check if commands were sent
        self.assertGreaterEqual(len(recorded_cmds), 2)
        
        # Stop tracking
        self.driver.track_none.membervalue = "On"
        await self.driver.handle_track_mode(None)
        self.assertIsNone(self.driver._tracking_task)

if __name__ == "__main__":
    unittest.main()
