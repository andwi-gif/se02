from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ModelConfig:
    name: str
    provider: str
    family: str = ""
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Task:
    task_id: str
    source_benchmark: str
    sdk: str
    base_version: str
    eval_versions: List[str]
    categories: List[str]
    prompt: str
    entrypoint: str
    tests: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Snippet:
    sdk: str
    version: str
    source_url: str
    summary: str
    retrieval_terms: str
    local_path: str
    raw_text: str

    def prompt_text(self) -> str:
        return f"Source: {self.source_url}\nSummary: {self.summary}\nKeywords: {self.retrieval_terms}"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GenerationRecord:
    generation_id: str
    run_name: str
    task_id: str
    source_benchmark: str
    sdk: str
    target_version: str
    eval_versions: List[str]
    model: str
    strategy: str
    sample_index: int
    prompt: str
    code: str
    docs_sources: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionRecord:
    generation_id: str
    run_name: str
    task_id: str
    source_benchmark: str
    sdk: str
    target_version: str
    eval_version: str
    model: str
    strategy: str
    sample_index: int
    backend: str
    executed: bool
    passed: bool
    error_category: str
    raw_error: str
    stdout: str = ""
    stderr: str = ""
    rewrite_rule: Optional[str] = None
    rewritten_from_strategy: Optional[str] = None
    code_pattern: str = ""
    elapsed_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ArtifactSummary:
    run_dir: str
    generations_path: str
    executions_path: str
    summary_csv: str
    drift_csv: str
    rag_gain_csv: str
    error_csv: str
    report_html: str
    figure_paths: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
