from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests

from quantum_api_drift_lab.types import GenerationRecord, ModelConfig, Snippet, Task


CODE_TEMPLATES: Dict[str, str] = {
    "qiskit_legacy_aer_execute": '''# MOCK_PATTERN: LEGACY_AER_EXECUTE
from qiskit import QuantumCircuit, Aer, execute

def bell_counts(shots: int = 256):
    qc = QuantumCircuit(2, 2)
    qc.h(0)
    qc.cx(0, 1)
    qc.measure([0, 1], [0, 1])
    backend = Aer.get_backend("qasm_simulator")
    result = execute(qc, backend, shots=shots).result()
    return result.get_counts()
''',
    "qiskit_modern_aer_simulator": '''# MOCK_PATTERN: MODERN_AER_SIMULATOR
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator

def bell_counts(shots: int = 256):
    qc = QuantumCircuit(2, 2)
    qc.h(0)
    qc.cx(0, 1)
    qc.measure([0, 1], [0, 1])
    backend = AerSimulator()
    job = backend.run(transpile(qc, backend), shots=shots)
    return job.result().get_counts()
''',
    "qiskit_old_signature_backend_options": '''# MOCK_PATTERN: OLD_SIGNATURE_BACKEND_OPTIONS
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator

def bell_counts(shots: int = 256):
    qc = QuantumCircuit(2, 2)
    qc.h(0)
    qc.cx(0, 1)
    qc.measure([0, 1], [0, 1])
    backend = AerSimulator()
    compiled = transpile(qc, backend)
    job = backend.run(compiled, shots=shots, backend_options={"method": "automatic"})
    return job.result().get_counts()
''',
    "qiskit_semantic_counts_list": '''# MOCK_PATTERN: SEMANTIC_COUNTS_LIST
from qiskit import QuantumCircuit

def bell_counts(shots: int = 256):
    qc = QuantumCircuit(2, 2)
    qc.h(0)
    qc.cx(0, 1)
    qc.measure([0, 1], [0, 1])
    return ["00", "11"]
''',
    "qiskit_legacy_qasm_method": '''# MOCK_PATTERN: LEGACY_QASM_METHOD
from qiskit import QuantumCircuit

def export_qasm():
    qc = QuantumCircuit(1, 1)
    qc.h(0)
    qc.measure(0, 0)
    return qc.qasm()
''',
    "qiskit_modern_qasm2": '''# MOCK_PATTERN: MODERN_QASM2_DUMPS
from qiskit import QuantumCircuit, qasm2

def export_qasm():
    qc = QuantumCircuit(1, 1)
    qc.h(0)
    qc.measure(0, 0)
    return qasm2.dumps(qc)
''',
    "pennylane_legacy_expval_cost": '''# MOCK_PATTERN: LEGACY_EXPVAL_COST
import pennylane as qml

def build_cost():
    dev = qml.device("default.qubit", wires=1)
    H = qml.PauliZ(0)
    def ansatz(theta):
        qml.RX(theta, wires=0)
    return qml.ExpvalCost(ansatz, H, dev)
''',
    "pennylane_modern_qnode_cost": '''# MOCK_PATTERN: MODERN_QNODE_COST
import pennylane as qml

def build_cost():
    dev = qml.device("default.qubit", wires=1)
    @qml.qnode(dev)
    def circuit(theta):
        qml.RX(theta, wires=0)
        return qml.expval(qml.PauliZ(0))
    def cost(theta=0.0):
        return circuit(theta)
    return cost
''',
    "pennylane_modern_simple_expval": '''# MOCK_PATTERN: MODERN_SIMPLE_EXPVAL
import pennylane as qml

def simple_expval(theta: float):
    dev = qml.device("default.qubit", wires=1)
    @qml.qnode(dev)
    def circuit(x):
        qml.RX(x, wires=0)
        return qml.expval(qml.PauliZ(0))
    return circuit(theta)
''',
    "pennylane_semantic_return_probs": '''# MOCK_PATTERN: SEMANTIC_RETURN_PROBS
import pennylane as qml

def simple_expval(theta: float):
    dev = qml.device("default.qubit", wires=1)
    @qml.qnode(dev)
    def circuit(x):
        qml.RX(x, wires=0)
        return qml.probs(wires=0)
    return circuit(theta)
''',
}


