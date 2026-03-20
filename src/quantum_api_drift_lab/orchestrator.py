from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from quantum_api_drift_lab.analysis.metrics import compute_metric_tables, records_to_frame, save_figures, save_tables
from quantum_api_drift_lab.analysis.report_builder import build_report
from quantum_api_drift_lab.benchmark.loaders import load_tasks
from quantum_api_drift_lab.config import ExperimentConfig, load_experiment_config
from quantum_api_drift_lab.execution.backends import (
    DockerExecutionBackend,
    MockExecutionBackend,
    VenvExecutionBackend,
    load_package_matrix,
)
from quantum_api_drift_lab.llm.providers import get_provider
from quantum_api_drift_lab.rag.retriever import SnippetRetriever
from quantum_api_drift_lab.rewrite.engine import RewriteEngine
from quantum_api_drift_lab.types import ArtifactSummary, ExecutionRecord, GenerationRecord, ModelConfig, Task
from quantum_api_drift_lab.utils.io import ensure_dir, slugify, write_jsonl


LogFn = Callable[[str], None]


class ConfigurationError(RuntimeError):
    pass



def run_experiment(
    config_path: Path,
    *,
    override_mode: Optional[str] = None,
    override_backend: Optional[str] = None,
    override_run_name: Optional[str] = None,
    enabled_model_names: Optional[Sequence[str]] = None,
    enabled_strategies: Optional[Sequence[str]] = None,
    log_fn: Optional[LogFn] = None,
) -> ArtifactSummary:
    log = log_fn or (lambda message: None)
    config = load_experiment_config(config_path)
    if override_mode:
        config.mode = override_mode
    if override_backend:
        config.isolation_backend = override_backend
    if override_run_name:
        config.run_name = override_run_name
    if enabled_model_names:
        config.models = [model for model in config.models if model.name in enabled_model_names]
    if enabled_strategies:
        config.strategies = [strategy for strategy in config.strategies if strategy in enabled_strategies]
    config.validate()

    _validate_runtime_requirements(config)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = ensure_dir(config.resolve(config.outputs_root) / f"{slugify(config.run_name)}_{timestamp}")
    figures_dir = ensure_dir(run_dir / "figures")
    log(f"Run directory: {run_dir}")

    task_paths = [config.resolve(path) for path in config.benchmark_files]
    tasks = load_tasks(task_paths)
    task_map: Dict[str, Task] = {task.task_id: task for task in tasks}
    log(f"Loaded {len(tasks)} tasks from {len(task_paths)} benchmark file(s).")

    retriever = SnippetRetriever(config.resolve(config.docs_root))
    rewrite_engine = RewriteEngine(config.resolve(config.rewrite_rules_path))
    package_matrix = load_package_matrix(config.resolve("configs/sdk_matrix.yaml"))
    backend = _create_backend(config, run_dir, package_matrix)
    log(f"Isolation backend: {backend.backend_name}")

    providers = {model.name: get_provider(model, config.mode) for model in config.enabled_models}
    generations: List[GenerationRecord] = []
    executions: List[ExecutionRecord] = []

    generation_strategies = [strategy for strategy in config.strategies if strategy != "rewrite_baseline"]
    for model in config.enabled_models:
        provider = providers[model.name]
        log(f"Using model: {model.name} ({model.family or model.provider})")
        for task in tasks:
            log(f"Preparing task {task.task_id} [{task.sdk} {task.base_version}] from {task.source_benchmark}")
            for strategy in generation_strategies:
                snippets = retriever.retrieve(task, task.base_version, top_k=2) if strategy == "rag_docs" else []
                if strategy == "rag_docs":
                    log(f"  Retrieved {len(snippets)} documentation snippet(s) for {task.sdk} {task.base_version}")
                for sample_index in range(1, config.k_samples + 1):
                    response = provider.generate(task, task.base_version, strategy, sample_index, snippets)
                    generation_id = _generation_id(task, model.name, strategy, sample_index, task.base_version)
                    generation = GenerationRecord(
                        generation_id=generation_id,
                        run_name=config.run_name,
                        task_id=task.task_id,
                        source_benchmark=task.source_benchmark,
                        sdk=task.sdk,
                        target_version=task.base_version,
                        eval_versions=task.eval_versions,
                        model=model.name,
                        strategy=strategy,
                        sample_index=sample_index,
                        prompt=response.prompt,
                        code=response.code,
                        docs_sources=response.docs_sources,
                        metadata=response.metadata,
                    )
                    generations.append(generation)
                    for eval_version in task.eval_versions:
                        execution = backend.execute(generation, task, eval_version)
                        executions.append(execution)
                        status = "PASS" if execution.passed else ("EXEC-FAIL" if not execution.executed else "TEST-FAIL")
                        log(f"    [{strategy}] sample={sample_index} eval={eval_version} -> {status} ({execution.error_category})")

    if "rewrite_baseline" in config.strategies:
        log("Applying rewrite baseline to broken vanilla programs.")
        vanilla_generations = {generation.generation_id: generation for generation in generations if generation.strategy == "vanilla"}
        broken_vanilla = [
            record
            for record in executions
            if record.strategy == "vanilla" and not record.passed and record.eval_version != record.target_version
        ]
        for failed in broken_vanilla:
            original_generation = vanilla_generations[failed.generation_id]
            task = task_map[failed.task_id]
            rewritten_code, rule_id = rewrite_engine.rewrite(task.sdk, failed.eval_version, original_generation.code)
            if not rule_id:
                log(f"    No rewrite rule matched {failed.task_id} on {failed.eval_version}")
                continue
            rewrite_generation = GenerationRecord(
                generation_id=f"{original_generation.generation_id}|rewrite|{failed.eval_version}",
                run_name=config.run_name,
                task_id=task.task_id,
                source_benchmark=task.source_benchmark,
                sdk=task.sdk,
                target_version=task.base_version,
                eval_versions=[task.base_version, failed.eval_version],
                model=failed.model,
                strategy="rewrite_baseline",
                sample_index=failed.sample_index,
                prompt=original_generation.prompt,
                code=rewritten_code,
                docs_sources=original_generation.docs_sources,
                metadata={"rewrite_rule": rule_id, "source_generation_id": original_generation.generation_id},
            )
            generations.append(rewrite_generation)
            for eval_version in [task.base_version, failed.eval_version]:
                rewrite_execution = backend.execute(rewrite_generation, task, eval_version)
                rewrite_execution.rewrite_rule = rule_id
                rewrite_execution.rewritten_from_strategy = "vanilla"
                executions.append(rewrite_execution)
                status = "PASS" if rewrite_execution.passed else ("EXEC-FAIL" if not rewrite_execution.executed else "TEST-FAIL")
                log(f"    [rewrite_baseline] {task.task_id} eval={eval_version} -> {status} ({rule_id})")

    generations_path = run_dir / "generations.jsonl"
    executions_path = run_dir / "executions.jsonl"
    write_jsonl(generations_path, generations)
    write_jsonl(executions_path, executions)
    log(f"Wrote {len(generations)} generation record(s) and {len(executions)} execution record(s).")

    frame = records_to_frame(executions)
    summary, drift, rag_gain, error_table = compute_metric_tables(frame)
    table_paths = save_tables(summary, drift, rag_gain, error_table, run_dir)
    figure_paths = save_figures(summary, drift, rag_gain, error_table, figures_dir, config.figures)
    report_html = run_dir / "report.html"
    figure_rel_paths = [Path("figures") / path.name for path in figure_paths]
    build_report(report_html, summary, drift, rag_gain, error_table, figure_rel_paths, config.run_name)
    log(f"Generated report: {report_html}")

    return ArtifactSummary(
        run_dir=str(run_dir),
        generations_path=str(generations_path),
        executions_path=str(executions_path),
        summary_csv=str(table_paths["summary_csv"]),
        drift_csv=str(table_paths["drift_csv"]),
        rag_gain_csv=str(table_paths["rag_gain_csv"]),
        error_csv=str(table_paths["error_csv"]),
        report_html=str(report_html),
        figure_paths=[str(path) for path in figure_paths],
    )



