from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import time
from typing import Callable

import openai


FEATURE_FILE = pathlib.Path(__file__).parent / "feature-final.json"

JUDGE_PROMPT = """You are an expert code evaluator.

Your task is to determine whether each specified feature is implemented in the given code.

You MUST follow these rules strictly:

[Evaluation Criteria]
- A feature is considered "implemented" ONLY if there is clear and explicit evidence in the code.
- Do NOT assume missing parts are implemented.
- Do NOT infer behavior that is not directly supported by the code.
- If the implementation is partial, unclear, or incorrect, mark it as false.
- Base your judgment ONLY on the provided code, not on expected behavior.

[Task Description]
{task}

[Code]
{code}

[Features to Evaluate]
Each feature is independent. Evaluate them one by one.

{features}

[Output Format]
Return ONLY a valid JSON object with no additional text.

- Keys must be feature indices starting from 1 (as strings)
- Values must be true or false

Example:
{{"results": {{
    "1": true,
    "2": false,
    "3": true
}}}}

"""


API_KEY  = os.environ.get("OPENAI_API_KEY", "")
BASE_URL = ""


MODELS: dict[str, str] = {
    "claude": "claude-sonnet-4-6",
    "gpt":    "gpt-5.2",
    "gemini": "gemini-3.1-pro-preview",
}



def load_features() -> dict:
    return json.loads(FEATURE_FILE.read_text(encoding="utf-8"))


def feature_key(task_id: str) -> str:
    """'task_0001' → 'task_1'  (strip leading zeros from the numeric part)."""
    m = re.search(r"\d+", task_id)
    if not m:
        raise ValueError(f"Cannot parse task number from '{task_id}'")
    return f"task_{int(m.group())}"


def format_features(features: list[str]) -> str:
    return "\n".join(f"{i + 1}. {feat}" for i, feat in enumerate(features))


def parse_response(text: str, feature_total: int) -> dict[str, bool]:
    """Extract {str(index): bool} from a model response, falling back to all-False."""
    text = text.strip()
    # Strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # Grab the first {...} block
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        text = m.group()
    try:
        data = json.loads(text)
        inner = data.get("results", data)
        return {str(k): bool(v) for k, v in inner.items()}
    except (json.JSONDecodeError, AttributeError):
        print("    [WARN] Failed to parse model response as JSON — defaulting to all False")
        return {str(i): False for i in range(1, feature_total + 1)}


def build_result(task_id: str, feature_results: dict[str, bool], features: list[str]) -> dict:
    feature_total = len(features)
    finished = sorted(int(k) for k, v in feature_results.items() if v)
    return {
        "task_id":         task_id,
        "feature_total":   feature_total,
        "feature_results": feature_results,
        "feature_finish":  finished,
        "finish_total":    len(finished),
        "completion_rate": round(len(finished) / feature_total, 4) if feature_total else 0.0,
    }


def with_retry(fn: Callable, retries: int = 3, backoff: float = 5.0):
    """Call fn(), retrying up to `retries` times on any exception."""
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except Exception as exc:
            if attempt == retries:
                raise
            wait = backoff * attempt
            print(f"    [RETRY {attempt}/{retries}] {exc!r} — waiting {wait}s")
            time.sleep(wait)



_client = openai.OpenAI(api_key=API_KEY, base_url=BASE_URL)


def call_model(model_name: str, task: str, code: str, features: list[str]) -> dict[str, bool]:
    prompt = JUDGE_PROMPT.format(
        task=task,
        code=code,
        features=format_features(features),
    )

    def _call():
        resp = _client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return parse_response(resp.choices[0].message.content, len(features))

    return with_retry(_call)



CALLERS: dict[str, Callable] = {
    name: (lambda t, c, f, mn=model: call_model(mn, t, c, f))
    for name, model in MODELS.items()
}



def calc_consensus(
    model_results: dict[str, dict[str, dict]],
    task_id: str,
    feature_total: int,
) -> dict:
    """A feature counts only if ALL 3 models marked it as complete."""
    consensus_finish = []
    for i in range(1, feature_total + 1):
        key = str(i)
        votes = sum(
            1
            for m_data in model_results.values()
            if m_data.get(task_id) is not None
            and m_data[task_id].get("feature_results", {}).get(key, False)
        )
        if votes == len(CALLERS):
            consensus_finish.append(i)

    return {
        "task_id":          task_id,
        "feature_total":    feature_total,
        "consensus_finish": consensus_finish,
        "finish_total":     len(consensus_finish),
        "completion_rate":  round(len(consensus_finish) / feature_total, 4) if feature_total else 0.0,
    }




