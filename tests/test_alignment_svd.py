import asyncio
import unittest
import numpy as np
import math
from alignment import AlignmentModel, vector_from_altaz, vector_to_altaz


class TestAlignmentSVD(unittest.TestCase):
    def test_basic_rotation(self):
        """Test if SVD finds a simple 90-degree rotation."""
        model = AlignmentModel()

        # Sky vectors: North, East
        s1 = [1, 0, 0]
        s2 = [0, 1, 0]

        # Mount is rotated 90 deg around Z
        # m1 = [0, 1, 0], m2 = [-1, 0, 0]
        m1 = [0, 1, 0]
        m2 = [-1, 0, 0]

        model.add_point(s1, m1)
        model.add_point(s2, m2)

        # Try to transform a vector in between (North-East)
        s_test = [1, 1, 0]
        m_res = model.transform_to_mount(s_test)

        # Expected: [-1, 1, 0]
        self.assertAlmostEqual(m_res[0], -1.0)
        self.assertAlmostEqual(m_res[1], 1.0)
        self.assertAlmostEqual(m_res[2], 0.0)

    def test_rms_calculation(self):
        """Test RMS error reporting."""
        model = AlignmentModel()

        # Perfect points
        model.add_point([1, 0, 0], [1, 0, 0])
        model.add_point([0, 1, 0], [0, 1, 0])
        self.assertAlmostEqual(model.rms_error_arcsec, 0.0)

        # Add a noisy point (1 degree error = 3600 arcsec)
        # Point at [0,0,1] but mount sees it at 1 deg offset
        err_rad = math.radians(1.0)
        m_noisy = [math.sin(err_rad), 0, math.cos(err_rad)]
        model.add_point([0, 0, 1], m_noisy)

        # RMS should be non-zero
        self.assertGreater(model.rms_error_arcsec, 0)
        # SVD minimizes squared error. With 1 deg error in one point out of 3,
        # reported RMS is around 1470 arcsec (approx 0.4 deg).
        self.assertAlmostEqual(model.rms_error_arcsec, 1470, delta=50)

    def test_pruning(self):
        """Test FIFO pruning logic."""
        model = AlignmentModel()
        for i in range(10):
            model.add_point([1, 0, 0], [1, 0, 0])

        self.assertEqual(len(model.points), 10)
        model.prune(5)
        self.assertEqual(len(model.points), 5)


if __name__ == "__main__":
    unittest.main()
