import json
from pathlib import Path


def normalize_code_text(code_text):

    if code_text is None:
        return None

    if not isinstance(code_text, str):
        code_text = str(code_text)

    s = code_text.strip()

    s = (
        s.replace("\\r\\n", "\n")
         .replace("\\n", "\n")
         .replace("\\t", "\t")
         .replace('\\"', '"')
         .replace("\\'", "'")
    )

    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = s.lstrip("\ufeff")
    s = s.strip() + "\n"

    return s


def clean_final_code(final_code):

    if final_code is None:
        return None

    if not isinstance(final_code, str):
        final_code = str(final_code)

    final_code = final_code.strip()

    if final_code.startswith("{") and final_code.endswith("}"):
        try:
            parsed = json.loads(final_code)
            if isinstance(parsed, dict) and "code" in parsed:
                inner_code = parsed["code"]
                if isinstance(inner_code, str):
                    return normalize_code_text(inner_code)
        except Exception:
            pass


    return normalize_code_text(final_code)


def extract_final_code_from_json(json_path: Path):

    try:
        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        final_code = data.get("result", {}).get("final_code", None)

        if final_code is None:
            return None

        final_code = clean_final_code(final_code)

        if not final_code:
            return None

        return final_code

    except Exception as e:
        return None


def save_codes(input_dir, output_dir=None, recursive=False):

    input_path = Path(input_dir)

    if output_dir is None:
        output_path = input_path
    else:
        output_path = Path(output_dir)

    output_path.mkdir(parents=True, exist_ok=True)

    if recursive:
        json_files = sorted(input_path.rglob("*.json"))
    else:
        json_files = sorted(input_path.glob("*.json"))

    if not json_files:
        return

    index = 0
    for json_file in json_files:
        final_code = extract_final_code_from_json(json_file)
        if final_code is None:
            continue

        instruction_dir = output_path / f"instruction{index}"
        instruction_dir.mkdir(parents=True, exist_ok=True)

        code_file = instruction_dir / "code.txt"
        with code_file.open("w", encoding="utf-8") as f:
            f.write(final_code)

        index += 1



if __name__ == "__main__":

    input_dir = "../outputs/qwen2.5-coder-32b-instruct-runs/planner_programmer/results"


    output_dir = "../extract/plan_withTask_programmer/qwen"

    recursive = False

    save_codes(input_dir, output_dir, recursive)