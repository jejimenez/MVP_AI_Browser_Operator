# app/infrastructure/snapshot_storage.py
from typing import Dict, Any
import json

class SnapshotStorage:
    def save_snapshot(self, snapshot: Dict[str, Any], file_path: str = "snapshot_json.jsonl") -> None:
        with open(file_path, mode='w', encoding='utf-8') as f:
            json.dump(snapshot, f, indent=2)