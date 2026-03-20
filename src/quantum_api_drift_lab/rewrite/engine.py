from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import yaml

from quantum_api_drift_lab.llm.providers import CODE_TEMPLATES


@dataclass
class RewriteRule:
    rule_id: str
    sdk: str
    applies_when_code_contains: List[str]
    target_versions: List[str]
    replacement_template: str
    rationale: str


class RewriteEngine:
    def __init__(self, rules_path: Path) -> None:
        payload = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
        self.rules = [
            RewriteRule(
                rule_id=item["id"],
                sdk=item["sdk"],
                applies_when_code_contains=item["applies_when_code_contains"],
                target_versions=item["target_versions"],
                replacement_template=item["replacement_template"],
                rationale=item["rationale"],
            )
            for item in payload.get("rules", [])
        ]

    def rewrite(self, sdk: str, eval_version: str, code: str) -> Tuple[str, Optional[str]]:
        for rule in self.rules:
            if rule.sdk != sdk:
                continue
            if eval_version not in rule.target_versions:
                continue
            if not all(token in code for token in rule.applies_when_code_contains):
                continue
            return CODE_TEMPLATES[rule.replacement_template], rule.rule_id
        return code, None
