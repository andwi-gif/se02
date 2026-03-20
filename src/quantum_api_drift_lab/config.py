from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

import yaml

from quantum_api_drift_lab.types import ModelConfig


@dataclass
class ExperimentConfig:
    run_name: str
    mode: str
    benchmark_files: List[str]
    sdk_versions: Dict[str, List[str]]
    models: List[ModelConfig]
    strategies: List[str]
    k_samples: int
    isolation_backend: str
    docs_root: str
    rewrite_rules_path: str
    outputs_root: str = "outputs"
    figures: Dict[str, str] = field(default_factory=dict)
    project_root: Path = field(default=Path("."))

    @property
    def enabled_models(self) -> List[ModelConfig]:
        return [model for model in self.models if model.enabled]

    def resolve(self, relative_path: str) -> Path:
        return (self.project_root / relative_path).resolve()

    def validate(self) -> None:
        if self.mode not in {"demo", "real"}:
            raise ValueError(f"Unsupported mode: {self.mode}")
        if self.k_samples < 1:
            raise ValueError("k_samples must be >= 1")
        if not self.enabled_models:
            raise ValueError("At least one model must be enabled")
        if not self.strategies:
            raise ValueError("At least one strategy must be enabled")
        for sdk, versions in self.sdk_versions.items():
            if not versions:
                raise ValueError(f"No versions configured for {sdk}")


def load_experiment_config(config_path: Path) -> ExperimentConfig:
    project_root = config_path.resolve().parents[1]
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    models = [ModelConfig(**row) for row in payload.get("models", [])]
    config = ExperimentConfig(
        run_name=payload["run_name"],
        mode=payload["mode"],
        benchmark_files=payload["benchmark_files"],
        sdk_versions=payload["sdk_versions"],
        models=models,
        strategies=payload["strategies"],
        k_samples=int(payload["k_samples"]),
        isolation_backend=payload["isolation_backend"],
        docs_root=payload["docs_root"],
        rewrite_rules_path=payload["rewrite_rules_path"],
        outputs_root=payload.get("outputs_root", "outputs"),
        figures=payload.get("figures", {}),
        project_root=project_root,
    )
    config.validate()
    return config
