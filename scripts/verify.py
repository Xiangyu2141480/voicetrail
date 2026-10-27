"""Shared CI/developer checks; --real additionally requires every real local gate."""
import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def deny_network(*_args, **_kwargs):
    raise RuntimeError("Network connections forbidden in engineering checks.")


def run(argv, cwd=ROOT, env=None):
    print(f"\nRunning: {' '.join(str(a) for a in argv)}", flush=True)
    subprocess.run([str(a) for a in argv], cwd=cwd, env=env, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real", action="store_true")
    parser.add_argument("--report", type=Path, help="Optional sanitized JSON result")
    parser.add_argument("--engineering-child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.engineering_child:
        socket.socket.connect = deny_network
        socket.create_connection = deny_network
        import pytest
        raise SystemExit(pytest.main(["-q"]))
    if sys.version_info[:2] != (3, 11):
        raise SystemExit("Use the project Python 3.11 environment.")
    for tool in ("ffmpeg", "ffprobe", "node", "npm"):
        if not shutil.which(tool):
            raise SystemExit(f"Required tool missing: {tool}")
    from backend.app.config import Settings
    settings = Settings.from_env()
    env = {**os.environ, "HF_HUB_OFFLINE": "1", "VOICETRAIL_PYTHON": sys.executable}
    if args.real:
        manifest = json.loads((ROOT / "docs/evaluation_manifest.json").read_text())
        for sample in manifest["samples"]:
            path = settings.data_dir / "evaluation" / sample["path"]
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != sample["sha256"]:
                raise SystemExit("Real checks require the frozen samples; run prepare_evaluation.")
        env["VOICETRAIL_EVALUATION"] = str(settings.data_dir / "evaluation")
        env["VOICETRAIL_MODEL_CACHE"] = str(settings.data_dir / "models")
    started = time.perf_counter()
    checks = []
    steps = [
        ("offline_engineering", [sys.executable, "-m", "scripts.verify", "--engineering-child"], ROOT),
        ("ruff", [sys.executable, "-m", "ruff", "check", "backend", "scripts", "tests"], ROOT),
        ("http_contract", [sys.executable, "-m", "scripts.contracts", "--check"], ROOT),
        ("frontend_typecheck", ["npm", "run", "typecheck"], ROOT / "frontend"),
        ("frontend_build", ["npm", "run", "build"], ROOT / "frontend"),
    ]
    if args.real:
        reference = next(s for s in manifest["samples"] if s["role"] == "reference")
        steps.extend([
            ("offline_real_model", [sys.executable, "-m", "scripts.smoke_model", "--offline",
                                   settings.data_dir / "evaluation" / reference["path"]], ROOT),
            ("frozen_retrieval", [sys.executable, "-m", "scripts.evaluate_retrieval", "--dataset",
                                 settings.data_dir / "evaluation"], ROOT),
            ("real_api", [sys.executable, "-m", "scripts.integration"], ROOT),
            ("real_browser", ["npm", "run", "e2e"], ROOT / "frontend"),
        ])
    for name, command, cwd in steps:
        run(command, cwd, env)
        checks.append({"name": name, "passed": True})
    report = {"passed": True, "mode": "real" if args.real else "engineering",
              "real_gates_run": args.real, "checks": checks,
              "elapsed_seconds": time.perf_counter() - started,
              "scope": "Engineering checks cannot substitute for real-model release gates."}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
