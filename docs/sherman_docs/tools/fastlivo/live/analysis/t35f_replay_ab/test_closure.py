import csv, math, os, tempfile, unittest
import closure


class ClosureTests(unittest.TestCase):
    def test_loop_that_misses_by_3_4_5(self):
        pts = [(0, 0), (6, 0), (6, 8), (3, 4)]  # last pose is 3 m / 4 m from the first: closure 5
        rows = [(i, x, y, 0.0, 0.0, 0.0, 0.0, 1.0) for i, (x, y) in enumerate(pts)]
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "o.csv")
            with open(p, "w") as f:
                f.write("stamp,x,y,z,qx,qy,qz,qw\n" + "".join(",".join(map(repr, r)) + "\n" for r in rows))
            c = closure.closure(closure.rows_csv(p))
        self.assertAlmostEqual(c["horizontal_m"], 5.0)
        self.assertAlmostEqual(c["path_m"], 6 + 8 + 5)
        self.assertAlmostEqual(c["yaw_deg"], 0.0)

    def test_yaw_change_wraps(self):
        a = (0, 0, 0, 0, 0, 0, 0, 1.0)
        h = math.radians(190) / 2  # +190 deg is -170 deg
        b = (1, 0, 0, 0, 0, 0, math.sin(h), math.cos(h))
        self.assertAlmostEqual(closure.closure([a, b])["yaw_deg"], -170.0, places=3)


if __name__ == "__main__":
    unittest.main()
