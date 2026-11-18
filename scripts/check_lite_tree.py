"""Check the staged/public source tree against the reviewed Lite file list."""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
COMMERCIAL_SIGNATURES = (
    r"execute_due_recurrings_for_user|MONETA_RECURRING_|subscription_run_now|"
    r"recurring_run_now|run_recurring\.py|salary_calculator\.js|journal_form\.js|"
    r"salaryCalculatorPanel|moneta-net-income-records|"
    r"def (ledger_create|ledger|net_income|export_recurring_csv|export_subscriptions_csv)\(|"
    r"views\.(ledger_create|ledger|net_income|export_recurring_csv|export_subscriptions_csv)|"
    r"SUBSCRIPTION_PRESETS|service_subscription_presets|img/services/"
)


def main():
    manifest = subprocess.check_output(
        ["git", "show", ":scripts/lite-files.txt"], cwd=ROOT, encoding="utf-8",
    )
    expected = set(manifest.splitlines())
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
    signatures = subprocess.run(
        ["git", "grep", "--cached", "--name-only", "-I", "-E", COMMERCIAL_SIGNATURES, "--",
         "config", "finanzas", "static", "templates",
         ":(exclude,glob)finanzas/**/migrations/**",
         ":(exclude,glob)finanzas/**/test*.py"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if signatures.returncode not in {0, 1}:
        raise SystemExit(signatures.stderr)
    for path in signatures.stdout.splitlines():
        print(f"Commercial module signature: {path}", file=sys.stderr)

    return int(actual != expected or bool(unexpected_modes) or signatures.returncode == 0)


if __name__ == "__main__":
    sys.exit(main())
