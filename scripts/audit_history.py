"""Scan all reachable Git history, including commits not present in the worktree."""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_SUFFIXES = {
    ".wav", ".flac", ".mp3", ".mp4", ".zip", ".sqlite", ".db", ".npy", ".npz", ".ckpt", ".log",
}
PATTERNS = [
    ("private_home_path", re.compile(r"/(?:Users|home)/[A-Za-z0-9_.-]+/")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("github_fine_grained_token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("aws_key", re.compile(r"\bAKIA[A-Z0-9]{16}\b")),
]


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def main():
    issues = []
    commits = git("rev-list", "--all").decode().splitlines()
    checked = set()
    entries = 0
    for commit in commits:
        for item in git("ls-tree", "-r", "-z", commit).split(b"\0"):
            if not item:
                continue
            info, path_bytes = item.split(b"\t", 1)
            _, kind, object_id = info.decode().split()
            path = path_bytes.decode()
            entries += 1
            if Path(path).suffix.lower() in FORBIDDEN_SUFFIXES or any(
                    part in {".venv", "node_modules", "models", "samples", "data"}
                    for part in Path(path).parts):
                issues.append({"commit": commit, "path": path, "reason": "runtime_or_media_file"})
            if kind != "blob" or object_id in checked:
                continue
            checked.add(object_id)
            contents = git("cat-file", "blob", object_id)
            if len(contents) > 1024 * 1024:
                issues.append({"commit": commit, "path": path, "reason": "blob_over_1MiB"})
            try:
                text = contents.decode("utf-8")
            except UnicodeDecodeError:
                if Path(path).suffix not in {".png", ".svg"}:
                    issues.append({"commit": commit, "path": path, "reason": "unexpected_binary"})
                continue
            for reason, pattern in PATTERNS:
                if pattern.search(text):
                    # Never echo the matching credential or private path.
                    issues.append({"commit": commit, "path": path, "reason": reason})
    report = {"reachable_commits": len(commits), "tree_entries": entries,
              "unique_blobs": len(checked), "issues": issues,
              "passed": not issues,
              "scope": "All refs; suffix/size/UTF8/token/home-path heuristics. "
                       "Manual source review is still required; not a guarantee of no secrets."}
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
