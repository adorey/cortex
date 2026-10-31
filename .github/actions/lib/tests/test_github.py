"""Downloading a release asset, against two local servers: the API, which redirects to its storage,
and the storage, which refuses a request that carries the token."""

import socket
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


def cut_short(handler, code):
    """An answer whose body stops after 4 of the 100 bytes it announced."""
    handler.send_response(code)
    handler.send_header("Content-Length", "100")
    handler.end_headers()
    handler.wfile.write(b"half")
    handler.close_connection = True


class DownloadTests(unittest.TestCase):
    def setUp(self):
        def storage(handler):
            if handler.path.startswith("/broken"):
                answer(handler, 500, b"the storage is down")
            elif handler.path.startswith("/hangup"):
                handler.close_connection = True   # no answer at all
            elif handler.headers.get("Authorization"):
                answer(handler, 400, b"the storage refuses a token")
            else:
                answer(handler, 200, ASSET)

        def api(handler):
            if handler.path.endswith("/missing"):
                answer(handler, 404, b'{"message": "Not Found"}')
            elif handler.path.endswith("/direct"):
                answer(handler, 200, ASSET)
            elif handler.path.endswith("/broken"):
                answer(handler, 302, location=f"{self.storage.url}/broken?sig=secret")
            elif handler.path.endswith("/hangup"):
                answer(handler, 302, location=f"{self.storage.url}/hangup?sig=secret")
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

    def test_the_storage_failing_is_a_github_error_that_keeps_its_signature_out(self):
        with self.assertRaises(GitHubError) as raised:
            self.github.download(f"{self.api.url}/repos/o/r/releases/assets/broken")
        self.assertEqual(raised.exception.status, 500)
        self.assertNotIn("secret", str(raised.exception))

    def test_the_storage_hanging_up_is_no_answer_that_keeps_its_signature_out(self):
        with self.assertRaises(GitHubError) as raised:
            self.github.download(f"{self.api.url}/repos/o/r/releases/assets/hangup")
        self.assertIsNone(raised.exception.status)
        self.assertNotIn("secret", str(raised.exception))


class NoAnswerTests(unittest.TestCase):
    """A network error is a GitHubError with no status: the API said nothing an action may act on."""

    def test_a_refused_connection(self):
        with socket.socket() as free:
            free.bind(("127.0.0.1", 0))
            port = free.getsockname()[1]   # closed once the block ends: nothing listens there
        github = GitHub("o/r", token="T", api=f"http://127.0.0.1:{port}")
        for call in (lambda: github.get("/repos/o/r/releases"), lambda: github.download(f"http://127.0.0.1:{port}/a")):
            with self.subTest(call=call), self.assertRaises(GitHubError) as raised:
                call()
            self.assertIsNone(raised.exception.status)
            self.assertTrue(str(raised.exception).startswith("no answer: "))

    def test_a_server_that_hangs_up(self):
        server = Server(lambda handler: setattr(handler, "close_connection", True))
        self.addCleanup(server.close)
        with self.assertRaises(GitHubError) as raised:
            GitHub("o/r", token="T", api=server.url).get("/repos/o/r/releases")
        self.assertIsNone(raised.exception.status)


    def test_an_answer_cut_short(self):
        # A success whose body stops is no answer; an error whose body stops keeps its status.
        for code, status in ((200, None), (502, 502)):
            with self.subTest(code=code):
                server = Server(lambda handler, code=code: cut_short(handler, code))
                self.addCleanup(server.close)
                with self.assertRaises(GitHubError) as raised:
                    GitHub("o/r", token="T", api=server.url).get("/repos/o/r/releases")
                self.assertEqual(raised.exception.status, status)


if __name__ == "__main__":
    unittest.main()
