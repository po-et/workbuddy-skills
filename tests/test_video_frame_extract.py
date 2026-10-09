"""Video CLI behavior checks; all videos and images are synthetic and local."""
import csv
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "skills/video-frame-extract/scripts/frames.py"


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "requires installed ffmpeg/ffprobe")
class VideoFrameCLITest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="synthetic-video-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.video = self.root / "synthetic input.mp4"
        made = subprocess.run([
            "ffmpeg", "-v", "error", "-n", "-f", "lavfi", "-i",
            "testsrc2=size=160x90:rate=12:duration=2", "-c:v", "libx264",
            "-pix_fmt", "yuv420p", "-g", "12", str(self.video),
        ], capture_output=True, text=True, timeout=30)
        self.assertEqual(made.returncode, 0, made.stderr)
        self.input_hash = hashlib.sha256(self.video.read_bytes()).hexdigest()

    def run_cli(self, mode, *args):
        result = subprocess.run([sys.executable, str(SCRIPT), mode, str(self.video), *args],
                                capture_output=True, text=True, timeout=30,
                                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(hashlib.sha256(self.video.read_bytes()).hexdigest(), self.input_hash)
        return result

    def test_interval_outputs_exact_count_index_and_dimensions(self):
        output = self.root / "frames"
        result = self.run_cli("interval", "--count", "4", "--width", "160", "--out-dir", str(output))
        self.assertEqual(result.returncode, 0, result.stderr)
        with (output / "index.csv").open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual([row["文件"] for row in rows], [f"f_{i:04d}.jpg" for i in range(4)])
        self.assertEqual([float(row["秒"]) for row in rows], [0, 0.5, 1, 1.5])
        self.assertEqual(len(list(output.glob("*.jpg"))), 4)
        self.assertIn("160x90", result.stdout)
        self.assertTrue(all((output / row["文件"]).stat().st_size > 0 for row in rows))

    def test_sheet_and_gif_are_readable_media(self):
        for mode, name, args in (
            ("sheet", "sheet.jpg", ("--cols", "2", "--rows", "2", "--width", "160")),
            ("gif", "clip.gif", ("--start", "0", "--duration", "1", "--fps", "6", "--width", "160")),
        ):
            with self.subTest(mode=mode):
                path = self.root / name
                result = self.run_cli(mode, *args, "--out", str(path))
                self.assertEqual(result.returncode, 0, result.stderr)
                probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height",
                                        "-of", "csv=p=0", str(path)], capture_output=True, text=True, timeout=10)
                self.assertEqual(probe.returncode, 0, probe.stderr)
                self.assertEqual(probe.stdout.strip(), "332,192" if mode == "sheet" else "160,90")

    def test_sheet_first_tile_matches_first_video_frame(self):
        output = self.root / "sheet.jpg"
        result = self.run_cli("sheet", "--cols", "2", "--rows", "2", "--width", "160", "--out", str(output))
        self.assertEqual(result.returncode, 0, result.stderr)

        def pixels(path, filters=()):
            command = ["ffmpeg", "-v", "error", "-i", str(path), *filters,
                       "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
            p = subprocess.run(command, capture_output=True, timeout=10)
            self.assertEqual(p.returncode, 0, p.stderr)
            return p.stdout

        first = pixels(self.video)
        tile = pixels(output, ("-vf", "crop=160:90:4:4"))
        self.assertEqual(len(first), 160 * 90 * 3)
        self.assertEqual(len(tile), len(first))
        # JPEG is lossy, so compare pixel error rather than a file hash.
        self.assertLess(sum(abs(a - b) for a, b in zip(first, tile)) / len(first), 5)

    def test_existing_image_and_index_are_preserved(self):
        cover = self.root / "cover.jpg"
        cover.write_bytes(b"existing-image")
        result = self.run_cli("shot", "--at", "0", "--out", str(cover))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(cover.read_bytes(), b"existing-image")
        output = self.root / "shared-output"
        output.mkdir()
        index = output / "index.csv"
        index.write_bytes(b"previous-mode-index")
        result = self.run_cli("interval", "--count", "4", "--out-dir", str(output))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(index.read_bytes(), b"previous-mode-index")
        self.assertEqual(list(output.glob("*.jpg")), [])

    def test_nonfinite_numbers_and_invalid_rates_fail_before_outputs(self):
        output = self.root / "invalid"
        cases = [
            ("pick", ("--start", "0", "--rate", rate, "--out", str(output)))
            for rate in ("0", "-1", "nan", "inf", "51")
        ] + [
            ("interval", ("--every", value, "--out-dir", str(output)))
            for value in ("nan", "inf")
        ] + [
            ("gif", ("--start", "nan", "--duration", "1", "--out", str(output))),
            ("pick", ("--start", "0", "--duration", "inf", "--out", str(output))),
        ]
        for mode, args in cases:
            with self.subTest(mode=mode, args=args):
                result = self.run_cli(mode, *args)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("参数错误", result.stderr)
                self.assertFalse(output.exists())

    def test_excessive_interval_is_rejected_without_creating_directory(self):
        for value in ("0.00001", "1e-320"):
            with self.subTest(value=value):
                output = self.root / "too-many"
                result = self.run_cli("interval", "--every", value, "--out-dir", str(output))
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("1000", result.stderr)
                self.assertFalse(output.exists())

    def test_invalid_or_out_of_range_time_fails_without_image(self):
        for value in ("1:61", "2", "99"):
            with self.subTest(value=value):
                output = self.root / "invalid-shot.jpg"
                result = self.run_cli("shot", "--at", value, "--out", str(output))
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertFalse(output.exists())

    def test_dry_run_creates_no_outputs(self):
        output = self.root / "dry-frames"
        result = self.run_cli("interval", "--count", "4", "--out-dir", str(output), "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("执行：", result.stdout)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
