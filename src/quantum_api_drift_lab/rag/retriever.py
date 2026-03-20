from __future__ import annotations

import re
from pathlib import Path
from typing import List

from quantum_api_drift_lab.types import Snippet, Task


TOKEN_RE = re.compile(r"[a-zA-Z0-9_\.]+")


class SnippetRetriever:
    def __init__(self, docs_root: Path) -> None:
        self.docs_root = docs_root

    def retrieve(self, task: Task, version: str, top_k: int = 2) -> List[Snippet]:
        candidates = self._load_version_snippets(task.sdk, version)
        if not candidates:
            return []
        query_tokens = set(self._tokenize(task.prompt + " " + " ".join(task.categories)))
        scored = []
        for snippet in candidates:
            snippet_tokens = set(self._tokenize(snippet.raw_text))
            score = len(query_tokens.intersection(snippet_tokens))
            if any(term in snippet.raw_text.lower() for term in [task.entrypoint.lower(), task.sdk.lower()]):
                score += 1
            scored.append((score, snippet))
        scored.sort(key=lambda row: row[0], reverse=True)
        return [snippet for score, snippet in scored[:top_k] if score > 0] or [scored[0][1]]

    def _load_version_snippets(self, sdk: str, version: str) -> List[Snippet]:
        version_dir = self.docs_root / sdk / version
        if not version_dir.exists():
            return []
        snippets: List[Snippet] = []
        for path in sorted(version_dir.glob("*.txt")):
            raw_text = path.read_text(encoding="utf-8")
            fields = self._parse_fields(raw_text)
            snippets.append(
                Snippet(
                    sdk=sdk,
                    version=version,
                    source_url=fields.get("source_url", ""),
                    summary=fields.get("summary", raw_text.strip()),
                    retrieval_terms=fields.get("retrieval_terms", ""),
                    local_path=str(path),
                    raw_text=raw_text,
                )
            )
        return snippets

    @staticmethod
    def _parse_fields(text: str) -> dict:
        fields = {}
        for line in text.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                if key.strip() in {"source_url", "summary", "retrieval_terms"}:
                    fields[key.strip()] = value.strip()
        return fields

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return [token.lower() for token in TOKEN_RE.findall(text)]
