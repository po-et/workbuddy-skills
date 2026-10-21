#!/usr/bin/env python3
"""Build deterministic standalone task ZIPs using only the Python standard library.

Code: MIT. See LICENSE. This builder never installs or publishes anything.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = 'https://github.com/po-et/workbuddy-skills'
KITS = (
    {'id': 'api-diff-test', 'skill': 'api-diff', 'skill_version': '0.1.1', 'inputs': ()},
    {'id': 'car-buying-checklist', 'skill': 'car-buying-checklist', 'skill_version': '0.1.2', 'inputs': ()},
    {'id': 'pptx-making', 'skill': 'pptx-making', 'skill_version': '0.1.2',
     'inputs': ('examples/pptx-fonts/inputs/before.pptx', 'examples/pptx-fonts/inputs/after.pptx')},
)
EXCLUDED = {'.git', '.DS_Store', '__pycache__', '.pytest_cache', '.venv'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8')


def safe_name(name):
    path = PurePosixPath(name)
    if not name or path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:
        raise ValueError('Unsafe archive path: ' + name)
    return name


def read_source(path):
    relative = path.relative_to(ROOT)
    if any((ROOT / Path(*relative.parts[:i])).is_symlink() for i in range(1, len(relative.parts) + 1)):
        raise ValueError('Symlink source rejected: ' + relative.as_posix())
    if not path.is_file():
        raise ValueError('Not a regular source file: ' + relative.as_posix())
    return path.read_bytes()


def source_commit():
    run = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True, check=True)
    commit = run.stdout.strip()
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Cannot resolve source commit')
    return commit


def collect_sources():
    """Snapshot tracked skill files plus the explicit kit build inputs.

    Untracked/ignored files beside a skill never become release assets. New kit
    templates may be uncommitted during development, but are marked as such.
    """
    paths = {'tools/task_kits.py', 'taskkits/start.py', 'LICENSE', 'LICENSE-CONTENT',
             '.github/ISSUE_TEMPLATE/task-kit-feedback.md'}
    for kit in KITS:
        prefix = 'skills/' + kit['skill'] + '/'
        run = subprocess.run(['git', 'ls-files', '-z', '--', prefix], cwd=ROOT,
                             capture_output=True, text=True, check=True)
        for name in run.stdout.split('\0'):
            if not name:
                continue
            safe_name(name)
            if not name.startswith(prefix):
                raise ValueError('Tracked file outside skill prefix: ' + name)
            relative = PurePosixPath(name[len(prefix):])
            if any(part in EXCLUDED for part in relative.parts) or relative.suffix in ('.pyc', '.pyo'):
                continue
            paths.add(name)
        paths.update(kit['inputs'])
        paths.add('taskkits/' + kit['id'] + '.md')
    return {name: read_source(ROOT / name) for name in sorted(paths)}


def source_clean(sources, commit):
    """Compare exact snapshotted bytes with HEAD blobs; never trust index flags."""
    for name, raw in sources.items():
        run = subprocess.run(['git', 'cat-file', 'blob', commit + ':' + name],
                             cwd=ROOT, capture_output=True)
        if run.returncode != 0 or run.stdout != raw:
            return False
    return True


def kit_archive(kit, version, commit, clean, sources):
    """Return archive bytes and public metadata; retain every authored skill file."""
    files, origins = {}, {}

    def add(name, source):
        name = safe_name(name)
        if name in files:
            raise ValueError('Duplicate archive path: ' + name)
        origin = source.relative_to(ROOT).as_posix()
        files[name] = sources[origin]
        origins[name] = origin

    prefix = 'skills/' + kit['skill'] + '/'
    for origin in sorted(sources):
        if origin.startswith(prefix):
            add('skill/' + origin[len(prefix):], ROOT / origin)
    skill_text = files['skill/SKILL.md'].decode('utf-8')
    match = re.search(r'^version:\s*[\'"]?([^\s\'\"]+)', skill_text, re.M)
    if match is None or match.group(1) != kit['skill_version']:
        raise ValueError('Skill version differs from pinned kit source: ' + kit['skill'])
    for source in kit['inputs']:
        add('inputs/' + Path(source).name, ROOT / source)
    add('start.py', ROOT / 'taskkits' / 'start.py')
    add('LICENSE', ROOT / 'LICENSE')
    add('LICENSE-CONTENT', ROOT / 'LICENSE-CONTENT')
    add('FEEDBACK.md', ROOT / '.github/ISSUE_TEMPLATE/task-kit-feedback.md')
    add('START-HERE.md', ROOT / 'taskkits' / (kit['id'] + '.md'))
    files['ATTRIBUTION.md'] = (
        '# 来源与许可\n\n'
        'Captain (https://github.com/po-et), workbuddy-skills.\n\n'
        '源代码仓库：' + REPOSITORY + '\n\n'
        '源提交：`' + commit + '`；原技能：`skills/' + kit['skill'] + '` '
        + kit['skill_version'] + '；任务包：' + version + '。\n\n'
        '原技能文件完整保留在 skill/，未作修改；新增入口、说明与合成案例打包供独立运行。\n\n'
        '代码使用 MIT（见 LICENSE）；技能正文、模板、说明及合成示例内容使用 '
        'CC BY 4.0（见 LICENSE-CONTENT，https://creativecommons.org/licenses/by/4.0/）。'
        '转载或改编这些内容时保留作者与来源，并注明改动。\n'
    ).encode('utf-8')
    origins['ATTRIBUTION.md'] = 'generated'
    config = {'kit_id': kit['id'], 'kit_version': version, 'skill_version': kit['skill_version'],
              'platform_slug': kit['id'], 'namespace': 'indiv-captain'}
    files['kit.json'] = json_bytes(config)
    origins['kit.json'] = 'generated'
    manifest = {
        'schema_version': 1, **config,
        'source': {'repository': REPOSITORY, 'commit': commit, 'skill_path': 'skills/' + kit['skill'],
                   'included_files_clean': clean, 'snapshot': 'commit' if clean else 'working_tree_with_recorded_hashes',
                   'builder_sha256': sha(sources['tools/task_kits.py'])},
        'runtime': {'python': '3.9+', 'dependencies': 'standard library only'},
        'manifest_scope': 'All files except kit-manifest.json itself; SHA256 of uncompressed bytes.',
        'files': [{'path': name, 'sha256': sha(files[name]), 'bytes': len(files[name]), 'origin': origins[name]}
                  for name in sorted(files)],
    }
    files['kit-manifest.json'] = json_bytes(manifest)
    folder = kit['id'] + '-task-kit-' + version
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(folder + '/' + safe_name(name), date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, files[name], compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    raw = buffer.getvalue()
    return raw, {'kit_id': kit['id'], 'skill_version': kit['skill_version'], 'file': folder + '.zip',
                 'sha256': sha(raw), 'bytes': len(raw), 'root_directory': folder,
                 'packaged_file_count': len(files)}


def build(version, out_dir):
    if not re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', version):
        raise ValueError('--version must be a semantic version such as 0.1.0')
    commit = source_commit()
    # Validate and assemble all sources before creating the requested directory.
    sources = collect_sources()
    clean = source_clean(sources, commit)
    prepared = [kit_archive(kit, version, commit, clean, sources) for kit in KITS]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=False)
    assets = []
    for raw, entry in prepared:
        with (out_dir / entry['file']).open('xb') as target:
            target.write(raw)
        assets.append(entry)
    release = {'schema_version': 1, 'version': version, 'tag': 'task-kits-v' + version,
               'source': {'repository': REPOSITORY, 'commit': commit, 'included_files_clean': clean,
                          'snapshot': 'commit' if clean else 'working_tree_with_recorded_hashes',
                          'builder_sha256': sha(sources['tools/task_kits.py'])}, 'assets': assets,
               'reproducibility': 'Fixed archive timestamps, order and permissions; same sources and Python/zlib runtime produce identical bytes.'}
    with (out_dir / 'release-manifest.json').open('xb') as target:
        target.write(json_bytes(release))
    checksums = [(entry['file'], entry['sha256']) for entry in assets]
    checksums.append(('release-manifest.json', sha((out_dir / 'release-manifest.json').read_bytes())))
    with (out_dir / 'SHA256SUMS.txt').open('x', encoding='utf-8', newline='\n') as target:
        target.write(''.join(digest + '  ' + name + '\n' for name, digest in sorted(checksums)))
    return release


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--version', default='0.1.0')
    parser.add_argument('--out-dir', type=Path, required=True, help='Must not already exist, including an empty directory')
    args = parser.parse_args()
    try:
        result = build(args.version, args.out_dir)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print('Build failed: ' + str(error), file=sys.stderr)
        return 1
    print(json.dumps({'output': str(args.out_dir.resolve()), 'version': result['version'],
                      'files': [a['file'] for a in result['assets']]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