MOCK_SELECTIONS: Dict[str, Dict[str, Dict[str, List[str]]]] = {
    "gpt-5": {
        "vanilla": {
            "qhe_qiskit_bell_counts": ["qiskit_legacy_aer_execute", "qiskit_modern_aer_simulator", "qiskit_modern_aer_simulator"],
            "qhe_qiskit_qasm_export": ["qiskit_legacy_qasm_method", "qiskit_modern_qasm2", "qiskit_modern_qasm2"],
            "qcb_pennylane_cost_function": ["pennylane_legacy_expval_cost", "pennylane_modern_qnode_cost", "pennylane_modern_qnode_cost"],
            "qcb_pennylane_simple_expval": ["pennylane_modern_simple_expval", "pennylane_modern_simple_expval", "pennylane_modern_simple_expval"],
        },
        "rag_docs": {
            "qhe_qiskit_bell_counts": ["qiskit_modern_aer_simulator", "qiskit_modern_aer_simulator", "qiskit_legacy_aer_execute"],
            "qhe_qiskit_qasm_export": ["qiskit_modern_qasm2", "qiskit_modern_qasm2", "qiskit_modern_qasm2"],
            "qcb_pennylane_cost_function": ["pennylane_modern_qnode_cost", "pennylane_modern_qnode_cost", "pennylane_legacy_expval_cost"],
            "qcb_pennylane_simple_expval": ["pennylane_modern_simple_expval", "pennylane_modern_simple_expval", "pennylane_modern_simple_expval"],
        },
    },
    "Qwen/Qwen2.5-Coder-32B-Instruct": {
        "vanilla": {
            "qhe_qiskit_bell_counts": ["qiskit_legacy_aer_execute", "qiskit_legacy_aer_execute", "qiskit_old_signature_backend_options"],
            "qhe_qiskit_qasm_export": ["qiskit_legacy_qasm_method", "qiskit_legacy_qasm_method", "qiskit_modern_qasm2"],
            "qcb_pennylane_cost_function": ["pennylane_legacy_expval_cost", "pennylane_legacy_expval_cost", "pennylane_modern_qnode_cost"],
            "qcb_pennylane_simple_expval": ["pennylane_modern_simple_expval", "pennylane_semantic_return_probs", "pennylane_modern_simple_expval"],
        },
        "rag_docs": {
            "qhe_qiskit_bell_counts": ["qiskit_modern_aer_simulator", "qiskit_modern_aer_simulator", "qiskit_old_signature_backend_options"],
            "qhe_qiskit_qasm_export": ["qiskit_modern_qasm2", "qiskit_modern_qasm2", "qiskit_modern_qasm2"],
            "qcb_pennylane_cost_function": ["pennylane_modern_qnode_cost", "pennylane_modern_qnode_cost", "pennylane_legacy_expval_cost"],
            "qcb_pennylane_simple_expval": ["pennylane_modern_simple_expval", "pennylane_modern_simple_expval", "pennylane_semantic_return_probs"],
        },
    },
}


@dataclass
class ProviderResponse:
    code: str
    prompt: str
    docs_sources: List[str]
    metadata: Dict[str, str]


class CodeProvider:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    def generate(
        self,
        task: Task,
        target_version: str,
        strategy: str,
        sample_index: int,
        snippets: Optional[List[Snippet]] = None,
    ) -> ProviderResponse:
        raise NotImplementedError


class MockProvider(CodeProvider):
    def generate(
        self,
        task: Task,
        target_version: str,
        strategy: str,
        sample_index: int,
        snippets: Optional[List[Snippet]] = None,
    ) -> ProviderResponse:
        snippets = snippets or []
        prompt = build_prompt(task, target_version, strategy, self.model_name, snippets)
        selection = MOCK_SELECTIONS[self.model_name][strategy][task.task_id]
        template_key = selection[min(sample_index - 1, len(selection) - 1)]
        code = CODE_TEMPLATES[template_key]
        return ProviderResponse(
            code=code,
            prompt=prompt,
            docs_sources=[snippet.source_url for snippet in snippets],
            metadata={"template_key": template_key},
        )


