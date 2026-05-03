from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import json
import hashlib
from dataclasses import dataclass
from datetime import datetime
from ..core.config import MemoryConfig


@dataclass
class MemoryItem:
    id: str
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class MemorySystem:
    def __init__(self, config: MemoryConfig):
        self.config = config
        self.memory_dir = Path(config.path)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.memory_dir / "index.json"
        self._memories: Dict[str, MemoryItem] = {}
        self._load_index()

    def _get_item_id(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _load_index(self):
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item_data in data:
                        item = MemoryItem(
                            id=item_data['id'],
                            content=item_data['content'],
                            metadata=item_data['metadata'],
                            embedding=item_data.get('embedding'),
                            timestamp=datetime.fromisoformat(item_data['timestamp'])
                        )
                        self._memories[item.id] = item
            except Exception:
                pass

    def _save_index(self):
        data = []
        for item in self._memories.values():
            data.append({
                'id': item.id,
                'content': item.content,
                'metadata': item.metadata,
                'embedding': item.embedding,
                'timestamp': item.timestamp.isoformat()
            })
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        item_id = self._get_item_id(content)
        item = MemoryItem(
            id=item_id,
            content=content,
            metadata=metadata or {}
        )
        self._memories[item_id] = item
        self._save_index()
        return item_id

    def get(self, item_id: str) -> Optional[MemoryItem]:
        return self._memories.get(item_id)

    def search(
        self,
        query: str,
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[MemoryItem, float]]:
        results = []
        query_lower = query.lower()

        for item in self._memories.values():
            if filters:
                match = True
                for k, v in filters.items():
                    if item.metadata.get(k) != v:
                        match = False
                        break
                if not match:
                    continue

            if query_lower in item.content.lower():
                relevance = item.content.lower().count(query_lower)
                results.append((item, relevance))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    def list_all(self, limit: Optional[int] = None) -> List[MemoryItem]:
        items = list(self._memories.values())
        items.sort(key=lambda x: x.timestamp, reverse=True)
        if limit:
            items = items[:limit]
        return items

    def delete(self, item_id: str) -> bool:
        if item_id in self._memories:
            del self._memories[item_id]
            self._save_index()
            return True
        return False

    def clear(self):
        self._memories.clear()
        self._save_index()
