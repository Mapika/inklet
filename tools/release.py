"""Release Inklet from master in one command.

    python tools/release.py 4.4.1            # check, build, confirm, publish
    python tools/release.py 4.4.1 --dry-run  # everything local; publish nothing
    python tools/release.py 4.4.1 --yes      # no confirmation prompts

The version must already be committed on master: `pyproject.toml`,
`inklet.__version__` and a `## X.Y.Z — date` heading in CHANGELOG.md. The
script then runs, in order:

1. preflight   clean checkout of master, in sync with origin, tag unused
2. checks      API reference, full test suite, strict docs, compatibility
3. build       wheel and sdist into out/release-X.Y.Z, wheel smoke test,
               sdist size budget, SHA256SUMS and release notes
4. push        push master and wait for the "Release checks" workflow
5. tag         annotated vX.Y.Z tag, pushed
6. release     GitHub release with the wheel, sdist and SHA256SUMS
7. pypi        publish workflow as a dry run, then the upload
8. verify      PyPI serves files with the same SHA-256 as the release

Every step that reaches GitHub or PyPI asks first. Steps already done (a pushed
commit, an existing tag or release, files on PyPI) are detected and skipped, so
a failed run can be repeated with the same command. `--from STEP` starts later.
Needs git, gh (authenticated) and uv on PATH.
"""
from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "Mapika/inklet"
STEPS = ("preflight", "checks", "build", "push", "tag", "release", "pypi", "verify")
# 4.4.0's sdist was 89 MB of rendered images; PyPI's default limit is 100 MB.
SDIST_BUDGET_MB = 25


class ReleaseError(RuntimeError):
    pass


def say(text: str) -> None:
    print(f"\n\033[1m==> {text}\033[0m", flush=True)


def run(*args: str, capture: bool = False, cwd: Path = ROOT, env: dict | None = None) -> str:
    shown = " ".join(args)
    if not capture:
        print(f"$ {shown}", flush=True)
    result = subprocess.run(args, cwd=cwd, text=True, env=env,
                            stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.PIPE if capture else None)
    if result.returncode != 0:
        detail = (result.stderr or "").strip() if capture else ""
        raise ReleaseError(f"command failed ({result.returncode}): {shown}\n{detail}".rstrip())
    return (result.stdout or "").strip() if capture else ""


def succeeds(*args: str) -> bool:
    return subprocess.run(args, cwd=ROOT, capture_output=True).returncode == 0


def confirm(question: str, assume_yes: bool) -> None:
    if assume_yes:
        return
    answer = input(f"{question} [y/N] ").strip().lower()
    if answer not in ("y", "yes"):
        raise ReleaseError("stopped at your request; rerun with --from to continue")


def python() -> str:
    venv_python = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return str(venv_python if venv_python.exists() else sys.executable)


