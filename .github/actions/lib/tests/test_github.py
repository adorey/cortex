"""Downloading a release asset, against two local servers: the API, which redirects to its storage,
and the storage, which refuses a request that carries the token."""

import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from github import GitHub, GitHubError  # noqa: E402

ASSET = b"the bytes of an asset"


class Server:
    """A local HTTP server on its own thread, answering GET with ``handle(handler)``."""

    def __init__(self, handle):
        self.seen = []
        seen = self.seen

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append((self.path, dict(self.headers)))
                handle(self)

            def log_message(self, *_):
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def answer(handler, code, body=b"", location=None):
    handler.send_response(code)
    if location:
        handler.send_header("Location", location)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class DownloadTests(unittest.TestCase):
    def setUp(self):
        def storage(handler):
            if handler.headers.get("Authorization"):
                answer(handler, 400, b"the storage refuses a token")
            else:
                answer(handler, 200, ASSET)

        def api(handler):
            if handler.path.endswith("/missing"):
                answer(handler, 404, b'{"message": "Not Found"}')
            elif handler.path.endswith("/direct"):
                answer(handler, 200, ASSET)
            else:
                answer(handler, 302, location=f"{self.storage.url}/blob?sig=x")

        self.storage, self.api = Server(storage), Server(api)
        self.github = GitHub("o/r", token="T0KEN", api=self.api.url)

    def tearDown(self):
        self.storage.close()
        self.api.close()

    def test_the_redirect_to_the_storage_is_followed_without_the_token(self):
        data = self.github.download(f"{self.api.url}/repos/o/r/releases/assets/1")
        self.assertEqual(data, ASSET)
        (path, headers), = self.api.seen
        self.assertEqual((headers.get("Authorization"), headers.get("Accept")), ("Bearer T0KEN", "application/octet-stream"))
        (path, headers), = self.storage.seen
        self.assertEqual(path, "/blob?sig=x")
        self.assertNotIn("Authorization", headers)

    def test_an_asset_served_with_no_redirect(self):
        self.assertEqual(self.github.download(f"{self.api.url}/repos/o/r/releases/assets/direct"), ASSET)
        self.assertEqual(self.storage.seen, [])

    def test_a_missing_asset_is_a_github_error(self):
        with self.assertRaises(GitHubError) as raised:
            self.github.download(f"{self.api.url}/repos/o/r/releases/assets/missing")
        self.assertEqual(raised.exception.status, 404)
        self.assertEqual(self.storage.seen, [])


if __name__ == "__main__":
    unittest.main()
