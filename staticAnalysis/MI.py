import json
import csv
import sys
from pathlib import Path

try:
    from radon.metrics import mi_visit, mi_rank
except ImportError:
    print("radon not installed. Run: pip install radon")
    sys.exit(1)


def compute_mi(code: str) -> dict:
    """Return MI score and rank for a code string."""
    try:
        score = mi_visit(code, multi=True)
        rank = mi_rank(score)
        return {"mi_score": round(score, 2), "mi_rank": rank, "error": ""}
    except Exception as exc:
        return {"mi_score": None, "mi_rank": None, "error": str(exc)}


def process_directory(input_dir: str, output_csv: str | None = None) -> str:
    base = Path(input_dir)
    if not base.is_dir():
        raise FileNotFoundError(f"Directory not found: {input_dir}")

    json_files = sorted(base.glob("*.json"))
    if not json_files:
        raise FileNotFoundError(f"No JSON files found in: {input_dir}")

    if output_csv is None:
        output_csv = str(base / "mi_summary.csv")

    rows = []
    for jf in json_files:
        with open(jf, encoding="utf-8") as f:
            data = json.load(f)

        task_id = data.get("task_id", jf.stem)
        result = data.get("result", {})
        final_code = result.get("final_code", "")

        if not final_code:
            rows.append({
                "task_id": task_id,
                "file": jf.name,
                "mi_score": None,
                "mi_rank": None,
                "error": "final_code is empty or missing",
            })
            continue

        mi = compute_mi(final_code)
        rows.append({
            "task_id": task_id,
            "file": jf.name,
            "mi_score": mi["mi_score"],
            "mi_rank": mi["mi_rank"],
            "error": mi["error"],
        })

    fieldnames = ["task_id", "file", "mi_score", "mi_rank", "error"]
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return output_csv


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python MI.py <input_dir> [output_csv]")
        sys.exit(1)

    input_dir = sys.argv[1]
    output_csv = sys.argv[2] if len(sys.argv) > 2 else None

    out = process_directory(input_dir, output_csv)
    print(f"Done. Results written to: {out}")
