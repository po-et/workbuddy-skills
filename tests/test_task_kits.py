"""Consumer-level verification of standalone task kits; no repository imports after unzip."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('task_kits_builder', ROOT / 'tools/task_kits.py')
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hashes(folder):
    return {p.relative_to(folder).as_posix(): sha(p) for p in folder.rglob('*') if p.is_file()}


class TaskKitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='standalone task kits ')
        cls.base = Path(cls.temp.name)
        cls.release = cls.base / 'release one'
        cls.other = cls.base / 'release two'
        BUILDER.build('0.1.0', cls.release)
        BUILDER.build('0.1.0', cls.other)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def unpack(self, kind):
        target = Path(tempfile.mkdtemp(prefix='fresh folder with spaces ', dir=self.base))
        with zipfile.ZipFile(self.release / (kind + '-task-kit-0.1.0.zip')) as archive:
            archive.extractall(target)
        return target / (kind + '-task-kit-0.1.0')

    def run_kit(self, folder, *args):
        # Deliberately outside the repo, without PYTHONPATH or any installed skillkit dependency.
        env = {k: v for k, v in os.environ.items() if k != 'PYTHONPATH'}
        env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
        return subprocess.run([sys.executable, '-I', '-B', str(folder / 'start.py'), *map(str, args)],
                              cwd=folder, env=env, capture_output=True, text=True, encoding='utf-8', timeout=90)

    def test_identical_builds_and_release_checksums(self):
        self.assertEqual(tree_hashes(self.release), tree_hashes(self.other))
        checksums = (self.release / 'SHA256SUMS.txt').read_text().splitlines()
        self.assertEqual(len(checksums), 4)
        for line in checksums:
            expected, name = line.split('  ', 1)
            self.assertEqual(sha(self.release / name), expected)
        release = json.loads((self.release / 'release-manifest.json').read_text())
        self.assertEqual(release['tag'], 'task-kits-v0.1.0')
        self.assertEqual(len(release['source']['commit']), 40)

    def test_archive_manifest_licenses_original_skill_and_paths(self):
        for kit in BUILDER.KITS:
            with self.subTest(kit=kit['id']):
                archive_path = self.release / (kit['id'] + '-task-kit-0.1.0.zip')
                with zipfile.ZipFile(archive_path) as archive:
                    names = archive.namelist()
                    self.assertEqual(len({name.split('/')[0] for name in names}), 1)
                    for item in archive.infolist():
                        self.assertEqual(item.date_time, (1980, 1, 1, 0, 0, 0))
                        self.assertEqual(item.external_attr >> 16, 0o100644)
                        self.assertNotIn('..', Path(item.filename).parts)
                        self.assertFalse(Path(item.filename).is_absolute())
                        self.assertFalse(any(part in BUILDER.EXCLUDED for part in Path(item.filename).parts))
                folder = self.unpack(kit['id'])
                manifest = json.loads((folder / 'kit-manifest.json').read_text())
                paths = {entry['path'] for entry in manifest['files']}
                self.assertNotIn('kit-manifest.json', paths)
                self.assertEqual(paths, set(tree_hashes(folder)) - {'kit-manifest.json'})
                for entry in manifest['files']:
                    self.assertEqual(sha(folder / entry['path']), entry['sha256'])
                originals = {p.relative_to(ROOT / 'skills' / kit['skill']).as_posix(): sha(p)
                             for p in (ROOT / 'skills' / kit['skill']).rglob('*')
                             if p.is_file() and not any(part in BUILDER.EXCLUDED for part in p.parts)
                             and p.suffix not in ('.pyc', '.pyo')}
                self.assertEqual(tree_hashes(folder / 'skill'), originals)
                self.assertEqual((folder / 'LICENSE').read_bytes(), (ROOT / 'LICENSE').read_bytes())
                self.assertEqual((folder / 'LICENSE-CONTENT').read_bytes(), (ROOT / 'LICENSE-CONTENT').read_bytes())
                self.assertIn('CC BY 4.0', (folder / 'ATTRIBUTION.md').read_text())
                for name in ('START-HERE.md', 'ATTRIBUTION.md'):
                    self.assertNotIn('/Users/', (folder / name).read_text())
                self.assertIn('task-kit-feedback.md', (folder / 'START-HERE.md').read_text())

    def test_car_demo_and_own_input_preserve_inputs_and_sources(self):
        folder = self.unpack('car-buying-checklist')
        before = tree_hashes(folder)
        output = self.base / 'car demo result'
        result = self.run_kit(folder, '--demo', '--out-dir', output)
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads((output / 'verification.json').read_text())
        self.assertTrue(summary['demo_verified'])
        self.assertTrue(summary['inputs_and_kit_unchanged'])
        self.assertEqual([r['exit_code'] for r in summary['runs']], [0, 0])
        missing = json.loads((output / 'missing-fee/comparison.json').read_text())
        self.assertIsNone(missing['quotes'][1]['finance_fee']['value'])
        complete = json.loads((output / 'complete-fee/comparison.json').read_text())
        comparison = next(c for c in complete['comparisons'] if c['scope'] == 'finance_fee')
        self.assertEqual(comparison['right_minus_left'], '1500')
        own = self.base / 'own quote.json'
        own.write_bytes((folder / 'skill/examples/two-quotes-complete.json').read_bytes())
        own_sha = sha(own)
        own_result = self.base / 'own car result'
        result = self.run_kit(folder, '--input', own, '--out-dir', own_result)
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads((own_result / 'verification.json').read_text())
        self.assertIsNone(summary['demo_verified'])
        self.assertEqual(summary['status'], 'input_processed')
        self.assertEqual(summary['input']['sha256'], own_sha)
        self.assertEqual(sha(own), own_sha)
        self.assertEqual(tree_hashes(folder), before)

    def test_ppt_demo_and_own_input_preserve_issue_exit_code(self):
        folder = self.unpack('pptx-making')
        before = tree_hashes(folder)
        output = self.base / 'ppt demo result'
        result = self.run_kit(folder, '--demo', '--out-dir', output)
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads((output / 'verification.json').read_text())
        self.assertTrue(summary['demo_verified'])
        self.assertEqual([r['exit_code'] for r in summary['runs']], [3, 3, 0, 0])
        self.assertEqual(json.loads((output / 'before.json').read_text())['font_size_coverage']['small_count'], 2)
        self.assertEqual(json.loads((output / 'after.json').read_text())['font_size_coverage']['unresolved_count'], 1)
        own_output = self.base / 'own ppt result'
        result = self.run_kit(folder, '--input', folder / 'inputs/before.pptx', '--out-dir', own_output)
        self.assertEqual(result.returncode, 3, result.stderr)
        own = json.loads((own_output / 'verification.json').read_text())
        self.assertEqual(own['status'], 'issues_found_in_checked_scope')
        self.assertTrue(own['check_completed'])
        self.assertIsNone(own['demo_verified'])
        self.assertEqual([r['exit_code'] for r in own['runs']], [3, 3])
        self.assertEqual(tree_hashes(folder), before)

    def test_failures_preserve_original_codes_and_never_claim_verified(self):
        for kind, filename, raw, expected in (
            ('car-buying-checklist', 'bad.json', b'{not-json', 1),
            ('pptx-making', 'bad.pptx', b'not a zip', 2),
        ):
            with self.subTest(kit=kind):
                folder = self.unpack(kind)
                source = self.base / filename
                source.write_bytes(raw)
                output = self.base / (kind + ' bad result')
                result = self.run_kit(folder, '--input', source, '--out-dir', output)
                self.assertEqual(result.returncode, expected, result.stderr)
                summary = json.loads((output / 'verification.json').read_text())
                self.assertEqual(summary['status'], 'source_script_failed')
                self.assertIsNone(summary['demo_verified'])
                self.assertTrue(all(r['exit_code'] == expected for r in summary['runs']))
                self.assertTrue(summary['inputs_and_kit_unchanged'])
                self.assertEqual(source.read_bytes(), raw)

    def test_existing_output_empty_or_nonempty_is_preserved(self):
        folder = self.unpack('car-buying-checklist')
        for name, with_file in (('empty output', False), ('saved output', True)):
            output = self.base / name
            output.mkdir()
            if with_file:
                (output / 'keep.txt').write_text('keep exact bytes\n')
            before = tree_hashes(output)
            result = self.run_kit(folder, '--demo', '--out-dir', output)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(tree_hashes(output), before)
            self.assertFalse((output / 'verification.json').exists())
        with self.assertRaises(FileExistsError):
            BUILDER.build('0.1.0', self.release)

    def test_modified_package_rejected_before_running(self):
        folder = self.unpack('pptx-making')
        script = folder / 'skill/scripts/pptx_check.py'
        script.write_bytes(script.read_bytes() + b'\n# changed\n')
        output = self.base / 'tampered result'
        result = self.run_kit(folder, '--demo', '--out-dir', output)
        self.assertEqual(result.returncode, 1)
        self.assertIn('Task kit file changed', result.stderr)
        self.assertFalse(output.exists())

    def test_demo_checks_expectations_not_only_zero_exit(self):
        folder = self.unpack('pptx-making')
        # A self-consistent repack with the repaired file substituted for the broken
        # fixture must fail the scenario expectation, even though the checker succeeds.
        before = folder / 'inputs/before.pptx'
        before.write_bytes((folder / 'inputs/after.pptx').read_bytes())
        path = folder / 'kit-manifest.json'
        manifest = json.loads(path.read_text())
        for entry in manifest['files']:
            if entry['path'] == 'inputs/before.pptx':
                entry['sha256'] = sha(before)
                entry['bytes'] = before.stat().st_size
        path.write_text(json.dumps(manifest))
        output = self.base / 'wrong demo result'
        result = self.run_kit(folder, '--demo', '--out-dir', output)
        self.assertEqual(result.returncode, 1)
        summary = json.loads((output / 'verification.json').read_text())
        self.assertFalse(summary['demo_verified'])
        self.assertEqual([r['exit_code'] for r in summary['runs']], [0, 0, 0, 0])
        self.assertIn('PPT demo exit codes differ', summary['errors'])

    def test_api_demo_uses_loopback_and_validates_original_verification(self):
        folder = self.unpack('api-diff-test')
        before = tree_hashes(folder)
        output = self.base / 'api demo result'
        result = self.run_kit(folder, '--demo', '--out-dir', output)
        summary = json.loads((output / 'verification.json').read_text())
        if result.returncode != 0:
            stderr = (output / 'demo.stderr.txt').read_text()
            if 'Operation not permitted' in stderr or 'Permission denied' in stderr:
                self.assertFalse(summary['demo_verified'])
                self.assertEqual(summary['runs'][0]['exit_code'], 1)
                self.skipTest('Actual loopback socket permission denied by execution sandbox; failure artifact was honest')
        self.assertEqual(result.returncode, 0, result.stderr + (output / 'demo.stderr.txt').read_text())
        self.assertTrue(summary['demo_verified'])
        original = json.loads((output / 'demo/verification.json').read_text())
        self.assertFalse(original['external_requests'])
        self.assertEqual(original['outcomes']['regressed']['exit_code'], 1)
        self.assertEqual(original['outcomes']['repaired']['exit_code'], 0)
        self.assertEqual(tree_hashes(folder), before)


    def private_repository(self, parent):
        """A private Git fixture; never changes the actual worktree or index."""
        repo = parent / 'private repository'
        repo.mkdir()
        sources = ['tools/task_kits.py', 'taskkits/start.py', 'LICENSE', 'LICENSE-CONTENT',
                   '.github/ISSUE_TEMPLATE/task-kit-feedback.md']
        sources.extend('taskkits/' + kit['id'] + '.md' for kit in BUILDER.KITS)
        for name in sources:
            destination = repo / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((ROOT / name).read_bytes())
        for kit in BUILDER.KITS:
            skill = repo / 'skills' / kit['skill']
            skill.mkdir(parents=True)
            (skill / 'SKILL.md').write_text('---\nname: ' + kit['skill'] + '\nversion: ' + kit['skill_version'] + '\n---\n')
            (skill / 'tracked.txt').write_text('authored original\n')
            for name in kit['inputs']:
                path = repo / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'synthetic fixture for packaging tests')
        (repo / '.gitignore').write_text('config.yaml\nconfig.yml\n*.local.*\nout/\nruns/\ndist/\n')
        self.git(repo, 'init', '-q')
        self.git(repo, 'add', '--all')
        self.git(repo, '-c', 'user.name=Task Kit Test', '-c', 'user.email=task-kit-test@example.invalid',
                 'commit', '-qm', 'Private packaging fixture')
        return repo

    @staticmethod
    def git(repo, *args):
        return subprocess.run(['git', *args], cwd=repo, capture_output=True, text=True, check=True).stdout

    def test_only_tracked_skill_files_packaged_ignored_local_data_never_leaks(self):
        with tempfile.TemporaryDirectory(prefix='private git packaging ') as folder:
            base = Path(folder)
            repo = self.private_repository(base)
            original = repo / 'skills/api-diff'
            extras = ['config.yaml', 'config.yml', 'credentials.local.json',
                      'out/report.txt', 'runs/result.txt', 'dist/old.zip', 'untracked-extra.txt']
            marker = b'PRIVATE-LOCAL-DATA-NOT-FOR-RELEASE'
            for name in extras:
                path = original / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(marker)
            with mock.patch.object(BUILDER, 'ROOT', repo):
                release = BUILDER.build('0.1.0', base / 'packed')
            self.assertTrue(release['source']['included_files_clean'])
            self.assertEqual(release['source']['snapshot'], 'commit')
            with zipfile.ZipFile(base / 'packed/api-diff-test-task-kit-0.1.0.zip') as archive:
                skill_names = [n for n in archive.namelist() if '/skill/' in n]
                self.assertEqual({n.split('/skill/', 1)[1] for n in skill_names}, {'SKILL.md', 'tracked.txt'})
                self.assertFalse(any(marker in archive.read(n) for n in archive.namelist()))
            # The builder must leave every excluded local file untouched.
            self.assertTrue(all((original / name).read_bytes() == marker for name in extras))

    def test_head_byte_comparison_detects_dirty_assume_unchanged_source(self):
        with tempfile.TemporaryDirectory(prefix='private git dirty source ') as folder:
            base = Path(folder)
            repo = self.private_repository(base)
            name = 'skills/api-diff/tracked.txt'
            self.git(repo, 'update-index', '--assume-unchanged', name)
            (repo / name).write_bytes(b'changed despite index flag\n')
            self.assertEqual(self.git(repo, 'status', '--porcelain'), '')
            with mock.patch.object(BUILDER, 'ROOT', repo):
                release = BUILDER.build('0.1.0', base / 'packed')
            self.assertFalse(release['source']['included_files_clean'])
            self.assertEqual(release['source']['snapshot'], 'working_tree_with_recorded_hashes')
            with zipfile.ZipFile(base / 'packed/api-diff-test-task-kit-0.1.0.zip') as archive:
                manifest = json.loads(archive.read('api-diff-test-task-kit-0.1.0/kit-manifest.json'))
                self.assertFalse(manifest['source']['included_files_clean'])
                entry = next(e for e in manifest['files'] if e['path'] == 'skill/tracked.txt')
                self.assertEqual(entry['sha256'], sha(repo / name))

    def test_missing_or_symlink_tracked_source_rejected(self):
        with tempfile.TemporaryDirectory(prefix='private git invalid source ') as folder:
            base = Path(folder)
            repo = self.private_repository(base)
            tracked = repo / 'skills/api-diff/tracked.txt'
            tracked.unlink()
            with mock.patch.object(BUILDER, 'ROOT', repo):
                with self.assertRaisesRegex(ValueError, 'Not a regular source file'):
                    BUILDER.build('0.1.0', base / 'missing')
            target = base / 'outside.txt'
            target.write_text('do not package link targets')
            try:
                tracked.symlink_to(target)
            except OSError:
                self.skipTest('Symlinks unavailable in this environment')
            with mock.patch.object(BUILDER, 'ROOT', repo):
                with self.assertRaisesRegex(ValueError, 'Symlink source rejected'):
                    BUILDER.build('0.1.0', base / 'linked')
            self.assertFalse((base / 'missing').exists())
            self.assertFalse((base / 'linked').exists())

    def test_safe_names_and_semver(self):
        for name in ('../escape', '/absolute', 'a/../../escape', 'C:/file', 'a\\b'):
            with self.assertRaises(ValueError):
                BUILDER.safe_name(name)
        with self.assertRaises(ValueError):
            BUILDER.build('task-kits-v0.1.0', self.base / 'bad version')
        link = self.base / 'existing-link'
        try:
            link.symlink_to(self.base / 'not-existing')
        except OSError:
            self.skipTest('Symlinks unavailable in this environment')
        folder = self.unpack('pptx-making')
        result = self.run_kit(folder, '--demo', '--out-dir', link)
        self.assertEqual(result.returncode, 1)
        self.assertTrue(link.is_symlink())
        self.assertFalse((self.base / 'not-existing').exists())


if __name__ == '__main__':
    unittest.main()
