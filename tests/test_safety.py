import asyncio
import unittest
import os
import subprocess
import time
from celestron_aux.celestron_indi_driver import (
    CelestronAUXDriver,
    AUXTargets,
    AUXCommand,
    AUXCommands,
    pack_int3_steps,
)


class TestSafetyAndAccessories(unittest.IsolatedAsyncioTestCase):
    """
    Test suite for safety features and accessory control.

    Verifies that the driver correctly enforces movement limits, handles
    cord-wrap prevention, and communicates with auxiliary components like
    Focuser and GPS modules.
    """

    sim_proc = None
    sim_port = 2002
    external_sim = False

    @classmethod
    def setUpClass(cls):
        """
        Launches a dedicated simulator instance for safety tests.
        """
        if os.environ.get("EXTERNAL_SIM"):
            cls.external_sim = True
            cls.sim_port = int(os.environ.get("SIM_PORT", 2000))
            return

        cls.sim_log = open("test_safety_sim.log", "w")
        cls.sim_proc = subprocess.Popen(
            [
                "./venv/bin/python",
                "-u",
                "src/celestron_aux/simulator/nse_simulator.py",
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
        if cls.external_sim:
            return
        if cls.sim_proc:
            cls.sim_proc.terminate()
            cls.sim_proc.wait()
        if hasattr(cls, "sim_log"):
            cls.sim_log.close()

    async def asyncSetUp(self):
        """
        Connects the driver to the simulator.
        """
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
            from celestron_aux.celestron_indi_driver import AUXCommand, AUXCommands

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

    async def test_slew_limits(self):
        """
        Description:
            Verifies that the driver prevents movement to positions outside the
            configured Altitude/Azimuth limits.

        Methodology:
            1. Sets Altitude limits to [0, 45] degrees.
            2. Attempts a GoTo to 60 degrees.
            3. Attempts a GoTo to 30 degrees.

        Expected Results:
            - The GoTo to 60 degrees must return `False` (blocked by driver).
            - The GoTo to 30 degrees must return `True` (allowed).
        """
        # Set limits: Alt [0, 45]
        self.driver.alt_limit_min.membervalue = 0
        self.driver.alt_limit_max.membervalue = 45

        # Try to GoTo 60 deg Alt
        target_alt = int((60.0 / 360.0) * 16777216)

        success = await self.driver.goto_position(0, target_alt)
        self.assertFalse(success, "Driver allowed GoTo outside Alt limits")

        # Try to GoTo 30 deg Alt (Allowed)
        target_alt = int((30.0 / 360.0) * 16777216)
        success = await self.driver.goto_position(0, target_alt)
        self.assertTrue(success, "Driver blocked GoTo inside Alt limits")

    async def test_focuser_control(self):
        """
        Description:
            Verifies the control of an external AUX Focuser.

        Methodology:
            1. Sets a target focuser position in the INDI property.
            2. Calls the focuser handler.
            3. Queries the simulator via AUX protocol to verify the physical
               position change.

        Expected Results:
            - The simulator's reported focuser position must match the target
              within 1 step tolerance.
        """
        target_pos = 500000
        self.driver.focus_pos.membervalue = target_pos
        # Mock event as a dictionary
        event = {"FOCUS_POS": target_pos}

        await self.driver.handle_focuser(event)

        # Verify simulator position
        resp = await self.driver.communicator.send_command(
            AUXCommand(AUXCommands.MC_GET_POSITION, AUXTargets.APP, AUXTargets.FOCUS)
        )
        self.assertIsNotNone(resp)
        sim_pos = int((resp.get_data_as_int() / 16777216.0) * 16777216)
        self.assertAlmostEqual(sim_pos, target_pos, delta=1)

    async def test_gps_refresh(self):
        """
        Description:
            Verifies location and time retrieval from a simulated GPS module.

        Methodology:
            1. Triggers a GPS refresh command.
            2. Calls the GPS refresh handler.
            3. Verifies that the Latitude and Longitude properties are updated
               with the simulator's default values.

        Expected Results:
            - Latitude should be approx 50.1822.
            - Longitude should be approx 19.7925.
        """
        self.driver.gps_refresh.membervalue = "On"
        event = {"REFRESH": "On"}
        await self.driver.handle_gps_refresh(event)

        self.assertAlmostEqual(float(self.driver.lat.membervalue), 50.1822, delta=0.001)
        self.assertAlmostEqual(
            float(self.driver.long.membervalue), 19.7925, delta=0.001
        )

    async def test_cordwrap_config(self):
        """
        Description:
            Verifies the configuration of cord-wrap prevention.

        Methodology:
            1. Enables cord-wrap in the driver.
            2. Calls the cord-wrap handler.
            3. Queries the simulator's MC state to verify the feature is active.

        Expected Results:
            - The simulator must report that cord-wrap protection is enabled (0xFF).
        """
        self.driver.cordwrap_enable.membervalue = "On"
        event = {"ENABLED": "On", "DISABLED": "Off"}
        await self.driver.handle_cordwrap(event)

        # Verify simulator
        resp = await self.driver.communicator.send_command(
            AUXCommand(AUXCommands.MC_POLL_CORDWRAP, AUXTargets.APP, AUXTargets.AZM)
        )
        self.assertIsNotNone(resp)
        self.assertEqual(resp.data[0], 0xFF)


if __name__ == "__main__":
    unittest.main()
