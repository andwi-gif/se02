from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import traceback
from pathlib import Path
from typing import Dict, Optional

import yaml
from packaging.version import Version

from quantum_api_drift_lab.types import ExecutionRecord, GenerationRecord, Task
from quantum_api_drift_lab.utils.io import ensure_dir


MOCK_PATTERN_RE = re.compile(r"MOCK_PATTERN:\s*([A-Z0-9_]+)")


class ExecutionBackend:
    backend_name = "base"

    def execute(self, generation: GenerationRecord, task: Task, eval_version: str) -> ExecutionRecord:
        raise NotImplementedError


class MockExecutionBackend(ExecutionBackend):
    backend_name = "mock"

    def execute(self, generation: GenerationRecord, task: Task, eval_version: str) -> ExecutionRecord:
        start = time.perf_counter()
        pattern = extract_code_pattern(generation.code)
        executed = True
        passed = True
        raw_error = ""
        stdout = ""
        stderr = ""

        if task.sdk == "qiskit":
            if pattern == "LEGACY_AER_EXECUTE":
                if Version(eval_version) >= Version("1.0.0"):
                    executed = False
                    passed = False
                    raw_error = "ImportError: cannot import name 'Aer' from 'qiskit'"
            elif pattern == "LEGACY_QASM_METHOD":
                if Version(eval_version) >= Version("1.0.0"):
                    executed = False
                    passed = False
                    raw_error = "AttributeError: 'QuantumCircuit' object has no attribute 'qasm'"
            elif pattern == "OLD_SIGNATURE_BACKEND_OPTIONS":
                if Version(eval_version) >= Version("2.0.0"):
                    executed = False
                    passed = False
                    raw_error = "TypeError: run() got an unexpected keyword argument 'backend_options'"
            elif pattern == "SEMANTIC_COUNTS_LIST":
                executed = True
                passed = False
                raw_error = "AssertionError: expected dict counts, got list"
            elif pattern in {"MODERN_AER_SIMULATOR", "MODERN_QASM2_DUMPS"}:
                stdout = "OK"
            else:
                executed = False
                passed = False
                raw_error = f"RuntimeError: Unknown qiskit mock pattern {pattern}"
        elif task.sdk == "pennylane":
            if pattern == "LEGACY_EXPVAL_COST":
                if Version(eval_version) >= Version("0.35.0"):
                    executed = False
                    passed = False
                    raw_error = "AttributeError: module 'pennylane' has no attribute 'ExpvalCost' (deprecated API removed)"
            elif pattern == "SEMANTIC_RETURN_PROBS":
                executed = True
                passed = False
                raw_error = "AssertionError: expected scalar expectation value, got probability vector"
            elif pattern in {"MODERN_QNODE_COST", "MODERN_SIMPLE_EXPVAL"}:
                stdout = "OK"
            else:
                executed = False
                passed = False
                raw_error = f"RuntimeError: Unknown pennylane mock pattern {pattern}"
        else:
            executed = False
            passed = False
            raw_error = f"Unsupported SDK: {task.sdk}"

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return ExecutionRecord(
            generation_id=generation.generation_id,
            run_name=generation.run_name,
            task_id=task.task_id,
            source_benchmark=task.source_benchmark,
            sdk=task.sdk,
            target_version=generation.target_version,
            eval_version=eval_version,
            model=generation.model,
            strategy=generation.strategy,
            sample_index=generation.sample_index,
            backend=self.backend_name,
            executed=executed,
            passed=passed,
            error_category=classify_error(raw_error, generation.code),
            raw_error=raw_error,
            stdout=stdout,
            stderr=stderr,
            code_pattern=pattern,
            elapsed_ms=elapsed_ms,
        )


class VenvExecutionBackend(ExecutionBackend):
    backend_name = "venv"

    def __init__(self, env_root: Path, package_matrix: Dict[str, Dict[str, Dict[str, object]]]) -> None:
        self.env_root = ensure_dir(env_root)
        self.package_matrix = package_matrix

    def execute(self, generation: GenerationRecord, task: Task, eval_version: str) -> ExecutionRecord:
        start = time.perf_counter()
        env_python = self._ensure_env(task.sdk, eval_version)
        with tempfile.TemporaryDirectory(prefix="qdrift-run-") as tmp:
            tmpdir = Path(tmp)
            candidate_path = tmpdir / "candidate.py"
            candidate_path.write_text(generation.code, encoding="utf-8")
            harness_path = tmpdir / "harness.py"
            harness_path.write_text(self._build_harness(task.entrypoint, task.tests), encoding="utf-8")
            result = subprocess.run(
                [str(env_python), str(harness_path)],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=180,
            )
        raw_error = result.stderr.strip() or result.stdout.strip()
        executed = result.returncode == 0 or "AssertionError" in raw_error
        passed = result.returncode == 0
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return ExecutionRecord(
            generation_id=generation.generation_id,
            run_name=generation.run_name,
            task_id=task.task_id,
            source_benchmark=task.source_benchmark,
            sdk=task.sdk,
            target_version=generation.target_version,
            eval_version=eval_version,
            model=generation.model,
            strategy=generation.strategy,
            sample_index=generation.sample_index,
            backend=self.backend_name,
            executed=executed,
            passed=passed,
            error_category=classify_error(raw_error, generation.code),
            raw_error=raw_error,
            stdout=result.stdout,
            stderr=result.stderr,
            code_pattern=extract_code_pattern(generation.code),
            elapsed_ms=elapsed_ms,
        )

    def _ensure_env(self, sdk: str, version: str) -> Path:
        env_dir = self.env_root / f"{sdk}-{version}"
        python_path = env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if python_path.exists():
            return python_path

        spec = self.package_matrix.get(sdk, {}).get(version)
        if not spec:
            raise RuntimeError(f"No package matrix entry for {sdk} {version}")
        requested_python = str(spec.get("python", "")).strip()
        creator = shutil.which(f"python{requested_python}") if requested_python else None
        creator = creator or sys.executable

        subprocess.run([creator, "-m", "venv", str(env_dir)], check=True, timeout=300)
        pip_path = env_dir / ("Scripts/pip.exe" if os.name == "nt" else "bin/pip")
        packages = list(spec.get("pip", [])) + ["pytest>=8.0.0"]
        subprocess.run([str(pip_path), "install", *packages], check=True, timeout=900)
        return python_path

    @staticmethod
    def _build_harness(entrypoint: str, tests: list[str]) -> str:
        tests_block = "\n".join(tests)
        return textwrap.dedent(
            f"""
            import traceback
            import candidate as candidate_module

            candidate = getattr(candidate_module, {entrypoint!r})

            try:
                {textwrap.indent(tests_block, '    ')}
            except Exception:
                traceback.print_exc()
                raise
            """
        ).strip() + "\n"


