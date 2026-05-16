
"""
Memory Store - Reference to OpenClaw's memory system
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json
import hashlib
import logging
import math
from ...utils.embedding import get_embedding, cosine_similarity

logger = logging.getLogger(__name__)


@dataclass
class MemoryItem:
    """Memory item with embedding support"""
    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "metadata": self.metadata,
            "embedding": self.embedding,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryItem":
        return cls(
            id=data["id"],
            content=data["content"],
            metadata=data.get("metadata", {}),
            embedding=data.get("embedding"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )


class MemoryStore:
    """
    Memory store with vector search support
    References OpenClaw's memory architecture
    """

    def __init__(self, path: str = "./data/memory"):
        self._path = Path(path)
        self._items: Dict[str, MemoryItem] = {}
        self._index_file = self._path / "memory_index.json"
        self._load_index()

    def _load_index(self):
        if self._index_file.exists():
            try:
                with open(self._index_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._items = {
                        item["id"]: MemoryItem.from_dict(item)
                        for item in data
                    }
            except Exception as e:
                logger.warning(f"Failed to load memory index: {e}")

    def _save_index(self):
        self._path.mkdir(parents=True, exist_ok=True)
        try:
            data = [item.to_dict() for item in self._items.values()]
            with open(self._index_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"Failed to save memory index: {e}")

    def _generate_id(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    async def add(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        generate_embedding: bool = True,
    ) -> str:
        """Add an item to memory"""
        item_id = self._generate_id(content)

        if item_id in self._items:
            item = self._items[item_id]
            item.updated_at = datetime.now()
        else:
            item = MemoryItem(
                id=item_id,
                content=content,
                metadata=metadata or {},
            )

        if generate_embedding and not item.embedding:
            try:
                item.embedding = await get_embedding(content)
            except Exception as e:
                logger.warning(f"Failed to generate embedding: {e}")

        self._items[item_id] = item
        self._save_index()
        logger.debug(f"Added memory item: {item_id}")
        return item_id

    def get(self, item_id: str) -> Optional[MemoryItem]:
        """Get item by ID"""
        return self._items.get(item_id)

    def delete(self, item_id: str) -> bool:
        """Delete item by ID"""
        if item_id in self._items:
            del self._items[item_id]
            self._save_index()
            return True
        return False

    async def search(
        self,
        query: str,
        limit: int = 10,
        threshold: float = 0.7,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[MemoryItem, float]]:
        """
        Search memory with vector similarity
        References OpenClaw's memory search
        """
        candidates = list(self._items.values())

        if metadata_filter:
            candidates = [
                item for item in candidates
                if all(item.metadata.get(k) == v for k, v in metadata_filter.items())
            ]

        try:
            query_embedding = await get_embedding(query)
            scored = []

            for item in candidates:
                if item.embedding:
                    similarity = cosine_similarity(query_embedding, item.embedding)
                    if similarity >= threshold:
                        scored.append((item, similarity))

            scored.sort(key=lambda x: x[1], reverse=True)
            return scored[:limit]

        except Exception as e:
            logger.warning(f"Vector search failed: {e}, falling back to keyword search")
            # Fallback to keyword search
            results = []
            query_lower = query.lower()
            for item in candidates:
                if query_lower in item.content.lower():
                    results.append((item, 0.0))
            return results[:limit]

    def list_all(
        self,
        limit: Optional[int] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[MemoryItem]:
        """List all memory items"""
        items = list(self._items.values())

        if metadata_filter:
            items = [
                item for item in items
                if all(item.metadata.get(k) == v for k, v in metadata_filter.items())
            ]

        items.sort(key=lambda x: x.updated_at, reverse=True)

        if limit:
            items = items[:limit]

        return items

    def count(self) -> int:
        """Get total item count"""
        return len(self._items)

    def clear(self):
        """Clear all memory"""
        self._items.clear()
        self._save_index()
