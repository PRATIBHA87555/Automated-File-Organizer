import tempfile, time, os, unittest
from pathlib import Path
import organizer

def mk(folder, name, old=True):
    p = Path(folder) / name
    p.write_text("x")
    if old:
        t = time.time() - 60
        os.utime(p, (t, t))
    return p

class T(unittest.TestCase):
    def test_organize_and_undo(self):
        with tempfile.TemporaryDirectory() as d:
            mk(d, "a.jpg"); mk(d, "b.PDF"); mk(d, "c.xyz"); mk(d, "d.crdownload")
            mk(d, "new.png", old=False)
            moves = organizer.plan(d)
            self.assertEqual({m.src.name for m in moves}, {"a.jpg", "b.PDF", "c.xyz"})
            done = organizer.apply(d, moves)
            self.assertEqual(len(done), 3)
            self.assertTrue((Path(d) / "Images" / "a.jpg").exists())
            self.assertTrue((Path(d) / "Documents" / "b.PDF").exists())
            self.assertTrue((Path(d) / "Others" / "c.xyz").exists())
            self.assertTrue((Path(d) / "new.png").exists())
            self.assertEqual(organizer.undo_last(d), 3)
            self.assertTrue((Path(d) / "a.jpg").exists())
            self.assertFalse((Path(d) / "Images").exists())
            self.assertEqual(organizer.undo_last(d), 0)

    def test_name_collision(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Images").mkdir()
            (Path(d) / "Images" / "a.jpg").write_text("old")
            mk(d, "a.jpg")
            organizer.apply(d, organizer.plan(d))
            self.assertTrue((Path(d) / "Images" / "a (1).jpg").exists())
            self.assertEqual((Path(d) / "Images" / "a.jpg").read_text(), "old")

if __name__ == "__main__":
    unittest.main()
