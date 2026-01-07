import unittest
import numpy as np
import math
from alignment import AlignmentModel, vector_from_altaz, vector_to_altaz


class TestAdvancedAlignment(unittest.TestCase):
    def test_0_points(self):
        model = AlignmentModel()
        v = vector_from_altaz(10, 20)
        res = model.transform_to_mount(v)
        self.assertAlmostEqual(res[0], v[0])
        self.assertAlmostEqual(res[1], v[1])
        self.assertAlmostEqual(res[2], v[2])

    def test_1_point(self):
        model = AlignmentModel()
        s1 = vector_from_altaz(0, 0)
        m1 = vector_from_altaz(10, 0)  # 10 deg Azm shift
        model.add_point(s1, m1)

        res = model.transform_to_mount(s1)
        az, alt = vector_to_altaz(res)
        self.assertAlmostEqual(az, 10.0)
        self.assertAlmostEqual(alt, 0.0)

    def test_thinning(self):
        model = AlignmentModel()
        s1 = vector_from_altaz(0, 0)
        m1 = vector_from_altaz(0, 0)
        model.add_point(s1, m1)

        # Add another point 1 degree away
        s2 = vector_from_altaz(1, 0)
        m2 = vector_from_altaz(1, 0)
        model.add_point(s2, m2, min_dist_deg=5.0)

        # Should have replaced first point or kept only one if they are too close
        # My implementation replaces.
        self.assertEqual(len(model.points), 1)
        az, alt = vector_to_altaz(model.points[0]["sky"])
        self.assertAlmostEqual(az, 1.0)

    def test_6param_fit(self):
        model = AlignmentModel()
        # Simulated mount with 1 deg Cone Error
        # delta Az = CH / cos(Alt)
        CH = 1.0

        points = [
            (0, 0),
            (90, 0),
            (180, 0),
            (270, 0),
            (0, 35),
            (90, 35),
            (180, 35),
            (270, 35),
            (0, 70),
            (90, 70),
            (180, 70),
            (270, 70),
        ]

        for az, alt in points:
            s = vector_from_altaz(az, alt)
            az_m = az + CH / math.cos(math.radians(alt))
            m = vector_from_altaz(az_m, alt)
            model.add_point(s, m)

        self.assertGreaterEqual(len(model.points), 8)

        # Parameters: [roll, pitch, yaw, ID, CH, NP]
        # p[4] should be CH in RADIANS
        self.assertAlmostEqual(math.degrees(model.params[4]), 1.0, delta=0.1)
        self.assertAlmostEqual(model.rms_error_arcsec, 0.0, delta=10)


if __name__ == "__main__":
    unittest.main()
