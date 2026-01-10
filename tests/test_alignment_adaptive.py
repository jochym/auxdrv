import unittest
import numpy as np
import math
from celestron_aux.alignment import AlignmentModel, vector_from_altaz


class TestAlignmentAdaptive(unittest.TestCase):
    def test_adaptive_parameters(self):
        model = AlignmentModel()

        # Identity mapping for simplicity
        def add_perfect_point(az, alt):
            v = vector_from_altaz(az, alt)
            model.add_point(v, v)

        # 1. 2 points -> SVD only (params should be 0)
        add_perfect_point(0, 45)
        add_perfect_point(90, 45)
        self.assertEqual(len(model.points), 2)
        self.assertTrue(np.all(model.params == 0))

        # 2. 3 points -> 4-parameter model
        add_perfect_point(180, 45)
        self.assertEqual(len(model.points), 3)
        # Check if ID was attempted (params[3])
        # Since it's perfect data, params should still be near 0, but solve_params was 4.
        # We can't easily check internal solve_params but we can check if it ran.

        # 3. 6 points -> 6-parameter model
        add_perfect_point(270, 45)
        add_perfect_point(45, 10)
        add_perfect_point(45, 80)
        self.assertEqual(len(model.points), 6)

        # Verify it doesn't crash
        v_in = vector_from_altaz(10, 10)
        v_out = model.transform_to_mount(v_in)
        self.assertEqual(len(v_out), 3)

    def test_imperfection_recovery(self):
        model = AlignmentModel()

        # ID error of 5 arcmin
        id_err_deg = 5.0 / 60.0

        def add_point_with_id_err(az, alt):
            sky = vector_from_altaz(az, alt)
            mount = vector_from_altaz(az, alt - id_err_deg)
            model.add_point(sky, mount)

        # Need 3 points for ID recovery
        add_point_with_id_err(0, 20)
        add_point_with_id_err(90, 45)
        add_point_with_id_err(180, 70)

        # Params[3] is ID in radians
        id_recovered_arcmin = math.degrees(model.params[3]) * 60.0
        print(f"Recovered ID: {id_recovered_arcmin:.2f}'")
        self.assertAlmostEqual(id_recovered_arcmin, -5.0, places=1)


if __name__ == "__main__":
    unittest.main()
