#!/usr/bin/env python3
"""Replay synthetic AutoFit cases against the checker; Python standard library only.

Does not open PowerPoint or validate rendered layout. Code: MIT, see ../../LICENSE.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile


ROOT = Path(__file__).resolve().parents[2]
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
BASE = ROOT / 'examples/pptx-fonts/inputs/after.pptx'
CHECKER = ROOT / 'skills/pptx-making/scripts/pptx_check.py'
# Expectations are fixed from the documented scale semantics, not the parser.
CASES = (
    ('no_autofit', None, []),
    ('default_scale', {}, []),
    ('integer_100_percent', {'fontScale': '100000'}, []),
    ('string_100_percent', {'fontScale': '100.000%'}, []),
    ('line_spacing_only', {'lnSpcReduction': '20000'}, []),
    ('full_scale_and_line_spacing', {'fontScale': '100000', 'lnSpcReduction': '20000'}, []),
    ('integer_62_5_percent', {'fontScale': '62500'}, ['auto_shrink']),
    ('string_62_5_percent', {'fontScale': '62.500%'}, ['auto_shrink']),
    ('integer_1_percent', {'fontScale': '1000'}, ['auto_shrink']),
    ('string_1_percent', {'fontScale': '1%'}, ['auto_shrink']),
    ('integer_99_999_percent', {'fontScale': '99999'}, ['auto_shrink']),
    ('string_99_999_percent', {'fontScale': '99.999%'}, ['auto_shrink']),
    ('below_supported_integer_range', {'fontScale': '999'}, ['unresolved_font_scale']),
    ('above_supported_integer_range', {'fontScale': '100001'}, ['unresolved_font_scale']),
    ('zero', {'fontScale': '0'}, ['unresolved_font_scale']),
    ('negative', {'fontScale': '-1'}, ['unresolved_font_scale']),
    ('non_finite', {'fontScale': 'NaN%'}, ['unresolved_font_scale']),
    ('unknown_text', {'fontScale': 'unknown'}, ['unresolved_font_scale']),
    ('unicode_digits', {'fontScale': '６２５００'}, ['unresolved_font_scale']),
    ('oversized_integer', {'fontScale': '9' * 6000}, ['unresolved_font_scale']),
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_input(path, attributes):
    with zipfile.ZipFile(BASE) as source, zipfile.ZipFile(path, 'x') as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == 'ppt/slides/slide1.xml':
                slide = ET.fromstring(data)
                body = next(slide.iter(A + 'bodyPr'))
                for child in list(body):
                    if child.tag in {A + 'normAutofit', A + 'noAutofit', A + 'spAutoFit'}:
                        body.remove(child)
                if attributes is not None:
                    ET.SubElement(body, A + 'normAutofit', attributes)
                data = ET.tostring(slide, encoding='utf-8', xml_declaration=True)
            target.writestr(info, data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir', type=Path, required=True, help='New output directory only')
    parser.add_argument('--checker', type=Path, default=CHECKER)
    args = parser.parse_args()
    original_hash, checker_hash = digest(BASE), digest(args.checker)
    args.out_dir.mkdir(parents=True, exist_ok=False)
    results = []
    for name, attributes, expected in CASES:
        source = args.out_dir / (name + '.pptx')
        make_input(source, attributes)
        before = digest(source)
        run = subprocess.run([sys.executable, '-I', '-B', str(args.checker.resolve()),
                              str(source.resolve()), '--json'], capture_output=True, text=True)
        (args.out_dir / (name + '.stdout.json')).write_text(run.stdout, encoding='utf-8')
        (args.out_dir / (name + '.stderr.txt')).write_text(run.stderr, encoding='utf-8')
        try:
            report = json.loads(run.stdout)
            actual = [issue['code'] for issue in report['issues']]
            coverage = report['font_size_coverage']
            passed = (actual == expected and run.returncode == (3 if expected else 0)
                      and report['source']['sha256'] == before
                      and coverage['text_piece_count'] == 8 and coverage['unresolved_count'] == 1)
        except (ValueError, KeyError):
            actual, passed = None, False
        unchanged = digest(source) == before
        results.append({'case': name, 'expected_issue_codes': expected, 'issue_codes': actual,
                        'exit_code': run.returncode, 'input_sha256': before,
                        'input_unchanged': unchanged, 'passed': passed and unchanged})
    summary = {'synthetic': True, 'visual_rendering_verified': False,
               'base_unchanged': digest(BASE) == original_hash,
               'checker_unchanged': digest(args.checker) == checker_hash,
               'checker_sha256': checker_hash, 'cases': results,
               'passed': sum(item['passed'] for item in results), 'total': len(results)}
    (args.out_dir / 'verification.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)
                                                   + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k != 'cases'}, ensure_ascii=False))
    return 0 if (summary['passed'] == summary['total'] and summary['base_unchanged']
                 and summary['checker_unchanged']) else 1


if __name__ == '__main__':
    sys.exit(main())
