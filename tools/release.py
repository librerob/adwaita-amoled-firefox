"""Publish unsigned release packages from a checked main-branch revision."""

import json
import os
import re
import subprocess

from theme import ROOT, VERSION, package


def gh(*args):
    return subprocess.check_output(["gh", *args], text=True)


def main():
    repository = os.environ.get("GITHUB_REPOSITORY")
    revision = os.environ.get("GITHUB_SHA", "")
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise SystemExit("Run the Release workflow from main.")
    if not re.fullmatch(r"[0-9a-f]{40}", revision) or not re.fullmatch(r"\d+\.\d+\.\d+", VERSION):
        raise SystemExit("Invalid revision or release version.")
    runs = json.loads(gh("api", f"repos/{repository}/actions/runs?head_sha={revision}&event=push&per_page=100"))["workflow_runs"]
    if not any(run["path"] == ".github/workflows/checks.yml" and run["head_sha"] == revision and run["status"] == "completed" and run["conclusion"] == "success" for run in runs):
        raise SystemExit("This main revision needs a successful Checks workflow before release.")
    subprocess.run(["python", "tools/check_amo.py"], check=True)
    package()
    notes = ROOT / "docs" / "releases" / f"{VERSION}.md"
    if not notes.is_file():
        raise SystemExit("Release notes are missing.")
    assets = sorted(str(path) for path in (ROOT / "dist").iterdir() if path.is_file())
    gh("release", "create", f"v{VERSION}", *assets, "--repo", repository, "--target", revision,
       "--title", f"Adwaita AMOLED {VERSION}", "--notes-file", str(notes))
    release = json.loads(gh("release", "view", f"v{VERSION}", "--repo", repository, "--json", "url,assets,isDraft"))
    expected = {f"adwaita-amoled-firefox-{VERSION}.zip", f"adwaita-amoled-firefox-{VERSION}.xpi", "SHA256SUMS"}
    if release["isDraft"] or {asset["name"] for asset in release["assets"]} != expected:
        raise SystemExit("The release asset list does not match the built package.")
    print(release["url"])


if __name__ == "__main__":
    main()
