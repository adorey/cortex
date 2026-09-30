"""Downloads over HTTPS, with the machine's certificates, from a binary built elsewhere.

A binary built by PyInstaller carries the OpenSSL of the machine that built it, and that OpenSSL
looks for certificates where that machine keeps them: AlmaLinux's ``/etc/pki/tls``, the framework
directory of a macOS build of Python. On a Debian, or on a Mac without that Python, it finds
none, and every download fails verification. When the default locations hold nothing, the
certificate bundles every common system keeps are tried in turn. ``SSL_CERT_FILE`` and
``SSL_CERT_DIR`` still win, as OpenSSL reads them itself.

Downloads go over https, redirects included. Plain http reaches this machine only — a release
served on it, for tests — and no other scheme, ``file:`` among them, is followed.
"""

from __future__ import annotations

import http.client
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from .version import VERSION

# Where Linux distributions and macOS keep their certificate bundle.
CA_BUNDLES = (
    "/etc/ssl/certs/ca-certificates.crt",      # Debian, Ubuntu, Arch, Alpine
    "/etc/pki/tls/certs/ca-bundle.crt",        # Fedora, RHEL, AlmaLinux
    "/etc/ssl/ca-bundle.pem",                  # openSUSE
    "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",
    "/etc/ssl/cert.pem",                       # macOS, Alpine
)
TIMEOUT = 30
LOOPBACK = ("127.0.0.1", "localhost", "::1")


class DownloadError(Exception):
    pass


def _defaults_hold_certificates() -> bool:
    if os.name == "nt":                        # Python reads the Windows certificate store
        return True
    if os.environ.get("SSL_CERT_FILE") or os.environ.get("SSL_CERT_DIR"):
        return True
    paths = ssl.get_default_verify_paths()     # cafile and capath are None when they do not exist
    if paths.cafile:
        return True
    try:
        return bool(paths.capath and os.listdir(paths.capath))      # a directory that holds none: none
    except OSError:
        return False


def fallback_bundle() -> Optional[str]:
    return next((path for path in CA_BUNDLES if os.path.isfile(path)), None)


def ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    if not _defaults_hold_certificates():
        bundle = fallback_bundle()
        if bundle is not None:
            context.load_verify_locations(cafile=bundle)
    return context


def check_url(url: str) -> None:
    """Refuse a URL to download from that is neither https nor http to this machine."""
    try:
        parts = urllib.parse.urlsplit(url)
        host = parts.hostname
    except ValueError as error:
        raise DownloadError(f"{url!r}: {error}")
    if parts.scheme == "https" or (parts.scheme == "http" and host in LOOPBACK):
        return
    raise DownloadError(f"{url}: only https is downloaded from — http only to this machine, for tests")


class _CheckedRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def get(url: str, max_bytes: int) -> bytes:
    """The body of ``url``, at most ``max_bytes`` of it — HTTPS verified, redirects followed as
    long as they stay on https."""
    check_url(url)
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl_context()), _CheckedRedirects())
    try:
        request = urllib.request.Request(url, headers={"User-Agent": f"cortex/{VERSION}"})
        with opener.open(request, timeout=TIMEOUT) as response:
            data = response.read(max_bytes + 1)
    except urllib.error.HTTPError as error:
        raise DownloadError(f"{url}: HTTP {error.code} {error.reason}")
    except (urllib.error.URLError, OSError) as error:
        reason = getattr(error, "reason", error)
        raise DownloadError(f"{url}: {reason}")
    except (ValueError, http.client.HTTPException) as error:   # InvalidURL: a control character in it
        raise DownloadError(f"{url!r}: {error}")
    if len(data) > max_bytes:
        raise DownloadError(f"{url}: larger than {max_bytes} bytes")
    return data
