import asyncio
import unittest
import math
import random
from simulator.nse_telescope import NexStarScope, pack_int3, unpack_int3, make_checksum


class TestSimulatorImperfections(unittest.IsolatedAsyncioTestCase):
    """
    Test suite for the NSE Simulator's mount imperfections.

    Verifies that mechanical and optical errors are correctly simulated
    in the physics engine and reported coordinates.
    """

    def setUp(self):
        self.config = {
            "simulator": {
                "imperfections": {
                    "backlash_steps": 100,
                    "periodic_error_arcsec": 3600.0,  # 1 degree for easy testing
                    "periodic_error_period_sec": 100.0,
                    "cone_error_arcmin": 60.0,  # 1 degree
                    "non_perpendicularity_arcmin": 60.0,
                    "refraction_enabled": True,
                    "encoder_jitter_steps": 0,
                    "clock_drift": 0.1,  # 10% drift
                }
            }
        }
        self.scope = NexStarScope(tui=False, config=self.config)

    async def test_backlash_sim(self):
        """
        Description:
            Verifies that mechanical backlash correctly delays axis movement.

        Methodology:
            1. Moves the Azimuth axis in a positive direction.
            2. Reverses direction to negative.
            3. Checks that the axis position does not change until the
               configured backlash steps are consumed.

        Expected Results:
            - The `azm_backlash_rem` should be initialized to the configured steps.
            - Movement should be zero while backlash is being consumed.
        """
        # Set a known state
        self.scope.azm = 0.5
        self.scope.azm_last_dir = 1
        self.scope.azm_backlash_rem = 0
        self.scope.azm_rate = -0.000001  # Very slow negative move

        # First tick triggers direction change
        self.scope.tick(1.0)
        self.assertEqual(self.scope.azm, 0.5)  # Should not have moved due to backlash
        # Backlash remaining should be total minus this one small move
        expected = (100 / 16777216.0) - 0.000001 * 1.1  # 1.1 is clock drift
        self.assertAlmostEqual(self.scope.azm_backlash_rem, expected, delta=1e-9)

    def test_periodic_error_sim(self):
        """
        Description:
            Verifies that Periodic Error is correctly applied to sky coordinates.

        Methodology:
            1. Sets a large PE amplitude.
            2. Compares encoder position with sky position at different times.

        Expected Results:
            - Sky position should deviate from encoder position following
              a sine wave.
        """
        self.scope.sim_time = 0
        _, sky_alt = self.scope.get_sky_altaz()

        self.scope.sim_time = 25.0  # 1/4 period of 100s
        sky_azm, _ = self.scope.get_sky_altaz()
        # PE is added to Azm
        # sky_azm = self.azm + amplitude * sin(2*pi*25/100) = self.azm + amplitude * 1
        expected = (self.scope.azm + self.scope.pe_amplitude) % 1.0
        self.assertAlmostEqual(sky_azm, expected)

    def test_cone_error_sim(self):
        """
        Description:
            Verifies that cone error is correctly applied to sky coordinates.

        Methodology:
            Compares encoder Altitude with reported sky Altitude (disabling refraction).

        Expected Results:
            - Sky Altitude should be offset by the configured cone error.
        """
        self.scope.refraction_enabled = False
        _, sky_alt = self.scope.get_sky_altaz()
        self.assertAlmostEqual(sky_alt, self.scope.alt + self.scope.cone_error)

    def test_clock_drift_sim(self):
        """
        Description:
            Verifies that clock drift correctly scales the simulation time.

        Methodology:
            Ticks the simulator with a 1.0s interval and checks `sim_time` increase.

        Expected Results:
            - `sim_time` should increase by 1.1s (1.0s + 10% drift).
        """
        self.scope.sim_time = 0
        self.scope.tick(1.0)
        self.assertAlmostEqual(self.scope.sim_time, 1.1)

    def test_refraction_sim(self):
        """
        Description:
            Verifies that atmospheric refraction is applied to sky Altitude.

        Methodology:
            1. Sets Altitude to 10 degrees (where refraction is significant).
            2. Compares sky Altitude with and without refraction.

        Expected Results:
            - Sky Altitude should be higher than mechanical Altitude.
        """
        self.scope.alt = 10.0 / 360.0
        self.scope.refraction_enabled = False
        _, sky_alt_no_ref = self.scope.get_sky_altaz()

        self.scope.refraction_enabled = True
        _, sky_alt_ref = self.scope.get_sky_altaz()

        self.assertGreater(sky_alt_ref, sky_alt_no_ref)


if __name__ == "__main__":
    unittest.main()
