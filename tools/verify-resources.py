#!/usr/bin/env python3
"""Verify that URLs documented in resources/ markdown files are still reachable.

Scans all .md files under resources/, extracts URLs, and checks each one with
HTTP HEAD (falling back to GET).  Reports OK / redirect / broken status and
optionally updates a <!-- last-verified: YYYY-MM-DD --> comment in each file.
"""

import argparse
import datetime
import json
import re
import ssl
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
RESOURCES_DIR = REPO_ROOT / "resources"

USER_AGENT = "gaia-minds-verify-resources/1.0 (+https://github.com/gaia-minds)"

# Regex patterns for URL extraction
# Matches [text](url) markdown links
MD_LINK_RE = re.compile(r"\[(?:[^\]]*)\]\((https?://[^\s\)]+)\)")
# Matches bare URLs (not already inside parentheses from the pattern above)
BARE_URL_RE = re.compile(r"(?<!\()(https?://[^\s\)\]\"'>`,]+)")
# Matches the last-verified HTML comment
VERIFIED_COMMENT_RE = re.compile(
    r"<!--\s*last-verified:\s*\d{4}-\d{2}-\d{2}\s*-->"
)

# URLs that are clearly example/template placeholders
SKIP_PATTERNS = [
    re.compile(r"^https?://\.\.\.$"),
    re.compile(r"^https?://example\.com"),
    re.compile(r"^https?://$"),          # bare scheme with no host
    re.compile(r"^https?://\s*$"),       # scheme with only whitespace
]

# ---------------------------------------------------------------------------
# Terminal colours (only when stdout is a TTY)
# ---------------------------------------------------------------------------

_IS_TTY = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _colour(code: str, text: str) -> str:
    if _IS_TTY:
        return f"\033[{code}m{text}\033[0m"
    return text


def green(text: str) -> str:
    return _colour("32", text)


def yellow(text: str) -> str:
    return _colour("33", text)


def red(text: str) -> str:
    return _colour("31", text)


def bold(text: str) -> str:
    return _colour("1", text)


def dim(text: str) -> str:
    return _colour("2", text)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class URLResult:
    url: str
    status_code: Optional[int] = None
    redirect_url: Optional[str] = None
    error: Optional[str] = None
    category: str = "unknown"  # "ok", "redirect", "broken"


@dataclass
class FileReport:
    path: Path
    relative_path: str = ""
    urls: List[str] = field(default_factory=list)
    results: List[URLResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# URL extraction
# ---------------------------------------------------------------------------


def extract_urls(text: str) -> List[str]:
    """Extract all unique HTTP(S) URLs from markdown text."""
    urls: Dict[str, None] = {}  # ordered set via dict

    for match in MD_LINK_RE.finditer(text):
        url = match.group(1).rstrip(".")
        urls[url] = None

    for match in BARE_URL_RE.finditer(text):
        url = match.group(1).rstrip(".")
        urls[url] = None

    # Filter out placeholder / example URLs
    filtered: List[str] = []
    for url in urls:
        if any(pat.match(url) for pat in SKIP_PATTERNS):
            continue
        filtered.append(url)

    return filtered


# ---------------------------------------------------------------------------
# URL checking
# ---------------------------------------------------------------------------


def _create_ssl_context() -> ssl.SSLContext:
    """Create a permissive SSL context (some docs sites have odd certs)."""
    ctx = ssl.create_default_context()
    # We are only checking reachability, not transacting sensitive data,
    # so we tolerate certificate issues.
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def check_url(url: str, timeout: int = 10) -> URLResult:
    """Check a single URL.  Try HEAD first, fall back to GET."""
    ssl_ctx = _create_ssl_context()
    result = URLResult(url=url)

    for method in ("HEAD", "GET"):
        req = urllib.request.Request(
            url,
            method=method,
            headers={"User-Agent": USER_AGENT},
        )
        try:
            # We use a custom opener that does NOT follow redirects so we
            # can report them explicitly.
            class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, headers, newurl):
                    raise urllib.error.HTTPError(
                        newurl, code, msg, headers, fp
                    )

            opener = urllib.request.build_opener(
                NoRedirectHandler,
                urllib.request.HTTPSHandler(context=ssl_ctx),
            )
            resp = opener.open(req, timeout=timeout)
            result.status_code = resp.status
            result.category = "ok"
            resp.close()
            return result

        except urllib.error.HTTPError as exc:
            code = exc.code
            # 3xx redirects
            if 300 <= code < 400:
                result.status_code = code
                location = exc.headers.get("Location", "") if exc.headers else ""
                result.redirect_url = location
                result.category = "redirect"
                return result

            # 405 Method Not Allowed on HEAD -- retry with GET
            if code == 405 and method == "HEAD":
                continue

            # 405 on GET means the server is up but only accepts other methods
            # (e.g. POST-only API endpoints).  Treat as reachable.
            if code == 405:
                result.status_code = code
                result.category = "ok"
                return result

            # Other client/server errors
            result.status_code = code
            result.error = str(exc.reason) if hasattr(exc, "reason") else str(exc)
            result.category = "broken"
            return result

        except urllib.error.URLError as exc:
            if method == "HEAD":
                # Some servers reject HEAD entirely at the socket level
                continue
            result.error = str(exc.reason) if hasattr(exc, "reason") else str(exc)
            result.category = "broken"
            return result

        except Exception as exc:  # noqa: BLE001
            if method == "HEAD":
                continue
            result.error = str(exc)
            result.category = "broken"
            return result

    # Should not normally reach here, but just in case
    result.category = "broken"
    result.error = "All request methods failed"
    return result


