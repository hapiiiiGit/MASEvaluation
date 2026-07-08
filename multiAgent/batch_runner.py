from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from multiAgent.config.setting import settings
from multiAgent.config.models import ModelConfig
from multiAgent.graphs import GRAPH_REGISTRY


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resolve_task_file(path_str: str) -> Path:
    candidates = [
        repo_root() / path_str,
        Path(__file__).resolve().parent / path_str,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Task file not found: {path_str}")


def load_tasks(source_file: str = "Task/feature-final.json") -> tuple[list[dict[str, Any]], list[str]]:
    path = resolve_task_file(source_file)
    data = json.loads(path.read_text(encoding="utf-8"))

    combined: list[dict[str, Any]] = []
    for key, value in data.items():
        combined.append(
            {
                "task_id": key,
                "task": value["task"],
                "source_file": source_file,
                "source_line_no": None,
            }
        )

    return combined, [source_file]


def load_manifest(manifest_path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}

    if not manifest_path.exists():
        return records

    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        records[record["task_id"]] = record

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

    for metric in metrics:
        agent = metric.get("agent", "unknown")
        if agent not in summary:
            summary[agent] = {
                "calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "wall_time_s": 0.0,
            }

        summary[agent]["calls"] += 1
        summary[agent]["input_tokens"] += int(metric.get("input_tokens", 0))
        summary[agent]["output_tokens"] += int(metric.get("output_tokens", 0))
        summary[agent]["total_tokens"] += int(metric.get("total_tokens", 0))
        summary[agent]["wall_time_s"] += float(metric.get("wall_time_s", 0.0))

    return summary


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


def configure_runtime(model: ModelConfig, graph_name: str, output_root: Path) -> None:
    settings.graph_name = graph_name
    settings.model_name = model.model_name
    settings.api_key = model.api_key
    settings.base_url = model.base_url
    settings.output_root = str(output_root)


def run_for_model(
    graph_name: str,
    model: ModelConfig,
    tasks: list[dict[str, Any]],
    source_files: list[str],
) -> None:
    output_root = repo_root() / "multiAgent" / "outputs" / model.folder_name
    run_dir = output_root / graph_name
    results_dir = run_dir / "results"
    manifest_path = run_dir / "manifest.jsonl"
    summary_path = run_dir / "summary.json"

    # configure_runtime must happen before building the graph so that
    # BaseAgent.__init__ picks up the correct api_key / base_url
    configure_runtime(model, graph_name, output_root)

    if graph_name not in GRAPH_REGISTRY:
        raise ValueError(
            f"Unknown graph_name: {graph_name}. Available: {list(GRAPH_REGISTRY.keys())}"
        )
    graph = GRAPH_REGISTRY[graph_name](
        model_name=model.model_name,
        temperature=settings.temperature,
        api_key=model.api_key,
        base_url=model.base_url,
    )

    run_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest(manifest_path)

    success_count = 0
    failed_count = 0
    skipped_count = 0

    print(f"\n===== GRAPH: {graph_name}  MODEL: {model.model_name} =====")
    print(f"Output dir: {run_dir}")

    for task_item in tasks:
        task_id = task_item["task_id"]
        task = task_item["task"]
        source_file = task_item["source_file"]
        source_line_no = task_item.get("source_line_no")
        result_path = results_dir / f"{task_id}.json"

        last_record = manifest.get(task_id)
        if (
            last_record is not None
            and last_record.get("status") == "SUCCESS"
            and result_path.exists()
        ):
            skipped_count += 1
            print(f"[SKIP] {model.model_name} {task_id} already finished.")
            continue

        print(f"[RUN ] {model.model_name} {task_id}")

        success = False
        last_error = ""

        for attempt in range(1, settings.max_retries + 1):
            started_at = datetime.now().isoformat(timespec="seconds")

            try:
                init_state = make_initial_state(task_id, task, programmer_mode=settings.programmer_mode)  # Bug 8 fix
                result = graph.invoke(init_state)

                if not result.get("success", False):  # Bug 2 fix: default False, not True
                    raise RuntimeError(result.get("error", "Unknown graph failure"))

                payload = {
                    "task_id": task_id,
                    "graph_name": graph_name,
                    "model_name": model.model_name,
                    "task": task,
                    "source_file": source_file,
                    "source_line_no": source_line_no,
                    "result": result,
                    "metrics_summary": summarize_metrics(result.get("metrics", [])),
                    "saved_at": datetime.now().isoformat(timespec="seconds"),
                }
                save_json(result_path, payload)

                record = {
                    "task_id": task_id,
                    "status": "SUCCESS",
                    "attempt": attempt,
                    "model_name": model.model_name,
                    "source_file": source_file,
                    "source_line_no": source_line_no,
                    "result_path": str(result_path),
                    "started_at": started_at,
                    "finished_at": datetime.now().isoformat(timespec="seconds"),
                }
                append_manifest(manifest_path, record)
                manifest[task_id] = record

                success = True
                success_count += 1
                print(f"[ OK ] {model.model_name} {task_id}")
                break

            except Exception as exc:
                last_error = str(exc)

                record = {
                    "task_id": task_id,
                    "status": "FAILED",
                    "attempt": attempt,
                    "model_name": model.model_name,
                    "source_file": source_file,
                    "source_line_no": source_line_no,
                    "error": last_error,
                    "started_at": started_at,
                    "finished_at": datetime.now().isoformat(timespec="seconds"),
                }
                append_manifest(manifest_path, record)
                manifest[task_id] = record

                print(
                    f"[ERR ] {model.model_name} {task_id} "
                    f"attempt={attempt} error={last_error}"
                )

                if attempt < settings.max_retries:
                    time.sleep(settings.retry_wait_seconds)

        if not success:
            failed_count += 1

    summary = {
        "graph_name": graph_name,
        "model_name": model.model_name,
        "task_files": source_files,
        "total_tasks": len(tasks),
        "success_count": success_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_json(summary_path, summary)

    print("\n===== SUMMARY =====")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