class OpenAIResponsesProvider(CodeProvider):
    def __init__(self, model_name: str, api_key: Optional[str] = None, base_url: Optional[str] = None) -> None:
        super().__init__(model_name)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")

    def generate(
        self,
        task: Task,
        target_version: str,
        strategy: str,
        sample_index: int,
        snippets: Optional[List[Snippet]] = None,
    ) -> ProviderResponse:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for real-mode GPT-5 runs.")
        snippets = snippets or []
        prompt = build_prompt(task, target_version, strategy, self.model_name, snippets)
        response = requests.post(
            f"{self.base_url}/responses",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model_name,
                "input": prompt,
            },
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        text = payload.get("output_text") or _extract_text_from_responses_api(payload)
        return ProviderResponse(
            code=extract_python_code(text),
            prompt=prompt,
            docs_sources=[snippet.source_url for snippet in snippets],
            metadata={"provider": "openai"},
        )


class OpenAICompatibleProvider(CodeProvider):
    def __init__(self, model_name: str, api_key: Optional[str] = None, base_url: Optional[str] = None) -> None:
        super().__init__(model_name)
        self.api_key = api_key or os.getenv("QWEN_API_KEY") or ""
        self.base_url = (base_url or os.getenv("QWEN_BASE_URL") or "").rstrip("/")

    def generate(
        self,
        task: Task,
        target_version: str,
        strategy: str,
        sample_index: int,
        snippets: Optional[List[Snippet]] = None,
    ) -> ProviderResponse:
        if not self.base_url:
            raise RuntimeError("QWEN_BASE_URL is required for real-mode Qwen runs.")
        snippets = snippets or []
        prompt = build_prompt(task, target_version, strategy, self.model_name, snippets)
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": "You write minimal, testable Python code only."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            },
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        text = payload["choices"][0]["message"]["content"]
        return ProviderResponse(
            code=extract_python_code(text),
            prompt=prompt,
            docs_sources=[snippet.source_url for snippet in snippets],
            metadata={"provider": "openai_compatible"},
        )



def build_prompt(task: Task, target_version: str, strategy: str, model_name: str, snippets: List[Snippet]) -> str:
    sections = [
        f"You are generating Python code for the quantum SDK {task.sdk} targeting version {target_version}.",
        f"Model label: {model_name}",
        f"Benchmark source: {task.source_benchmark}",
        f"Entry point: {task.entrypoint}",
        f"Task categories: {', '.join(task.categories)}",
        "Return Python code only. Do not include explanations.",
        "Task:",
        task.prompt,
        "Unit test expectations:",
        "\n".join(f"- {test}" for test in task.tests),
    ]
    if strategy == "rag_docs" and snippets:
        sections.append("Version-specific official documentation snippets:")
        sections.extend(snippet.prompt_text() for snippet in snippets)
    return "\n\n".join(sections)



def extract_python_code(text: str) -> str:
    match = re.search(r"```python\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip() + "\n"
    match = re.search(r"```\s*(.*?)```", text, flags=re.DOTALL)
    if match:
        return match.group(1).strip() + "\n"
    return text.strip() + "\n"



def _extract_text_from_responses_api(payload: Dict[str, object]) -> str:
    output = payload.get("output", [])
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content", [])
            if isinstance(content, list):
                for chunk in content:
                    if isinstance(chunk, dict) and chunk.get("type") == "output_text":
                        return str(chunk.get("text", ""))
    return ""



def get_provider(model: ModelConfig, mode: str) -> CodeProvider:
    if mode == "demo":
        return MockProvider(model.name)
    if model.provider == "openai":
        return OpenAIResponsesProvider(model.name)
    if model.provider == "openai_compatible":
        return OpenAICompatibleProvider(model.name)
    raise ValueError(f"Unsupported provider: {model.provider}")
