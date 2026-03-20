# Quantum API Drift Lab

A production-oriented, proposal-aligned benchmark harness for **Quantum API Drift in LLM Generated Code**.

This artifact implements the methodology requested in the attached proposal:
- **SDKs:** Qiskit + PennyLane
- **Models:** one strong proprietary model (**GPT-5**) + one open-source code model (**Qwen/Qwen2.5-Coder-32B-Instruct**)
- **Generation settings:** Vanilla, **RAG-docs**, and **Rewrite baseline**
- **Sampling:** `k = 3`
- **Execution:** isolated multi-version execution harness
- **Metrics:** Exec@1, Pass@1, Drift-break-rate, and RAG gain
- **Analysis:** cross-version breakage, mitigation effectiveness, and error taxonomy

## What is included

- A **CLI** for batch experiments
- A **Gradio demo UI** for live walkthroughs and screenshots
- A **mock/demo mode** that runs without external API keys so reviewers can inspect the full pipeline quickly
- A **real mode** for GPT-5 + Qwen experiments using actual model endpoints
- A **rewrite engine** for rule-based migration baselines
- A **retriever** over version-specific official documentation snippets
- A **report generator** that writes CSVs, PNG figures, and an HTML report

## Quick start

### Demo mode (fast, no API keys required)

```bash
cd quantum_api_drift_lab
python -m venv .venv
source .venv/bin/activate
pip install -e .
qdrift run --config configs/experiment.demo.yaml
qdrift serve --config configs/experiment.demo.yaml
```

### Real mode (proposal-style live run)

```bash
cd quantum_api_drift_lab
python -m venv .venv
source .venv/bin/activate
pip install -e .[quantum]
cp .env.example .env
# export OPENAI_API_KEY, QWEN_BASE_URL, and (optionally) QWEN_API_KEY
qdrift run --config configs/experiment.full.yaml --mode real --backend docker
```

## Core commands

```bash
# Run the demo pipeline
qdrift run --config configs/experiment.demo.yaml

# Launch the UI
qdrift serve --config configs/experiment.demo.yaml --server-port 7860

# Real run with custom filters
qdrift run \
  --config configs/experiment.full.yaml \
  --mode real \
  --backend docker \
  --models gpt-5 Qwen/Qwen2.5-Coder-32B-Instruct \
  --strategies vanilla rag_docs rewrite_baseline
```

## Project structure

```text
configs/                  experiment configs, SDK matrix, rewrite rules
src/quantum_api_drift_lab/
  benchmark/              task loading
  llm/                    GPT-5, Qwen, prompt building, demo templates
  rag/                    version-specific documentation retrieval
  rewrite/                rule-based repair baseline
  execution/              mock, venv, and docker backends
  analysis/               metrics, figures, HTML report
  ui/                     Gradio demo app
  orchestrator.py         end-to-end pipeline
  cli.py                  command-line entrypoint
data/demo/                demo tasks and official-doc snippets
outputs/                  generated runs, CSVs, figures, reports
screenshots/              PNG screenshots for the demo walkthrough
docs/                     proposal mapping, operation guide, screenshot index
```

## Notes on reproducibility

- **Demo mode** is intentionally lightweight and deterministic so reviewers can see the full workflow in minutes.
- **Real mode** is where live model calls and isolated environments are used for actual experiments.
- The included demo benchmark is a **mini subset** used for UI walkthrough and artifact validation.
- The pipeline already supports the full proposal methodology; to scale up, point `benchmark_files` to the real QCircuitBench and Qiskit HumanEval subsets.

## Deliverables produced by each run

Each run writes a timestamped folder under `outputs/` containing:
- `generations.jsonl`
- `executions.jsonl`
- `summary_metrics.csv`
- `drift_break_rate.csv`
- `rag_gain.csv`
- `error_taxonomy.csv`
- `figures/*.png`
- `report.html`

## Where to read next

- `docs/PROPOSAL_ALIGNMENT.md`
- `docs/OPERATION_GUIDE.md`
- `docs/SCREENSHOT_INDEX.md`
