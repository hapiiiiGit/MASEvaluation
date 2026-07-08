import json
import sys


def analyze_completion_rate(filepath: str):
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = []

    print(f"{'Task':<20} {'completion_rate':>16}")
    print("-" * 38)

    for task_id, task_data in sorted(data.items()):
        rate = task_data.get("completion_rate")
        if rate is None:
            print(f"{task_id:<20} {'(missing)':>16}")
            continue
        results.append((task_id, rate))
        print(f"{task_id:<20} {rate:>15.4f}")

    if results:
        avg = sum(r for _, r in results) / len(results)
        print("-" * 38)
        print(f"{'Tasks processed:':<20} {len(results):>16}")
        print(f"{'Average rate:':<20} {avg:>15.4f}")


if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else r"G:\LLM\MAS-final\LLMasJudge\example\feature_coverage.json"
    analyze_completion_rate(filepath)
