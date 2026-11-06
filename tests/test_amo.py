"""Exercise registry retries without depending on a network connection."""

import io
from pathlib import Path
import sys
import unittest
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from check_amo import fetch_versions, RegistryUnavailable


class RegistryTests(unittest.TestCase):
    def test_retry_then_success(self):
        waits = []
        attempts = []
        def open_registry(request, timeout):
            attempts.append(timeout)
            if len(attempts) < 3:
                raise URLError("temporary connection failure")
            return io.BytesIO(b'{"versions":["159.0"]}')
        self.assertEqual(fetch_versions(open_registry, waits.append), ["159.0"])
        self.assertEqual(attempts, [10, 10, 10])
        self.assertEqual(waits, [1, 2])

    def test_outage_is_not_invalid_version(self):
        attempts = []
        def unavailable(*args, **kwargs):
            attempts.append(True)
            raise URLError("service unavailable")
        with self.assertRaisesRegex(RegistryUnavailable, "compatibility was not determined"):
            fetch_versions(unavailable, lambda seconds: None)
        self.assertEqual(len(attempts), 3)

    def test_transient_http_error(self):
        attempts = []
        def overloaded(request, timeout):
            attempts.append(True)
            if len(attempts) == 1:
                raise HTTPError(request.full_url, 503, "Unavailable", {}, None)
            return io.BytesIO(b'{"versions":["159.0"]}')
        self.assertEqual(fetch_versions(overloaded, lambda seconds: None), ["159.0"])

    def test_permanent_http_error_is_not_retried(self):
        attempts = []
        def denied(request, timeout):
            attempts.append(True)
            raise HTTPError(request.full_url, 403, "Forbidden", {}, None)
        with self.assertRaisesRegex(RegistryUnavailable, "HTTP 403"):
            fetch_versions(denied, lambda seconds: None)
        self.assertEqual(len(attempts), 1)

    def test_malformed_response_is_unavailable(self):
        with self.assertRaises(RegistryUnavailable):
            fetch_versions(lambda *args, **kwargs: io.BytesIO(b'{"versions":"unexpected"}'), lambda seconds: None)


if __name__ == "__main__":
    unittest.main()
