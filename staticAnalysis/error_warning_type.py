import sys
import pandas as pd
from collections import Counter

EXCLUDE = {"import-error", "import_error", "reimported"}


def count_issue_types(series):
    total_counter = Counter()
    file_counter = Counter()
    for cell in series.dropna():
        seen = set()
        for item in str(cell).split("|"):
            item = item.strip()
            if not item:
                continue
            issue_type, count = item.rsplit(":", 1)
            if issue_type in EXCLUDE:
                continue
            total_counter[issue_type] += int(count)
            seen.add(issue_type)
        for t in seen:
            file_counter[t] += 1
    return (
        pd.DataFrame(
            [{"Type": t, "Files": file_counter[t], "Count": total_counter[t]} for t in total_counter]
        )
        .sort_values("Count", ascending=False)
        .reset_index(drop=True)
    )


def has_non_excluded_issue(cell) -> bool:
    if pd.isna(cell):
        return False
    for item in str(cell).split("|"):
        item = item.strip()
        if not item:
            continue
        issue_type = item.rsplit(":", 1)[0]
        if issue_type not in EXCLUDE:
            return True
    return False


def analyze(filepath: str):
    df = pd.read_csv(filepath)
    total_files = len(df)

    for col_name, label in [
        ("error_types", "Error"),
        ("warning_types", "Warning"),
    ]:
        files_with_issue = df[col_name].apply(has_non_excluded_issue).sum()
        stats = count_issue_types(df[col_name])
        total = stats["Count"].sum()
        print(f"\n{'='*40}")
        print(f"{label} types  ({len(stats)} kinds, {total} total)")
        print(f"Files with {label.lower()}: {files_with_issue} / {total_files}")
        print(f"{'='*40}")
        print(f"{'Type':<45} {'Files':>6} {'Count':>6}")
        print("-" * 59)
        for _, row in stats.iterrows():
            print(f"{row['Type']:<45} {int(row['Files']):>6} {int(row['Count']):>6}")


if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else r"G:\LLM\MAS-final\staticAnalysis\example\pylint_summary.csv"
    analyze(filepath)