import pytest
import asyncio
import subprocess
import sys
import os
import time
import socket
from typing import Optional, List, Dict

# Constants for integration tests
SIM_AUX_PORT = 2000
INDI_SERVER_PORT = 7624


@pytest.fixture(scope="session")
def simulator_process():
    """Starts the mount simulator using the standalone caux-sim command."""
    sim_port = int(os.environ.get("SIM_PORT", 2000))
    if os.environ.get("EXTERNAL_SIM"):
        # Dummy process-like object
        class DummyProc:
            pid = 0

            def wait(self):
                pass

        return DummyProc()

    cmd = [
        "caux-sim",
        "--text",
        "--perfect",
        "--hc",
        "--web",
        "--web-host",
        "0.0.0.0",
        "--web-port",
        "8080",
        "--port",
        str(sim_port),
    ]
    env = os.environ.copy()
    # caux-sim is assumed to be in the PATH as per user instructions

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        preexec_fn=os.setsid if hasattr(os, "setsid") else None,
    )

    time.sleep(3)
    yield proc
    try:
        if hasattr(os, "killpg"):
            os.killpg(os.getpgid(proc.pid), 15)
        else:
            proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        proc.kill()


@pytest.fixture(scope="session")
def driver_process(simulator_process):
    """Starts the Celestron AUX driver as a standalone INDI server."""
    cmd = [
        sys.executable,
        "-m",
        "celestron_aux.celestron_indi_driver",
        "--server",
        "--port",
        str(INDI_SERVER_PORT),
        "--name",
        "Celestron AUX",
    ]

    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(os.getcwd(), "src")
    env["PORT"] = f"socket://localhost:{SIM_AUX_PORT}"

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        preexec_fn=os.setsid,
    )

    time.sleep(3)  # Give it a bit more time

    yield proc

    # Cleanup
    os.killpg(os.getpgid(proc.pid), 15)
    proc.wait()


class SimpleIndiClient:
    """A lightweight INDI client for integration testing."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.buffer = ""
        self._read_task: Optional[asyncio.Task] = None

    async def connect(self, timeout: float = 5.0):
        self.reader, self.writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port), timeout=timeout
        )
        self._read_task = asyncio.create_task(self._read_loop())

    async def disconnect(self):
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()

    async def _read_loop(self):
        if not self.reader:
            return
        try:
            while True:
                data = await self.reader.read(4096)
                if not data:
                    break
                self.buffer += data.decode("utf-8", errors="ignore")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Client read error: {e}")

    async def send(self, message: str):
        """Sends an INDI message (XML)."""
        if self.writer:
            self.writer.write(message.encode("utf-8"))
            await self.writer.drain()

    async def wait_for(self, pattern: str, timeout: float = 10.0) -> bool:
        """Waits for a specific string pattern to appear in the received XML stream."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if pattern in self.buffer:
                return True
            await asyncio.sleep(0.1)
        return False

    def clear_buffer(self):
        self.buffer = ""


@pytest.fixture
async def indi_client(driver_process):
    """Provides a connected SimpleIndiClient instance."""
    client = SimpleIndiClient("localhost", INDI_SERVER_PORT)
    await client.connect()
    yield client
    await client.disconnect()
