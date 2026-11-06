"""Check the minimum Firefox version against AMO's application-version registry.

web-ext lint does not check this submission-server constraint.
"""

import json
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
VERSIONS_URL = "https://addons.mozilla.org/api/v5/applications/firefox/"


def check_version(manifest, versions):
    minimum = manifest["browser_specific_settings"]["gecko"]["strict_min_version"]
    if minimum not in versions:
        raise ValueError(f"AMO does not recognize strict_min_version {minimum!r}. Check {VERSIONS_URL}")
    return minimum


if __name__ == "__main__":
    request = Request(VERSIONS_URL, headers={"User-Agent": "adwaita-amoled-firefox compatibility check"})
    with urlopen(request, timeout=30) as response:
        versions = json.load(response)["versions"]
    manifest = json.loads((ROOT / "theme/manifest.json").read_text())
    print(f"AMO recognizes Firefox minimum {check_version(manifest, versions)}.")
