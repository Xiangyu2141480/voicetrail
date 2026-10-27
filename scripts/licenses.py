"""Record locked dependency metadata and preserve installed upstream license texts."""
import hashlib
import importlib.metadata
import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERRIDES = {
    "fastapi": "MIT", "huggingface-hub": "Apache-2.0", "hyperpyyaml": "Apache-2.0",
    "jinja2": "BSD-3-Clause", "mpmath": "BSD-3-Clause", "numpy": "BSD-3-Clause + bundled notices",
    "ruff": "MIT + bundled notices", "scipy": "BSD-3-Clause + bundled notices",
    "soundfile": "BSD-3-Clause + libsndfile LGPL-2.1", "speechbrain": "Apache-2.0",
    "sympy": "BSD-3-Clause", "torchaudio": "BSD-2-Clause", "webrtcvad-wheels": "MIT + WebRTC BSD-3",
}


def normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def clean_text(content):
    # Preserve all wording/indentation; normalize line endings and trailing spaces.
    return "\n".join(line.rstrip() for line in content.decode(errors="replace").splitlines()).rstrip()


def main():
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    installed = {normalize(d.metadata["Name"]): d for d in importlib.metadata.distributions()}
    python = []
    for package in lock["package"]:
        name = package["name"]
        if name == "voicetrail":
            continue
        dist = installed.get(normalize(name))
        row = {"name": name, "version": package["version"], "source": package["source"],
               "metadata_url": f"https://pypi.org/project/{name}/{package['version'].split('+')[0]}/"}
        if dist:
            row["license"] = OVERRIDES.get(name) or dist.metadata.get("License-Expression") or (
                dist.metadata.get("License") or "").strip()
            if not row["license"]:
                raise SystemExit(f"License metadata needs review: {name}")
            texts = []
            files = []
            for file in dist.files or []:
                if Path(str(file)).name.lower() in {
                    "license", "license.txt", "license.md", "notice", "notice.txt",
                    "copying", "licence", "licence.txt", "license.apache", "license.bsd",
                    "license-apache", "license-mit",
                }:
                    content = Path(dist.locate_file(file)).read_bytes()
                    files.append({"path_in_distribution": str(file),
                                  "sha256": hashlib.sha256(content).hexdigest()})
                    texts.append(f"--- {file} ---\n" + clean_text(content))
            row["license_files"] = files
            if texts:
                path = ROOT / "docs/licenses/python" / f"{name}.txt"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("\n\n".join(texts) + "\n")
                row["preserved_text"] = str(path.relative_to(ROOT))
            row["verification"] = "Installed distribution metadata and available license files"
        else:
            # colorama is a Windows-only test dependency, not installed on macOS/Linux.
            if name != "colorama":
                raise SystemExit(f"Unreviewed platform dependency: {name}")
            row["license"] = "BSD-3-Clause"
            row["verification"] = "Upstream PyPI metadata; Windows-only dependency"
        python.append(row)
    npm = json.loads((ROOT / "frontend/package-lock.json").read_text())
    frontend = []
    for location, package in npm["packages"].items():
        if not location:
            continue
        name = location.split("node_modules/")[-1]
        if not package.get("license"):
            raise SystemExit(f"Missing npm license: {name}")
        row = {"name": name, "version": package["version"], "license": package["license"],
               "location": location, "metadata_url": f"https://www.npmjs.com/package/{name}"}
        text_files = []
        directory = ROOT / "frontend" / location
        if directory.is_dir():
            for path in directory.iterdir():
                if path.is_file() and path.name.lower() in {
                    "license", "license.txt", "license.md", "notice", "thirdpartynotices.txt",
                }:
                    content = path.read_bytes()
                    text_files.append(f"--- {path.name} ---\n" + clean_text(content))
            if text_files:
                destination = ROOT / "docs/licenses/npm" / (name.replace("/", "__") + ".txt")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text("\n\n".join(text_files) + "\n")
                row["preserved_text"] = str(destination.relative_to(ROOT))
        row["verification"] = "npm lock metadata; available installed upstream notices preserved"
        frontend.append(row)
    report = {"scope": "Complete uv/npm locks including platform variants; source-only release. "
                       "Primary labels do not replace bundled third-party notices.",
              "python": python, "npm": frontend}
    (ROOT / "docs/dependency_licenses.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Recorded {len(python)} Python lock entries and {len(frontend)} npm lock entries.")


if __name__ == "__main__":
    main()
