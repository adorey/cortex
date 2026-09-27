"""Downloads over HTTPS, with the machine's certificates, from a binary built elsewhere.

A binary built by PyInstaller carries the OpenSSL of the machine that built it, and that OpenSSL
looks for certificates where that machine keeps them: AlmaLinux's ``/etc/pki/tls``, the framework
directory of a macOS build of Python. On a Debian, or on a Mac without that Python, it finds
none, and every download fails verification. When the default locations hold nothing, the
certificate bundles every common system keeps are tried in turn. ``SSL_CERT_FILE`` and
``SSL_CERT_DIR`` still win, as OpenSSL reads them itself.
"""

from __future__ import annotations

import os
import ssl
import urllib.error
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


class DownloadError(Exception):
    pass


def _defaults_hold_certificates() -> bool:
    if os.name == "nt":                        # Python reads the Windows certificate store
        return True
    if os.environ.get("SSL_CERT_FILE") or os.environ.get("SSL_CERT_DIR"):
        return True
    paths = ssl.get_default_verify_paths()     # cafile and capath are None when they do not exist
    return bool(paths.cafile or paths.capath)


def fallback_bundle() -> Optional[str]:
    return next((path for path in CA_BUNDLES if os.path.isfile(path)), None)


def ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    if not _defaults_hold_certificates():
        bundle = fallback_bundle()
        if bundle is not None:
            context.load_verify_locations(cafile=bundle)
    return context


def get(url: str, max_bytes: int) -> bytes:
    """The body of ``url``, at most ``max_bytes`` of it — HTTPS verified, redirects followed."""
    request = urllib.request.Request(url, headers={"User-Agent": f"cortex/{VERSION}"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT, context=ssl_context()) as response:
            data = response.read(max_bytes + 1)
    except urllib.error.HTTPError as error:
        raise DownloadError(f"{url}: HTTP {error.code} {error.reason}")
    except (urllib.error.URLError, OSError) as error:
        reason = getattr(error, "reason", error)
        raise DownloadError(f"{url}: {reason}")
    if len(data) > max_bytes:
        raise DownloadError(f"{url}: larger than {max_bytes} bytes")
    return data
