"""Check the staged/public source tree against the reviewed Lite file list."""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "scripts/lite-files.txt"


def main():
    expected = set(MANIFEST.read_text(encoding="utf-8").splitlines())
    index = subprocess.check_output(["git", "ls-files", "--stage", "-z"], cwd=ROOT)
    actual = set()
    unexpected_modes = []
    for item in index.decode("utf-8").split("\0"):
        if not item:
            continue
        metadata, path = item.split("\t", 1)
        mode, _, stage = metadata.split()
        actual.add(path)
        if mode not in {"100644", "100755"} or stage != "0":
            unexpected_modes.append(path)

    for label, paths in (
        ("Unreviewed path", sorted(actual - expected)),
        ("Manifest path missing", sorted(expected - actual)),
        ("Unsupported Git index entry", sorted(unexpected_modes)),
    ):
        for path in paths:
            print(f"{label}: {path}", file=sys.stderr)
    return int(actual != expected or bool(unexpected_modes))


if __name__ == "__main__":
    sys.exit(main())