def _validate_runtime_requirements(config: ExperimentConfig) -> None:
    if config.mode == "real":
        for model in config.enabled_models:
            if model.provider == "openai":
                import os
                if not os.getenv("OPENAI_API_KEY"):
                    raise ConfigurationError("OPENAI_API_KEY is missing for real-mode GPT-5 runs.")
            if model.provider == "openai_compatible":
                import os
                if not os.getenv("QWEN_BASE_URL"):
                    raise ConfigurationError("QWEN_BASE_URL is missing for real-mode Qwen runs.")



def _create_backend(config: ExperimentConfig, run_dir: Path, package_matrix: Dict[str, Dict[str, Dict[str, object]]]):
    backend_name = config.isolation_backend.lower()
    if backend_name == "mock":
        return MockExecutionBackend()
    if backend_name == "venv":
        return VenvExecutionBackend(run_dir / "envs", package_matrix)
    if backend_name == "docker":
        return DockerExecutionBackend(package_matrix)
    raise ValueError(f"Unsupported backend: {config.isolation_backend}")



def _generation_id(task: Task, model_name: str, strategy: str, sample_index: int, target_version: str) -> str:
    safe_model = model_name.replace("/", "__")
    return f"{task.task_id}|{safe_model}|{strategy}|sample{sample_index}|{target_version}"
