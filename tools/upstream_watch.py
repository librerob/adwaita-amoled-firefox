"""Report upstream changes without advancing the committed review baseline."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from check_amo import check_version, fetch_versions

ROOT = Path(__file__).resolve().parents[1]
VERSIONS_URL = "https://product-details.mozilla.org/1.0/firefox_versions.json"


def fetch_json(url, opener=urlopen, sleep=time.sleep):
    headers = {"User-Agent": "adwaita-amoled-firefox upstream watch"}
    if url.startswith("https://api.github.com/"):
        headers["Accept"] = "application/vnd.github+json"
        if os.environ.get("GH_TOKEN"):
            headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    request = Request(url, headers=headers)
    for attempt in range(3):
        try:
            with opener(request, timeout=20) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code not in (408, 429, 500, 502, 503, 504):
                raise RuntimeError(f"HTTP {error.code}: {url}") from error
            cause = error
        except (URLError, TimeoutError, OSError, ValueError) as error:
            cause = error
        if attempt < 2:
            sleep(2 ** attempt)
    raise RuntimeError(f"Source unavailable after three attempts: {url}") from cause


def snapshot(data, kind):
    if kind == "directory":
        if not isinstance(data, list) or not data or len(data) >= 1000:
            raise ValueError("Directory missing, empty or possibly truncated")
        entries = {}
        for entry in data:
            if entry["type"] not in ("file", "dir") or not re.fullmatch(r"[0-9a-f]{40}", entry["sha"]):
                raise ValueError("Unexpected directory entry")
            entries[entry["name"]] = entry["sha"]
        if len(entries) != len(data):
            raise ValueError("Duplicate directory entry")
        return {"entries": entries}
    if kind != "file" or not isinstance(data, dict) or data.get("type") != "file":
        raise ValueError("Expected a regular source file")
    if not re.fullmatch(r"[0-9a-f]{40}", data.get("sha", "")):
        raise ValueError("Missing source blob SHA")
    return {"sha": data["sha"]}


def changed_entries(baseline, current):
    if "entries" in baseline:
        old, new = baseline["entries"], current["entries"]
        return sorted(name for name in old.keys() | new.keys() if old.get(name) != new.get(name))
    return ["file contents"] if baseline["sha"] != current["sha"] else []


def collect(config, fetch=fetch_json, amo_versions=fetch_versions, manifest=None):
    if config.get("schema_version") != 1:
        raise ValueError("Unsupported upstream watch configuration")
    rows = []

    def add(name, state, detail, url):
        rows.append({"name": name, "state": state, "detail": detail, "url": url})

    try:
        versions = fetch(VERSIONS_URL)
        for key, baseline in config["versions"].items():
            current = versions[key]
            if not isinstance(current, str) or not re.fullmatch(r"[0-9][0-9A-Za-z.]*", current):
                raise ValueError(f"Unexpected version for {key}")
            add(key, "unchanged" if current == baseline else "review-needed",
                f"Baseline {baseline}; current {current}", VERSIONS_URL)
    except Exception as error:
        add("Firefox release metadata", "error", str(error), VERSIONS_URL)

    linter_url = "https://api.github.com/repos/mozilla/web-ext/releases/latest"
    try:
        release = fetch(linter_url)
        version = release["tag_name"].removeprefix("v")
        if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
            raise ValueError("Unexpected web-ext release version")
        add("web-ext linter", "unchanged" if version == config["web_ext"] else "review-needed",
            f"CI pins {config['web_ext']}; upstream {version}", "https://github.com/mozilla/web-ext/releases")
    except Exception as error:
        add("web-ext linter", "error", str(error), linter_url)

    for source in config["repositories"]:
        repo = source["repo"]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
            raise ValueError("Invalid upstream repository")
        api = f"https://api.github.com/repos/{repo}"
        try:
            # Pin every path to the same observed commit, avoiding moving-branch races.
            head = fetch(f"{api}/commits/{quote(source['branch'], safe='')}")["sha"]
            if not re.fullmatch(r"[0-9a-f]{40}", head):
                raise ValueError("Missing upstream commit SHA")
        except Exception as error:
            add(repo, "error", str(error), f"https://github.com/{repo}")
            continue
        for entry in source["paths"]:
            path = entry["path"]
            url = f"https://github.com/{repo}/{'tree' if entry['kind'] == 'directory' else 'blob'}/{head}/{path}"
            try:
                data = fetch(f"{api}/contents/{quote(path, safe='/')}?ref={head}")
                current = snapshot(data, entry["kind"])
                changes = changed_entries(entry, current)
                row = {"name": f"{repo}: {path}", "state": "review-needed" if changes else "unchanged",
                       "detail": ", ".join(changes) if changes else "Matches captured baseline", "url": url,
                       "commit": head, "observed": current,
                       "compare": f"https://github.com/{repo}/compare/{source['baseline_commit']}...{head}"}
                rows.append(row)
            except Exception as error:
                add(f"{repo}: {path}", "error", str(error), url)

    try:
        current_manifest = manifest if manifest is not None else json.loads((ROOT / "theme/manifest.json").read_text())
        minimum = check_version(current_manifest, amo_versions())
        add("AMO minimum Firefox version", "unchanged", f"AMO recognizes {minimum}",
            "https://addons.mozilla.org/api/v5/applications/firefox/")
    except Exception as error:
        add("AMO minimum Firefox version", "error", str(error),
            "https://addons.mozilla.org/api/v5/applications/firefox/")
    return {"checked_at": datetime.now(timezone.utc).isoformat(), "baseline_date": config["captured_on"],
            "rows": rows, "errors": sum(r["state"] == "error" for r in rows),
            "changes": sum(r["state"] == "review-needed" for r in rows)}


def markdown(report):
    lines = ["## Firefox upstream watch", "", f"Checked {report['checked_at']}. Baseline captured {report['baseline_date']}.", "",
             f"**{report['changes']} items need review; {report['errors']} checks could not be completed.**", "",
             "A source or version change is a review signal, not a confirmed theme regression. Errors never count as up to date.", "",
             "| Source | Result | Detail |", "| --- | --- | --- |"]
    for row in report["rows"]:
        clean = lambda value: str(value).replace("|", "\\|").replace("\n", " ")
        detail = clean(row["detail"])
        if row.get("compare") and row["state"] == "review-needed":
            detail += f" ([compare]({row['compare']}))"
        lines.append(f"| [{clean(row['name'])}]({row['url']}) | {row['state']} | {detail} |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="artifacts/upstream-watch")
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    config = json.loads((ROOT / "maintenance/upstream-watch.json").read_text())
    report = collect(config)
    text = markdown(report)
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (output / "report.md").write_text(text, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write(text)
    print(f"Upstream watch: {report['changes']} review signals, {report['errors']} errors.")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
