from quantum_api_drift_lab.execution.backends import classify_error


def test_module_relocation_classification():
    assert classify_error("ImportError: cannot import name 'Aer' from 'qiskit'") == "Module relocation"


def test_signature_mismatch_classification():
    assert classify_error("TypeError: run() got an unexpected keyword argument 'backend_options'") == "Signature mismatch"


def test_deprecated_api_classification():
    assert classify_error("AttributeError: module 'pennylane' has no attribute 'ExpvalCost' (deprecated API removed)") == "Deprecated API"
