#!/usr/bin/env python3
"""Regenerate the AUTO:* blocks of docs/PROJECT_STATE.md.

Hand-written sections (STACK, ARCH, DECISIONS, DB, API, TASKS, CONVENTIONS, GOTCHAS)
are never touched. Only the marked blocks are replaced:

    <!-- AUTO:STATUS START --> ... <!-- AUTO:STATUS END -->
    <!-- AUTO:ROUTES START --> ... <!-- AUTO:ROUTES END -->
    <!-- AUTO:RECENT START --> ... <!-- AUTO:RECENT END -->

Usage
    python3 scripts/update_project_state.py             # rewrite the blocks
    python3 scripts/update_project_state.py --quiet     # same, used by the git hook
    python3 scripts/update_project_state.py --amending  # HEAD is about to be amended:
                                                        # write "HEAD" instead of a sha
                                                        # that the amend would invalidate
    python3 scripts/update_project_state.py --check     # exit 1 if stale (CI guard)

Stdlib only. Safe to run anywhere inside the repo.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

STATE_PATH = Path("docs/PROJECT_STATE.md")
RECENT_COMMITS = 8
MAX_ROUTES = 90

AREA_MAP = [
    ("backend/app/api", "api"),
    ("backend/app/services/price_source", "price"),
    ("backend/app/services", "services"),
    ("backend/app/workers", "workers"),
    ("backend/app/bot", "bot"),
    ("backend/app/db", "models"),
    ("backend/app/schemas", "schemas"),
    ("backend/app/core", "core"),
    ("backend/alembic", "migration"),
    ("backend/tests", "tests"),
    ("frontend/src/views", "views"),
    ("frontend/src/components", "components"),
    ("frontend/src/stores", "stores"),
    ("frontend/src", "fe"),
    ("docs", "docs"),
    (".github", "ci"),
    ("scripts", "scripts"),
    ("docker-compose", "infra"),
]


def git(*args: str, default: str = "") -> str:
    try:
        return subprocess.run(
            ["git", *args], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return default


def repo_root() -> Path:
    top = git("rev-parse", "--show-toplevel")
    return Path(top) if top else Path.cwd()


def area_of(path: str) -> str | None:
    for prefix, name in AREA_MAP:
        if path.startswith(prefix):
            return name
    return None


def migration_head(root: Path) -> str:
    versions = root / "backend" / "alembic" / "versions"
    if not versions.is_dir():
        return "-"
    revisions: dict[str, str | None] = {}
    for f in versions.glob("*.py"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        rev = re.search(r"^revision(?::\s*str)?\s*=\s*[\"']([^\"']+)", text, re.M)
        down = re.search(r"^down_revision(?::[^=]*)?\s*=\s*[\"']([^\"']+)", text, re.M)
        if rev:
            revisions[rev.group(1)] = down.group(1) if down else None
    if not revisions:
        return "-"
    parents = {d for d in revisions.values() if d}
    heads = sorted(r for r in revisions if r not in parents)
    return ",".join(heads) if heads else "-"


def count_files(root: Path, rel: str, pattern: str) -> int:
    base = root / rel
    return sum(1 for _ in base.rglob(pattern)) if base.is_dir() else 0


def status_block(root: Path, amending: bool = False) -> str:
    branch = git("rev-parse", "--abbrev-ref", "HEAD", default="-")
    commit = "HEAD" if amending else git("rev-parse", "--short", "HEAD", default="-")
    dirty = "yes" if git("status", "--porcelain") else "no"
    return (
        f"gen={dt.date.today().isoformat()} | branch={branch} | commit={commit} | "
        f"dirty={dirty} | migration_head={migration_head(root)} | "
        f"py_files={count_files(root, 'backend/app', '*.py')} | "
        f"vue_files={count_files(root, 'frontend/src', '*.vue')} | "
        f"tests={count_files(root, 'backend/tests', 'test_*.py')}"
    )


def routes_block(root: Path) -> str:
    api_dir = root / "backend" / "app" / "api"
    if not api_dir.is_dir():
        return "none yet"
    decorator = re.compile(
        r"@router\.(get|post|put|patch|delete)\(\s*[\"']([^\"']*)[\"']", re.I
    )
    prefix_re = re.compile(r"APIRouter\([^)]*prefix\s*=\s*[\"']([^\"']*)[\"']", re.S)
    lines: list[str] = []
    for f in sorted(api_dir.rglob("*.py")):
        text = f.read_text(encoding="utf-8", errors="ignore")
        prefix_match = prefix_re.search(text)
        prefix = prefix_match.group(1) if prefix_match else ""
        for method, path in decorator.findall(text):
            full = (prefix + path) or "/"
            lines.append(f"{method.upper():6} /api/v1{full}")
    if not lines:
        return "none yet"
    lines = sorted(set(lines))
    if len(lines) > MAX_ROUTES:
        extra = len(lines) - MAX_ROUTES
        lines = lines[:MAX_ROUTES] + [f"... (+{extra} more, see /docs)"]
    return "\n".join(lines)


def recent_block(amending: bool = False) -> str:
    log = git("log", f"-{RECENT_COMMITS}", "--no-merges", "--date=short",
              "--pretty=%h\t%ad\t%s")
    if not log:
        return "none yet"
    out: list[str] = []
    for index, line in enumerate(log.splitlines()):
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        sha, date, subject = parts[0], parts[1], parts[2]
        files = git("show", "--name-only", "--pretty=format:", sha).splitlines()
        areas = sorted({a for f in files if (a := area_of(f.strip()))})
        tag = f" [{','.join(areas)}]" if areas else ""
        # the tip commit is rewritten by the hook's amend, so its sha is not final yet
        label = "HEAD   " if amending and index == 0 else sha
        out.append(f"{label} {date} {subject}{tag}")
    return "\n".join(out) or "none yet"


def replace_block(text: str, name: str, body: str) -> str:
    pattern = re.compile(
        rf"(<!-- AUTO:{name} START -->\n).*?(\n<!-- AUTO:{name} END -->)", re.S
    )
    if not pattern.search(text):
        print(f"warning: AUTO:{name} block missing from {STATE_PATH}", file=sys.stderr)
        return text
    return pattern.sub(lambda m: m.group(1) + body + m.group(2), text)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit 1 if the file is stale")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument(
        "--amending",
        action="store_true",
        help="the tip commit will be amended: label it HEAD instead of a soon-dead sha",
    )
    args = ap.parse_args()

    root = repo_root()
    state = root / STATE_PATH
    if not state.is_file():
        print(f"error: {STATE_PATH} not found under {root}", file=sys.stderr)
        return 1

    original = state.read_text(encoding="utf-8")
    updated = original
    for name, body in (
        ("STATUS", status_block(root, args.amending)),
        ("ROUTES", routes_block(root)),
        ("RECENT", recent_block(args.amending)),
    ):
        updated = replace_block(updated, name, body)

    # Staleness is judged on content, not on volatile identifiers: the gen date moves
    # on every rerun, and the tip sha is unknowable while the post-commit hook is still
    # about to amend it (it writes the literal "HEAD" there instead).
    def normalize(text: str) -> str:
        text = re.sub(r"gen=\d{4}-\d{2}-\d{2}", "gen=", text)
        text = re.sub(r"commit=(?:HEAD|[0-9a-f]{7,40})", "commit=", text)
        return re.sub(
            r"^(?:HEAD\s*|[0-9a-f]{7,12}) (?=\d{4}-\d{2}-\d{2} )", "", text, flags=re.M
        )

    unchanged = normalize(updated) == normalize(original)

    if args.check:
        if unchanged:
            return 0
        print(f"{STATE_PATH} is stale: run scripts/update_project_state.py", file=sys.stderr)
        return 1

    if unchanged:
        if not args.quiet:
            print(f"{STATE_PATH}: already up to date")
        return 0

    state.write_text(updated, encoding="utf-8")
    if not args.quiet:
        print(f"{STATE_PATH}: AUTO blocks updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