# ---------------------------------------------------------------------------
# File scanning
# ---------------------------------------------------------------------------


def scan_files(resources_dir: Path) -> List[FileReport]:
    """Find all .md files and extract their URLs."""
    reports: List[FileReport] = []
    md_files = sorted(resources_dir.rglob("*.md"))

    for md_path in md_files:
        try:
            text = md_path.read_text(encoding="utf-8")
        except (OSError, PermissionError) as exc:
            print(red(f"  Error reading {md_path}: {exc}"), file=sys.stderr)
            continue

        urls = extract_urls(text)
        rel = str(md_path.relative_to(REPO_ROOT))
        report = FileReport(path=md_path, relative_path=rel, urls=urls)
        reports.append(report)

    return reports


# ---------------------------------------------------------------------------
# Parallel checking
# ---------------------------------------------------------------------------


def check_all_urls(
    reports: List[FileReport],
    workers: int = 8,
    timeout: int = 10,
) -> Tuple[List[FileReport], Dict[str, URLResult]]:
    """Check every unique URL across all reports in parallel.

    Returns the reports (with results populated) and a global map of
    url -> URLResult for deduplication / JSON output.
    """
    # Collect unique URLs and map them back to reports
    url_to_reports: Dict[str, List[FileReport]] = {}
    for report in reports:
        for url in report.urls:
            url_to_reports.setdefault(url, []).append(report)

    global_results: Dict[str, URLResult] = {}

    if not url_to_reports:
        return reports, global_results

    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_url = {
            pool.submit(check_url, url, timeout): url
            for url in url_to_reports
        }
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001
                result = URLResult(url=url, error=str(exc), category="broken")
            global_results[url] = result

    # Populate per-file results
    for report in reports:
        report.results = [global_results[url] for url in report.urls]

    return reports, global_results


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _status_icon(result: URLResult) -> str:
    if result.category == "ok":
        return green("[OK]")
    if result.category == "redirect":
        return yellow("[REDIRECT]")
    return red("[BROKEN]")


def _status_detail(result: URLResult) -> str:
    parts: List[str] = []
    if result.status_code is not None:
        parts.append(f"HTTP {result.status_code}")
    if result.redirect_url:
        parts.append(f"-> {result.redirect_url}")
    if result.error:
        parts.append(result.error)
    return " ".join(parts)


def print_human_report(
    reports: List[FileReport],
    global_results: Dict[str, URLResult],
) -> None:
    """Pretty-print results to stdout."""
    for report in reports:
        if not report.urls:
            continue
        print()
        print(bold(f"  {report.relative_path}"))
        for result in report.results:
            icon = _status_icon(result)
            detail = _status_detail(result)
            detail_str = f"  {dim(detail)}" if detail else ""
            print(f"    {icon} {result.url}{detail_str}")

    # Summary
    total = len(global_results)
    ok = sum(1 for r in global_results.values() if r.category == "ok")
    redirects = sum(1 for r in global_results.values() if r.category == "redirect")
    broken = sum(1 for r in global_results.values() if r.category == "broken")
    files_with_urls = sum(1 for r in reports if r.urls)
    total_files = len(reports)

    print()
    print(bold("  Summary"))
    print(f"    Files scanned:    {total_files}")
    print(f"    Files with URLs:  {files_with_urls}")
    print(f"    Unique URLs:      {total}")
    print(f"    {green('OK')}:              {ok}")
    print(f"    {yellow('Redirects')}:       {redirects}")
    print(f"    {red('Broken')}:          {broken}")
    print()


