import asyncio
import unittest
import struct
import math
from simulator.nse_telescope import NexStarScope, make_checksum, pack_int3, unpack_int3


class TestSimulatorCore(unittest.IsolatedAsyncioTestCase):
    """
    Test suite for the NSE Simulator's physics engine and protocol logic.
    """

    def setUp(self):
        # Config with no imperfections for baseline tests
        self.config = {
            "simulator": {
                "imperfections": {
                    "backlash_steps": 0,
                    "periodic_error_arcsec": 0,
                    "cone_error_arcmin": 0,
                    "encoder_jitter_steps": 0,
                }
            }
        }
        self.scope = NexStarScope(tui=False, config=self.config)

    def test_checksum(self):
        """Verify protocol checksum calculation."""
        # Packet: Length=3, Target=0x10, Source=0x20, Cmd=0x01
        header = bytes([0x03, 0x10, 0x20, 0x01])
        cs = make_checksum(header)
        # sum = 0x34. ~sum = 0xcb. +1 = 0xcc.
        self.assertEqual(cs, 0xCC)

    def test_kinematics_fast(self):
        """Verify GoTo Fast kinematics (speed and duration)."""
        # Move Azm 180 degrees (0.5 rotation)
        # Max speed is 4 deg/s = 4/360 rot/s.
        # 180 deg should take 180/4 = 45 seconds.

        target = 0.5
        # MC_GOTO_FAST: Length=6, Source=0x20, Target=0x10, Cmd=0x02, Data=3 bytes
        cmd = b"\x06\x20\x10\x02" + pack_int3(target)
        msg = b";" + cmd + bytes([make_checksum(cmd)])
        self.scope.handle_msg(msg)

        self.assertTrue(self.scope.slewing)
        self.assertTrue(self.scope.goto)

        # Advance 10 seconds
        self.scope.tick(10.0)
        # Expected pos: 10s * 4 deg/s = 40 deg. 40/360 = 0.111...
        self.assertAlmostEqual(self.scope.azm, 40.0 / 360.0, delta=0.001)

    async def test_backlash(self):
        """Verify mechanical backlash simulation."""
        self.scope.backlash_steps = 1000
        # Start moving positive
        self.scope.azm_rate = 0.01  # 3.6 deg/s
        self.scope.tick(1.0)
        pos1 = self.scope.azm

        # Reverse direction
        self.scope.azm_rate = -0.01
        # First tick should trigger dir change and initialize backlash
        self.scope.tick(0.00001)
        self.assertGreater(self.scope.azm_backlash_rem, 0)
        self.assertLessEqual(self.scope.azm_backlash_rem, 1000 / 16777216.0)

        self.scope.tick(0.001)  # Still in backlash zone
        pos2 = self.scope.azm
        self.assertAlmostEqual(pos1, pos2, delta=1e-7)

    def test_periodic_error(self):
        """Verify Periodic Error (PE) injection in reported sky position."""
        self.scope.pe_amplitude = 100.0 / (360 * 3600)  # 100 arcsec
        self.scope.pe_period = 100.0  # 100 seconds

        # At t=0, sin(0)=0
        self.scope.sim_time = 0
        p0, _ = self.scope.get_sky_altaz()
        self.assertAlmostEqual(p0, self.scope.azm, delta=1e-7)

        # At t=25 (1/4 period), sin(pi/2)=1
        self.scope.sim_time = 25.0
        p1, _ = self.scope.get_sky_altaz()
        self.assertAlmostEqual(p1, self.scope.azm + self.scope.pe_amplitude, delta=1e-7)


if __name__ == "__main__":
    unittest.main()
