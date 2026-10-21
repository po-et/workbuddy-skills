#!/usr/bin/env python3
"""Re-run the public synthetic PPT case; compare actual stdout with client artifacts."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CHECKER = REPO / 'skills/pptx-making/scripts/pptx_check.py'
EXPECTED = {
    'before': ('bd3c23c1ef0447fd7d22b07116735badb38ca26e13cd42c16af17871320adce2', 3, 2),
    'after': ('e019418d9214219547d1a670b44f83939dd222788871ba284e20cb6cf73fe298', 0, 0),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    checked = []
    original = {p: digest(p) for p in [CHECKER, *(HERE / 'inputs').glob('*.pptx')]}
    for name, (expected_sha, exit_code, small_count) in EXPECTED.items():
        source = HERE / 'inputs' / f'{name}.pptx'
        require(digest(source) == expected_sha, f'{name}: fixture hash changed')
        for structured in (False, True):
            suffix = 'json' if structured else 'txt'
            command = [sys.executable, '-B', str(CHECKER), str(source)]
            if structured:
                command.append('--json')
            run = subprocess.run(command, capture_output=True)
            require(run.returncode == exit_code, f'{name}.{suffix}: exit={run.returncode}')
            require(not run.stderr, f'{name}.{suffix}: unexpected stderr')
            recorded = HERE / 'outputs' / f'{name}.{suffix}'
            require(recorded.read_bytes() == run.stdout, f'{name}.{suffix}: stdout differs from recorded client artifact')
            if structured:
                report = json.loads(run.stdout)
                require(report['source']['sha256'] == expected_sha, f'{name}: wrong input hash')
                require(report['slide_count'] == 4, f'{name}: wrong slide count')
                cov = report['font_size_coverage']
                for key, value in {'text_piece_count': 8, 'resolved_count': 7,
                                   'unresolved_count': 1, 'small_count': small_count,
                                   'unreadable_slide_count': 0}.items():
                    require(cov[key] == value, f'{name}: wrong {key}')
                issues = report['issues']
                require(len(issues) == small_count and all(i['code'] == 'small_font' for i in issues), f'{name}: unexpected issues')
                pieces = cov['text_pieces']
                for slide, font_source in ((1, 'paragraph'), (2, 'list_style')):
                    piece = [p for p in pieces if p['slide'] == slide and p['font_source'] == font_source]
                    require(len(piece) == 1 and piece[0]['font_size_pt'] == (8 if name == 'before' else 24), f'{name}: wrong slide {slide} default size')
                third = [p for p in pieces if p['slide'] == 3 and p['font_size_pt'] == 24]
                require(len(third) == 1 and third[0]['font_source'] == 'run', f'{name}: run override lost')
                unknown = [p for p in pieces if p['font_size_pt'] is None]
                require(len(unknown) == 1 and unknown[0]['slide'] == 4, f'{name}: unknown lost')
                if name == 'after':
                    require(report['status'] == 'no_issues_in_checked_scope', 'after: overclaimed pass')
            checked.append({'artifact': f'{name}.{suffix}', 'exit_code': run.returncode,
                            'recorded_stdout_matches': True, 'sha256': digest(recorded)})
    require(all(digest(p) == sha for p, sha in original.items()), 'source or inputs changed during verification')
    print(json.dumps({'case': 'synthetic_ppt_font_styles', 'checks_passed': True,
                      'inputs_and_checker_unchanged': True, 'artifacts': checked,
                      'boundary': 'Maintainer reproduction; no independent-user or PowerPoint-rendering claim.'},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f'Verification failed: {exc}', file=sys.stderr)
        raise SystemExit(1)
