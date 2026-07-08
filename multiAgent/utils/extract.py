from __future__ import annotations

import json
import re
from pathlib import Path



RESULTS_DIR = Path("../outputs/deepseek-v3-250324-runs/plan_programmer_tester/results")
OUTPUT_DIR = Path("../extract/plan-programmer-tester/deepseek")



def extract_task_number(path: Path) -> tuple[int, str]:

    match = re.search(r"(\d+)", path.stem)
    if match:
        return int(match.group(1)), path.name
    return 10**12, path.name


def load_final_code(json_path: Path) -> str:

    data = json.loads(json_path.read_text(encoding="utf-8"))

    if "result" not in data or not isinstance(data["result"], dict):
        raise ValueError(f"{json_path.name} does not contain a valid 'result' object.")

    final_code = data["result"].get("final_code")
    if not isinstance(final_code, str):
        raise ValueError(f"{json_path.name} does not contain a valid 'result.final_code' string.")

    return final_code


def main() -> None:
    if not RESULTS_DIR.exists():
        raise FileNotFoundError(f"RESULTS_DIR does not exist: {RESULTS_DIR}")

    if not RESULTS_DIR.is_dir():
        raise NotADirectoryError(f"RESULTS_DIR is not a directory: {RESULTS_DIR}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    json_files = sorted(RESULTS_DIR.rglob("*.json"), key=extract_task_number)

    if not json_files:
        print(f"[WARN] No json files found under: {RESULTS_DIR}")
        return

    success_count = 0
    fail_count = 0

    for json_file in json_files:
        try:
            final_code = load_final_code(json_file)


            instruction_dir = OUTPUT_DIR / f"instruction{success_count}"
            instruction_dir.mkdir(parents=True, exist_ok=True)

            code_file = instruction_dir / "code.txt"
            code_file.write_text(final_code, encoding="utf-8")

            print(f"[OK] {json_file.name} -> {code_file}")
            success_count += 1

        except Exception as e:
            print(f"[ERROR] {json_file.name}: {e}")
            fail_count += 1

    print("\n===== DONE =====")
    print(f"results dir : {RESULTS_DIR}")
    print(f"output dir  : {OUTPUT_DIR}")
    print(f"success     : {success_count}")
    print(f"failed      : {fail_count}")


if __name__ == "__main__":
    main()