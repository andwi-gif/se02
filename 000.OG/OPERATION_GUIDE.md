# Operation guide

This is the step-by-step operating guide for the demo and the full study pipeline.

## 1. Start the system

### Demo mode

```bash
cd quantum_api_drift_lab
python -m venv .venv
source .venv/bin/activate
pip install -e .
qdrift serve --config configs/experiment.demo.yaml
```

Then open:

```text
http://127.0.0.1:7860
```

### Headless batch run

```bash
qdrift run --config configs/experiment.demo.yaml
```

### Real experiment mode

```bash
pip install -e .[quantum]
export OPENAI_API_KEY=...
export QWEN_BASE_URL=http://localhost:8001/v1
export QWEN_API_KEY=...
qdrift run --config configs/experiment.full.yaml --mode real --backend docker
```

## 2. What input the system takes

The UI and CLI take the following inputs:
- run name
- mode: `demo` or `real`
- isolation backend: `mock`, `venv`, or `docker`
- enabled models
- enabled strategies
- benchmark files from the selected config

Each task itself carries:
- benchmark source
- SDK name
- base version
- list of evaluation versions
- task prompt
- entrypoint
- executable test expectations

## 3. How the system processes the input

The end-to-end flow is:
1. Load experiment config.
2. Load benchmark tasks.
3. Create the requested providers:
   - GPT-5 provider
   - Qwen provider
4. For `rag_docs`, retrieve version-specific official documentation snippets.
5. Generate `k = 3` code samples for each task.
6. Execute each sample across the configured SDK version path.
7. Capture execution success/failure and test pass/fail.
8. Apply rewrite rules to broken vanilla programs.
9. Re-evaluate rewritten programs.
10. Compute metrics and build the report.

## 4. How the system detects success

A run is considered successful when:
- config validation passes
- tasks are loaded
- generation records are created
- execution records are created
- CSV metrics and PNG figures are written
- `report.html` is generated

At the per-sample level:
- **Execution success** means the candidate imports and runs without compilation/runtime failure.
- **Pass success** means the candidate also satisfies the attached unit tests.

## 5. How the system catches errors

### Configuration errors
Examples:
- no models selected
- no strategies selected
- real mode without `OPENAI_API_KEY`
- real mode without `QWEN_BASE_URL`

These are raised before the experiment begins.

### Environment errors
Examples:
- missing Docker for docker backend
- missing Python interpreter for a requested version
- package installation failure inside an isolated environment

### Generation/runtime errors
Examples:
- import failure after SDK upgrade
- removed API symbol
- signature mismatch after a method change
- semantic test failures where code runs but returns the wrong thing

## 6. How the system shows result analysis

The UI shows:
- summary metrics table
- drift-break-rate table
- mitigation gains table
- error taxonomy table
- figures gallery
- downloadable artifacts

The headless CLI writes all analysis into the run folder under `outputs/`.

## 7. Recommended demo script for presentation

1. Launch the UI in demo mode.
2. Show the default screen.
3. Click **Show processing preview** so the audience sees the benchmark and environment preparation phase.
4. Click **Run experiment**.
5. Show the success status.
6. Open the summary and drift tables.
7. Point out the RAG gain and rewrite gain figures.
8. Switch to `real` mode without credentials once to show the error handling path.
9. Return to demo mode and re-run if needed.

## 8. Cases you can demonstrate

### Case A — normal demo run
- mode: demo
- backend: mock
- models: GPT-5 + Qwen
- strategies: vanilla + rag_docs + rewrite_baseline

### Case B — missing API credentials
- mode: real
- backend: docker or venv
- no `OPENAI_API_KEY`
- expected result: clear configuration error in UI

### Case C — mitigation comparison
- run all three strategies
- expected result: lower drift-break-rate for `rag_docs` than `vanilla`
- expected result: `rewrite_baseline` recovers some broken vanilla programs

### Case D — benchmark inspection
- open `data/demo/tasks/*.jsonl`
- show that tasks cover circuit construction, measurement, backends, and gradients
