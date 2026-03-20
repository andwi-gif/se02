from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List

from quantum_api_drift_lab.types import Task



def load_tasks(paths: Iterable[Path]) -> List[Task]:
    tasks: List[Task] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                tasks.append(Task(**payload))
    return tasks
