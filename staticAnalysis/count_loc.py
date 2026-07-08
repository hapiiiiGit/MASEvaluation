import json
import os
import sys


def count_loc(code: str) -> int:
    """Count non-empty lines of code."""
    lines = code.split("\n")
    return sum(1 for line in lines if line.strip())


def analyze_folder(folder_path: str):
    results = []

    json_files = sorted(
        f for f in os.listdir(folder_path) if f.endswith(".json")
    )

    if not json_files:
        print(f"No JSON files found in: {folder_path}")
        return

    print(f"{'File':<30} {'LoC':>6}")
    print("-" * 38)

    for filename in json_files:
        filepath = os.path.join(folder_path, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            final_code = data.get("result", {}).get("final_code") or data.get("final_code")

            if final_code is None:
                print(f"{filename:<30} {'(no final_code)':>6}")
                continue

            loc = count_loc(final_code)
            results.append((filename, loc))
            print(f"{filename:<30} {loc:>6}")

        except (json.JSONDecodeError, KeyError) as e:
            print(f"{filename:<30} {'(error)':>6}  [{e}]")

    if results:
        total = sum(loc for _, loc in results)
        avg = total / len(results)
        print("-" * 38)
        print(f"{'Files processed:':<30} {len(results):>6}")
        print(f"{'Total LoC:':<30} {total:>6}")
        print(f"{'Average LoC:':<30} {avg:>9.1f}")


if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else r"G:\LLM\MAS-final\staticAnalysis\example"
    analyze_folder(folder)
