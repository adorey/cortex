"""The store, in process — ADR-008 §3.3.

``test_cli_sync`` drives the store through the command; these tests call it directly, with its
version, its embedded spec and its downloads given, to reach what a command line cannot: a
binary's embedded archive, a write interrupted, two writes of one version at once.
"""

import hashlib
import io
import os
import shutil
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parents[2] / "core"),
                str(Path(__file__).resolve().parent)]
from cortex_cli import net, store  # noqa: E402
from cortex_cli.semver import Version  # noqa: E402
from release_fixture import spec_archive  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
AS_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0


class StoreTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cortex-store-"))
        self.addCleanup(self.cleanup)
        self.home = self.tmp / "home"

    def cleanup(self):
        for directory, subdirs, files in os.walk(self.tmp):
            for name in subdirs + files:
                os.chmod(os.path.join(directory, name), 0o700)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def listing(self):
        versions = self.home / "versions"
        return sorted(p.name for p in versions.iterdir()) if versions.is_dir() else []


class EmbeddedTests(StoreTestCase):
    def test_a_binary_writes_the_archive_it_embeds(self):
        archive = spec_archive(self.tmp, "2.0.0")
        the_store = store.Store(self.home, own_version="2.0.0", embedded=archive, fetch=self.no_network)
        self.assertEqual(the_store.ensure(Version("2.0.0")), "written")
        self.assertEqual(sorted(p.name for p in the_store.path(Version("2.0.0")).iterdir()), sorted(store.SPEC_TREES))
        self.assertEqual(the_store.ensure(Version("2.0.0")), "stored")

    def test_a_source_checkout_writes_its_own_spec(self):
        the_store = store.Store(self.home, own_version="2.0.0", checkout=REPO, fetch=self.no_network)
        the_store.ensure(Version("2.0.0"))
        written = the_store.path(Version("2.0.0"))
        self.assertEqual((written / "agents" / "roles" / "prompt-manager.md").read_bytes(),
                         (REPO / "agents" / "roles" / "prompt-manager.md").read_bytes())
        self.assertFalse((written / "agents" / "personalities" / ".active-theme").exists())

    def test_a_dev_version_serves_itself(self):
        the_store = store.Store(self.home, own_version="0.0.0-dev.7", checkout=REPO, fetch=self.no_network)
        self.assertEqual(the_store.ensure(Version("0.0.0-dev.7")), "written")

    @unittest.skipIf(AS_ROOT, "root writes any file")
    def test_it_is_read_only_once_written(self):
        the_store = store.Store(self.home, own_version="2.0.0", checkout=REPO, fetch=self.no_network)
        the_store.ensure(Version("2.0.0"))
        card = the_store.path(Version("2.0.0")) / "agents" / "roles" / "prompt-manager.md"
        with self.assertRaises(PermissionError):
            card.write_text("edited", encoding="utf-8")

    def test_an_interrupted_write_leaves_nothing(self):
        the_store = store.Store(self.home, own_version="2.0.0", checkout=self.tmp / "no-such-checkout",
                                fetch=self.no_network)
        with self.assertRaises(FileNotFoundError):
            the_store.ensure(Version("2.0.0"))
        self.assertEqual(self.listing(), [])

    def test_a_version_written_meanwhile_by_another_sync(self):
        # Two syncs that both found the version missing: the second rename finds it in place.
        the_store = store.Store(self.home, own_version="2.0.0", checkout=REPO, fetch=self.no_network)
        the_store.versions.mkdir(parents=True)
        fill = lambda staging: store._copy_trees(REPO, staging)  # noqa: E731
        the_store._install(Version("2.0.0"), fill)
        the_store._install(Version("2.0.0"), fill)
        self.assertEqual(self.listing(), ["2.0.0"])

    def test_an_empty_version_directory_is_no_version(self):
        the_store = store.Store(self.home, own_version="2.0.0", checkout=REPO, fetch=self.no_network)
        the_store.path(Version("2.0.0")).mkdir(parents=True)
        self.assertFalse(the_store.has(Version("2.0.0")))
        with self.assertRaisesRegex(store.StoreError, "holds no complete spec"):
            the_store.ensure(Version("2.0.0"))

    @unittest.skipIf(os.name == "nt", "the mode of a directory is POSIX's")
    def test_a_version_left_writable_is_made_read_only_again(self):
        # Interrupted between the rename and the chmod, a sync left the version writable.
        the_store = store.Store(self.home, own_version="2.0.0", checkout=REPO, fetch=self.no_network)
        the_store.ensure(Version("2.0.0"))
        store.make_writable(the_store.path(Version("2.0.0")))
        self.assertEqual(the_store.ensure(Version("2.0.0")), "stored")
        self.assertFalse(os.stat(the_store.path(Version("2.0.0"))).st_mode & 0o222)

    def test_a_file_left_writable_is_made_read_only_again(self):
        # On Windows the read-only attribute is a file's, never a directory's: a file tells.
        the_store = store.Store(self.home, own_version="2.0.0", checkout=REPO, fetch=self.no_network)
        the_store.ensure(Version("2.0.0"))
        card = the_store.path(Version("2.0.0")) / "agents" / "roles" / "prompt-manager.md"
        os.chmod(card, 0o644)
        self.assertEqual(the_store.ensure(Version("2.0.0")), "stored")
        self.assertFalse(os.stat(card).st_mode & 0o222)

    def test_a_staging_left_for_a_day_is_removed(self):
        the_store = store.Store(self.home, own_version="2.0.0", checkout=REPO, fetch=self.no_network)
        the_store.ensure(Version("2.0.0"))
        old, fresh = the_store.versions / ".2.0.1-abandoned", the_store.versions / ".download-inflight"
        old.mkdir()
        fresh.write_bytes(b"x")
        os.utime(old, (0, 0))
        the_store.ensure(Version("2.0.0"))
        self.assertFalse(old.exists())
        self.assertTrue(fresh.exists())

    @staticmethod
    def no_network(url, limit):
        raise AssertionError(f"no download expected, got {url}")


