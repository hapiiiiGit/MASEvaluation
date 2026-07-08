from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from multiAgent.config.setting import settings
from multiAgent.graphs import GRAPH_REGISTRY


def load_tasks(task_file: str) -> list[tuple[str, str]]:

    path = Path(task_file)
    if not path.exists():
        raise FileNotFoundError(f"Task file not found: {task_file}")

    if path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        return [(key, v["task"]) for key, v in data.items()]

    tasks: list[tuple[str, str]] = []
    seq = 1
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if text:
            tasks.append((f"task_{seq:04d}", text))
            seq += 1
    return tasks


def load_manifest(manifest_path: Path) -> dict[str, dict[str, Any]]:

    records: dict[str, dict[str, Any]] = {}

    if not manifest_path.exists():
        return records

    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        records[rec["task_id"]] = rec

    return records


def append_manifest(manifest_path: Path, record: dict[str, Any]) -> None:
    with manifest_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def summarize_metrics(metrics: list[dict[str, Any]]) -> dict[str, Any]:

    summary: dict[str, dict[str, Any]] = {}

    for m in metrics:
        agent = m.get("agent", "unknown")
        if agent not in summary:
            summary[agent] = {
                "calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "wall_time_s": 0.0,
            }

        summary[agent]["calls"] += 1
        summary[agent]["input_tokens"] += int(m.get("input_tokens", 0))
        summary[agent]["output_tokens"] += int(m.get("output_tokens", 0))
        summary[agent]["total_tokens"] += int(m.get("total_tokens", 0))
        summary[agent]["wall_time_s"] += float(m.get("wall_time_s", 0.0))

    return summary


def build_graph():
    graph_name = settings.graph_name

    if graph_name not in GRAPH_REGISTRY:
        raise ValueError(
            f"Unknown graph_name: {graph_name}. "
            f"Available: {list(GRAPH_REGISTRY.keys())}"
        )

    builder = GRAPH_REGISTRY[graph_name]
    return builder(
        model_name=settings.model_name,
        temperature=settings.temperature,
        api_key=settings.api_key,
        base_url=settings.base_url,
    )


def make_initial_state(task_id: str, task: str, *, programmer_mode: str = "") -> dict[str, Any]:
    return {
        "task_id":                task_id,
        "task":                   task,
        "plans":                  [],
        "architectures":          [],
        "codes":                  [],
        "reviews":                [],
        "test_cases":             [],
        "iteration":              0,
        "reviewer_iteration":     0,
        "tester_iteration":       0,
        "max_reviewer_iterations": settings.max_reviewer_iterations,
        "max_tester_iterations":  settings.max_tester_iterations,
        "need_revision":          False,
        "programmer_mode":        programmer_mode,
    }


def main():
    graph = build_graph()
    tasks = load_tasks(settings.task_file)

    run_dir = Path(settings.output_root) / settings.graph_name
    results_dir = run_dir / "results"
    manifest_path = run_dir / "manifest.jsonl"
    summary_path = run_dir / "summary.json"

    run_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest(manifest_path)

    total_tasks = len(tasks)
    success_count = 0
    failed_count = 0
    skipped_count = 0

    for task_id, task in tasks:  # Bug 3 fix: task_id now comes from load_tasks
        result_path = results_dir / f"{task_id}.json"

        last_record = manifest.get(task_id)
        if (
            last_record is not None
            and last_record.get("status") == "SUCCESS"
            and result_path.exists()
        ):
            skipped_count += 1
            print(f"[SKIP] {task_id} already finished.")
            continue

        print(f"[RUN ] {task_id}")

        last_error = ""
        success = False

        for attempt in range(1, settings.max_retries + 1):
            started_at = datetime.now().isoformat(timespec="seconds")

            try:
                init_state = make_initial_state(task_id, task, programmer_mode=settings.programmer_mode)  # Bug 8 fix
                result = graph.invoke(init_state)

                if not result.get("success", False):  # Bug 2 fix: default False, not True
                    raise RuntimeError(result.get("error", "Unknown graph failure"))

                payload = {
                    "task_id": task_id,
                    "graph_name": settings.graph_name,
                    "task": task,
                    "result": result,
                    "metrics_summary": summarize_metrics(result.get("metrics", [])),
                    "saved_at": datetime.now().isoformat(timespec="seconds"),
                }
                save_json(result_path, payload)

                record = {
                    "task_id": task_id,
                    "status": "SUCCESS",
                    "attempt": attempt,
                    "result_path": str(result_path),
                    "started_at": started_at,
                    "finished_at": datetime.now().isoformat(timespec="seconds"),
                }
                append_manifest(manifest_path, record)
                manifest[task_id] = record

                success = True
                success_count += 1
                print(f"[ OK ] {task_id}")
                break

            except Exception as e:
                last_error = str(e)

                record = {
                    "task_id": task_id,
                    "status": "FAILED",
                    "attempt": attempt,
                    "error": last_error,
                    "started_at": started_at,
                    "finished_at": datetime.now().isoformat(timespec="seconds"),
                }
                append_manifest(manifest_path, record)
                manifest[task_id] = record

                print(f"[ERR ] {task_id} attempt={attempt} error={last_error}")

                if attempt < settings.max_retries:
                    time.sleep(settings.retry_wait_seconds)

        if not success:
            failed_count += 1

    summary = {
        "graph_name": settings.graph_name,
        "task_file": settings.task_file,
        "total_tasks": total_tasks,
        "success_count": success_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_json(summary_path, summary)

    print("\n===== SUMMARY =====")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
