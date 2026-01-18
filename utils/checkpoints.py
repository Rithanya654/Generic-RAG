"""
Checkpoint Manager for GraphRAG Pipeline
----------------------------------------
Stores progress after each bot so pipeline
can resume safely after failure.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional

CHECKPOINT_DIR = Path("outputs/checkpoints")
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)


class CheckpointManager:
    def __init__(self, doc_id: str):
        self.doc_id = doc_id
        self.path = CHECKPOINT_DIR / f"{doc_id}.json"

        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.data = {
                "doc_id": doc_id,
                "completed_steps": [],
                "artifacts": {},
            }

    # --------------------------------------------------
    # Core
    # --------------------------------------------------

    def save(self):
        self.path.write_text(
            json.dumps(self.data, indent=2),
            encoding="utf-8"
        )

    def mark_completed(self, step: str):
        if step not in self.data["completed_steps"]:
            self.data["completed_steps"].append(step)
            self.save()

    def is_completed(self, step: str) -> bool:
        return step in self.data["completed_steps"]

    # --------------------------------------------------
    # Artifact storage
    # --------------------------------------------------

    def store(self, key: str, value: Any):
        self.data["artifacts"][key] = value
        self.save()

    def load(self, key: str) -> Optional[Any]:
        return self.data["artifacts"].get(key)

    # --------------------------------------------------
    # Debug
    # --------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "completed_steps": self.data["completed_steps"],
            "artifacts": list(self.data["artifacts"].keys()),
        }