class DownloadTests(StoreTestCase):
    """Other versions come from their release's spec archive, checked against its SHA256SUMS."""

    def release(self, version, archive_bytes=None, sums_line=None):
        archive = archive_bytes if archive_bytes is not None else spec_archive(self.tmp, version).read_bytes()
        digest = hashlib.sha256(archive).hexdigest()
        files = {"SHA256SUMS": (sums_line if sums_line is not None else f"{digest}  cortex-spec.tar.gz\n").encode(),
                 "cortex-spec.tar.gz": archive}
        self.requested = []

        def fetch(url, limit):
            self.requested.append(url)
            name = url.rsplit("/", 1)[1]
            if f"/download/{version}/" not in url or name not in files:
                raise net.DownloadError(f"{url}: HTTP 404 Not Found")
            return files[name]
        return store.Store(self.home, own_version="3.0.0", embedded=self.tmp / "unused.tar.gz", fetch=fetch)

    def test_downloaded_and_verified(self):
        the_store = self.release("2.0.0")
        self.assertEqual(the_store.ensure(Version("2.0.0")), "downloaded")
        self.assertIn("Cortex 2.0.0", (the_store.path(Version("2.0.0")) / "agents/roles/prompt-manager.md").read_text(encoding="utf-8"))
        self.assertEqual([u.rsplit("/", 2)[-2:] for u in self.requested], [["2.0.0", "SHA256SUMS"], ["2.0.0", "cortex-spec.tar.gz"]])

    def test_a_checksum_that_differs(self):
        the_store = self.release("2.0.0", sums_line=f"{'0' * 64}  cortex-spec.tar.gz\n")
        with self.assertRaisesRegex(store.StoreError, "does not match its checksum"):
            the_store.ensure(Version("2.0.0"))
        self.assertEqual(self.listing(), [])

    def test_a_checksum_in_upper_case_or_with_a_star_is_read(self):
        archive = spec_archive(self.tmp, "2.0.0").read_bytes()
        line = f"{hashlib.sha256(archive).hexdigest().upper()} *cortex-spec.tar.gz\n"
        self.release("2.0.0", archive, sums_line=line).ensure(Version("2.0.0"))
        self.assertEqual(self.listing(), ["2.0.0"])

    def test_members_a_spec_archive_cannot_hold(self):
        def archive_with(member):
            buffer = io.BytesIO()
            with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
                for tree in store.SPEC_TREES:
                    info = tarfile.TarInfo(f"{tree}/x.md")
                    info.size = 1
                    tar.addfile(info, io.BytesIO(b"x"))
                tar.addfile(member, io.BytesIO(b"x" * member.size))
            return buffer.getvalue()

        link = tarfile.TarInfo("agents/evil")
        link.type, link.linkname = tarfile.SYMTYPE, "/etc/passwd"
        hard = tarfile.TarInfo("agents/hard")
        hard.type, hard.linkname = tarfile.LNKTYPE, "../../outside"
        device = tarfile.TarInfo("agents/dev")
        device.type = tarfile.CHRTYPE
        escape = tarfile.TarInfo("../escape.md")
        escape.size = 1
        for member in (link, hard, device, escape):
            with self.subTest(member=member.name):
                with self.assertRaisesRegex(store.StoreError, "which a spec archive cannot hold"):
                    self.release("2.0.0", archive_with(member)).ensure(Version("2.0.0"))
                self.assertEqual(self.listing(), [])

    def test_an_archive_without_the_three_trees(self):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
            info = tarfile.TarInfo("agents/x.md")
            info.size = 1
            tar.addfile(info, io.BytesIO(b"x"))
        with self.assertRaisesRegex(store.StoreError, "holds agents, not agents, templates, docs"):
            self.release("2.0.0", buffer.getvalue()).ensure(Version("2.0.0"))
        self.assertEqual(self.listing(), [])

    def test_the_versions_it_serves(self):
        the_store = self.release("2.0.0")
        with self.assertRaisesRegex(store.StoreError, "newer than this cortex, 3.0.0"):
            the_store.ensure(Version("3.0.1"))
        with self.assertRaisesRegex(store.StoreError, "has no spec archive: the first one is 1.0.0"):
            the_store.ensure(Version("0.10.1"))
        with self.assertRaisesRegex(store.StoreError, "has no spec archive"):
            the_store.ensure(Version("1.0.0-rc.1"))
        self.assertEqual(self.requested, [])

    def test_a_known_checksum_the_release_contradicts_is_refused(self):
        # SHA256SUMS comes from where the archive does: a release replaced wholesale passes it.
        # The checksum this binary was built with does not move.
        the_store = self.release("2.0.0")
        the_store.known = {"2.0.0": "f" * 64}
        with self.assertRaisesRegex(store.StoreError, "the release was changed since this binary was built"):
            the_store.ensure(Version("2.0.0"))
        self.assertEqual(self.listing(), [])

    def test_a_known_checksum_that_agrees(self):
        archive = spec_archive(self.tmp, "2.0.0").read_bytes()
        the_store = self.release("2.0.0", archive)
        the_store.known = {"2.0.0": hashlib.sha256(archive).hexdigest()}
        self.assertEqual(the_store.ensure(Version("2.0.0")), "downloaded")

    def test_a_version_the_binary_does_not_know_falls_back_on_sha256sums(self):
        # A release made after this binary, on an older line — 2.0.1 after 3.0.0 — is not in its table.
        the_store = self.release("2.0.0")
        the_store.known = {"1.0.0": "a" * 64}
        self.assertEqual(the_store.ensure(Version("2.0.0")), "downloaded")

    def test_a_release_that_does_not_exist(self):
        with self.assertRaisesRegex(store.StoreError, "could not download the SHA256SUMS of Cortex 2.5.0"):
            self.release("2.0.0").ensure(Version("2.5.0"))


