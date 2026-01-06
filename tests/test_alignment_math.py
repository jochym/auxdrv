
import math
import unittest
from alignment import AlignmentModel, vector_from_altaz, vector_to_altaz

class TestAlignment(unittest.TestCase):
    def test_identity(self):
        model = AlignmentModel()
        # 3 points on a sphere
        p1 = vector_from_altaz(0, 0)
        p2 = vector_from_altaz(90, 0)
        p3 = vector_from_altaz(0, 45)
        
        model.add_point(p1, p1)
        model.add_point(p2, p2)
        model.add_point(p3, p3)
        
        self.assertIsNotNone(model.matrix)
        # Check identity
        test_p = vector_from_altaz(45, 20)
        res_p = model.transform_to_mount(test_p)
        
        self.assertAlmostEqual(test_p[0], res_p[0])
        self.assertAlmostEqual(test_p[1], res_p[1])
        self.assertAlmostEqual(test_p[2], res_p[2])

    def test_rotation(self):
        model = AlignmentModel()
        # Offset Az by 10 degrees
        p1_sky = vector_from_altaz(0, 0)
        p1_mnt = vector_from_altaz(10, 0)
        
        p2_sky = vector_from_altaz(90, 0)
        p2_mnt = vector_from_altaz(100, 0)
        
        p3_sky = vector_from_altaz(0, 45)
        p3_mnt = vector_from_altaz(10, 45)
        
        model.add_point(p1_sky, p1_mnt)
        model.add_point(p2_sky, p2_mnt)
        model.add_point(p3_sky, p3_mnt)
        
        test_p = vector_from_altaz(45, 20)
        res_p = model.transform_to_mount(test_p)
        res_az, res_alt = vector_to_altaz(res_p)
        
        self.assertAlmostEqual(res_az, 55.0)
        self.assertAlmostEqual(res_alt, 20.0)

if __name__ == "__main__":
    unittest.main()
