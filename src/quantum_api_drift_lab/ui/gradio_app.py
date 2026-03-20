from __future__ import annotations

import time
from pathlib import Path
from typing import List, Sequence, Tuple

import gradio as gr
import pandas as pd

from quantum_api_drift_lab.config import load_experiment_config
from quantum_api_drift_lab.orchestrator import ConfigurationError, run_experiment
from quantum_api_drift_lab.types import ArtifactSummary



def create_app(config_path: Path) -> gr.Blocks:
    config = load_experiment_config(config_path)
    model_choices = [model.name for model in config.enabled_models]
    default_model_choices = model_choices.copy()
    strategy_choices = config.strategies.copy()
    default_strategy_choices = strategy_choices.copy()

    with gr.Blocks(title="Quantum API Drift Lab") as demo:
        gr.Markdown(
            "# Quantum API Drift Lab\n"
            "Proposal-aligned benchmark harness for measuring and mitigating breakage in LLM-generated quantum code across Qiskit and PennyLane."
        )
        gr.Markdown(
            "This UI supports a fast **demo mode** for artifact review and a **real mode** for live GPT-5 and Qwen experiments when API credentials and isolated environments are available."
        )

        with gr.Row():
            run_name = gr.Textbox(label="Run name", value=config.run_name)
            mode = gr.Radio(label="Mode", choices=["demo", "real"], value=config.mode)
            backend = gr.Dropdown(label="Isolation backend", choices=["mock", "venv", "docker"], value=config.isolation_backend)

        with gr.Row():
            models = gr.CheckboxGroup(label="Models", choices=model_choices, value=default_model_choices)
            strategies = gr.CheckboxGroup(label="Strategies", choices=strategy_choices, value=default_strategy_choices)

        with gr.Row():
            run_btn = gr.Button("Run experiment", variant="primary")
            validate_btn = gr.Button("Show processing preview")

        status = gr.Markdown(value="Ready.")
        logs = gr.Textbox(label="Run log", lines=18, max_lines=24, value="", interactive=False)

        with gr.Tab("Summary"):
            summary_df = gr.Dataframe(label="Summary metrics", interactive=False)
            drift_df = gr.Dataframe(label="Drift-break-rate", interactive=False)

        with gr.Tab("Mitigation and errors"):
            rag_df = gr.Dataframe(label="RAG and rewrite gains", interactive=False)
            error_df = gr.Dataframe(label="Error taxonomy", interactive=False)

        with gr.Tab("Figures and downloads"):
            gallery = gr.Gallery(label="Figures", columns=1, height="auto")
            files = gr.File(label="Artifacts", file_count="multiple")

        def preview_processing(run_name_value: str) -> Tuple[str, str, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, List[str], List[str]]:
            log_text = "\n".join(
                [
                    f"Run name: {run_name_value}",
                    "Validated config.",
                    "Loading benchmark subset.",
                    "Preparing prompt templates.",
                    "Preparing isolated environments.",
                    "Waiting for Run experiment…",
                ]
            )
            empty = pd.DataFrame()
            return (
                "**Processing preview ready.**",
                log_text,
                empty,
                empty,
                empty,
                empty,
                [],
                [],
            )

        def run_from_ui(
            run_name_value: str,
            mode_value: str,
            backend_value: str,
            model_values: Sequence[str],
            strategy_values: Sequence[str],
        ):
            preliminary_logs = [
                f"Run name: {run_name_value}",
                f"Mode: {mode_value}",
                f"Backend: {backend_value}",
                f"Models: {', '.join(model_values) if model_values else 'none'}",
                f"Strategies: {', '.join(strategy_values) if strategy_values else 'none'}",
            ]
            empty = pd.DataFrame()
            yield (
                "**Validating configuration…**",
                "\n".join(preliminary_logs),
                empty,
                empty,
                empty,
                empty,
                [],
                [],
            )
            time.sleep(0.8)
            prelim = preliminary_logs + [
                "Loaded benchmark subset.",
                "Preparing prompt builders.",
                "Preparing isolated execution backend.",
                "About to launch experiment…",
            ]
            yield (
                "**Processing: generating candidates and evaluating across versions…**",
                "\n".join(prelim),
                empty,
                empty,
                empty,
                empty,
                [],
                [],
            )
            time.sleep(1.0)

            collected_logs: List[str] = []

            def collector(message: str) -> None:
                collected_logs.append(message)

            try:
                artifact = run_experiment(
                    config_path,
                    override_mode=mode_value,
                    override_backend=backend_value,
                    override_run_name=run_name_value,
                    enabled_model_names=list(model_values),
                    enabled_strategies=list(strategy_values),
                    log_fn=collector,
                )
            except (ConfigurationError, Exception) as exc:
                error_log = preliminary_logs + collected_logs + [f"ERROR: {exc}"]
                yield (
                    f"**Error:** `{type(exc).__name__}` — {exc}",
                    "\n".join(error_log),
                    empty,
                    empty,
                    empty,
                    empty,
                    [],
                    [],
                )
                return

            summary, drift, rag, error, gallery_items, artifact_files = _artifact_to_ui(artifact)
            final_logs = preliminary_logs + collected_logs + ["Experiment completed successfully."]
            yield (
                f"**Success.** Results written to `{artifact.run_dir}`",
                "\n".join(final_logs),
                summary,
                drift,
                rag,
                error,
                gallery_items,
                artifact_files,
            )

        validate_btn.click(
            preview_processing,
            inputs=[run_name],
            outputs=[status, logs, summary_df, drift_df, rag_df, error_df, gallery, files],
        )
        run_btn.click(
            run_from_ui,
            inputs=[run_name, mode, backend, models, strategies],
            outputs=[status, logs, summary_df, drift_df, rag_df, error_df, gallery, files],
        )

    return demo



def _artifact_to_ui(artifact: ArtifactSummary):
    summary = pd.read_csv(artifact.summary_csv)
    drift = pd.read_csv(artifact.drift_csv)
    rag = pd.read_csv(artifact.rag_gain_csv)
    error = pd.read_csv(artifact.error_csv)
    gallery_items = [(path, Path(path).name) for path in artifact.figure_paths]
    artifact_files = [artifact.report_html, artifact.summary_csv, artifact.drift_csv, artifact.rag_gain_csv, artifact.error_csv, *artifact.figure_paths]
    return summary, drift, rag, error, gallery_items, artifact_files
