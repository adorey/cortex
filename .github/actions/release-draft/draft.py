"""The draft release (ADR-009 §3.3, §3.7): created last, once its assets are built and checked.

The draft is titled after its version, its body the note the version action wrote, its target the
very commit the job built — never a branch, which may move — and it has no tag until someone
publishes it. Its assets are every file of one directory, which must be exactly the ones expected.

If a release of the same version exists, published or draft, the job stops and changes nothing:
a new commit is a new version.

Once uploaded, the assets are read back, by name and size. Standard library only.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from github import GitHub, GitHubError, quote  # noqa: E402


class Refused(Exception):
    pass


def existing(github: GitHub, version: str) -> Optional[Dict[str, Any]]:
    return next((r for r in github.releases() if r.get("tag_name") == version), None)


def check_assets(directory: Path, expected: Sequence[str]) -> List[Path]:
    files = sorted(p for p in directory.iterdir() if p.is_file())
    names = sorted(p.name for p in files)
    if expected and names != sorted(expected):
        missing = sorted(set(expected) - set(names))
        extra = sorted(set(names) - set(expected))
        raise Refused(f"the assets are not the ones expected — missing {missing or 'none'}, unexpected {extra or 'none'}")
    if not files:
        raise Refused(f"{directory} holds no asset")
    return files


def draft(github: GitHub, version: str, target: str, body: str, prerelease: bool, latest: bool,
          files: Sequence[Path]) -> Dict[str, Any]:
    found = existing(github, version)
    if found is not None:
        if not found.get("draft"):
            raise Refused(f"{version} is already published: nothing is changed")
        raise Refused(f"a draft {version} is waiting: nothing is changed")

    release = github.request("POST", github.repo("/releases"), body={
        "tag_name": version, "target_commitish": target, "name": version, "body": body, "draft": True,
        "prerelease": prerelease, "make_latest": "true" if latest else "false"})
    upload = release["upload_url"].split("{", 1)[0]
    for path in files:
        github.request("POST", "", data=path.read_bytes(), content_type="application/octet-stream",
                       url=f"{upload}?name={quote(path.name)}")

    # Read back: every asset there, with its size.
    assets = {a["name"]: a["size"] for a in github.get(github.repo(f"/releases/{release['id']}/assets?per_page=100"))}
    wrong = [p.name for p in files if assets.get(p.name) != p.stat().st_size]
    if wrong or len(assets) != len(files):
        raise Refused(f"the draft {version} does not hold its assets as built: {wrong or sorted(assets)}")
    return release


def main(argv: Optional[Sequence[str]] = None, github: Optional[GitHub] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--version", required=True)
    parser.add_argument("--target", required=True, help="the commit the job built")
    parser.add_argument("--body-file", required=True)
    parser.add_argument("--assets", required=True, help="the directory of the assets")
    parser.add_argument("--expected", default="", help="the names of the assets, one per line")
    parser.add_argument("--prerelease", default="false")
    parser.add_argument("--latest", default="false")
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    args = parser.parse_args(argv)
    github = github or GitHub(args.repository)
    try:
        files = check_assets(Path(args.assets), [n.strip() for n in args.expected.splitlines() if n.strip()])
        release = draft(github, args.version, args.target, Path(args.body_file).read_text(encoding="utf-8"),
                        args.prerelease == "true", args.latest == "true", files)
    except Refused as why:
        print(f"::error title=release draft::{why}")
        return 1
    except GitHubError as error:
        print(f"::error title=release draft::{error}")
        return 2
    kind = "pre-release" if args.prerelease == "true" else "release"
    text = (f"The draft {kind} {args.version} is ready, with {len(files)} assets, from {args.target[:12]}: "
            f"publish it from the Releases page — {release.get('html_url', '')}")
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"### Release draft\n\nThe draft **{kind} {args.version}** is ready, with {len(files)} assets, "
                     f"from `{args.target[:12]}`. [Publish it]({release.get('html_url', '')}) from the Releases page.\n")
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as fh:
            fh.write(f"id={release['id']}\nurl={release.get('html_url', '')}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
