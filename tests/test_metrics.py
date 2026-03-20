from quantum_api_drift_lab.analysis.metrics import compute_metric_tables, records_to_frame
from quantum_api_drift_lab.types import ExecutionRecord



def _record(task_id: str, strategy: str, eval_version: str, executed: bool, passed: bool):
    return ExecutionRecord(
        generation_id=f"{task_id}-{strategy}-{eval_version}",
        run_name="demo",
        task_id=task_id,
        source_benchmark="demo",
        sdk="qiskit",
        target_version="0.45.3",
        eval_version=eval_version,
        model="gpt-5",
        strategy=strategy,
        sample_index=1,
        backend="mock",
        executed=executed,
        passed=passed,
        error_category="None" if passed else "Module relocation",
        raw_error="" if passed else "ImportError",
    )


def test_drift_and_rag_gain_tables_are_computed():
    records = [
        _record("t1", "vanilla", "0.45.3", True, True),
        _record("t1", "vanilla", "1.0.2", False, False),
        _record("t1", "rag_docs", "0.45.3", True, True),
        _record("t1", "rag_docs", "1.0.2", True, True),
    ]
    frame = records_to_frame(records)
    summary, drift, rag_gain, error_table = compute_metric_tables(frame)
    assert not summary.empty
    assert not drift.empty
    assert not rag_gain.empty
    row = rag_gain.iloc[0]
    assert row["rag_gain"] == 1.0
    assert not error_table.empty
