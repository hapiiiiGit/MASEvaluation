from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


_CONDA_ENV_NAME = "metagpt-3.10"


def _find_conda_python(env_name: str) -> str:

    conda_exe = (
        shutil.which("conda")
        or shutil.which("conda.bat")
        or "conda"
    )
    try:
        probe = subprocess.run(
            [
                conda_exe, "run", "--no-capture-output",
                "-n", env_name,
                "python", "-c", "import sys; print(sys.executable)",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if probe.returncode == 0:
            exe = probe.stdout.strip()
            if exe and Path(exe).exists():
                return exe
    except Exception:
        pass

    home = Path.home()
    candidates: list[Path] = [
        home / "miniconda3"  / "envs" / env_name / "python.exe",
        home / "anaconda3"   / "envs" / env_name / "python.exe",
        home / "mambaforge"  / "envs" / env_name / "python.exe",
        Path("C:/ProgramData/miniconda3/envs")  / env_name / "python.exe",
        Path("C:/ProgramData/anaconda3/envs")   / env_name / "python.exe",
        Path("C:/tools/miniconda3/envs")        / env_name / "python.exe",
        home / "miniconda3"  / "envs" / env_name / "bin" / "python",
        home / "anaconda3"   / "envs" / env_name / "bin" / "python",
        home / "mambaforge"  / "envs" / env_name / "bin" / "python",
        Path("/opt/conda/envs") / env_name / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    # Last resort: current interpreter (may lack required packages)
    return sys.executable



_CONDA_PYTHON: str = _find_conda_python(_CONDA_ENV_NAME)


@dataclass
class ExecutionResult:
    success: bool      
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool



def run_tests(code: str, test_code: str, timeout: int = 15) -> ExecutionResult:
    """
    Write *code* to ``solution.py`` and *test_code* to ``test_solution.py``
    inside a temporary directory under the OS Temp folder, then run
    ``python -m unittest test_solution -v`` with the metagpt-3.10 interpreter.

    Both stdout and stderr are captured and concatenated so no output is lost.
    """
    tmp_root = Path(__file__).resolve().parent.parent / "Temp"
    tmp_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=tmp_root, prefix="mas_test_") as tmpdir:
        solution_path = os.path.join(tmpdir, "solution.py")
        test_path     = os.path.join(tmpdir, "test_solution.py")

        with open(solution_path, "w", encoding="utf-8") as f:
            f.write(code)
        with open(test_path, "w", encoding="utf-8") as f:
            f.write(test_code)

        try:
            result = subprocess.run(
                [_CONDA_PYTHON, "-m", "unittest", "test_solution", "-v"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return ExecutionResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                timed_out=False,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"Execution timed out after {timeout} seconds.",
                exit_code=-1,
                timed_out=True,
            )
