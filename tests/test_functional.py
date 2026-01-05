
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

    @classmethod
    def setUpClass(cls):
        # Start simulator and capture output
        cls.sim_log = open('test_sim.log', 'w')
        cls.sim_proc = subprocess.Popen(
            ['./venv/bin/python', 'simulator/nse_simulator.py', '-t', '-p', str(cls.sim_port)],
            stdout=cls.sim_log,
            stderr=cls.sim_log
        )
        time.sleep(2) 

    @classmethod
    def tearDownClass(cls):
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
        await self.driver.slew_to(AUXTargets.AZM, 5000)
        await asyncio.sleep(1)
        
        # Park
        self.driver.park_switch.membervalue = "On"
        await self.driver.handle_park(None)
        
        reached_home = False
        for i in range(15):
            await self.driver.read_mount_position()
            azm = int(self.driver.azm_steps.membervalue)
            # print(f"Park progress {i}: AZM={azm}")
            if azm < 150: # Increased margin
                reached_home = True
                break
            await asyncio.sleep(1)
            
        self.assertTrue(reached_home)
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

if __name__ == "__main__":
    unittest.main()
