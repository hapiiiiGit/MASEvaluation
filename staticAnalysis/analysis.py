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

_SEPARATOR_RE = re.compile(
    r"^\s*#\s*[=\-]{5,}\s*(.*?)\s*[=\-]{5,}\s*$"
)

def split_multi_file_code(code: str) -> list[tuple[str, str]]:
    """
    Split *code* into (filename, content) pairs when it contains multi-file
    separator comments.  Returns [(filename, content), ...].

    If no separators are found, returns [("", code)] so the caller can treat
    single-file and multi-file outputs uniformly.

    filename may be an empty string when the separator line carries no name,
    or a descriptive label like "END OF FILES" / "Unit Tests".
    """
    lines = code.splitlines(keepends=True)
    segments: list[tuple[str, list[str]]] = []  # (filename, lines)

    current_name: str | None = None
    current_lines: list[str] = []

    for line in lines:
        m = _SEPARATOR_RE.match(line)
        if m:
            inner = m.group(1).strip()
            # inner may be e.g. "config.py", "File: utils.py", "END OF FILES", ""
            # strip common prefixes like "File: " or "file: "
            filename = re.sub(r"(?i)^file\s*:\s*", "", inner).strip()

            if current_name is not None:
                segments.append((current_name, current_lines))
            current_name = filename
            current_lines = []
        else:
            if current_name is None:
                # code before the first separator – treat as preamble
                current_name = ""
            current_lines.append(line)

    if current_name is not None and current_lines:
        segments.append((current_name, current_lines))

    if not segments:
        return [("", code)]

    # If no separator was ever hit, segments will have a single ("", ...) entry
    has_real_separator = len(segments) > 1 or (
        len(segments) == 1 and segments[0][0] != ""
    )
    if not has_real_separator:
        return [("", code)]

    return [(name, "".join(lines_)) for name, lines_ in segments]


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
        return "|".join(f"{sym}:{n}" for sym, n in counter.most_common())

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


def _is_py_segment(filename: str, content: str) -> bool:
    """Return True if this segment should be linted as Python."""
    if not content.strip():
        return False
    # Skip obvious non-Python segments by filename extension
    if filename:
        ext = Path(filename).suffix.lower()
        if ext and ext not in (".py", ""):
            return False
    # Skip section markers with no real code (e.g. "END OF FILES", "Unit Tests")
    # Heuristic: if fewer than 2 non-comment, non-blank lines → skip
    real_lines = [
        l for l in content.splitlines()
        if l.strip() and not l.strip().startswith("#")
    ]
    return len(real_lines) >= 2


def _pylint_segment(content: str) -> tuple[list, str]:
    """Write *content* to a temp file, run pylint, return (issues, score)."""
    with tempfile.NamedTemporaryFile(
        suffix=".py", mode="w", encoding="utf-8", delete=False
    ) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        issues = run_pylint_json(tmp_path)
        score  = run_pylint_score(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)
    return issues, score


def process_json_file(json_path: Path) -> Optional[dict]:
    """
    Extract final_code from *json_path*, run pylint, and return a stats row.
    Returns None if the file should be skipped.

    When final_code contains multi-file separators, each Python segment is
    linted independently and results are aggregated, avoiding false positives
    caused by import-order and name-collision artefacts from concatenation.
    """
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[SKIP] {json_path.name}: cannot read JSON – {exc}")
        return None

    # final_code may be at the top level or nested under "result"
    code = data.get("final_code") or data.get("result", {}).get("final_code", "")
    if not isinstance(code, str) or not code.strip():
        print(f"[SKIP] {json_path.name}: 'final_code' is missing or empty")
        return None

    task_id = data.get("task_id") or data.get("result", {}).get("task_id", json_path.stem)

    segments = split_multi_file_code(code)
    py_segments = [(name, content) for name, content in segments if _is_py_segment(name, content)]

    # Fall back to whole-code analysis if splitting produced nothing useful
    if not py_segments:
        py_segments = [("", code)]

    is_multi = len(py_segments) > 1

    all_issues: list = []
    scores: list[str] = []

    for _, content in py_segments:
        issues, score = _pylint_segment(content)
        all_issues.extend(issues)
        if score != "N/A":
            scores.append(score)

    # Aggregate score: average of per-file scores (or N/A)
    if scores:
        avg = sum(float(s.split("/")[0]) for s in scores) / len(scores)
        agg_score = f"{avg:.2f}/10"
    else:
        agg_score = "N/A"

    loc = sum(1 for line in code.splitlines() if line.strip())
    stats = summarise_issues(all_issues)

    tag = f"[{len(py_segments)} files]" if is_multi else ""
    print(
        f"[OK] {task_id:<20s} | score={agg_score:<8s} | LOC={loc} {tag}| "
        f"E={stats['error_count']} W={stats['warning_count']} "
        f"C={stats['convention_count']} R={stats['refactor_count']}"
    )
    return {"task_id": task_id, "pylint_score": agg_score, "loc": loc, **stats}


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
