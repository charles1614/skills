#!/usr/bin/env python3
"""deepwiki-cli — thin API client for a deployed DeepWiki server.

All commands go through the server's HTTP API; this tool NEVER touches the
database or R2 directly. That matters: a wiki exists on the site only when
the app writes its Postgres records (Wiki -> WikiFile -> WikiVersion); R2
only stores content blobs. The API is the single write path that keeps both
consistent (permissions, slugs, versioning, checksums, image rewriting), so
schema or storage-backend changes never break this client.

Commands:
  publish <export-dir>     upload a wiki export (multipart POST /api/wiki/upload)
                           [--dry-run]
  list                     list wikis visible to the account (GET /api/wiki/list)
  get <slug> [--out DIR]   download a wiki's markdown files [--force]
  delete <slug> --yes      delete a wiki (DELETE /api/wiki/bulk-delete)
  check                    verify authentication and exit

Configuration (env vars, overridable per-command with flags):
  DEEPWIKI_URL       server base URL (default http://localhost:3000)
  DEEPWIKI_EMAIL     account email     (required for publish/delete/check)
  DEEPWIKI_PASSWORD  account password  (prefer the env var over --password)

Auth flow per invocation: GET /api/auth/csrf -> POST
/api/auth/callback/credentials -> GET /api/auth/session. Read commands
(list/get) work anonymously against public wikis when no credentials are set.

Requires: curl (cookie/multipart handling); Python stdlib only.
Exit codes: 0 success; 1 validation/auth/API failure.
"""

import argparse
import json
import mimetypes
import os
import subprocess
import sys
import tempfile
import urllib.parse
from pathlib import Path

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp"}
# Mirror the web uploader's client-side limits so a publish that would be
# rejected in the UI fails fast here too.
MAX_FILES = 50
MAX_TOTAL_BYTES = 10 * 1024 * 1024
MAX_IMAGE_BYTES = 5 * 1024 * 1024


def fail(msg: str):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def run_curl(args, expect_json=False):
    cmd = ["curl", "-sS", "--max-time", "300"] + args
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        fail(f"curl failed ({proc.returncode}): {proc.stderr.strip()}")
    if expect_json:
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError:
            fail(f"expected JSON, got: {proc.stdout[:300]!r}")
    return proc.stdout


# ---------------------------------------------------------------- auth

def login(base_url: str, email: str, password: str, jar: str):
    csrf = run_curl(["-c", jar, f"{base_url}/api/auth/csrf"], expect_json=True)
    token = csrf.get("csrfToken")
    if not token:
        fail("no csrfToken in /api/auth/csrf response — is this a DeepWiki instance?")

    run_curl([
        "-b", jar, "-c", jar, "-X", "POST",
        "--data-urlencode", f"csrfToken={token}",
        "--data-urlencode", f"email={email}",
        "--data-urlencode", f"password={password}",
        f"{base_url}/api/auth/callback/credentials",
    ])

    session = run_curl(["-b", jar, f"{base_url}/api/auth/session"], expect_json=True)
    user = (session or {}).get("user")
    if not user:
        fail("login failed — check DEEPWIKI_EMAIL / DEEPWIKI_PASSWORD")
    return user


def maybe_login(args, jar: str, required: bool):
    """Authenticate when credentials are available; fail only if required."""
    if args.email and args.password:
        user = login(args.base_url, args.email, args.password, jar)
        print(f"Authenticated as {user.get('email', '?')} against {args.base_url}")
        return user
    if required:
        fail("credentials missing — set DEEPWIKI_EMAIL and DEEPWIKI_PASSWORD (or --email/--password)")
    print(f"No credentials set — anonymous access to {args.base_url} (public wikis only)")
    return None


# ---------------------------------------------------------------- publish

def collect_files(export_dir: Path):
    """Markdown at the export root; images anywhere below it."""
    md_files = sorted(p for p in export_dir.glob("*.md"))
    images = sorted(
        p for p in export_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    )
    if not any(p.name == "index.md" for p in md_files):
        fail(f"{export_dir}/index.md not found — the upload API requires it")
    # Subdirectory .md files would be flattened server-side ('adr/x.md' ->
    # 'adr-x.md'), breaking the export's internal links — refuse instead.
    stray_md = [p for p in export_dir.rglob("*.md") if p.parent != export_dir]
    if stray_md:
        names = ", ".join(str(p.relative_to(export_dir)) for p in stray_md[:5])
        fail(
            f"markdown files in subdirectories would be renamed on upload and "
            f"break internal links: {names}. Keep all .md files flat at the "
            f"export root (numbered prefixes express hierarchy)."
        )
    return md_files, images


