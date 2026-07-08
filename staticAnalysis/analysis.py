import argparse
import csv
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Optional


def run_pylint_json(py_file: Path) -> list:
    """Run pylint on *py_file* and return the parsed JSON issue list."""
    result = subprocess.run(
        ["pylint", str(py_file), "--output-format=json", "--score=no"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if not (result.stdout or "").strip():
        return []
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


def run_pylint_score(py_file: Path) -> str:
    """Return the pylint score string, e.g. '7.50/10', or 'N/A'."""
    result = subprocess.run(
        ["pylint", str(py_file), "--output-format=text"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    stdout = result.stdout or ""
    match = re.search(r"rated at ([\d.]+/10)", stdout)
    return match.group(1) if match else "N/A"


def summarise_issues(issues: list) -> dict:
    """Return counts and unique symbol lists grouped by pylint message type."""
    TYPES = ("error", "warning", "convention", "refactor", "fatal")
    counts: Counter = Counter()
    symbol_counts: dict = {t: Counter() for t in TYPES}

    for issue in issues:
        t = issue.get("type", "")
        counts[t] += 1
        if t in symbol_counts:
            sym = issue.get("symbol") or issue.get("message-id", "")
            symbol_counts[t][sym] += 1

    def fmt(counter: Counter) -> str:
        """Format as 'symbol:count|symbol:count', sorted by count desc."""
        return "|".join(
            f"{sym}:{n}" for sym, n in counter.most_common()
        )

    return {
        "total_issues":     len(issues),
        "error_count":      counts.get("error", 0),
        "warning_count":    counts.get("warning", 0),
        "convention_count": counts.get("convention", 0),
        "refactor_count":   counts.get("refactor", 0),
        "fatal_count":      counts.get("fatal", 0),
        "error_types":      fmt(symbol_counts["error"]),
        "warning_types":    fmt(symbol_counts["warning"]),
        "convention_types": fmt(symbol_counts["convention"]),
        "refactor_types":   fmt(symbol_counts["refactor"]),
        "fatal_types":      fmt(symbol_counts["fatal"]),
    }


def process_json_file(json_path: Path) -> Optional[dict]:
    """
    Extract final_code from *json_path*, run pylint, and return a stats row.
    Returns None if the file should be skipped.
    """
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[SKIP] {json_path.name}: cannot read JSON – {exc}")
        return None

    # final_code ma1y be at the top level or nested under "result"
    code = data.get("final_code") or data.get("result", {}).get("final_code", "")
    if not isinstance(code, str) or not code.strip():
        print(f"[SKIP] {json_path.name}: 'final_code' is missing or empty")
        return None

    task_id = data.get("task_id") or data.get("result", {}).get("task_id", json_path.stem)

    # Write code to a temp .py file so pylint can analyse it
    with tempfile.NamedTemporaryFile(
        suffix=".py", mode="w", encoding="utf-8", delete=False
    ) as tmp:
        tmp.write(code)
        tmp_path = Path(tmp.name)

    loc = sum(1 for line in code.splitlines() if line.strip())

    try:
        issues = run_pylint_json(tmp_path)
        score  = run_pylint_score(tmp_path)
        stats  = summarise_issues(issues)
    finally:
        tmp_path.unlink(missing_ok=True)

    print(
        f"[OK] {task_id:<20s} | score={score:<8s} | LOC={loc} | "
        f"E={stats['error_count']} W={stats['warning_count']} "
        f"C={stats['convention_count']} R={stats['refactor_count']}"
    )
    return {"task_id": task_id, "pylint_score": score, "loc": loc, **stats}


CSV_FIELDS = [
    "task_id",
    "pylint_score",
    "loc",
    "total_issues",
    "error_count",
    "warning_count",
    "convention_count",
    "refactor_count",
    "fatal_count",
    "error_types",
    "warning_types",
    "convention_types",
    "refactor_types",
    "fatal_types",
]


def write_csv(rows: list, output_path: Path) -> None:
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run pylint on final_code fields in task JSON files and write a CSV summary."
    )
    parser.add_argument("input_dir", help="Folder containing task_*.json files")
    parser.add_argument(
        "output_csv",
        nargs="?",
        help="Output CSV path (default: <input_dir>/pylint_summary.csv)",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.is_dir():
        sys.exit(f"Error: '{input_dir}' is not a directory.")

    output_csv = (
        Path(args.output_csv) if args.output_csv else input_dir / "pylint_summary.csv"
    )

    json_files = sorted(input_dir.glob("*.json"))
    if not json_files:
        sys.exit(f"No JSON files found in '{input_dir}'.")

    # ---- resume: collect already-processed task ids ----
    done: set = set()
    if output_csv.exists():
        with output_csv.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if "task_id" in row:
                    done.add(row["task_id"])
        print(f"Resuming: {len(done)} task(s) already in '{output_csv}', skipping them.\n")

    json_files = [jf for jf in json_files if jf.stem not in done]

    print(f"Found {len(json_files)} JSON file(s) remaining in '{input_dir}'\n")

    total = len(json_files)
    written = 0

    # append if resuming, write-new otherwise
    mode = "a" if done else "w"
    with output_csv.open(mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if mode == "w":
            writer.writeheader()
        f.flush()

        for i, jf in enumerate(json_files, 1):
            print(f"[{i}/{total}] {jf.name}", flush=True)
            row = process_json_file(jf)
            if row is not None:
                writer.writerow(row)
                f.flush()
                written += 1

    if written == 0 and not done:
        sys.exit("No valid tasks processed – CSV is empty.")

    print(f"\nDone. {written}/{total} task(s) written to '{output_csv}'")


if __name__ == "__main__":
    main()