def source_env() -> dict:
    """Run tools against this checkout, not whatever inklet the venv installed."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    return env


def changelog_notes(version: str) -> str:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    heading = re.search(rf"^## {re.escape(version)} — .+$", text, re.MULTILINE)
    if heading is None:
        raise ReleaseError(f"CHANGELOG.md has no '## {version} — <date>' heading")
    following = re.search(r"^## ", text[heading.end():], re.MULTILINE)
    end = heading.end() + following.start() if following else len(text)
    return text[heading.end():end].strip() + "\n"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def wait_for_run(workflow: str, sha: str, *, since: float | None = None) -> None:
    """Find the newest run of `workflow` for `sha` and wait until it finishes green."""
    deadline = time.time() + 300
    while True:
        runs = json.loads(run("gh", "run", "list", "--repo", REPO, "--workflow", workflow,
                              "--commit", sha, "--limit", "5", "--json",
                              "databaseId,status,conclusion,createdAt", capture=True))
        if since is not None:
            runs = [r for r in runs if _epoch(r["createdAt"]) >= since - 5]
        if runs:
            break
        if time.time() > deadline:
            raise ReleaseError(f"no {workflow} run appeared for {sha[:7]} within 5 minutes")
        time.sleep(10)
    run_id = str(runs[0]["databaseId"])
    print(f"following {workflow} run {run_id}", flush=True)
    subprocess.run(["gh", "run", "watch", run_id, "--repo", REPO, "--interval", "30"], cwd=ROOT)
    outcome = json.loads(run("gh", "run", "view", run_id, "--repo", REPO,
                             "--json", "conclusion,jobs", capture=True))
    for job in outcome["jobs"]:
        print(f"  {job['conclusion'] or 'pending':<10} {job['name']}")
    if outcome["conclusion"] != "success":
        raise ReleaseError(f"{workflow} run {run_id} ended {outcome['conclusion']}: "
                           f"https://github.com/{REPO}/actions/runs/{run_id}")


def _epoch(stamp: str) -> float:
    return calendar.timegm(time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ"))


def pypi_digests(version: str) -> dict[str, str]:
    try:
        with urllib.request.urlopen(f"https://pypi.org/pypi/inklet/{version}/json", timeout=30) as reply:
            data = json.load(reply)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return {}
        raise
    return {item["filename"]: item["digests"]["sha256"] for item in data["urls"]}


class Release:
    def __init__(self, version: str, *, assume_yes: bool, dry_run: bool, fast: bool):
        self.version = version
        self.tag = f"v{version}"
        self.assume_yes = assume_yes
        self.dry_run = dry_run
        self.fast = fast
        self.dist = ROOT / "out" / f"release-{version}"
        self.files = (f"inklet-{version}-py3-none-any.whl", f"inklet-{version}.tar.gz")

    def outward(self, question: str) -> bool:
        """False when --dry-run; otherwise ask before touching GitHub or PyPI."""
        if self.dry_run:
            print(f"(dry run) would now: {question.rstrip('?')}")
            return False
        confirm(question, self.assume_yes)
        return True

    # -- 1 --------------------------------------------------------------
    def preflight(self) -> None:
        for tool in ("git", "gh", "uv"):
            if shutil.which(tool) is None:
                raise ReleaseError(f"{tool} is not on PATH")
        run("gh", "auth", "status", capture=True)
        branch = run("git", "rev-parse", "--abbrev-ref", "HEAD", capture=True)
        if branch != "master":
            raise ReleaseError(f"release from master, not {branch}")
        dirty = run("git", "status", "--porcelain", "--untracked-files=no", capture=True)
        if dirty:
            raise ReleaseError(f"commit or discard these changes first:\n{dirty}")
        run("git", "fetch", "--quiet", "--tags", "origin")
        behind = run("git", "rev-list", "--count", "HEAD..origin/master", capture=True)
        if behind != "0":
            raise ReleaseError(f"master is {behind} commit(s) behind origin; pull first")
        declared = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
        init = (ROOT / "src/inklet/__init__.py").read_text()
        package = re.search(r'^__version__ = "([^"]+)"', init, re.MULTILINE).group(1)
        if declared != self.version or package != self.version:
            raise ReleaseError(f"pyproject says {declared} and __version__ says {package}; "
                               f"both must be {self.version}")
        changelog_notes(self.version)
        if succeeds("git", "rev-parse", "--verify", "--quiet", f"refs/tags/{self.tag}"):
            tagged = run("git", "rev-list", "-n", "1", self.tag, capture=True)
            if tagged != run("git", "rev-parse", "HEAD", capture=True):
                raise ReleaseError(f"{self.tag} already exists on another commit ({tagged[:7]})")
            print(f"{self.tag} already points at HEAD; continuing a previous run")
        print(f"releasing {self.version} from {run('git', 'rev-parse', '--short', 'HEAD', capture=True)}")

    # -- 2 --------------------------------------------------------------
    def checks(self) -> None:
        env = source_env()
        run(python(), "tools/gen_api.py", "--check", env=env)
        run(python(), "tools/check_compatibility.py", env=env)
        run(python(), "-m", "mkdocs", "build", "--strict", "--quiet",
            "--site-dir", str(ROOT / "out" / "release-site"), env=env)
        if self.fast:
            print("--fast: skipping the local test suite; CI still runs it")
        else:
            run(python(), "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider",
                "-m", "not acceptance", env=env)

    # -- 3 --------------------------------------------------------------
    def build(self) -> None:
        shutil.rmtree(self.dist, ignore_errors=True)
        run("uv", "build", "--wheel", "--sdist", "--out-dir", str(self.dist))
        missing = [name for name in self.files if not (self.dist / name).exists()]
        if missing:
            raise ReleaseError(f"the build did not produce {missing}")
        run(python(), "tools/check_wheel.py", str(self.dist / self.files[0]))
        sdist_mb = (self.dist / self.files[1]).stat().st_size / 1e6
        print(f"wheel {(self.dist / self.files[0]).stat().st_size / 1e6:.1f} MB, sdist {sdist_mb:.1f} MB")
        if sdist_mb > SDIST_BUDGET_MB:
            raise ReleaseError(f"sdist is {sdist_mb:.0f} MB, over the {SDIST_BUDGET_MB} MB budget; "
                               "check [tool.hatch.build.targets.sdist] in pyproject.toml")
        sums = "".join(f"{sha256(self.dist / name)}  {name}\n" for name in self.files)
        (self.dist / "SHA256SUMS").write_text(sums)
        (self.dist / "notes.md").write_text(changelog_notes(self.version))
        print(sums, end="")

    # -- 4 --------------------------------------------------------------
    def push(self) -> None:
        head = run("git", "rev-parse", "HEAD", capture=True)
        ahead = run("git", "rev-list", "--count", "origin/master..HEAD", capture=True)
        if ahead != "0":
            if not self.outward(f"Push {ahead} commit(s) on master to origin?"):
                return
            run("git", "push", "origin", "master")
        elif self.dry_run:
            print("(dry run) master is already on origin; would wait for its CI run")
            return
        wait_for_run("checks.yml", head)

    # -- 5 --------------------------------------------------------------
    def tag_release(self) -> None:
        head = run("git", "rev-parse", "HEAD", capture=True)
        if not succeeds("git", "rev-parse", "--verify", "--quiet", f"refs/tags/{self.tag}"):
            if not self.outward(f"Create tag {self.tag} on {head[:7]} and push it?"):
                return
            run("git", "tag", "-a", self.tag, "-m", f"Inklet {self.version}", head)
        if succeeds("git", "ls-remote", "--exit-code", "--tags", "origin", f"refs/tags/{self.tag}"):
            print(f"{self.tag} is already on origin")
            return
        if not self.outward(f"Push tag {self.tag} to origin?"):
            return
        run("git", "push", "origin", self.tag)

    # -- 6 --------------------------------------------------------------
    def release(self) -> None:
        if succeeds("gh", "release", "view", self.tag, "--repo", REPO):
            print(f"GitHub release {self.tag} already exists")
            return
        for name in (*self.files, "SHA256SUMS", "notes.md"):
            if not (self.dist / name).exists():
                raise ReleaseError(f"{self.dist / name} is missing; run the build step again")
        if not self.outward(f"Create the GitHub release {self.tag} with the wheel, sdist and SHA256SUMS?"):
            return
        # The publish workflow requires development and RC tags to be prereleases.
        prerelease = ("--prerelease", "--latest=false") if re.search(r"rc|dev", self.version) else ()
        run("gh", "release", "create", self.tag, "--repo", REPO,
            "--title", f"Inklet {self.version}", "--notes-file", str(self.dist / "notes.md"),
            "--verify-tag", *prerelease, *(str(self.dist / name) for name in (*self.files, "SHA256SUMS")))

    # -- 7 --------------------------------------------------------------
    def pypi(self) -> None:
        if pypi_digests(self.version):
            print(f"inklet {self.version} is already on PyPI")
            return
        head = run("git", "rev-parse", "origin/master", capture=True)
        for dry in ("true", "false"):
            label = "dry run" if dry == "true" else "upload"
            if dry == "false" and not self.outward(f"Upload inklet {self.version} to PyPI? This cannot be undone"):
                return
            if dry == "true" and self.dry_run:
                print("(dry run) would now run the PyPI workflow as a dry run, then upload")
                return
            say(f"PyPI {label}")
            started = time.time()
            run("gh", "workflow", "run", "publish.yml", "--repo", REPO, "--ref", "master",
                "-f", f"tag={self.tag}", "-F", f"dry_run={dry}")
            wait_for_run("publish.yml", head, since=started)

    # -- 8 --------------------------------------------------------------
    def verify(self) -> None:
        if self.dry_run:
            print("(dry run) nothing was published, so there is nothing to verify")
            return
        for attempt in range(12):
            served = pypi_digests(self.version)
            if len(served) >= len(self.files):
                break
            time.sleep(10)
        else:
            raise ReleaseError(f"PyPI does not list inklet {self.version} yet")
        expected = dict(line.split()[::-1] for line in
                        (self.dist / "SHA256SUMS").read_text().splitlines())
        for name in self.files:
            if served.get(name) != expected[name]:
                raise ReleaseError(f"{name}: PyPI has {served.get(name)}, release has {expected[name]}")
            print(f"  match  {name}  {expected[name][:16]}…")
        print(f"\nInklet {self.version} is out:\n"
              f"  https://github.com/{REPO}/releases/tag/{self.tag}\n"
              f"  https://pypi.org/project/inklet/{self.version}/")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog="Steps: " + ", ".join(STEPS))
    parser.add_argument("version", help="the version to release, e.g. 4.4.1")
    parser.add_argument("--from", dest="start", choices=STEPS, default=STEPS[0],
                        help="skip the steps before this one")
    parser.add_argument("--yes", action="store_true", help="do not ask before publishing steps")
    parser.add_argument("--dry-run", action="store_true",
                        help="run the local steps and show what would be published")
    parser.add_argument("--fast", action="store_true",
                        help="skip the local test suite (CI still runs it before tagging)")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:(?:rc|\.dev)\d+)?", args.version):
        parser.error(f"{args.version!r} is not a version such as 4.4.1, 5.0.0rc1 or 5.0.0.dev1")

    release = Release(args.version, assume_yes=args.yes, dry_run=args.dry_run, fast=args.fast)
    actions = {"preflight": release.preflight, "checks": release.checks, "build": release.build,
               "push": release.push, "tag": release.tag_release, "release": release.release,
               "pypi": release.pypi, "verify": release.verify}
    try:
        if args.start != "preflight":
            say("preflight")
            release.preflight()
        for step in STEPS[STEPS.index(args.start):]:
            if step == "preflight" and args.start != "preflight":
                continue
            say(step)
            actions[step]()
    except ReleaseError as error:
        print(f"\n\033[31mrelease stopped: {error}\033[0m", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nrelease interrupted; rerun the same command to continue", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
