import asyncio
import unittest
import numpy as np
import math
from alignment import AlignmentModel, vector_from_altaz, vector_to_altaz


class TestAlignmentSVD(unittest.TestCase):
    """
    Verification of the high-level Multi-Point SVD alignment solver.

    Verifies that the Singular Value Decomposition correctly finds the optimal
    rotation matrix for multiple points and reports accurate residuals.
    """

    def test_basic_rotation(self):
        """
        Description:
            Verifies if the SVD solver finds a simple 90-degree rotation
            around the Z axis.

        Methodology:
            1. Defines two sky vectors (North and East).
            2. Defines two mount vectors rotated by 90 degrees.
            3. Fits the model and transforms a North-East vector.

        Expected Results:
            - The transformed vector must reflect the 90-degree rotation.
        """
        model = AlignmentModel()

        # Sky vectors: North, East
        s1 = [1, 0, 0]
        s2 = [0, 1, 0]

        # Mount is rotated 90 deg around Z
        m1 = [0, 1, 0]
        m2 = [-1, 0, 0]

        model.add_point(s1, m1)
        model.add_point(s2, m2)

        # Try to transform a vector in between (North-East)
        s_test = [1, 1, 0]
        m_res = model.transform_to_mount(s_test)

        self.assertAlmostEqual(m_res[0], -1.0)
        self.assertAlmostEqual(m_res[1], 1.0)
        self.assertAlmostEqual(m_res[2], 0.0)

    def test_rms_calculation(self):
        """
        Description:
            Verifies that the Root Mean Square (RMS) error calculation is accurate.

        Methodology:
            1. Adds two perfect alignment points (0 error).
            2. Adds a third point with a known 1-degree error.
            3. Verifies reported RMS.

        Expected Results:
            - RMS error should be non-zero.
            - Reported error should be approximately 1470 arcseconds (result of
              least-squares fit over 3 points with one 1-deg outlier).
        """
        model = AlignmentModel()

        # Perfect points
        model.add_point([1, 0, 0], [1, 0, 0])
        model.add_point([0, 1, 0], [0, 1, 0])
        self.assertAlmostEqual(model.rms_error_arcsec, 0.0)

        # Add a noisy point (1 degree error = 3600 arcsec)
        err_rad = math.radians(1.0)
        m_noisy = [math.sin(err_rad), 0, math.cos(err_rad)]
        model.add_point([0, 0, 1], m_noisy)

        self.assertGreater(model.rms_error_arcsec, 0)
        # Reported RMS should be around 1470 arcsec.
        self.assertAlmostEqual(model.rms_error_arcsec, 1470, delta=50)

    def test_thinning(self):
        """Test thinning logic."""
        model = AlignmentModel()
        # Add points close to each other (within 5 deg)
        for i in range(10):
            model.add_point(
                vector_from_altaz(i * 0.5, 0),
                vector_from_altaz(i * 0.5, 0),
                min_dist_deg=5.0,
            )

        # They should keep replacing each other, maintaining count 1
        self.assertEqual(len(model.points), 1)

        # Add a distant point
        model.add_point(
            vector_from_altaz(20, 0), vector_from_altaz(20, 0), min_dist_deg=5.0
        )
        self.assertEqual(len(model.points), 2)


if __name__ == "__main__":
    unittest.main()
