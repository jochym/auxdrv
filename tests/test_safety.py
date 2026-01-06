import asyncio
import unittest
import os
import subprocess
import time
from celestron_indi_driver import (
    CelestronAUXDriver,
    AUXTargets,
    AUXCommand,
    AUXCommands,
    pack_int3_steps,
)


class TestSafetyAndAccessories(unittest.IsolatedAsyncioTestCase):
    sim_proc = None
    sim_port = 2002

    @classmethod
    def setUpClass(cls):
        cls.sim_log = open("test_safety_sim.log", "w")
        # Use venv python
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

        async def mock_send(xmldata):
            pass

        self.driver.send = mock_send
        self.driver.conn_connect.membervalue = "On"
        await self.driver.handle_connection(None)

    async def asyncTearDown(self):
        if self.driver.communicator:
            await self.driver.communicator.disconnect()

    async def test_slew_limits(self):
        """Test if the driver prevents moving outside configured limits."""
        # Set limits: Alt [0, 45]
        self.driver.alt_limit_min.membervalue = 0
        self.driver.alt_limit_max.membervalue = 45

        # Try to GoTo 60 deg Alt
        # 60 deg = 60/360 * 2^24 = 2796202
        target_alt = int((60.0 / 360.0) * 16777216)

        success = await self.driver.goto_position(0, target_alt)
        self.assertFalse(success, "Driver allowed GoTo outside Alt limits")

        # Try to GoTo 30 deg Alt (Allowed)
        target_alt = int((30.0 / 360.0) * 16777216)
        success = await self.driver.goto_position(0, target_alt)
        self.assertTrue(success, "Driver blocked GoTo inside Alt limits")

    async def test_focuser_control(self):
        """Test focuser movement."""
        target_pos = 500000
        self.driver.focus_pos.membervalue = target_pos
        # Mocking rxevent for ABS_FOCUS_POSITION
        event = type("obj", (object,), {"vectorname": "ABS_FOCUS_POSITION", "root": []})

        # We need a real-ish event root or just call the handler
        await self.driver.handle_focuser(event)

        # Verify simulator position
        resp = await self.driver.communicator.send_command(
            AUXCommand(AUXCommands.MC_GET_POSITION, AUXTargets.APP, AUXTargets.FOCUS)
        )
        self.assertIsNotNone(resp)
        sim_pos = int(
            (resp.get_data_as_int() / 16777216.0) * 16777216
        )  # Should match target_pos
        self.assertAlmostEqual(sim_pos, target_pos, delta=1)

    async def test_gps_refresh(self):
        """Test GPS data retrieval."""
        self.driver.gps_refresh.membervalue = "On"
        event = type("obj", (object,), {"vectorname": "GPS_REFRESH", "root": []})
        await self.driver.handle_gps_refresh(event)

        # Default simulator GPS: 50d 10' 56" N, 19d 47' 33" E
        # 50 + 10/60 + 56/3600 = 50.18222
        # 19 + 47/60 + 33/3600 = 19.7925
        self.assertAlmostEqual(float(self.driver.lat.membervalue), 50.1822, delta=0.001)
        self.assertAlmostEqual(
            float(self.driver.long.membervalue), 19.7925, delta=0.001
        )

    async def test_cordwrap_config(self):
        """Test cordwrap configuration."""
        self.driver.cordwrap_enable.membervalue = "On"
        event = type("obj", (object,), {"vectorname": "TELESCOPE_CORDWRAP", "root": []})
        await self.driver.handle_cordwrap(event)

        # Verify simulator
        resp = await self.driver.communicator.send_command(
            AUXCommand(AUXCommands.MC_POLL_CORDWRAP, AUXTargets.APP, AUXTargets.AZM)
        )
        self.assertIsNotNone(resp)
        self.assertEqual(resp.data[0], 0xFF)


if __name__ == "__main__":
    unittest.main()
