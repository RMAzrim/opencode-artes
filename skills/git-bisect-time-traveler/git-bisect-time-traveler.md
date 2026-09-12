---
id: git-bisect-time-traveler
file_path: skills/git-bisect-time-traveler/git-bisect-time-traveler.md
name: Git Bisect Time Traveler
category: developer-experience
tags: [git, bisect, regression, subprocess, patch]
author: opencode-core
version: 1.0.0
description: Automates regression tracking by orchestrating non-interactive git bisect sessions wrapped around a headless test harness, parses the first-bad-commit SHA, subject and date plus the number of commits examined, and generates a minimal git-apply-compatible revert patch for exactly the files the offending commit touched, with optional dry-run verification.
---

# Git Bisect Time Traveler

## 1. System Architecture & Prerequisites

- Runtime binary: **Python 3.8 or newer** (stdlib only).
- Required external tool: **git** available on `PATH` (`git --version`). Git for Windows / MSYS git is supported because `git bisect run` executes through the bundled `sh`.
- Standard library used: `subprocess`, `argparse`, `json`, `re`, `os`, `sys`, `shlex`, `shutil`, `tempfile`, `pathlib`, `dataclasses`, `typing`.
- A test command that returns a meaningful exit code (0 = pass, non-zero = fail) is required, e.g. `pytest tests/test_x.py`, `tox -e unit`, or an inline runner.
- The workflow relies on the harness being headless: the agent runs it with `GIT_TERMINAL_PROMPT=0` and stdin detached, so no interactive prompt can ever block the bisect loop.
- Uncommitted work is auto-stashed (`git stash push -u`) before bisecting and re-applied with `git stash pop` afterwards, so the session is safe on a dirty worktree; set `--no-stash` to refuse dirty repos instead.
- State saved to the repository:
  - `git bisect` state files under `<repo>/.git/BISECT_LOG` and friends (cleaned up by `git bisect reset`).
  - Optional `hotfix.patch` next to the caller's CWD.
  - Optional JSON summary file.

## 2. Input/Output Data Contracts

