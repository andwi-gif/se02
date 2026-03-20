from pathlib import Path

from quantum_api_drift_lab.rewrite.engine import RewriteEngine
from quantum_api_drift_lab.llm.providers import CODE_TEMPLATES


RULES = Path(__file__).resolve().parents[1] / "configs" / "rewrite_rules.yaml"


def test_qiskit_aer_rule_rewrites_legacy_code():
    engine = RewriteEngine(RULES)
    rewritten, rule_id = engine.rewrite("qiskit", "1.0.2", CODE_TEMPLATES["qiskit_legacy_aer_execute"])
    assert rule_id == "qiskit_aer_import_migration"
    assert "MODERN_AER_SIMULATOR" in rewritten


def test_no_rule_returns_original_code():
    engine = RewriteEngine(RULES)
    original = CODE_TEMPLATES["pennylane_modern_simple_expval"]
    rewritten, rule_id = engine.rewrite("pennylane", "0.44.1", original)
    assert rule_id is None
    assert rewritten == original
