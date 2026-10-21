#!/usr/bin/env python3
"""Run the included task demo, or process your own car/PPT input. Python 3.9+; MIT."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys

HERE = Path(__file__).resolve().parent
CAR_FIXTURES = {'missing-fee': 'two-quotes-missing-fee.json', 'complete-fee': 'two-quotes-complete.json'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text('utf-8'))


def write_json(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as target:
        target.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_package():
    manifest = read_json(HERE / 'kit-manifest.json')
    original = {}
    for entry in manifest['files']:
        name = entry['path']
        relative = PurePosixPath(name)
        require(not relative.is_absolute() and '..' not in relative.parts and '\\' not in name and ':' not in name,
                'Unsafe path in kit manifest')
        path = HERE.joinpath(*relative.parts)
        require(not any(HERE.joinpath(*relative.parts[:i]).is_symlink()
                        for i in range(1, len(relative.parts) + 1)), 'Symlink in task kit: ' + name)
        require(path.is_file() and digest(path) == entry['sha256'], 'Task kit file changed: ' + name)
        original[path] = entry['sha256']
    # Include the manifest in the no-modification check too (it cannot hash itself).
    original[HERE / 'kit-manifest.json'] = digest(HERE / 'kit-manifest.json')
    return original


def command(command_args, output, stem):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    result = subprocess.run([sys.executable, '-B', *map(str, command_args)], capture_output=True,
                            env=env, timeout=60)
    (output / (stem + '.stdout.txt')).write_bytes(result.stdout)
    (output / (stem + '.stderr.txt')).write_bytes(result.stderr)
    return {'name': stem, 'exit_code': result.returncode,
            'stdout': stem + '.stdout.txt', 'stderr': stem + '.stderr.txt'}


def car_task(source, output, name):
    return command([HERE / 'skill/scripts/compare_quotes.py', '--input', source,
                    '--out-dir', output / name], output, name)


def verify_car(output):
    missing = read_json(output / 'missing-fee/comparison.json')
    complete = read_json(output / 'complete-fee/comparison.json')
    for name, report in (('missing-fee', missing), ('complete-fee', complete)):
        fixture = HERE / 'skill/examples' / CAR_FIXTURES[name]
        require(report['input_sha256'] == digest(fixture), name + ': wrong input hash')
        require(report['quotes'][0]['finance_fee']['value'] == '15000', name + ': wrong quote A fees')
    right = missing['quotes'][1]['finance_fee']
    require(right['complete'] is False and right['value'] is None and right['known_subtotal'] == '10500',
            'Missing fee must remain unknown, with known subtotal 10500')
    require(right['missing_fields'] == ['/quotes/1/finance/fees_outside_total'], 'Wrong missing field')
    for metric in ('finance_fee', 'recorded_total'):
        left = next(c for c in missing['comparisons'] if c['scope'] == metric)
        right = next(c for c in complete['comparisons'] if c['scope'] == metric)
        require(left['comparable'] is False and left['right_minus_left'] is None,
                metric + ': incomplete quote must not be compared')
        require(right['comparable'] is True and right['right_minus_left'] == '1500',
                metric + ': complete synthetic difference must be 1500')
    require(complete['quotes'][1]['finance_fee']['value'] == '16500', 'Wrong complete quote B fees')


def ppt_task(source, output, name):
    entries = []
    for mode, extra, suffix in (('human', [], 'txt'), ('json', ['--json'], 'json')):
        entry = command([HERE / 'skill/scripts/pptx_check.py', source, *extra], output, name + '.' + mode)
        # Keep the original report bytes in directly readable .txt/.json files.
        (output / (name + '.' + suffix)).write_bytes((output / entry['stdout']).read_bytes())
        entries.append(entry)
    return entries


def verify_ppt(output):
    for name, small in (('before', 2), ('after', 0)):
        report = read_json(output / (name + '.json'))
        require(report['source']['sha256'] == digest(HERE / 'inputs' / (name + '.pptx')), name + ': wrong input hash')
        require(report['slide_count'] == 4, name + ': wrong slide count')
        coverage = report['font_size_coverage']
        for key, expected in {'text_piece_count': 8, 'resolved_count': 7, 'unresolved_count': 1,
                              'small_count': small, 'unreadable_slide_count': 0}.items():
            require(coverage[key] == expected, name + ': wrong ' + key)
        issues = report['issues']
        require(len(issues) == small and all(i['code'] == 'small_font' for i in issues), name + ': unexpected issues')
        pieces = coverage['text_pieces']
        for slide, source in ((1, 'paragraph'), (2, 'list_style')):
            matches = [p for p in pieces if p['slide'] == slide and p['font_source'] == source]
            require(len(matches) == 1 and matches[0]['font_size_pt'] == (8 if name == 'before' else 24),
                    name + ': wrong inherited font on slide ' + str(slide))
        overrides = [p for p in pieces if p['slide'] == 3 and p['font_size_pt'] == 24]
        require(len(overrides) == 1 and overrides[0]['font_source'] == 'run', name + ': explicit 24pt override lost')
        unknown = [p for p in pieces if p['font_size_pt'] is None]
        require(len(unknown) == 1 and unknown[0]['slide'] == 4, name + ': unknown font lost')
        if name == 'after':
            require(report['status'] == 'no_issues_in_checked_scope', 'Do not claim a complete visual pass')


def api_demo(output, runs):
    entry = command([HERE / 'skill/examples/local_order_demo.py', '--out', output / 'demo'], output, 'demo')
    runs.append(entry)
    require(entry['exit_code'] == 0, 'API demo failed; inspect demo.stderr.txt (loopback server permission may be required)')
    report = read_json(output / 'demo/verification.json')
    require(report['verified'] is True and report['synthetic'] is True, 'API demo verification failed')
    require(report['external_requests'] is False and report['credentials_used'] is False,
            'API demo scope differs from loopback/no-credential contract')
    outcomes = report['outcomes']
    expected = {'$.paid_amount', '$.items[0].quantity', '$.can_refund', '$.note'}
    require(outcomes['regressed']['exit_code'] == 1 and set(outcomes['regressed']['diff_paths']) == expected,
            'API regression paths or original exit code differ')
    require(outcomes['repaired']['exit_code'] == 0 and outcomes['repaired']['verdict'] == 'same',
            'API repaired response is not equal')
    require(report['fixture_sha256'] == digest(HERE / 'skill/examples/order-responses.json')
            and report['script_sha256'] == digest(HERE / 'skill/scripts/api_diff.py'), 'API source hashes differ')
    requests = report['requests']
    require(len(requests) == 2 and all(len(side) == 2 for side in requests)
            and all(request == {'method': 'GET', 'path': '/api/orders/DEMO-001'}
                    for side in requests for request in side), 'Unexpected API request scope')


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--demo', action='store_true', help='Run included synthetic cases and verify explicit expected results')
    mode.add_argument('--input', type=Path, help='Your own quote JSON or .pptx; never modified')
    parser.add_argument('--out-dir', required=True, type=Path, help='A directory that does not yet exist, even if empty')
    args = parser.parse_args()
    output = args.out_dir.expanduser().absolute()
    summary = {'schema_version': 1, 'mode': 'demo' if args.demo else 'own_input',
               'demo_verified': False if args.demo else None, 'runs': [], 'errors': []}
    created = False
    result_code = 1
    original = {}
    try:
        require(sys.version_info >= (3, 9), 'Python 3.9 or later is required')
        original = verify_package()
        config = read_json(HERE / 'kit.json')
        summary.update(kit_id=config['kit_id'], kit_version=config['kit_version'], skill_version=config['skill_version'])
        require(args.demo or config['kit_id'] != 'api-diff-test',
                'API own-input usage is documented in START-HERE.md; call the original api_diff.py CLI')
        source = None
        if args.input is not None:
            source = args.input.expanduser().absolute()
            require(source.is_file() and not source.is_symlink(), 'Input must be a regular file, not a symlink')
            original[source] = digest(source)
            summary['input'] = {'filename': source.name, 'sha256': original[source]}
        # mkdir is the atomic no-overwrite gate, including dangling symlinks and empty directories.
        output.mkdir(parents=True, exist_ok=False)
        created = True
        kind = config['kit_id']
        if kind == 'api-diff-test':
            api_demo(output, summary['runs'])
        elif kind == 'car-buying-checklist':
            if args.demo:
                for name in ('missing-fee', 'complete-fee'):
                    summary['runs'].append(car_task(HERE / 'skill/examples' / CAR_FIXTURES[name], output, name))
                require(all(r['exit_code'] == 0 for r in summary['runs']), 'Car demo script failed; inspect stderr files')
                verify_car(output)
            else:
                summary['runs'].append(car_task(source, output, 'comparison'))
        elif kind == 'pptx-making':
            names = ('before', 'after') if args.demo else ('input',)
            for name in names:
                summary['runs'].extend(ppt_task(HERE / 'inputs' / (name + '.pptx') if args.demo else source, output, name))
            if args.demo:
                require([r['exit_code'] for r in summary['runs']] == [3, 3, 0, 0], 'PPT demo exit codes differ')
                verify_ppt(output)
        else:
            raise ValueError('Unknown task kit')
        if args.demo:
            summary.update(demo_verified=True, status='demo_expectations_verified')
            result_code = 0
        else:
            codes = [r['exit_code'] for r in summary['runs']]
            result_code = next((code for code in codes if code != 0), 0)
            summary['status'] = ('issues_found_in_checked_scope' if kind == 'pptx-making' and all(c == 3 for c in codes)
                                 else 'input_processed' if result_code == 0 else 'source_script_failed')
            summary['check_completed'] = all(c in (0, 3) for c in codes) if kind == 'pptx-making' else result_code == 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        summary['errors'].append(str(error))
        summary['status'] = 'failed'
        summary['demo_verified'] = False if args.demo else None
        print('Task failed: ' + str(error), file=sys.stderr)
        result_code = 1
    finally:
        if original:
            try:
                summary['inputs_and_kit_unchanged'] = all(digest(path) == sha for path, sha in original.items())
            except OSError:
                summary['inputs_and_kit_unchanged'] = False
            if not summary['inputs_and_kit_unchanged']:
                summary['status'] = 'failed'
                summary['demo_verified'] = False if args.demo else None
                summary['errors'].append('An input or task kit file changed during execution')
                result_code = 1
        if created:
            write_json(output / 'verification.json', summary)
    if created:
        print(json.dumps({'output': str(output), 'status': summary['status'], 'demo_verified': summary['demo_verified'],
                          'exit_code': result_code}, ensure_ascii=False, indent=2))
    return result_code


if __name__ == '__main__':
    sys.exit(main())