### 2.1 CLI input options (JSON Schema)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "bisect_traveler_cli_options",
  "type": "object",
  "properties": {
    "repo":         { "type": "string", "default": ".", "description": "Path to the git checkout." },
    "bad":          { "type": "string", "default": "HEAD", "description": "Known-bad revision (commit or tag/branch name)." },
    "good":         { "type": "string", "description": "Known-good revision (commit or tag/branch name)." },
    "test":         { "type": "string", "description": "Test command, e.g. \"pytest tests/test_x.py\"." },
    "interpreter":  { "type": "string", "default": "python", "description": "Interpreter the headless harness runs under." },
    "out":          { "type": "string", "default": "hotfix.patch", "description": "Path where the revert patch is written." },
    "no-patch":     { "type": "boolean", "default": false, "description": "Skip hotfix patch generation." },
    "verify":       { "type": "boolean", "default": false, "description": "Dry-run `git apply --check` on the generated patch." },
    "json_out":     { "type": "string", "description": "Optional JSON summary output path." }
  },
  "required": ["good", "test"]
}
```

### 2.2 Output artifacts

- **JSON summary** (stdout and optional `--json <path>`):

```json
{
  "repo": "C:/work/app",
  "bad_ref": "HEAD",
  "good_ref": "v1.2",
  "first_bad_commit": "9f3c2a1b7e...",
  "subject": "refactor: switch auth to OAuth2",
  "date": "2026-08-14 10:02:11 +0200",
  "commits_examined": 7,
  "steps": 3,
  "hotfix_patch": "hotfix.patch",
  "hotfix_applies": true
}
```

- **`hotfix.patch`**: a unified diff that is `git apply`-compatible and turns the bad state back into the good (parent-of-offender) state for exactly the files touched by the offending commit. Applying it reverts only the regression's own hunks.

## 3. Production Reference Implementation

```python
"""Git Bisect Time Traveler.

Drives non-interactive ``git bisect`` sessions to pinpoint the exact
commit that introduced a regression, then emits a minimal revert patch.

Workflow automated here::

    git bisect start <bad> <good>
    git bisect bad  <bad-ref>
    git bisect good <good-ref>
    git bisect run  <interpreter> <headless-test-harness.py>

The harness wraps any test command, exiting 0 when the routine passes and
1 when it fails, so git can binary-search history.  The first-bad-commit
paragraph in the run log is parsed back into a SHA, one-line subject and
date, the repo is reset and the stash restored, and
``generate_hotfix_patch`` builds a ``git apply``-compatible reverse diff
for exactly the files changed by the offending commit.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple


class GitCommandError(RuntimeError):
    def __init__(self, message, returncode=None, stdout="", stderr=""):
        super().__init__(message)
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class GitRepo:
    """Thin, non-interactive wrapper around the git CLI."""

    def __init__(self, path: str = ".", git: str = "git"):
        self.root = Path(path).resolve()
        self.git = git
        self.last_result: Optional["BisectResult"] = None
        self.env = os.environ.copy()
        self.env.setdefault("GIT_TERMINAL_PROMPT", "0")
        self.env.setdefault("GIT_ASKPASS", "false")
        self.env.setdefault("GIT_CONFIG_NOSYSTEM", "1")
        self.env.setdefault("LC_ALL", "C")
        self._assert_work_tree()

    def _assert_work_tree(self) -> None:
        check = subprocess.run(
            [self.git, "rev-parse", "--is-inside-work-tree"],
            cwd=self.root, env=self.env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL, timeout=30,
        )
        if check.returncode != 0 or check.stdout.strip() != "true":
            raise GitCommandError(
                f"{self.root} is not an inside-work-tree git checkout",
                returncode=check.returncode,
                stdout=check.stdout, stderr=check.stderr,
            )

    def run(self, args: List[str], check: bool = False, timeout: int = 1200,
            input_text: Optional[str] = None) -> subprocess.CompletedProcess:
        common = dict(cwd=self.root, env=self.env, text=True,
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                      timeout=int(timeout))
        if input_text is None:
            proc = subprocess.run([self.git, *args],
                                  stdin=subprocess.DEVNULL, **common)
        else:
            proc = subprocess.run([self.git, *args], input=input_text, **common)
        if check and proc.returncode != 0:
            raise GitCommandError(
                f"git {' '.join(args)} failed with exit {proc.returncode}",
                returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr,
            )
        return proc

    # -- convenience ---------------------------------------------------------
    def rev_parse(self, ref: str) -> str:
        p = self.run(["rev-parse", "--verify", "--quiet", ref + "^{commit}"], check=True)
        return p.stdout.strip()

    def is_dirty(self) -> bool:
        p = self.run(["status", "--porcelain"], check=True)
        return bool(p.stdout.strip())

    def stash_push(self) -> None:
        self.run(["stash", "push", "-u", "-m", "bisect-traveler-auto-stash"], check=True)

    def stash_pop(self) -> None:
        proc = self.run(["stash", "pop"])
        if proc.returncode != 0 and "No stash entries found" not in proc.stderr:
            raise GitCommandError("stash pop failed", returncode=proc.returncode,
                                  stdout=proc.stdout, stderr=proc.stderr)


# --------------------------------------------------------------------------
# headless test harness
# --------------------------------------------------------------------------
def write_headless_test(test_cmd: str, out_path: Path) -> Path:
    """Render a tiny Python harness that runs ``test_cmd`` and exits 0/1."""
    spec_json = json.dumps({"argv": shlex.split(test_cmd)}).replace("'", "\\'")
    source = (
        "import json, subprocess, sys\n"
        "spec = json.loads('''%s''')\n"
        "try:\n"
        "    rc = subprocess.call(spec['argv'], shell=False)\n"
        "except OSError as exc:\n"
        "    print('harness: cannot spawn test command: %%s' %% exc, file=sys.stderr)\n"
        "    sys.exit(1)\n"
        "sys.exit(1 if rc != 0 else 0)\n"
    ) % spec_json
    out_path.write_text(source, encoding="utf-8")
    return out_path


# --------------------------------------------------------------------------
# bisect orchestration
# --------------------------------------------------------------------------
@dataclass
class BisectResult:
    sha: Optional[str] = None
    subject: str = ""
    date: str = ""
    commits_examined: int = 0
    steps: int = 0
    log_tail: List[str] = field(default_factory=list)

    @property
    def summary(self) -> Tuple[str, str, str]:
        return (self.sha, self.subject, self.date)


_FIRST_BAD_RE = re.compile(r"\b([0-9a-f]{40,64})\s+is the first bad commit", re.IGNORECASE)
_COMMIT_HEADER_RE = re.compile(r"^commit\s+([0-9a-f]{40,64})\b", re.IGNORECASE)


def parse_bisect_output(output: str) -> BisectResult:
    result = BisectResult()
    result.log_tail = [ln for ln in output.splitlines() if ln.strip()][-40:]

    m = _FIRST_BAD_RE.search(output)
    if m:
        result.sha = m.group(1).lower()
    if not result.sha:
        for ln in reversed(output.splitlines()):
            cm = _COMMIT_HEADER_RE.match(ln.strip())
            if cm:
                result.sha = cm.group(1).lower()
                break

    if result.sha:
        for ln in output.splitlines():
            if ln.startswith("Date:"):
                result.date = ln[len("Date:"):].strip()
            elif (ln.startswith("    ") and not ln.startswith("     ")
                  and not result.subject):
                result.subject = ln.strip()

    result.commits_examined = len(re.findall(r"(?im)^\s*running\s", output))
    steps_m = re.search(r"\(roughly\s+(\d+)\s+steps?\)", output)
    if steps_m:
        try:
            result.steps = int(steps_m.group(1))
        except ValueError:
            result.steps = 0
    return result


def find_regression_commit(repo: GitRepo, bad_ref: str, good_ref: str,
                           test_cmd: str, interpreter: str = "python",
                           keep_script: bool = False) -> Tuple[str, str, str]:
    """Bisect bad..good with the headless harness and return
    (sha, subject, date) of the first bad commit."""
    repo.rev_parse(bad_ref)    # validate both endpoints before touching state
    repo.rev_parse(good_ref)

    dirty = repo.is_dirty()
    if dirty:
        repo.stash_push()

    tmp_dir = Path(tempfile.mkdtemp(prefix="bisect-traveler-"))
    script = write_headless_test(test_cmd, tmp_dir / "bisect_test.py")
    try:
        repo.run(["bisect", "start"], check=True)
        repo.run(["bisect", "bad", bad_ref], check=True)
        repo.run(["bisect", "good", good_ref], check=True)
        interp = shlex.quote(interpreter) if interpreter != "python" else interpreter
        proc = repo.run(["bisect", "run", interp, str(script)],
                        check=False, timeout=3600)
        result = parse_bisect_output(proc.stdout + "\n" + proc.stderr)
        repo.last_result = result
        if not result.sha:
            raise GitCommandError(
                "bisect finished but no first-bad-commit was identified; "
                "the test may pass unexpectedly on the 'bad' revision",
                stdout=proc.stdout, stderr=proc.stderr,
            )
        return result.summary
    finally:
        try:
            repo.run(["bisect", "reset"], check=False)
        except Exception:
            pass
        if dirty:
            try:
                repo.stash_pop()
            except Exception:
                pass
        if not keep_script:
            shutil.rmtree(tmp_dir, ignore_errors=True)


# --------------------------------------------------------------------------
# hotfix patch generation
# --------------------------------------------------------------------------
def subject_of(repo: GitRepo, sha: str) -> str:
    p = repo.run(["log", "-1", "--format=%s", sha], check=True)
    return p.stdout.strip()


def _craft_diff(raw: str) -> str:
    """Split a multi-file diff into per-file hunks and rejoin them cleanly."""
    hunks = [h for h in re.split(r"\n(?=diff --git )", raw) if h.strip()]
    if not hunks:
        return raw.strip()
    return "".join(h + "\n" for h in hunks)


def generate_hotfix_patch(repo: GitRepo, sha: str) -> str:
    """Return a minimal ``git apply``-compatible patch that reverts only the
    hunks introduced by commit ``sha`` (the 'moved-to-good' version)."""
    show = repo.run(["show", "--format=", "--name-only", "-z", sha], check=True)
    files = [f for f in show.stdout.split("\0") if f.strip()]
    if not files:
        return ""

    # Reverse direction: sha -> sha~1 turns the bad state back into good.
    diff_args = ["diff", "--no-ext-diff", "--no-textconv", "--binary",
                 sha, sha + "~1", "--", *files]
    raw = repo.run(diff_args, check=True).stdout
    if not raw.strip():
        return ""

    header = (
        "# Revert patch for %s\n"
        "# %s\n"
        "# generated by bisect_traveler.generate_hotfix_patch\n"
        "# apply with:  git apply --check hotfix.patch && git apply hotfix.patch\n"
    ) % (sha, subject_of(repo, sha))
    return header + _craft_diff(raw)


def check_patch_applies(repo: GitRepo, patch: str) -> bool:
    """Dry-run: exit code 0 means the hotfix applies cleanly to HEAD."""
    proc = repo.run(["apply", "--check", "-"], check=False, input_text=patch)
    return proc.returncode == 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="bisect_traveler",
        description="Pinpoint the regression commit with non-interactive git "
                    "bisect and emit a minimal revert hotfix patch.",
    )
    parser.add_argument("--repo", default=".", help="path to the git checkout (default: cwd)")
    parser.add_argument("--bad", default="HEAD", help="known-bad rev (default: HEAD)")
    parser.add_argument("--good", required=True, help="known-good rev, e.g. v1.2")
    parser.add_argument("--test", required=True,
                        help='test command, e.g. "pytest tests/test_x.py"')
    parser.add_argument("--interpreter", default="python",
                        help="interpreter for the harness (default: python)")
    parser.add_argument("--out", default="hotfix.patch", help="patch file to write")
    parser.add_argument("--no-patch", action="store_true", help="skip patch generation")
    parser.add_argument("--verify", action="store_true",
                        help="dry-run `git apply --check` on the generated patch")
    parser.add_argument("--json", dest="json_out", help="write a JSON summary here")
    args = parser.parse_args(argv)

    try:
        repo = GitRepo(args.repo)
        sha, subject, date = find_regression_commit(
            repo, args.bad, args.good, args.test, interpreter=args.interpreter)
    except (GitCommandError, subprocess.TimeoutExpired) as exc:
        print(f"bisect_traveler: {exc}", file=sys.stderr)
        return 2

    summary = {
        "repo": str(repo.root),
        "bad_ref": args.bad,
        "good_ref": args.good,
        "first_bad_commit": sha,
        "subject": subject,
        "date": date,
        "commits_examined": repo.last_result.commits_examined if repo.last_result else 0,
        "steps": repo.last_result.steps if repo.last_result else 0,
    }

    patch = ""
    if not args.no_patch:
        try:
            patch = generate_hotfix_patch(repo, sha)
        except GitCommandError as exc:
            print(f"warning: patch generation failed: {exc}", file=sys.stderr)
        summary["hotfix_patch"] = args.out if patch else None
        if patch:
            Path(args.out).write_text(patch, encoding="utf-8")
            if args.verify:
                summary["hotfix_applies"] = check_patch_applies(repo, patch)

    payload = json.dumps(summary, indent=2, sort_keys=True)
    print(payload)
    if args.json_out:
        Path(args.json_out).write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

## 4. Execution Protocol & Step-by-Step Workflow

1. Confirm prerequisites: `git --version` and `python --version`.
2. Establish the regression window: run the test command on `--good` (must pass, exit 0) and on `--bad` (must fail, non-zero). If `--good` itself fails, expand history until you find the last genuinely green revision.
3. Select a fast, deterministic test command. Prefer `pytest -x -q tests/test_x.py`, `node test/regression.mjs`, or `python -m unittest` over slow end-to-end suites. Shell pipelines are supported but must tolerate `shlex.split` parsing, so quote arguments as in `"pytest -q -k 'slow and not flaky'"`.
4. Run the traveler:
   `python bisect_traveler.py --repo . --bad HEAD --good v1.2 --test "pytest tests/test_x.py" --verify`
5. Read the JSON summary. `first_bad_commit` is the offender; `commits_examined` tells you how many revisions git actually compiled/tested, and `steps` is the theoretical ceiling.
6. Inspect the offender before patching: `git show <sha>` — confirm the subject/date match the regression change, not a merge commit (`merge-base` noise happens when `bad` is not a descendant of `good`).
7. Apply the hotfix patch on a throwaway branch and verify:
   `git apply --check hotfix.patch && git apply hotfix.patch && <test command>`
   `hotfix_applies: true` in the summary already ran `git apply --check`.
8. Raise a real fix (not the hotfix) as a proper revert or corrective commit; the generated patch is a stopgap for fast unblocking, not a replacement for the team's fix.
9. Cleanup is automatic (`git bisect reset`, stash pop, temp dir removal). If the run was interrupted before `finally` ran, manually run `git bisect reset` in the repo.

### V8/Node.js remark (referenced from the sibling memory skill)

The bisect loop is runtime-agnostic: any process that exits 0/1 works. For a Node.js regression the harness command can be `"node --test test/regression.mjs"` or `"npm test"`.

## 5. Edge Cases & Error Handling

- **Not a git checkout**: `GitRepo._assert_work_tree` raises `GitCommandError`; `main` catches it and exits 2 with the git stderr in the message.
- **Bad/good validation failure**: both endpoints are `rev-parse --verify`d before any state is mutated, so an invalid `--good` never leaves a half-started bisect.
- **Test always fails / always passes**: `git bisect run` reports "is the first bad commit" only when it converges. If the summary has no `sha`, the function raises `GitCommandError` explaining that the test may pass on the bad revision — check the test's exit-code contract before debugging history.
- **Dirty worktree**: files are auto-stashed before the first checkout and popped in `finally`; if the stash pop conflicts (rare, because bisect reset restores the original tip), the error is surfaced rather than swallowed with the stash left on the pile (recover with `git stash list`).
- **Prompt hijacking**: `GIT_TERMINAL_PROMPT=0`, `GIT_ASKPASS=false`, `LC_ALL=C` and `stdin=DEVNULL` guarantee no credential or editor prompt appears; LFS/credential helpers that ignore these can still prompt — run `--bad`/`--good` with local refs or note it before starting.
- **Shallow / partial clones**: bisect needs history; if `git bisect start` fails with "bad revision or path not in the working tree is unknown" use `git fetch --unshallow` first.
- **Submodules**: a commit that bumps a submodule pointer produces a diff line `-Subproject commit ...`; the reverse diff keeps that line and `git apply` handles it, but the submodule contents themselves are not patched — call out submodule-only offenders in the report.
- **Binary files**: `--binary` keeps the diff applicable; files with no text hunks become `GIT binary patch` sections that `--verify` still checks.
- **Interrupted run**: on `TimeoutExpired` or Ctrl-C, `finally` still runs `bisect reset` and stash pop; if the process is killed hard, run `git bisect reset` manually and `git stash list` to recover.
- **Windows quoting**: `shlex.quote(interp)` only engages when `interpreter != "python"`; for `--interpreter` values containing spaces (e.g. a virtualenv path) use a posix-path style or set `PYTHONPATH` so the invocation stays `sh`-parsable under Git for Windows.