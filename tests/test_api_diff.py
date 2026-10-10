"""API diff CLI regressions using synthetic loopback HTTP responses only."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "skills/api-diff/scripts/api_diff.py"


class APIResponseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.responses = [{}, {}]
        self.hits = [[], []]
        self.bases = []
        for side in range(2):
            responses, hits = self.responses[side], self.hits[side]

            class Handler(BaseHTTPRequestHandler):
                def handle_request(self, responses=responses, hits=hits):
                    hits.append((self.command, self.path, dict(self.headers)))
                    status, body, content_type = responses.get(self.path, (200, {}, "application/json"))
                    self.send_response(status)
                    self.send_header("Content-Type", content_type)
                    if status == 302:
                        self.send_header("Location", "/redirect-target")
                    self.end_headers()
                    data = body if isinstance(body, bytes) else json.dumps(body).encode() if content_type == "application/json" else body.encode()
                    if self.command != "HEAD":
                        self.wfile.write(data)

                do_GET = handle_request
                do_HEAD = handle_request
                do_POST = handle_request

                def log_message(self, *args):
                    pass

            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)
            self.bases.append(f"http://127.0.0.1:{server.server_port}")

    def cli(self, left=None, right=None, *, cases=None, args=(), env=None, content_type="application/json", status=200):
        self.responses[0]["/order"] = (status, left, content_type)
        self.responses[1]["/order"] = (status, right, content_type)
        source = self.root / "cases.json"
        source.write_text(json.dumps(cases if cases is not None else [{"name": "synthetic", "path": "/order"}]), encoding="utf-8")
        original = hashlib.sha256(source.read_bytes()).hexdigest()
        out = self.root / "report.json"
        if out.exists():
            out.unlink()
        cli_env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        cli_env.pop("API_DIFF_HEADERS", None)
        cli_env = {key: value for key, value in cli_env.items() if not key.lower().endswith("_proxy")}
        cli_env["NO_PROXY"] = "127.0.0.1,localhost,::1"
        cli_env.update(env or {})
        result = subprocess.run([sys.executable, str(SCRIPT), "--a", self.bases[0], "--b", self.bases[1],
                                 "--cases", str(source), "--out", str(out), *args],
                                text=True, capture_output=True, env=cli_env)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(original, hashlib.sha256(source.read_bytes()).hexdigest())
        return result, json.loads(out.read_text()) if out.exists() else None

    def test_equal_success_and_numeric_representation_pass(self):
        result, report = self.cli({"amount": 12}, {"amount": 12.0})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report[0]["verdict"], "same")

    def test_same_http_failure_cannot_pass(self):
        result, report = self.cli({"error": "unavailable"}, {"error": "unavailable"}, status=500)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report[0]["verdict"], "http_error")

    def test_head_and_no_content_responses_pass_without_json_body(self):
        for status, cases in ((200, [{"path": "/order", "method": "HEAD"}]), (204, None)):
            with self.subTest(status=status):
                result, report = self.cli(b"", b"", status=status, cases=cases)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(report[0]["verdict"], "same")

    def test_distinct_invalid_utf8_text_bytes_are_not_equal(self):
        result, report = self.cli(b"\xff", b"\xfe", content_type="text/plain")
        self.assertEqual(result.returncode, 1)
        self.assertNotEqual(report[0]["a"]["body_sha256"], report[0]["b"]["body_sha256"])

    def test_invalid_utf8_json_is_an_error(self):
        result, report = self.cli(b'{"v":"\xff"}', b'{"v":"\xfe"}')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report[0]["verdict"], "error")

    def test_boolean_and_number_are_different_json_types(self):
        result, report = self.cli({"enabled": False}, {"enabled": 0})
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report[0]["diffs"][0]["kind"], "type")
        self.assertEqual(report[0]["diffs"][0]["path"], "$.enabled")

    def test_missing_and_explicit_null_stay_distinct(self):
        result, report = self.cli({"note": None}, {})
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report[0]["diffs"][0]["kind"], "only_in_a")

    def test_root_null_and_empty_text_stay_distinct(self):
        self.responses[1]["/text"] = (200, "", "text/plain")
        result, report = self.cli(None, None, cases=[{"path": "/order", "path_b": "/text"}])
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report[0]["diffs"][0]["kind"], "format")

    def test_arrays_report_lengths_and_nested_values(self):
        result, report = self.cli({"items": [{"qty": 2}, {"qty": 1}]}, {"items": [{"qty": 3}]})
        self.assertEqual(result.returncode, 1)
        self.assertEqual({d["path"] for d in report[0]["diffs"]}, {"$.items", "$.items[0].qty"})

    def test_id_ignore_does_not_hide_order_id(self):
        result, report = self.cli({"id": "volatile-a", "order_id": "one"},
                                  {"id": "volatile-b", "order_id": "two"}, args=("--ignore", "id"))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report[0]["ignored_paths"], ["$.id"])
        self.assertEqual(report[0]["diffs"][0]["path"], "$.order_id")

    def test_noise_is_ignored_but_actual_paths_are_reported(self):
        result, report = self.cli({"trace_id": "a", "data": {"updated_at": "old", "amount": 12}},
                                  {"trace_id": "b", "data": {"updated_at": "new", "amount": 12}},
                                  args=("--ignore", "trace_id,updated_at"))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(report[0]["ignored_paths"], ["$.data.updated_at", "$.trace_id"])

    def test_business_fields_cannot_be_silently_ignored(self):
        for left, right, pattern in (({"paidAmount": 100}, {"paidAmount": 90}, ".*"),
                                     ({"data": {"quantity": 2}}, {"data": {"quantity": 3}}, "data")):
            with self.subTest(pattern=pattern):
                result, report = self.cli(left, right, args=("--ignore", pattern))
                self.assertEqual(result.returncode, 2)
                self.assertTrue(report[0]["ignore_rejected"])
                self.assertTrue(report[0]["diffs"])

    def test_text_changes_after_4000_characters_are_not_lost(self):
        result, report = self.cli("a" * 5000 + "old", "a" * 5000 + "new", content_type="text/plain")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report[0]["diffs"][0]["kind"], "text")

    def test_json_parse_errors_are_failures(self):
        for invalid in ('{"broken":', '{"amount":NaN}', '{"amount":1,"amount":2}'):
            with self.subTest(invalid=invalid):
                self.responses[1]["/broken"] = (200, invalid, "application/problem+json; charset=utf-8")
                result, report = self.cli({}, {}, cases=[{"path": "/order", "path_b": "/broken"}])
                self.assertEqual(result.returncode, 1)
                self.assertEqual(report[0]["verdict"], "error")

    def test_post_requires_explicit_write_opt_in(self):
        result, report = self.cli({}, {}, cases=[{"path": "/order", "method": "POST", "body": {"q": "synthetic"}}])
        self.assertEqual(result.returncode, 2)
        self.assertIsNone(report)
        self.assertEqual(self.hits, [[], []])
        result, report = self.cli({}, {}, cases=[{"path": "/order", "method": "POST", "body": {"q": "synthetic"}}],
                                  args=("--allow-write",))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.hits[0][0][0], "POST")

    def test_external_endpoint_is_blocked_before_any_request(self):
        result, _ = self.cli({}, {}, args=("--b", "https://example.invalid"))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.hits, [[], []])

    def test_credentials_in_cases_are_rejected_without_echo(self):
        for header in ("Authorization", "Cookie", "X-API-Key", "X-Custom-Token"):
            with self.subTest(header=header):
                secret = "SYNTHETIC_SECRET_MUST_NOT_APPEAR"
                result, _ = self.cli({}, {}, cases=[{"path": "/order", "headers": {header: secret}}])
                self.assertEqual(result.returncode, 2)
                self.assertNotIn(secret, result.stdout + result.stderr)
                self.assertEqual(self.hits, [[], []])

    def test_environment_headers_are_sent_without_echo(self):
        secret = "SYNTHETIC_TOKEN_DO_NOT_REPORT"
        result, report = self.cli({}, {}, env={"API_DIFF_HEADERS": json.dumps({"Authorization": "Bearer " + secret})})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.hits[0][0][2]["Authorization"], "Bearer " + secret)
        self.assertNotIn(secret, result.stdout + result.stderr + json.dumps(report))

    def test_reflected_environment_credentials_are_redacted(self):
        secret = "SYNTHETIC_TOKEN_DO_NOT_REPORT_" + "x" * 90
        result, report = self.cli({"echo": secret}, {"echo": "different"},
                                  env={"API_DIFF_HEADERS": json.dumps({"Authorization": "Bearer " + secret})})
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report[0]["diffs"][0]["a"], "[hidden]")
        self.assertNotIn("SYNTHETIC_TOKEN", result.stdout + result.stderr + json.dumps(report))

    def test_short_cookie_values_cannot_mutate_report_schema(self):
        result, report = self.cli({"amount": 12}, {"amount": 12},
                                  env={"API_DIFF_HEADERS": '{"Cookie":"ab=a; lang=en"}'})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("name", report[0])
        self.assertEqual(report[0]["verdict"], "same")

    def test_cookie_value_colliding_with_verdict_preserves_semantics(self):
        result, report = self.cli({"label": "same"}, {"label": "same"},
                                  cases=[{"name": "same", "path": "/order"}],
                                  env={"API_DIFF_HEADERS": '{"Cookie":"feature=same"}'})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(report[0]["verdict"], "same")
        self.assertEqual(report[0]["name"], "[hidden]")
        self.assertIn("一致 1", result.stdout)

    def test_decimal_changes_are_not_lost_to_float_rounding(self):
        self.responses[0]["/precise"] = (200, '{"paidAmount":1.0000000000000001}', "application/problem+json")
        self.responses[1]["/precise"] = (200, '{"paidAmount":1.0}', "application/problem+json")
        result, report = self.cli({}, {}, cases=[{"path": "/precise"}])
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report[0]["diffs"][0]["path"], "$.paidAmount")

    def test_redirect_is_not_followed(self):
        result, report = self.cli("", "", status=302, content_type="text/plain")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report[0]["verdict"], "http_error")
        self.assertEqual([h[1] for h in self.hits[0]], ["/order"])

    def test_invalid_input_fails_before_any_request(self):
        for cases, args in (([], ()), ([{"path": "//example.com"}], ()),
                            ([{"path": "/order"}], ("--timeout", "nan")),
                            ([{"path": "/order"}], ("--ignore", "["))):
            with self.subTest(cases=cases, args=args):
                result, _ = self.cli({}, {}, cases=cases, args=args)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(self.hits, [[], []])

    def test_network_failure_is_not_equal_failure(self):
        result, report = self.cli({}, {}, args=("--a", "http://127.0.0.1:1", "--b", "http://127.0.0.1:1", "--timeout", "0.2"))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report[0]["verdict"], "error")

    def test_large_difference_set_is_marked_as_truncated(self):
        result, report = self.cli({f"field_{i:03d}": 1 for i in range(250)},
                                  {f"field_{i:03d}": 2 for i in range(250)})
        self.assertEqual(result.returncode, 1)
        self.assertTrue(report[0]["diffs_truncated"])
        self.assertGreater(report[0]["diff_count"], len(report[0]["diffs"]))

    def test_complete_public_demo_replays_failure_then_success(self):
        demo = SCRIPT.parents[1] / "examples/local_order_demo.py"
        output = self.root / "demo"
        result = subprocess.run([sys.executable, str(demo), "--out", str(output)],
                                text=True, capture_output=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        verified = json.loads((output / "verification.json").read_text())
        self.assertTrue(verified["verified"])
        self.assertEqual(verified["outcomes"]["regressed"]["exit_code"], 1)
        self.assertEqual(verified["outcomes"]["repaired"]["exit_code"], 0)
        self.assertEqual(len(verified["outcomes"]["regressed"]["diff_paths"]), 4)
        original = hashlib.sha256((output / "regressed.json").read_bytes()).hexdigest()
        retry = subprocess.run([sys.executable, str(demo), "--out", str(output)],
                               text=True, capture_output=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(retry.returncode, 2)
        self.assertEqual(original, hashlib.sha256((output / "regressed.json").read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
