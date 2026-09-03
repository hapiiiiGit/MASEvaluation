from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


MODEL = "gpt-4.1-2025-04-14"
MODEL_FOLDER = "gpt-4.1-2025-04-14-runs"
CONDA_ENV = "mastesting"

GRAPHS = [
    "solo_programmer",
    "planner_programmer",
    "planner_architect_programmer",
    "planner_architect_programmer_reviewer",
    "planner_architect_programmer_reviewer_tester",
]

OUTPUTS_ROOT = Path("multiAgent/outputs") / MODEL_FOLDER
TASK_FILE = "Task/feature-final.json"


MASTESTING_PYTHON: str | None = None  # resolved in main()


def resolve_python() -> str:
    """Return the python executable for the mastesting conda env."""
    # Try conda run approach
    conda = subprocess.run(
        ["conda", "run", "-n", CONDA_ENV, "which", "python"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if conda.returncode == 0 and conda.stdout.strip():
        return f"conda run -n {CONDA_ENV} python"

    # Fallback: direct paths
    fallbacks = [
        f"\\{CONDA_ENV}\\python.exe",
        f"/{CONDA_ENV}/python.exe",
    ]
    for p in fallbacks:
        if Path(p).is_file():
            return p
    return sys.executable

def banner(text: str) -> None:
    line = "=" * 70
    print(f"\n{line}")
    print(f"  {text}")
    print(f"{line}\n", flush=True)


def build_cmd(script_args: list[str]) -> list[str]:
    """Prepend the MASTesting python to script arguments."""
    py = MASTESTING_PYTHON
    if py.startswith("conda "):
        return py.split() + script_args
    return [py, *script_args]


def run(script_args: list[str], step_label: str) -> bool:
    """Run a script under MASTesting python. Returns True on success."""
    cmd = build_cmd(script_args)
    print(f"[CMD] {' '.join(cmd)}", flush=True)
    t0 = time.time()
    result = subprocess.run(cmd, text=True, encoding="utf-8")
    elapsed = time.time() - t0
    if result.returncode == 0:
        print(f"[OK]  {step_label}  ({elapsed:.1f}s)\n", flush=True)
        return True
    else:
        print(f"[FAIL] {step_label} exited with code {result.returncode}  ({elapsed:.1f}s)\n",
              flush=True)
        return False

def step1_run_graphs(graphs: list[str]) -> bool:
    banner(f"STEP 1 — Run multiAgent graphs  (model={MODEL})")
    return run(
        ["-m", "multiAgent.run_all",
         "--model", MODEL,
         "--graph", *graphs,
         "--task-file", TASK_FILE],
        f"multiAgent.run_all  graphs={graphs}",
    )


def step2_llm_judge(graphs: list[str]) -> dict[str, bool]:
    banner("STEP 2 — LLMasJudge feature coverage")
    results: dict[str, bool] = {}
    for graph in graphs:
        results_dir = OUTPUTS_ROOT / graph / "results"
        if not results_dir.is_dir():
            print(f"[SKIP] {graph}: results folder not found at {results_dir}")
            results[graph] = False
            continue
        print(f"--- {graph} ---")
        ok = run(
            ["LLMasJudge/calcFeature.py", str(results_dir)],
            f"LLMasJudge  graph={graph}",
        )
        results[graph] = ok
    return results


def step3_static_analysis(graphs: list[str]) -> dict[str, bool]:
    banner("STEP 3 — Static analysis (pylint)")
    results: dict[str, bool] = {}
    for graph in graphs:
        results_dir = OUTPUTS_ROOT / graph / "results"
        if not results_dir.is_dir():
            print(f"[SKIP] {graph}: results folder not found at {results_dir}")
            results[graph] = False
            continue
        csv_out = OUTPUTS_ROOT / graph / "pylint_summary.csv"
        print(f"--- {graph} ---")
        ok = run(
            ["staticAnalysis/analysis.py", str(results_dir), str(csv_out)],
            f"staticAnalysis  graph={graph}",
        )
        results[graph] = ok
    return results


def print_summary(
    graphs: list[str],
    step1_ok: bool | None,
    judge_results: dict[str, bool] | None,
    static_results: dict[str, bool] | None,
) -> None:
    banner("SUMMARY")
    if step1_ok is not None:
        print(f"  Step 1 (multiAgent run) : {'OK' if step1_ok else 'FAILED'}")

    for step_name, results, file_suffix in [
        ("Step 2 (LLMasJudge)", judge_results, "results/feature_coverage.json"),
        ("Step 3 (staticAnalysis)", static_results, "pylint_summary.csv"),
    ]:
        if results is None:
            print(f"  {step_name:<25s} : SKIPPED")
        else:
            print(f"  {step_name:<25s} :")
            for g in graphs:
                ok = results.get(g)
                if ok:
                    print(f"    {g:<55s} OK  → {OUTPUTS_ROOT / g / file_suffix}")
                else:
                    print(f"    {g:<55s} FAILED")
    print()




def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Full experiment pipeline for gpt-4.1-2025-04-14")
    parser.add_argument("--skip-run",    action="store_true", help="Skip step 1 (multiAgent run)")
    parser.add_argument("--skip-judge",  action="store_true", help="Skip step 2 (LLMasJudge)")
    parser.add_argument("--skip-static", action="store_true", help="Skip step 3 (staticAnalysis)")
    parser.add_argument(
        "--graphs", nargs="+", default=None, metavar="GRAPH",
        help=f"Graphs to process (default: all {len(GRAPHS)})",
    )
    return parser.parse_args()


def main() -> None:
    global MASTESTING_PYTHON
    MASTESTING_PYTHON = resolve_python()

    args = parse_args()
    graphs = args.graphs if args.graphs else GRAPHS

    # Validate graph names
    unknown = [g for g in graphs if g not in GRAPHS]
    if unknown:
        sys.exit(f"Unknown graphs: {unknown}\nAvailable: {GRAPHS}")

    print(f"Model  : {MODEL}")
    print(f"Graphs : {graphs}")
    print(f"Output : {OUTPUTS_ROOT}")
    print(f"Python : {MASTESTING_PYTHON}")

    step1_ok: bool | None = None
    judge_results: dict[str, bool] | None = None
    static_results: dict[str, bool] | None = None

    total_t0 = time.time()

    if not args.skip_run:
        step1_ok = step1_run_graphs(graphs)
        if not step1_ok:
            print("[WARN] multiAgent run reported failures — continuing with steps 2 & 3 anyway.\n")
    else:
        print("[SKIP] Step 1 skipped.\n")

    if not args.skip_judge:
        judge_results = step2_llm_judge(graphs)
    else:
        print("[SKIP] Step 2 skipped.\n")

    if not args.skip_static:
        static_results = step3_static_analysis(graphs)
    else:
        print("[SKIP] Step 3 skipped.\n")

    print_summary(graphs, step1_ok, judge_results, static_results)
    print(f"Total wall time: {time.time() - total_t0:.1f}s")


if __name__ == "__main__":
    main()
