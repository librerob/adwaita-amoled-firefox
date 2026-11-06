"""Check the minimum Firefox version against AMO's application-version registry.

web-ext lint does not check this submission-server constraint.
"""

import json
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
VERSIONS_URL = "https://addons.mozilla.org/api/v5/applications/firefox/"


class RegistryUnavailable(RuntimeError):
    """The registry could not be checked; this is not a theme validation result."""


def fetch_versions(opener=urlopen, sleep=time.sleep):
    request = Request(VERSIONS_URL, headers={"User-Agent": "adwaita-amoled-firefox compatibility check"})
    for attempt in range(3):
        try:
            with opener(request, timeout=10) as response:
                versions = json.load(response)["versions"]
            if not isinstance(versions, list) or not all(isinstance(v, str) for v in versions):
                raise ValueError("Unexpected version registry format")
            return versions
        except HTTPError as error:
            if error.code not in (408, 429, 500, 502, 503, 504):
                raise RegistryUnavailable(f"AMO registry returned HTTP {error.code}.") from error
            cause = error
        except (URLError, TimeoutError, OSError, ValueError, KeyError) as error:
            cause = error
        if attempt < 2:
            sleep(2 ** attempt)
    raise RegistryUnavailable("AMO registry unavailable after three attempts; theme compatibility was not determined.") from cause


def check_version(manifest, versions):
    minimum = manifest["browser_specific_settings"]["gecko"]["strict_min_version"]
    if minimum not in versions:
        raise ValueError(f"AMO does not recognize strict_min_version {minimum!r}. Check {VERSIONS_URL}")
    return minimum


if __name__ == "__main__":
    manifest = json.loads((ROOT / "theme/manifest.json").read_text())
    try:
        versions = fetch_versions()
    except RegistryUnavailable as error:
        print(f"AMO service check unavailable: {error}", file=sys.stderr)
        sys.exit(2)
    try:
        minimum = check_version(manifest, versions)
    except ValueError as error:
        print(f"AMO compatibility error: {error}", file=sys.stderr)
        sys.exit(1)
    print(f"AMO recognizes Firefox minimum {minimum}.")
