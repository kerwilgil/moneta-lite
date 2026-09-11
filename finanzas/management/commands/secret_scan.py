"""Reproducible secret scanner (``python manage.py secret_scan``).

Scans git-tracked text files (or explicit paths) for likely credentials: cloud
keys, provider API keys, bearer tokens, passwords in URLs, private-key blocks and
hard-coded ``SECRET_KEY`` assignments.  Matches are reported by location and rule
with the value **masked** — the full secret is never printed.

Exit code 0 = clean, 1 = findings.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from django.core.management.base import BaseCommand

HIGH_CONFIDENCE_RULES = [
    ("aws-access-key-id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("openai-key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("github-token", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("slack-token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("google-api-key", re.compile(r"AIza[0-9A-Za-z_\-]{35}")),
    ("private-key-block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----")),
    ("password-in-url", re.compile(r"[a-z]+://[^\s:@/]+:[^\s:@/]{4,}@")),
]
HEURISTIC_RULES = [
    ("bearer-literal", re.compile(r"[Bb]earer\s+[A-Za-z0-9._\-]{16,}")),
    ("authorization-header-literal", re.compile(r"[\"']?[Aa]uthorization[\"']?\s*[:=]\s*[\"'][A-Za-z0-9+/=._\- ]{16,}[\"']")),
    ("hardcoded-secret-key", re.compile(r"SECRET_KEY\s*=\s*[\"'][^\"'\n]{16,}[\"']")),
    ("generic-api-key-assign", re.compile(r"(?i)(api[_\-]?key|client_secret|access_token|refresh_token)\s*[:=]\s*[\"'][A-Za-z0-9+/=_\-]{16,}[\"']")),
]
RULES = HIGH_CONFIDENCE_RULES + HEURISTIC_RULES

ALLOWLIST_SUBSTRINGS = (
    "os.getenv", "os.environ", "settings.SECRET_KEY", "getattr(settings",
    "secrets.token_urlsafe", "secrets.token_hex", "hash_token(", "example",
    "REDACTED", "your-", "changeme", "<tu-token>", "&lt;tu-token&gt;",
    "dev-only-change-me", "replace-this-with", "faker", "dummy",
    "token_urlsafe", "compare_digest",
)
BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".woff",
              ".woff2", ".ttf", ".otf", ".mo", ".pyc", ".sqlite3", ".db"}
SKIP_DIRS = {".git", "__pycache__", ".tmp", "node_modules", "staticfiles",
             ".cache", "releases", "_publish", "variants", "instances"}


def _is_test_file(path: Path) -> bool:
    return (path.name == "tests.py" or path.name.startswith("test_")
            or "tests" in path.parts or "test" in path.parts)


def _mask(text: str) -> str:
    text = text.strip()
    if len(text) <= 12:
        return text[:2] + "…"
    return f"{text[:4]}…{text[-2:]} ({len(text)} chars)"


def _tracked_files(root: Path):
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=root,
                             capture_output=True, text=True, check=True).stdout
        return [root / n for n in out.split("\0") if n]
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return [p for p in root.rglob("*")
                if p.is_file() and not (set(p.parts) & SKIP_DIRS)]


def _iter_paths(paths):
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            for child in p.rglob("*"):
                if child.is_file() and not (set(child.parts) & SKIP_DIRS):
                    yield child
        elif p.is_file():
            yield p


def scan_file(path: Path):
    if path.suffix.lower() in BINARY_EXT or (set(path.parts) & SKIP_DIRS):
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    rules = HIGH_CONFIDENCE_RULES if _is_test_file(path) else RULES
    findings = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if any(s in line for s in ALLOWLIST_SUBSTRINGS):
            continue
        for rule, rx in rules:
            m = rx.search(line)
            if m:
                findings.append((str(path), lineno, rule, _mask(m.group(0))))
    return findings


def scan_staged(root: Path):
    try:
        diff = subprocess.run(["git", "diff", "--cached", "--unified=0"],
                              cwd=root, capture_output=True, text=True,
                              check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return []
    findings, current = [], "?"
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            body = line[1:]
            if any(s in body for s in ALLOWLIST_SUBSTRINGS):
                continue
            for rule, rx in RULES:
                if rx.search(body):
                    findings.append((current, 0, f"staged:{rule}",
                                     _mask(rx.search(body).group(0))))
    return findings


class Command(BaseCommand):
    help = "Scan the repository for accidentally committed secrets."

    def add_arguments(self, parser):
        parser.add_argument("paths", nargs="*", help="explicit files/dirs")
        parser.add_argument("--staged", action="store_true")
        parser.add_argument("--root", default=".")

    def handle(self, *args, **options):
        root = Path(options["root"]).resolve()
        targets = (list(_iter_paths(options["paths"])) if options["paths"]
                   else _tracked_files(root))
        findings = []
        for f in targets:
            findings.extend(scan_file(f))
        if options["staged"]:
            findings.extend(scan_staged(root))

        if findings:
            self.stdout.write(f"SECRET SCAN: {len(findings)} hallazgo(s)\n")
            for path, lineno, rule, masked in findings:
                loc = f"{path}:{lineno}" if lineno else path
                self.stdout.write(f"  [{rule}] {loc} -> {masked}")
            raise SystemExit(1)
        self.stdout.write(f"SECRET SCAN: limpio ({len(targets)} archivos)")
