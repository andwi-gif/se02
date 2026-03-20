# Proposal alignment matrix

This document maps the proposal methodology to concrete code in this artifact.

## 5.1 SDK and Version Selection

**Proposal requirement**
- Evaluate Qiskit and PennyLane.
- Use 3–4 versions spanning about 2–3 years with at least one breaking change.

**Implemented here**
- `configs/sdk_matrix.yaml`
- Qiskit demo matrix: `0.45.3`, `1.0.2`, `2.0.3`
- PennyLane demo matrix: `0.32.0`, `0.35.1`, `0.44.1`
- Isolation backends: `MockExecutionBackend`, `VenvExecutionBackend`, `DockerExecutionBackend` in `src/quantum_api_drift_lab/execution/backends.py`

## 5.2 Task Selection

**Proposal requirement**
- Use tasks from QCircuitBench and Qiskit HumanEval.

**Implemented here**
- Demo subset files:
  - `data/demo/tasks/qiskit_humaneval_demo.jsonl`
  - `data/demo/tasks/qcircuitbench_demo.jsonl`
- Loader: `src/quantum_api_drift_lab/benchmark/loaders.py`
- Full-scale config placeholder:
  - `configs/experiment.full.yaml`
  - expects real external benchmark subsets under `data/external/`

## 5.3 Models and Generation Settings

**Proposal requirement**
- One strong proprietary code-capable model
- One open-source code model
- `k = 3`
- Vanilla, RAG-docs, Rewrite baseline

**Implemented here**
- Models configured in `configs/experiment.demo.yaml` and `configs/experiment.full.yaml`
- Providers in `src/quantum_api_drift_lab/llm/providers.py`
- Defaults:
  - proprietary: `gpt-5`
  - open source: `Qwen/Qwen2.5-Coder-32B-Instruct`
- Sampling: `k_samples: 3`
- Strategies:
  - `vanilla`
  - `rag_docs`
  - `rewrite_baseline`

## 5.4 Multi-Version Execution Harness

**Proposal requirement**
- Isolated installation per target SDK version
- Attempt execution
- Capture compilation/runtime errors
- Run tests where available

**Implemented here**
- Orchestration: `src/quantum_api_drift_lab/orchestrator.py`
- Backends: `src/quantum_api_drift_lab/execution/backends.py`
- Output artifacts:
  - `generations.jsonl`
  - `executions.jsonl`
- Error taxonomy:
  - Missing or renamed symbol
  - Module relocation
  - Signature mismatch
  - Deprecated API
  - Semantic runtime error

## 5.5 Analysis

**Proposal requirement**
- Cross-version breakage analysis
- Version-gap sensitivity analysis
- Qiskit vs PennyLane comparison
- RAG effectiveness evaluation

**Implemented here**
- Metrics: `src/quantum_api_drift_lab/analysis/metrics.py`
- Report builder: `src/quantum_api_drift_lab/analysis/report_builder.py`
- Generated figures:
  - Exec@1 by eval version
  - Pass@1 by eval version
  - Drift-break-rate
  - RAG gain and rewrite gain
  - Error taxonomy

## Demo support requested by the user

**Implemented here**
- UI: `src/quantum_api_drift_lab/ui/gradio_app.py`
- CLI: `src/quantum_api_drift_lab/cli.py`
- Screenshots directory: `screenshots/`
