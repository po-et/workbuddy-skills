#!/usr/bin/env python3
"""Replay synthetic order responses on two loopback HTTP servers; no credentials."""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/api_diff.py"
FIXTURE = Path(__file__).with_name("order-responses.json")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", help="New or empty output directory; existing reports are preserved")
    parser.add_argument("--script", type=Path, default=SCRIPT,
                        help="Optional alternate CLI for before/after verification")
    args = parser.parse_args()
    output = Path(args.out).resolve() if args.out else Path(tempfile.mkdtemp(prefix="api-diff-demo-"))
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        parser.error("--out must be a new or empty directory")
    output.mkdir(parents=True, exist_ok=True)
    fixture = json.loads(FIXTURE.read_text("utf-8"))
    source_hash = sha(FIXTURE)
    payloads = [fixture["old"], fixture["regressed"]]
    servers, bases, requests = [], [], [[], []]
    try:
        for side in range(2):
            class Handler(BaseHTTPRequestHandler):
                def do_GET(self, side=side):
                    requests[side].append({"method": "GET", "path": self.path})
                    good = self.path == "/api/orders/DEMO-001"
                    self.send_response(200 if good else 404)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(payloads[side] if good else {"error": "not-found"}).encode())

                def log_message(self, *args):
                    pass

            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            servers.append(server)
            bases.append(f"http://127.0.0.1:{server.server_port}")
        cases = output / "cases.json"
        cases.write_text(json.dumps([{"name": "合成订单契约", "method": "GET", "path": "/api/orders/DEMO-001"}],
                                    ensure_ascii=False, indent=2) + "\n", "utf-8")
        cases_hash = sha(cases)
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        env.pop("API_DIFF_HEADERS", None)
        env = {key: value for key, value in env.items() if not key.lower().endswith("_proxy")}
        env["NO_PROXY"] = "127.0.0.1,localhost,::1"
        outcomes = {}
        for phase in ("regressed", "repaired"):
            payloads[1] = fixture[phase]
            command = [sys.executable, str(args.script), "--a", bases[0], "--b", bases[1],
                       "--cases", str(cases), "--ignore", "id,request_id,updated_at", "--timeout", "2",
                       "--out", str(output / f"{phase}.json"), "--md", str(output / f"{phase}.md")]
            process = subprocess.run(command, capture_output=True, text=True, env=env)
            (output / f"{phase}.log").write_text(process.stdout + process.stderr, "utf-8")
            if not (output / f"{phase}.json").exists():
                raise RuntimeError(f"{phase}: CLI did not produce a report (exit {process.returncode})")
            report = json.loads((output / f"{phase}.json").read_text("utf-8"))[0]
            outcomes[phase] = {"exit_code": process.returncode, "verdict": report["verdict"],
                               "diff_paths": [entry["path"] for entry in report["diffs"]],
                               "ignored_paths": report.get("ignored_paths", [])}
        expected = {"$.paid_amount", "$.items[0].quantity", "$.can_refund", "$.note"}
        passed = (outcomes["regressed"]["exit_code"] == 1
                  and set(outcomes["regressed"]["diff_paths"]) == expected
                  and outcomes["repaired"]["exit_code"] == 0
                  and outcomes["repaired"]["verdict"] == "same"
                  and sha(FIXTURE) == source_hash and sha(cases) == cases_hash)
        summary = {"synthetic": True, "external_requests": False, "credentials_used": False,
                   "request_method": "GET", "requests": requests, "outcomes": outcomes,
                   "fixture_sha256": source_hash, "cases_sha256": cases_hash,
                   "script_sha256": sha(args.script), "verified": passed}
        (output / "verification.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", "utf-8")
        print(json.dumps({"output": str(output), "verified": passed, "outcomes": outcomes},
                         ensure_ascii=False, indent=2))
        return 0 if passed else 1
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Demo failed: {error}", file=sys.stderr)
        return 1
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    sys.exit(main())
