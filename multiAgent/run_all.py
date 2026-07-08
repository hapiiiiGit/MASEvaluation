from __future__ import annotations

import argparse

from multiAgent.config.models import MODEL_CONFIGS
from multiAgent.batch_runner import load_tasks, run_for_model
from multiAgent.graphs import GRAPH_REGISTRY


GRAPH_NAMES = list(GRAPH_REGISTRY.keys())
MODEL_NAMES = [m.model_name for m in MODEL_CONFIGS]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run multiAgent experiment.")
    parser.add_argument(
        "--model",
        choices=MODEL_NAMES,
        default="deepseek-v3-250324",
        help="Model to use (default: deepseek-v3-250324)",
    )
    parser.add_argument(
        "--graph",
        choices=GRAPH_NAMES,
        nargs="+",
        default=None,
        metavar="GRAPH",
        help="One or more graph names to run (default: all graphs)",
    )
    parser.add_argument(
        "--task-file",
        default="Task/feature-final.json",
        help="Path to the task JSON file",
    )
    parser.add_argument(
        "--max-tasks",
        type=int,
        default=None,
        metavar="N",
        help="Only run the first N tasks (default: all tasks)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    model = next(m for m in MODEL_CONFIGS if m.model_name == args.model)

    tasks, source_files = load_tasks(args.task_file)
    if not tasks:
        raise ValueError(f"No tasks loaded from {args.task_file}")

    if args.max_tasks is not None:
        tasks = tasks[: args.max_tasks]

    print(f"Model     : {model.model_name}")
    print(f"Tasks     : {len(tasks)} (from {', '.join(source_files)})")

    graphs_to_run = args.graph if args.graph else GRAPH_NAMES
    print(f"Graphs    : {graphs_to_run}")

    for graph_name in graphs_to_run:
        run_for_model(graph_name, model, tasks, source_files)


if __name__ == "__main__":
    main()