def validate_sizes(md_files, images):
    total = sum(p.stat().st_size for p in md_files + images)
    problems = []
    if len(md_files) + len(images) > MAX_FILES:
        problems.append(f"{len(md_files) + len(images)} files exceeds the {MAX_FILES}-file upload limit")
    if total > MAX_TOTAL_BYTES:
        problems.append(f"total {total / 1e6:.1f} MB exceeds the {MAX_TOTAL_BYTES / 1e6:.0f} MB upload limit")
    for img in images:
        if img.stat().st_size > MAX_IMAGE_BYTES:
            problems.append(f"{img.name} is {img.stat().st_size / 1e6:.1f} MB (image limit {MAX_IMAGE_BYTES / 1e6:.0f} MB)")
    if problems:
        fail("; ".join(problems))
    return total


def cmd_publish(args, jar: str):
    export_dir = args.export_dir.resolve()
    if not export_dir.is_dir():
        fail(f"{export_dir} is not a directory")

    md_files, images = collect_files(export_dir)
    total = validate_sizes(md_files, images)
    print(f"Export: {len(md_files)} markdown + {len(images)} image file(s), {total / 1e6:.2f} MB total")

    if args.dry_run:
        for p in md_files + images:
            print(f"  would upload: {p.relative_to(export_dir)}")
        return

    maybe_login(args, jar, required=True)

    form_args = []
    for p in md_files:
        form_args += ["-F", f"files=@{p};type=text/markdown"]
    for p in images:
        mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        # curl sends the basename as the part filename, which is what the
        # API's image-path resolution matches against.
        form_args += ["-F", f"files=@{p};type={mime}"]

    result = run_curl(
        ["-b", jar, "-X", "POST"] + form_args + [f"{args.base_url}/api/wiki/upload"],
        expect_json=True,
    )
    if not result.get("success"):
        fail(f"upload rejected: {result.get('error', result)}")

    wiki = result.get("wiki", {})
    statuses = {}
    errors = []
    for r in result.get("results", []):
        statuses[r["status"]] = statuses.get(r["status"], 0) + 1
        if r["status"] == "error":
            errors.append(f"  {r['filename']}: {r.get('error', 'unknown error')}")

    summary = ", ".join(f"{n} {s}" for s, n in sorted(statuses.items()))
    print(f"Published '{wiki.get('title')}' -> {args.base_url}/wiki/{wiki.get('slug')}  ({summary})")
    if errors:
        print("Per-file errors:", file=sys.stderr)
        print("\n".join(errors), file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------- list

def cmd_list(args, jar: str):
    maybe_login(args, jar, required=False)
    result = run_curl(["-b", jar, f"{args.base_url}/api/wiki/list"], expect_json=True)
    if not result.get("success"):
        fail(f"list failed: {result.get('error', result)}")
    wikis = result.get("wikis", [])
    if not wikis:
        print("No wikis found.")
        return
    print(f"{'SLUG':<32} {'FILES':>5}  {'VISIBILITY':<10} TITLE")
    for w in wikis:
        files = (w.get("_count") or {}).get("files", "?")
        vis = "public" if w.get("isPublic") else "private"
        print(f"{w.get('slug', '?'):<32} {files:>5}  {vis:<10} {w.get('title', '')}")


# ---------------------------------------------------------------- get

def fetch_wiki(args, jar: str, slug: str):
    quoted = urllib.parse.quote(slug, safe="")
    result = run_curl(["-b", jar, f"{args.base_url}/api/wiki/slug/{quoted}"], expect_json=True)
    if not result.get("success"):
        fail(f"wiki '{slug}' not found or not accessible: {result.get('error', result)}")
    return result["wiki"]


def cmd_get(args, jar: str):
    maybe_login(args, jar, required=False)
    wiki = fetch_wiki(args, jar, args.slug)
    files = wiki.get("files", [])
    md_files = [f for f in files if f.get("filename", "").endswith(".md")]
    skipped = len(files) - len(md_files)

    out_dir = (args.out or Path(args.slug)).resolve()
    if out_dir.exists() and any(out_dir.iterdir()) and not args.force:
        fail(f"{out_dir} is not empty — pass --force to write into it")
    out_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    for f in md_files:
        filename = f["filename"]
        quoted = f"{urllib.parse.quote(args.slug, safe='')}/file/{urllib.parse.quote(filename, safe='')}"
        result = run_curl(["-b", jar, f"{args.base_url}/api/wiki/{quoted}"], expect_json=True)
        if not result.get("success"):
            print(f"  WARN: could not fetch {filename}: {result.get('error')}", file=sys.stderr)
            continue
        (out_dir / filename).write_text(result.get("content", ""), encoding="utf-8")
        written += 1
        print(f"  wrote {filename}")

    note = f" ({skipped} non-markdown file(s) skipped — images are referenced by URL inside the markdown)" if skipped else ""
    print(f"Downloaded {written}/{len(md_files)} markdown file(s) from '{wiki.get('title')}' to {out_dir}{note}")
    if written < len(md_files):
        sys.exit(1)


# ---------------------------------------------------------------- delete

def cmd_delete(args, jar: str):
    maybe_login(args, jar, required=True)
    wiki = fetch_wiki(args, jar, args.slug)
    n_files = len(wiki.get("files", []))
    print(f"Target: '{wiki.get('title')}' (slug {wiki.get('slug')}, {n_files} file(s), "
          f"{'public' if wiki.get('isPublic') else 'private'})")

    if not args.yes:
        fail("refusing to delete without --yes (deletion removes the wiki, all files, versions, and storage objects)")

    result = run_curl([
        "-b", jar, "-X", "DELETE",
        "-H", "Content-Type: application/json",
        "-d", json.dumps({"wikiIds": [wiki["id"]]}),
        f"{args.base_url}/api/wiki/bulk-delete",
    ], expect_json=True)
    if not result.get("success"):
        fail(f"delete failed: {result.get('error', result)}")
    print(result.get("message", f"Deleted {result.get('deletedCount', '?')} wiki(s)"))


# ---------------------------------------------------------------- check

def cmd_check(args, jar: str):
    maybe_login(args, jar, required=True)
    print("Auth check OK")


# ---------------------------------------------------------------- main

def add_common(parser):
    parser.add_argument("--url", dest="base_url",
                        default=os.environ.get("DEEPWIKI_URL", "http://localhost:3000"),
                        help="DeepWiki base URL (default: $DEEPWIKI_URL or http://localhost:3000)")
    parser.add_argument("--email", default=os.environ.get("DEEPWIKI_EMAIL"))
    parser.add_argument("--password", default=os.environ.get("DEEPWIKI_PASSWORD"))


def main():
    ap = argparse.ArgumentParser(
        prog="deepwiki_cli.py", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("publish", help="upload a wiki export directory")
    p.add_argument("export_dir", type=Path)
    p.add_argument("--dry-run", action="store_true", help="list files, no network")
    add_common(p)
    p.set_defaults(func=cmd_publish)

    p = sub.add_parser("list", help="list wikis visible to the account")
    add_common(p)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("get", help="download a wiki's markdown files")
    p.add_argument("slug")
    p.add_argument("--out", type=Path, help="output directory (default: ./<slug>/)")
    p.add_argument("--force", action="store_true", help="write into a non-empty directory")
    add_common(p)
    p.set_defaults(func=cmd_get)

    p = sub.add_parser("delete", help="delete a wiki (requires --yes)")
    p.add_argument("slug")
    p.add_argument("--yes", action="store_true", help="confirm deletion")
    add_common(p)
    p.set_defaults(func=cmd_delete)

    p = sub.add_parser("check", help="verify authentication and exit")
    add_common(p)
    p.set_defaults(func=cmd_check)

    args = ap.parse_args()
    args.base_url = args.base_url.rstrip("/")

    with tempfile.TemporaryDirectory() as tmp:
        jar = str(Path(tmp) / "cookies.txt")
        args.func(args, jar)


if __name__ == "__main__":
    main()