def _write_json(path: pathlib.Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_json(path: pathlib.Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}



def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate feature coverage with 3 independent LLM judges"
    )
    parser.add_argument("folder", help="Folder containing task_*.json files")
    args = parser.parse_args()

    folder = pathlib.Path(args.folder)
    if not folder.is_dir():
        sys.exit(f"Error: '{folder}' is not a directory")

    feature_db = load_features()
    task_files = sorted(folder.glob("task_*.json"))
    if not task_files:
        sys.exit(f"No task_*.json files found in '{folder}'")

    print(f"Folder : {folder}")
    print(f"Tasks  : {len(task_files)} files")
    print(f"Models : { {n: m for n, m in MODELS.items()} }\n")

    # Load any existing partial results (supports resume after crash)
    model_results: dict[str, dict[str, dict | None]] = {}
    for model_name in CALLERS:
        path = folder / f"judge_results-{model_name}.json"
        existing = _load_json(path)
        model_results[model_name] = existing
        if existing:
            print(f"[RESUME] {model_name}: loaded {len(existing)} existing result(s)")

    consensus: dict[str, dict] = _load_json(folder / "feature_coverage.json")
    if consensus:
        print(f"[RESUME] consensus: loaded {len(consensus)} existing result(s)")

    total_tasks = len(task_files)
    skipped = 0

    for task_idx, task_file in enumerate(task_files, 1):
        raw = json.loads(task_file.read_text(encoding="utf-8"))
        task_id    = raw["task_id"]
        task_text  = raw["task"]
        final_code = raw.get("result", {}).get("final_code", "")
        fkey       = feature_key(task_id)

        # ── progress header ────────────────────────────────────────────────
        bar_done  = int(20 * (task_idx - 1) / total_tasks)
        bar_str   = "#" * bar_done + "-" * (20 - bar_done)
        print(f"\n[{task_idx:>3}/{total_tasks}] [{bar_str}] {task_id}")

        if fkey not in feature_db:
            print(f"  [SKIP] no feature definition for key '{fkey}'")
            skipped += 1
            continue
        if not final_code:
            print(f"  [SKIP] final_code is empty")
            skipped += 1
            continue

        features     = feature_db[fkey]["features"]
        num_models   = len(CALLERS)
        print(f"  Features: {len(features)}")

        for model_idx, (model_name, caller) in enumerate(CALLERS.items(), 1):
            prefix = f"  [{model_idx}/{num_models}] {model_name:<8}"

            # Skip if this task was already judged by this model
            if model_results[model_name].get(task_id) is not None:
                r = model_results[model_name][task_id]
                print(f"{prefix} already done  {r['finish_total']}/{r['feature_total']} ({r['completion_rate']:.0%})")
                continue

            print(f"{prefix} calling {MODELS[model_name]} ...", end=" ", flush=True)
            try:
                feature_results = caller(task_text, final_code, features)
                result = build_result(task_id, feature_results, features)
                model_results[model_name][task_id] = result

                # ── real-time write ────────────────────────────────────────
                _write_json(folder / f"judge_results-{model_name}.json",
                            model_results[model_name])

                print(f"{result['finish_total']}/{result['feature_total']} ({result['completion_rate']:.0%})  [saved]")
            except Exception as exc:
                print(f"FAILED: {exc}")
                model_results[model_name][task_id] = None
                _write_json(folder / f"judge_results-{model_name}.json",
                            model_results[model_name])

            time.sleep(0.5)  # polite inter-call delay

        # ── update consensus after all models have processed this task ─────
        feature_total = next(
            (
                model_results[m][task_id]["feature_total"]
                for m in model_results
                if model_results[m].get(task_id) is not None
            ),
            0,
        )
        if feature_total > 0:
            consensus[task_id] = calc_consensus(model_results, task_id, feature_total)
            _write_json(folder / "feature_coverage.json", consensus)
            c = consensus[task_id]
            print(f"  Consensus: {c['finish_total']}/{c['feature_total']} ({c['completion_rate']:.0%})  [saved]")

        # ── rolling summary ────────────────────────────────────────────────
        evaluated = len(consensus)
        if evaluated:
            avg = sum(r["completion_rate"] for r in consensus.values()) / evaluated
            print(f"  Overall so far: {evaluated} tasks evaluated, avg coverage {avg:.2%}")

    # ── Final summary ────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    evaluated = len(consensus)
    if evaluated:
        avg = sum(r["completion_rate"] for r in consensus.values()) / evaluated
        print(f"Done — {evaluated}/{total_tasks} tasks evaluated  (skipped {skipped})")
        print(f"Average consensus coverage: {avg:.2%}")
    else:
        print("Done — no tasks were evaluated.")


if __name__ == "__main__":
    main()
