"""The guard (ADR-009 §3.5): what a published release is checked against.

For releases and pre-releases alike:

1. the tag is a version: ``X.Y.Z`` or ``X.Y.Z-(alpha|beta|rc).N``;
2. the build provenance of every asset names the tag's commit — its attestations, read through the
   API, then ``gh attestation verify``, signed by the workflow that built it. The API failing to
   answer is no finding: the guard stops, and says nothing of the release. ``gh`` still fetches its
   trust root over the network, and a failure there reads as one;
3. the assets expected are there, no other, and ``SHA256SUMS`` matches them;
4. the release is immutable;
5. ``latest`` is the highest version without a suffix — among the releases that carry every asset
   expected and are not marked pre-release: a release that fails its guard leaves ``latest`` to the
   highest of them, or says none is left, since ``releases/latest/download/…`` would serve it; one
   that misses an asset never becomes it again.

It repairs item 5 only, since immutability locks everything else: when an older line, a
pre-release or a release that fails took ``latest``, it moves it. On any other failure it fails, and opens one issue
naming what it found and the only fix: the release cannot be repaired, only deleted, and its
version is spent; the next patch ships what it should have. Standard library only, and ``gh``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from github import GitHub, GitHubError, quote  # noqa: E402
from semver import Version, highest, is_prerelease, is_release  # noqa: E402

SUMS = "SHA256SUMS"


@dataclass
class Report:
    tag: str
    findings: List[str] = field(default_factory=list)
    repaired: List[str] = field(default_factory=list)
    passed: List[str] = field(default_factory=list)


def tag_commit(github: GitHub, tag: str) -> str:
    ref = github.get(github.repo(f"/git/ref/tags/{quote(tag)}"))["object"]
    while ref["type"] == "tag":   # an annotated tag points at a tag object first
        ref = github.get(github.repo(f"/git/tags/{ref['sha']}"))["object"]
    return ref["sha"]


def attestations(github: GitHub, path: Path) -> List[Dict[str, Any]]:
    """The attestations of ``path``'s digest, none when it has none. Any other failure of the API is
    a GitHubError: the guard cannot tell, so it stops, and fails no release for it."""
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    try:
        return github.get(github.repo(f"/attestations/sha256:{digest}")).get("attestations") or []
    except GitHubError as error:
        if error.status == 404:
            return []
        raise


def gh_verify(path: Path, bundle: Path, repository: str, commit: str, signer: str) -> Optional[str]:
    """None when ``path``'s provenance, in the attestations of ``bundle``, names ``commit`` and
    ``signer``; why not otherwise."""
    out = subprocess.run(["gh", "attestation", "verify", str(path), "--bundle", str(bundle), "--repo", repository,
                          "--source-digest", commit, "--signer-workflow", signer], capture_output=True, text=True)
    if out.returncode == 0:
        return None
    lines = (out.stderr or out.stdout).strip().splitlines()
    return lines[-1] if lines else "verification failed"


def check(github: GitHub, release: Dict[str, Any], expected: Sequence[str], signer: str, workdir: Path,
          verify: Callable[[Path, Path, str, str, str], Optional[str]] = gh_verify) -> Report:
    tag = release["tag_name"]
    report = Report(tag)

    # 1. A version.
    if is_release(tag) or is_prerelease(tag):
        report.passed.append(f"the tag {tag} is a version")
    else:
        report.findings.append(f"the tag {tag!r} is no version: X.Y.Z or X.Y.Z-(alpha|beta|rc).N")

    # 3. The assets, and SHA256SUMS over them — downloaded once, for 2 as well.
    names = sorted(a["name"] for a in release.get("assets", []))
    if expected:
        missing = sorted(set(expected) - set(names))
        extra = sorted(set(names) - set(expected))
        if missing:
            report.findings.append(f"assets missing: {', '.join(missing)}")
        if extra:
            report.findings.append(f"assets not expected: {', '.join(extra)}")
        if not missing and not extra:
            report.passed.append(f"the {len(names)} assets expected are there")
    files: Dict[str, Path] = {}
    for asset in release.get("assets", []):
        data = github.download(asset["url"])
        path = workdir / asset["name"]
        path.write_bytes(data)
        files[asset["name"]] = path
    if SUMS in files:
        listed = {}
        for line in files[SUMS].read_text(encoding="utf-8").splitlines():
            fields = line.split()
            if len(fields) == 2:
                listed[fields[1].lstrip("*")] = fields[0].lower()
        wrong = [n for n, p in files.items() if n != SUMS and listed.get(n) != hashlib.sha256(p.read_bytes()).hexdigest()]
        unlisted_files = sorted(set(listed) - set(files))
        if wrong:
            report.findings.append(f"{SUMS} does not match: {', '.join(sorted(wrong))}")
        if unlisted_files:
            report.findings.append(f"{SUMS} lists files the release does not have: {', '.join(unlisted_files)}")
        if not wrong and not unlisted_files:
            report.passed.append(f"{SUMS} matches the assets")
    else:
        report.findings.append(f"there is no {SUMS} to check the assets against")

    # 2. The provenance of every asset names the tag's commit.
    try:
        commit = tag_commit(github, tag)
    except GitHubError as error:
        if error.status != 404:
            raise   # the API in trouble says nothing of the release
        report.findings.append(f"the tag {tag} cannot be read: {error}")
    else:
        failed = []
        bundles = workdir / ".attestations"
        bundles.mkdir()
        for name, path in sorted(files.items()):
            found = [a["bundle"] for a in attestations(github, path) if a.get("bundle")]
            if not found:
                failed.append(f"{name} (no attestation)")
                continue
            bundle = bundles / f"{name}.jsonl"
            bundle.write_text("".join(json.dumps(b) + "\n" for b in found), encoding="utf-8")
            why = verify(path, bundle, github.repository, commit, signer)
            if why:
                failed.append(f"{name} ({why})")
        if failed:
            report.findings.append(f"the provenance does not name the tag's commit {commit[:12]}, signed by {signer}: "
                                   f"{'; '.join(failed)}")
        elif files:
            report.passed.append(f"the provenance of every asset names {commit[:12]}, signed by {signer}")

    # 4. Immutable.
    if release.get("immutable") is True:
        report.passed.append("the release is immutable")
    else:
        report.findings.append("the release is mutable: its assets could still be replaced")
    return report


def keep_latest(github: GitHub, report: Report, expected: Sequence[str]) -> None:
    """5. ``latest`` on the highest version without a suffix that carries every asset expected — the
    one thing the guard repairs. A release missing one stays out, whichever guard runs: it cannot
    pass. GitHub makes no pre-release ``latest``. Deleting a release that was ``latest`` leaves
    none at all: GitHub does not move it."""
    failing = report.tag if report.findings else None
    # Chosen by their assets, not by a guard of their own: 1.0.0 to 1.2.2 are signed by binary.yml, not
    # release.yml, and would fail one, so `latest` could never come back to them. A release with every
    # asset that fails any other check — provenance, SHA256SUMS, an extra asset, immutability — could
    # take `latest` back until it is deleted: its issue says so (ADR-009 §9).
    published = [r for r in github.releases() if not r.get("draft") and is_release(r.get("tag_name"))
                 and r.get("tag_name") != failing and not r.get("prerelease")
                 and set(expected) <= {a["name"] for a in r.get("assets", [])}]
    top = highest(Version(r["tag_name"]) for r in published)
    try:
        current = github.get(github.repo("/releases/latest"))["tag_name"]
    except GitHubError as error:
        if error.status != 404:
            raise   # the API in trouble: `latest` is unknown, so nothing is said of it
        current = None
    if top is None:
        if failing and failing == current:
            report.findings.append(f"latest stays on {failing}: no other release carries every asset expected")
        return
    if current == str(top):
        report.passed.append(f"latest is {top}, the highest version" + (" with every asset expected" if failing else ""))
        return
    target = next(r for r in published if r["tag_name"] == str(top))
    github.request("PATCH", github.repo(f"/releases/{target['id']}"), body={"make_latest": "true"})
    why = f"the highest version with every asset expected, while {failing} fails" if failing and failing == current else "the highest version"
    report.repaired.append(f"latest was {current or 'none'}; it is {top} again, {why}")


def open_issue(github: GitHub, report: Report, label: str, url: str) -> Optional[str]:
    """One issue per release: none is opened when one is open already."""
    title = f"Release {report.tag} failed its guard"
    for issue in github.paginate(github.repo(f"/issues?state=open&labels={quote(label)}")):
        if issue.get("title") == title:
            return issue.get("html_url")
    body = (f"The guard found what [{report.tag}]({url}) should not have:\n\n"
            + "".join(f"- {f}\n" for f in report.findings)
            + "\n**It cannot be repaired.** A published release is immutable: it can only be deleted, and its "
              f"version is spent — {report.tag} can never be used again. The next patch ships what this one "
              "should have, through the release cycle.\n\n"
              f"The guard moves `latest` off {report.tag} when it holds it, to the highest `X.Y.Z` release, not "
              "marked pre-release, that carries every asset expected, if there is one: its run says whether it "
              f"could. A later guard gives `latest` only to such a release: {report.tag}, if it is one, could take "
              "it back until it is deleted. If you delete it, check that `latest` still names a "
              "release: GitHub does not move it when the latest release is deleted.\n")
    issue = github.request("POST", github.repo("/issues"), body={"title": title, "body": body, "labels": [label]})
    return issue.get("html_url")


def main(argv: Optional[Sequence[str]] = None, github: Optional[GitHub] = None,
         verify: Callable[[Path, Path, str, str, str], Optional[str]] = gh_verify) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--tag", required=True)
    parser.add_argument("--expected", default="", help="the names of the assets, one per line")
    parser.add_argument("--signer-workflow", required=True, help="OWNER/REPO/.github/workflows/FILE that builds releases")
    parser.add_argument("--label", default="type:infra")
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    args = parser.parse_args(argv)
    github = github or GitHub(args.repository)
    expected = [n.strip() for n in args.expected.splitlines() if n.strip()]
    report: Optional[Report] = None
    try:
        release = next((r for r in github.releases() if r.get("tag_name") == args.tag and not r.get("draft")), None)
        if release is None:
            print(f"::error title=release guard::no published release is tagged {args.tag}")
            return 2
        with tempfile.TemporaryDirectory(prefix="release-guard-") as tmp:
            report = check(github, release, expected, args.signer_workflow, Path(tmp), verify)
        # Both writes are tried, whatever the other does: `latest` moved off a release whose issue
        # cannot be opened, and the issue opened while `latest` cannot move.
        try:
            keep_latest(github, report, expected)
        finally:
            issue = open_issue(github, report, args.label, release.get("html_url", "")) if report.findings else None
    except GitHubError as error:
        print(f"::error title=release guard::{error}")
        if report is not None:   # what the guard found before the API failed, for the log
            print(f"No verdict on {args.tag}: the guard stopped. What it found before:\n" + "\n".join(_lines(report)))
        return 2

    lines = _lines(report)
    verdict = (f"{args.tag} passes its guard." if not report.findings
               else f"{args.tag} fails its guard: it cannot be repaired, only deleted, and its version is spent. {issue or ''}")
    print(verdict + "\n" + "\n".join(lines))
    for finding in report.findings:
        print(f"::error title=release guard::{finding}")
    for repair in report.repaired:
        print(f"::notice title=release guard::{repair}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"### Release guard\n\n{verdict}\n\n" + "\n".join(lines) + "\n")
    return 1 if report.findings else 0


def _lines(report: Report) -> List[str]:
    return [f"- ✓ {p}" for p in report.passed] + [f"- ↺ {r}" for r in report.repaired] + [f"- ✗ {f}" for f in report.findings]


if __name__ == "__main__":
    sys.exit(main())
