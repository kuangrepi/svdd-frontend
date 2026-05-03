import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional

DB_PATH = Path(__file__).parent / "singer_references.json"


class SingerDatabase:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            self._write({"singers": {}})

    def _read(self) -> dict:
        with open(self.db_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, data: dict) -> None:
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def list_singers(self) -> List[Dict]:
        singers = self._read()["singers"]
        return [{"name": name, "clips_count": info["clips_count"]} for name, info in singers.items()]

    def add_embedding(self, name: str, embedding: np.ndarray) -> int:
        data = self._read()
        singers = data["singers"]

        new_emb = embedding.astype(np.float32)
        norm = np.linalg.norm(new_emb)
        if norm > 0:
            new_emb = new_emb / norm

        if name in singers:
            n = singers[name]["clips_count"]
            old_emb = np.array(singers[name]["embedding"], dtype=np.float32)
            avg_emb = (old_emb * n + new_emb) / (n + 1)
            avg_norm = np.linalg.norm(avg_emb)
            if avg_norm > 0:
                avg_emb = avg_emb / avg_norm
            singers[name] = {"embedding": avg_emb.tolist(), "clips_count": n + 1}
        else:
            singers[name] = {"embedding": new_emb.tolist(), "clips_count": 1}

        data["singers"] = singers
        self._write(data)
        return singers[name]["clips_count"]

    def delete_singer(self, name: str) -> bool:
        data = self._read()
        if name not in data["singers"]:
            return False
        del data["singers"][name]
        self._write(data)
        return True

    def query(self, query_embedding: np.ndarray, top_k: int = 3) -> List[Dict]:
        singers = self._read()["singers"]
        if not singers:
            return []

        q = query_embedding.astype(np.float32)
        q_norm = np.linalg.norm(q)
        if q_norm > 0:
            q = q / q_norm

        results = []
        for name, entry in singers.items():
            ref_emb = np.array(entry["embedding"], dtype=np.float32)
            ref_norm = np.linalg.norm(ref_emb)
            if ref_norm > 0:
                ref_emb = ref_emb / ref_norm
            similarity = float(np.clip(np.dot(q, ref_emb), -1.0, 1.0))
            results.append({"name": name, "similarity": similarity})

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    def has_references(self) -> bool:
        return len(self._read()["singers"]) > 0
