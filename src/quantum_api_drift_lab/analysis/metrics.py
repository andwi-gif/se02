from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from quantum_api_drift_lab.types import ExecutionRecord
from quantum_api_drift_lab.utils.io import ensure_dir


METRIC_GROUP = ["sdk", "target_version", "eval_version", "model", "strategy"]



def records_to_frame(records: Iterable[ExecutionRecord]) -> pd.DataFrame:
    rows = [record.to_dict() for record in records]
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)



def compute_metric_tables(frame: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if frame.empty:
        empty = pd.DataFrame()
        return empty, empty, empty, empty

    first = frame[frame["sample_index"] == 1].copy()
    summary = (
        first.groupby(METRIC_GROUP, dropna=False)
        .agg(tasks=("task_id", "nunique"), exec_at_1=("executed", "mean"), pass_at_1=("passed", "mean"))
        .reset_index()
    )
    sample_summary = (
        frame.groupby(METRIC_GROUP, dropna=False)
        .agg(
            sample_exec_rate=("executed", "mean"),
            sample_pass_rate=("passed", "mean"),
            samples=("generation_id", "count"),
        )
        .reset_index()
    )
    summary = summary.merge(sample_summary, on=METRIC_GROUP, how="left")

    drift_rows: List[Dict[str, object]] = []
    for (sdk, target_version, model, strategy), group in first.groupby(["sdk", "target_version", "model", "strategy"], dropna=False):
        base = group[group["eval_version"] == target_version][["task_id", "executed"]].rename(columns={"executed": "base_executed"})
        for eval_version, eval_group in group.groupby("eval_version", dropna=False):
            if eval_version == target_version:
                continue
            merged = eval_group[["task_id", "executed"]].merge(base, on="task_id", how="left")
            eligible = merged[merged["base_executed"] == True]
            denominator = len(eligible)
            broken = int(((eligible["executed"] == False)).sum()) if denominator else 0
            drift_rows.append(
                {
                    "sdk": sdk,
                    "target_version": target_version,
                    "eval_version": eval_version,
                    "model": model,
                    "strategy": strategy,
                    "eligible_programs": denominator,
                    "broken_after_upgrade": broken,
                    "drift_break_rate": (broken / denominator) if denominator else np.nan,
                }
            )
    drift = pd.DataFrame(drift_rows)

    rag_gain = pd.DataFrame()
    if not drift.empty:
        pivot = drift.pivot_table(
            index=["sdk", "target_version", "eval_version", "model"],
            columns="strategy",
            values="drift_break_rate",
            aggfunc="mean",
        ).reset_index()
        if "vanilla" in pivot.columns and "rag_docs" in pivot.columns:
            pivot["rag_gain"] = (pivot["vanilla"] - pivot["rag_docs"]) / pivot["vanilla"].replace(0, np.nan)
        else:
            pivot["rag_gain"] = np.nan
        if "vanilla" in pivot.columns and "rewrite_baseline" in pivot.columns:
            pivot["rewrite_gain"] = (pivot["vanilla"] - pivot["rewrite_baseline"]) / pivot["vanilla"].replace(0, np.nan)
        else:
            pivot["rewrite_gain"] = np.nan
        rag_gain = pivot

    error_df = frame[frame["error_category"] != "None"].copy()
    if error_df.empty:
        error_table = pd.DataFrame(columns=["sdk", "model", "strategy", "error_category", "count"])
    else:
        error_table = (
            error_df.groupby(["sdk", "model", "strategy", "error_category"], dropna=False)
            .size()
            .reset_index(name="count")
            .sort_values(["sdk", "model", "strategy", "count"], ascending=[True, True, True, False])
        )

    return summary, drift, rag_gain, error_table



def save_tables(summary: pd.DataFrame, drift: pd.DataFrame, rag_gain: pd.DataFrame, error_table: pd.DataFrame, run_dir: Path) -> Dict[str, Path]:
    ensure_dir(run_dir)
    outputs = {
        "summary_csv": run_dir / "summary_metrics.csv",
        "drift_csv": run_dir / "drift_break_rate.csv",
        "rag_gain_csv": run_dir / "rag_gain.csv",
        "error_csv": run_dir / "error_taxonomy.csv",
    }
    summary.to_csv(outputs["summary_csv"], index=False)
    drift.to_csv(outputs["drift_csv"], index=False)
    rag_gain.to_csv(outputs["rag_gain_csv"], index=False)
    error_table.to_csv(outputs["error_csv"], index=False)
    return outputs



def save_figures(
    summary: pd.DataFrame,
    drift: pd.DataFrame,
    rag_gain: pd.DataFrame,
    error_table: pd.DataFrame,
    figures_dir: Path,
    figure_names: Dict[str, str],
) -> List[Path]:
    ensure_dir(figures_dir)
    outputs: List[Path] = []

    exec_path = figures_dir / figure_names.get("exec_plot", "exec_at_1_by_eval_version.png")
    _bar_metric_plot(summary, value_col="exec_at_1", title="Exec@1 by evaluation version", ylabel="Exec@1", path=exec_path)
    outputs.append(exec_path)

    pass_path = figures_dir / figure_names.get("pass_plot", "pass_at_1_by_eval_version.png")
    _bar_metric_plot(summary, value_col="pass_at_1", title="Pass@1 by evaluation version", ylabel="Pass@1", path=pass_path)
    outputs.append(pass_path)

    drift_path = figures_dir / figure_names.get("drift_plot", "drift_break_rate_heatmap.png")
    _drift_plot(drift, drift_path)
    outputs.append(drift_path)

    rag_path = figures_dir / figure_names.get("rag_plot", "rag_gain.png")
    _rag_gain_plot(rag_gain, rag_path)
    outputs.append(rag_path)

    error_path = figures_dir / figure_names.get("error_plot", "error_taxonomy.png")
    _error_plot(error_table, error_path)
    outputs.append(error_path)

    return outputs



def _bar_metric_plot(frame: pd.DataFrame, value_col: str, title: str, ylabel: str, path: Path) -> None:
    plt.figure(figsize=(14, 6))
    if frame.empty:
        plt.text(0.5, 0.5, "No data", ha="center", va="center")
        plt.axis("off")
    else:
        plot = frame.copy()
        plot["label"] = plot.apply(
            lambda row: f"{row['sdk']}\n{row['target_version']}→{row['eval_version']}\n{row['model'].split('/')[-1]}",
            axis=1,
        )
        strategies = list(plot["strategy"].dropna().unique())
        x = np.arange(len(plot["label"].unique()))
        width = 0.25
        label_order = list(dict.fromkeys(plot["label"].tolist()))
        for idx, strategy in enumerate(strategies):
            subset = plot[plot["strategy"] == strategy].set_index("label").reindex(label_order)
            plt.bar(x + (idx - (len(strategies) - 1) / 2) * width, subset[value_col].fillna(0), width=width, label=strategy)
        plt.xticks(x, label_order, rotation=45, ha="right")
        plt.ylim(0, 1.05)
        plt.ylabel(ylabel)
        plt.title(title)
        plt.legend()
        plt.tight_layout()
    plt.savefig(path, bbox_inches="tight")
    plt.close()



def _drift_plot(frame: pd.DataFrame, path: Path) -> None:
    plt.figure(figsize=(14, 6))
    if frame.empty:
        plt.text(0.5, 0.5, "No drift data", ha="center", va="center")
        plt.axis("off")
    else:
        plot = frame.copy()
        plot["label"] = plot.apply(
            lambda row: f"{row['sdk']}\n{row['target_version']}→{row['eval_version']}\n{row['model'].split('/')[-1]}",
            axis=1,
        )
        strategies = list(plot["strategy"].dropna().unique())
        x = np.arange(len(plot["label"].unique()))
        width = 0.25
        label_order = list(dict.fromkeys(plot["label"].tolist()))
        for idx, strategy in enumerate(strategies):
            subset = plot[plot["strategy"] == strategy].set_index("label").reindex(label_order)
            plt.bar(x + (idx - (len(strategies) - 1) / 2) * width, subset["drift_break_rate"].fillna(0), width=width, label=strategy)
        plt.xticks(x, label_order, rotation=45, ha="right")
        plt.ylim(0, 1.05)
        plt.ylabel("Drift-break-rate")
        plt.title("Cross-version drift-break-rate")
        plt.legend()
        plt.tight_layout()
    plt.savefig(path, bbox_inches="tight")
    plt.close()



def _rag_gain_plot(frame: pd.DataFrame, path: Path) -> None:
    plt.figure(figsize=(14, 6))
    if frame.empty:
        plt.text(0.5, 0.5, "No RAG gain data", ha="center", va="center")
        plt.axis("off")
    else:
        plot = frame.copy()
        plot["label"] = plot.apply(
            lambda row: f"{row['sdk']}\n{row['target_version']}→{row['eval_version']}\n{row['model'].split('/')[-1]}",
            axis=1,
        )
        x = np.arange(len(plot))
        width = 0.35
        plt.bar(x - width / 2, plot["rag_gain"].fillna(0), width=width, label="RAG gain")
        if "rewrite_gain" in plot.columns:
            plt.bar(x + width / 2, plot["rewrite_gain"].fillna(0), width=width, label="Rewrite gain")
        plt.xticks(x, plot["label"], rotation=45, ha="right")
        plt.ylabel("Relative reduction")
        plt.title("Mitigation effectiveness vs vanilla drift-break-rate")
        plt.axhline(0.0, linewidth=1)
        plt.legend()
        plt.tight_layout()
    plt.savefig(path, bbox_inches="tight")
    plt.close()



def _error_plot(frame: pd.DataFrame, path: Path) -> None:
    plt.figure(figsize=(14, 6))
    if frame.empty:
        plt.text(0.5, 0.5, "No error taxonomy data", ha="center", va="center")
        plt.axis("off")
    else:
        plot = frame.copy()
        plot["label"] = plot.apply(lambda row: f"{row['sdk']}\n{row['model'].split('/')[-1]}\n{row['strategy']}", axis=1)
        pivot = plot.pivot_table(index="label", columns="error_category", values="count", aggfunc="sum", fill_value=0)
        bottom = np.zeros(len(pivot))
        x = np.arange(len(pivot))
        for column in pivot.columns:
            values = pivot[column].to_numpy()
            plt.bar(x, values, bottom=bottom, label=column)
            bottom += values
        plt.xticks(x, pivot.index, rotation=45, ha="right")
        plt.ylabel("Count")
        plt.title("Failure taxonomy")
        plt.legend()
        plt.tight_layout()
    plt.savefig(path, bbox_inches="tight")
    plt.close()