def build_json_report(
    reports: List[FileReport],
    global_results: Dict[str, URLResult],
) -> dict:
    """Build a JSON-serialisable dict of the full report."""
    files = []
    for report in reports:
        file_entry = {
            "file": report.relative_path,
            "urls": [],
        }
        for result in report.results:
            entry: dict = {
                "url": result.url,
                "category": result.category,
            }
            if result.status_code is not None:
                entry["status_code"] = result.status_code
            if result.redirect_url:
                entry["redirect_url"] = result.redirect_url
            if result.error:
                entry["error"] = result.error
            file_entry["urls"].append(entry)
        files.append(file_entry)

    total = len(global_results)
    ok = sum(1 for r in global_results.values() if r.category == "ok")
    redirects = sum(1 for r in global_results.values() if r.category == "redirect")
    broken = sum(1 for r in global_results.values() if r.category == "broken")

    return {
        "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "summary": {
            "files_scanned": len(reports),
            "files_with_urls": sum(1 for r in reports if r.urls),
            "unique_urls": total,
            "ok": ok,
            "redirects": redirects,
            "broken": broken,
        },
        "files": files,
    }


# ---------------------------------------------------------------------------
# --update: stamp files with last-verified date
# ---------------------------------------------------------------------------


def update_verified_dates(reports: List[FileReport]) -> None:
    """Insert or update <!-- last-verified: YYYY-MM-DD --> in each file."""
    today = datetime.date.today().isoformat()
    stamp = f"<!-- last-verified: {today} -->"

    for report in reports:
        if not report.urls:
            continue  # nothing to verify in this file

        try:
            text = report.path.read_text(encoding="utf-8")
        except (OSError, PermissionError) as exc:
            print(
                red(f"  Cannot read {report.relative_path} for update: {exc}"),
                file=sys.stderr,
            )
            continue

        if VERIFIED_COMMENT_RE.search(text):
            new_text = VERIFIED_COMMENT_RE.sub(stamp, text)
        else:
            # Append the comment at the end of the file
            new_text = text.rstrip("\n") + "\n\n" + stamp + "\n"

        if new_text != text:
            try:
                report.path.write_text(new_text, encoding="utf-8")
                print(dim(f"  Updated {report.relative_path}"))
            except (OSError, PermissionError) as exc:
                print(
                    red(f"  Cannot write {report.relative_path}: {exc}"),
                    file=sys.stderr,
                )


# ---------------------------------------------------------------------------
# --dry-run
# ---------------------------------------------------------------------------


def print_dry_run(reports: List[FileReport]) -> None:
    """Show what would be checked without making any requests."""
    total_urls = 0
    unique_urls: Dict[str, None] = {}

    for report in reports:
        if not report.urls:
            continue
        print()
        print(bold(f"  {report.relative_path}"))
        for url in report.urls:
            print(f"    {dim('would check')} {url}")
            unique_urls[url] = None
        total_urls += len(report.urls)

    print()
    print(bold("  Dry-run summary"))
    print(f"    Files to scan:    {len(reports)}")
    print(f"    Files with URLs:  {sum(1 for r in reports if r.urls)}")
    print(f"    Total URL refs:   {total_urls}")
    print(f"    Unique URLs:      {len(unique_urls)}")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify URLs in resources/ markdown files are still reachable."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output results as JSON instead of human-readable text.",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        default=False,
        help=(
            "Update (or add) a <!-- last-verified: YYYY-MM-DD --> comment "
            "at the bottom of each checked file."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Show what would be checked without making HTTP requests.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        metavar="N",
        help="Number of parallel workers (default: 8).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        metavar="N",
        help="HTTP request timeout in seconds (default: 10).",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    if not RESOURCES_DIR.is_dir():
        print(
            red(f"  Resources directory not found: {RESOURCES_DIR}"),
            file=sys.stderr,
        )
        return 1

    # Scan files
    reports = scan_files(RESOURCES_DIR)

    if not reports:
        print("  No markdown files found under resources/.", file=sys.stderr)
        return 0

    # Dry-run mode: just list what we would do
    if args.dry_run:
        print_dry_run(reports)
        return 0

    # Check URLs
    if not args.json:
        unique_count = len({u for r in reports for u in r.urls})
        print()
        print(
            bold("  Verifying resource URLs")
            + dim(f"  ({unique_count} unique URLs, {args.workers} workers)")
        )

    reports, global_results = check_all_urls(
        reports,
        workers=args.workers,
        timeout=args.timeout,
    )

    # Output
    if args.json:
        data = build_json_report(reports, global_results)
        print(json.dumps(data, indent=2))
    else:
        print_human_report(reports, global_results)

    # Optionally update files
    if args.update:
        if not args.json:
            print(bold("  Updating last-verified dates..."))
        update_verified_dates(reports)

    # Exit code: 1 if any URL is broken, 0 otherwise
    has_broken = any(r.category == "broken" for r in global_results.values())
    return 1 if has_broken else 0


if __name__ == "__main__":
    raise SystemExit(main())