class NetTests(unittest.TestCase):
    def test_the_context_verifies_certificates(self):
        context = net.ssl_context()
        import ssl

        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)

    @unittest.skipIf(os.name == "nt", "Windows gives Python its own certificate store")
    def test_with_no_default_certificates_a_system_bundle_is_loaded(self):
        from unittest import mock
        import ssl

        empty = ssl.DefaultVerifyPaths(None, None, "SSL_CERT_FILE", "/nonexistent/cert.pem", "SSL_CERT_DIR", "/nonexistent")
        bundle = net.fallback_bundle()
        if bundle is None:
            self.skipTest("no system bundle on this machine")
        with mock.patch("ssl.get_default_verify_paths", return_value=empty), \
                mock.patch.dict(os.environ, {}, clear=False) as env:
            env.pop("SSL_CERT_FILE", None)
            env.pop("SSL_CERT_DIR", None)
            with mock.patch.object(ssl.SSLContext, "load_verify_locations") as loaded:
                net.ssl_context()
        loaded.assert_called_with(cafile=bundle)

    def test_only_https_or_http_to_this_machine(self):
        for url in ("https://github.com/x", "http://127.0.0.1:8765/x", "http://localhost/x", "http://[::1]:80/x"):
            with self.subTest(url=url):
                net.check_url(url)
        for url in ("http://example.com/x", "file:///etc/passwd", "ftp://example.com/x", "http://127.0.0.1.example.com/x"):
            with self.subTest(url=url):
                with self.assertRaises(net.DownloadError):
                    net.check_url(url)

    def test_the_releases_url_is_checked(self):
        from unittest import mock

        with mock.patch.dict(os.environ, {"CORTEX_RELEASES_URL": "file:///srv/releases"}):
            with self.assertRaisesRegex(store.StoreError, "CORTEX_RELEASES_URL"):
                store.releases_url()

    def test_a_redirect_off_https_is_refused(self):
        import http.server
        import threading

        class Redirect(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", "http://example.com/SHA256SUMS")
                self.end_headers()

            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        with self.assertRaisesRegex(net.DownloadError, "only https"):
            net.get(f"http://127.0.0.1:{server.server_address[1]}/SHA256SUMS", 1024)

    def test_a_url_holding_a_control_character(self):
        with self.assertRaises(net.DownloadError):
            net.get("https://github.com/adorey/cortex/releases/download/1.0.0\n/SHA256SUMS", 1024)

    @unittest.skipIf(os.name == "nt", "Windows gives Python its own certificate store")
    def test_an_empty_certificate_directory_holds_no_certificate(self):
        from unittest import mock
        import ssl
        import tempfile

        with tempfile.TemporaryDirectory() as empty:
            paths = ssl.DefaultVerifyPaths(None, empty, "SSL_CERT_FILE", "/nonexistent", "SSL_CERT_DIR", empty)
            with mock.patch("ssl.get_default_verify_paths", return_value=paths), \
                    mock.patch.dict(os.environ, {}, clear=False) as env:
                env.pop("SSL_CERT_FILE", None)
                env.pop("SSL_CERT_DIR", None)
                self.assertFalse(net._defaults_hold_certificates())

    @unittest.skipUnless(os.environ.get("CI") == "true", "reaches github.com: in CI only")
    def test_github_is_reached_over_verified_https(self):
        # A release page that does not exist: a 404 proves the TLS handshake was verified.
        with self.assertRaisesRegex(net.DownloadError, "HTTP 404"):
            net.get("https://github.com/adorey/cortex/releases/download/0.0.0-no-such-release/SHA256SUMS", 1024)


if __name__ == "__main__":
    unittest.main()
