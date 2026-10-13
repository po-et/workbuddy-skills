import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "tools/skillhub_prep.py"
spec = importlib.util.spec_from_file_location("prep_license", SCRIPT)
prep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prep)


class PrepLicenseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.src = self.root / "source"
        self.src.mkdir()
        self.fm = '---\nname: fixture\nversion: 0.1.0\ndisplay_name: Fixture\ndescription: Build a fixture\n'

    def tearDown(self):
        self.temp.cleanup()

    def run_prep(self, extra=""):
        (self.src / "SKILL.md").write_text(self.fm + extra + '---\n# Fixture\n')
        with patch.object(prep, "source_dir", return_value=self.src):
            return prep.prep("fixture", self.root / "out")

    def test_explicit_mixed_license_retained_once(self):
        dst = self.run_prep('license: CC-BY-4.0 AND MIT\nhomepage: https://example.com\n')
        fm, _ = prep.split_frontmatter((dst / "SKILL.md").read_text())
        self.assertEqual(prep.get(fm, "license"), "CC-BY-4.0 AND MIT")
        self.assertEqual(fm.count("\nlicense:"), 1)
        self.assertEqual(fm.count("\nhomepage:"), 1)
        self.assertEqual(prep.get(fm, "homepage"), "https://example.com")

    def test_license_bytes_preserved_for_upload(self):
        content = b"MIT License\nCopyright Example\nFULL NOTICE\n"
        (self.src / "LICENSE").write_bytes(content)
        dst = self.run_prep()
        self.assertFalse((dst / "LICENSE").exists())
        self.assertEqual((dst / "LICENSE.md").read_bytes(), content)
        self.assertTrue((self.src / "LICENSE").exists())

    def test_notice_bytes_preserved(self):
        (self.src / "NOTICE").write_bytes(b"attribution notice\n")
        dst = self.run_prep()
        self.assertEqual((dst / "NOTICE.md").read_bytes(), b"attribution notice\n")

    def test_conflicting_preserved_license_rejected(self):
        (self.src / "LICENSE").write_text("original")
        (self.src / "LICENSE.md").write_text("different")
        with self.assertRaises(ValueError):
            self.run_prep()


if __name__ == "__main__":
    unittest.main()