class DockerExecutionBackend(ExecutionBackend):
    backend_name = "docker"

    def __init__(self, package_matrix: Dict[str, Dict[str, Dict[str, object]]]) -> None:
        self.package_matrix = package_matrix

    def execute(self, generation: GenerationRecord, task: Task, eval_version: str) -> ExecutionRecord:
        if shutil.which("docker") is None:
            raise RuntimeError("Docker is not installed. Use the mock or venv backend, or install Docker.")
        start = time.perf_counter()
        spec = self.package_matrix.get(task.sdk, {}).get(eval_version)
        if not spec:
            raise RuntimeError(f"No package matrix entry for {task.sdk} {eval_version}")

        with tempfile.TemporaryDirectory(prefix="qdrift-docker-") as tmp:
            tmpdir = Path(tmp)
            candidate_path = tmpdir / "candidate.py"
            candidate_path.write_text(generation.code, encoding="utf-8")
            harness_path = tmpdir / "harness.py"
            harness_path.write_text(VenvExecutionBackend._build_harness(task.entrypoint, task.tests), encoding="utf-8")
            dockerfile = tmpdir / "Dockerfile"
            dockerfile.write_text(
                textwrap.dedent(
                    f"""
                    FROM python:{spec['python']}-slim
                    WORKDIR /app
                    COPY candidate.py harness.py ./
                    RUN pip install {' '.join(spec['pip'])} pytest>=8.0.0
                    CMD ["python", "harness.py"]
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            tag = f"qdrift-{task.sdk}-{eval_version.replace('.', '-')}-temp"
            subprocess.run(["docker", "build", "-t", tag, str(tmpdir)], check=True, timeout=1200)
            result = subprocess.run(["docker", "run", "--rm", tag], capture_output=True, text=True, timeout=300)
            subprocess.run(["docker", "image", "rm", "-f", tag], check=False, timeout=300)

        raw_error = result.stderr.strip() or result.stdout.strip()
        executed = result.returncode == 0 or "AssertionError" in raw_error
        passed = result.returncode == 0
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return ExecutionRecord(
            generation_id=generation.generation_id,
            run_name=generation.run_name,
            task_id=task.task_id,
            source_benchmark=task.source_benchmark,
            sdk=task.sdk,
            target_version=generation.target_version,
            eval_version=eval_version,
            model=generation.model,
            strategy=generation.strategy,
            sample_index=generation.sample_index,
            backend=self.backend_name,
            executed=executed,
            passed=passed,
            error_category=classify_error(raw_error, generation.code),
            raw_error=raw_error,
            stdout=result.stdout,
            stderr=result.stderr,
            code_pattern=extract_code_pattern(generation.code),
            elapsed_ms=elapsed_ms,
        )



def extract_code_pattern(code: str) -> str:
    match = MOCK_PATTERN_RE.search(code)
    return match.group(1) if match else "UNKNOWN"



def classify_error(raw_error: str, code: str = "") -> str:
    text = f"{raw_error}\n{code}".lower()
    if not raw_error:
        return "None"
    if "deprecated" in text or "expvalcost" in text:
        return "Deprecated API"
    if "cannot import name" in text or "no module named" in text or "namespace" in text:
        return "Module relocation"
    if "unexpected keyword" in text or "too many positional" in text or "missing 1 required positional" in text:
        return "Signature mismatch"
    if "has no attribute" in text or "nameerror" in text or "not available" in text:
        return "Missing or renamed symbol"
    return "Semantic runtime error"



def load_package_matrix(path: Path) -> Dict[str, Dict[str, Dict[str, object]]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    matrix: Dict[str, Dict[str, Dict[str, object]]] = {}
    for sdk, rows in payload.items():
        matrix[sdk] = {}
        for row in rows:
            matrix[sdk][row["version"]] = row
    return matrix
