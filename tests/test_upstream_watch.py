"""Keep change detection and failure reporting independent of live services."""

import copy
import io
import json
import os
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from upstream_watch import collect, fetch_json, markdown, snapshot

OLD, NEW = "a" * 40, "b" * 40
MANIFEST = {"browser_specific_settings": {"gecko": {"strict_min_version": "159.0"}}}


class WatchTests(unittest.TestCase):
    def test_linter_baseline_matches_the_actual_ci_pin(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / "maintenance/upstream-watch.json").read_text())
        workflow = (root / ".github/workflows/checks.yml").read_text()
        self.assertEqual(re.findall(r"web-ext@([0-9]+\.[0-9]+\.[0-9]+)", workflow), [config["web_ext"]])

    def setUp(self):
        self.config = {
            "schema_version": 1, "captured_on": "2026-11-06", "web_ext": "8.9.0",
            "versions": {"LATEST_FIREFOX_VERSION": "159.0.1"},
            "repositories": [{"repo": "mozilla-firefox/firefox", "branch": "main", "baseline_commit": OLD,
                "paths": [{"path": "theme.json", "kind": "file", "sha": OLD},
                          {"path": "styles", "kind": "directory", "entries": {"nested": OLD, "removed.css": OLD}}]}]
        }
        self.urls = []

    def fetch(self, url):
        self.urls.append(url)
        if "firefox_versions.json" in url:
            return {"LATEST_FIREFOX_VERSION": "159.0.1"}
        if "releases/latest" in url:
            return {"tag_name": "8.9.0"}
        if "/commits/" in url:
            return {"sha": NEW}
        if "/contents/theme.json" in url:
            return {"type": "file", "sha": OLD}
        if "/contents/styles" in url:
            return [{"name": "nested", "type": "dir", "sha": OLD},
                    {"name": "removed.css", "type": "file", "sha": OLD}]
        raise AssertionError(f"Unexpected request: {url}")

    def report(self, fetch=None, amo=None):
        return collect(self.config, fetch or self.fetch, amo or (lambda: ["159.0"]), MANIFEST)

    def test_unchanged_files_do_not_alert_on_unrelated_commits(self):
        before = copy.deepcopy(self.config)
        report = self.report()
        self.assertEqual((report["changes"], report["errors"]), (0, 0))
        self.assertEqual(before, self.config)  # Never acknowledge changes automatically.
        contents = [url for url in self.urls if "/contents/" in url]
        self.assertTrue(all(url.endswith("?ref=" + NEW) for url in contents))

    def test_file_and_nested_added_removed_directory_changes(self):
        def changed(url):
            if "/contents/theme.json" in url:
                return {"type": "file", "sha": NEW}
            if "/contents/styles" in url:
                return [{"name": "nested", "type": "dir", "sha": NEW},
                        {"name": "added.css", "type": "file", "sha": NEW}]
            return self.fetch(url)
        report = self.report(changed)
        self.assertEqual((report["changes"], report["errors"]), (2, 0))
        row = next(row for row in report["rows"] if row["name"].endswith(": styles"))
        self.assertEqual(row["detail"], "added.css, nested, removed.css")
        self.assertIn(OLD + "..." + NEW, row["compare"])

    def test_new_browser_and_linter_versions_need_review(self):
        def changed(url):
            if "firefox_versions.json" in url:
                return {"LATEST_FIREFOX_VERSION": "160.0"}
            if "releases/latest" in url:
                return {"tag_name": "v9.0.0"}
            return self.fetch(url)
        self.assertEqual(self.report(changed)["changes"], 2)

    def test_deleted_source_is_an_error_not_up_to_date(self):
        def missing(url):
            if "/contents/theme.json" in url:
                raise RuntimeError("HTTP 404")
            return self.fetch(url)
        report = self.report(missing)
        self.assertEqual(report["errors"], 1)
        self.assertIn("error", markdown(report))

    def test_repository_failure_does_not_hide_other_checks(self):
        def unavailable(url):
            if "/commits/" in url:
                raise RuntimeError("service unavailable")
            return self.fetch(url)
        report = self.report(unavailable)
        self.assertEqual(report["errors"], 1)
        self.assertEqual(report["rows"][-1]["name"], "AMO minimum Firefox version")

    def test_amo_failure_is_unknown_not_a_clean_result(self):
        def unavailable():
            raise RuntimeError("AMO unavailable")
        self.assertEqual(self.report(amo=unavailable)["errors"], 1)
        self.assertEqual(self.report(amo=lambda: ["158.0"])["errors"], 1)

    def test_incomplete_directory_and_wrong_file_kind_are_rejected(self):
        with self.assertRaises(ValueError):
            snapshot([{"name": "a", "type": "file", "sha": OLD}] * 1000, "directory")
        with self.assertRaises(ValueError):
            snapshot({"type": "symlink", "sha": OLD}, "file")

    def test_github_credentials_do_not_reach_mozilla_metadata(self):
        requests = []
        def opener(request, timeout):
            requests.append(request)
            return io.BytesIO(b'{}')
        with patch.dict(os.environ, {"GH_TOKEN": "test-only-token"}):
            fetch_json("https://api.github.com/repos/mozilla/web-ext", opener)
            fetch_json("https://product-details.mozilla.org/1.0/firefox_versions.json", opener)
        self.assertEqual(requests[0].get_header("Authorization"), "Bearer test-only-token")
        self.assertIsNone(requests[1].get_header("Authorization"))

    def test_transient_failure_retries_but_missing_source_does_not(self):
        attempts, waits = [], []
        def intermittent(request, timeout):
            attempts.append(timeout)
            if len(attempts) < 3:
                raise URLError("temporary outage")
            return io.BytesIO(b'{"ok": true}')
        self.assertEqual(fetch_json("https://api.github.com/test", intermittent, waits.append), {"ok": True})
        self.assertEqual(waits, [1, 2])
        attempts.clear()
        def missing(request, timeout):
            attempts.append(timeout)
            raise HTTPError(request.full_url, 404, "Not found", {}, None)
        with self.assertRaisesRegex(RuntimeError, "HTTP 404"):
            fetch_json("https://api.github.com/test", missing, waits.append)
        self.assertEqual(len(attempts), 1)


if __name__ == "__main__":
    unittest.main()
