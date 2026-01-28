import asyncio
import unittest
import os
import subprocess
import time
from typing import Optional
from celestron_aux.celestron_indi_driver import CelestronAUXDriver


class CelestronAUXBaseTest(unittest.IsolatedAsyncioTestCase):
    """
    Base class for Celestron AUX tests providing standardized simulator lifecycle management.
    """

    sim_proc: Optional[subprocess.Popen] = None
    sim_port: int = 2000
    external_sim: bool = False
    sim_log = None

    @classmethod
    def setUpClass(cls):
        """
        Starts the simulator if EXTERNAL_SIM is not set.
        """
        cls.sim_port = int(os.environ.get("SIM_PORT", 2000))
        if os.environ.get("EXTERNAL_SIM"):
            cls.external_sim = True
            return

        log_name = f"{cls.__name__}_sim.log"
        cls.sim_log = open(log_name, "w")

        # Standardized command for starting caux-sim
        cmd = [
            "caux-sim",
            "--text",
            "--debug",
            "--perfect",
            "--hc",
            "--web",
            "--web-host",
            "0.0.0.0",
            "--web-port",
            "8080",
            "--port",
            str(cls.sim_port),
        ]

        env = os.environ.copy()
        cls.sim_proc = subprocess.Popen(
            cmd,
            stdout=cls.sim_log,
            stderr=cls.sim_log,
            env=env,
            preexec_fn=os.setsid if hasattr(os, "setsid") else None,
        )
        # Wait for simulator to initialize
        time.sleep(3)

    @classmethod
    def tearDownClass(cls):
        """
        Stops the simulator if it was started by the test.
        """
        if cls.external_sim:
            return

        if cls.sim_proc:
            try:
                if hasattr(os, "killpg"):
                    os.killpg(os.getpgid(cls.sim_proc.pid), 15)
                else:
                    cls.sim_proc.terminate()
                cls.sim_proc.wait(timeout=5)
            except Exception:
                if cls.sim_proc:
                    cls.sim_proc.kill()

        if cls.sim_log:
            cls.sim_log.close()

    async def asyncSetUp(self):
        """
        Initializes the driver and connects to the simulator.
        """
        self.driver = CelestronAUXDriver()
        self.driver.port_name.membervalue = f"socket://localhost:{self.sim_port}"

        # Mock the send method to avoid actual INDI network traffic
        async def mock_send(xmldata):
            pass

        self.driver.send = mock_send

        self.driver.conn_connect.membervalue = "On"
        await self.driver.handle_connection(None)

    async def asyncTearDown(self):
        """
        Disconnects the driver.
        """
        if hasattr(self, "driver") and self.driver.communicator:
            await self.driver.communicator.disconnect()
