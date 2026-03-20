from __future__ import annotations

import json
import re
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Iterable, List


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")



def write_jsonl(path: Path, rows: Iterable[Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            payload = row
            if is_dataclass(row):
                payload = asdict(row)
            handle.write(json.dumps(payload, default=json_default) + "\n")



def read_jsonl(path: Path) -> List[Any]:
    rows: List[Any] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows
