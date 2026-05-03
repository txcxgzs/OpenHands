"""
Tests for memory store
"""

import pytest
from auroraagent import MemoryStore


@pytest.fixture
def memory_store(tmp_path):
    """Create temp memory store"""
    return MemoryStore(path=str(tmp_path / "memory"))


@pytest.mark.asyncio
async def test_add_memory(memory_store):
    """Test adding memory"""
    item_id = await memory_store.add("Test memory content")
    assert item_id is not None


@pytest.mark.asyncio
async def test_get_memory(memory_store):
    """Test getting memory"""
    item_id = await memory_store.add("Test memory content")
    item = memory_store.get(item_id)
    assert item is not None
    assert item.content == "Test memory content"


@pytest.mark.asyncio
async def test_search_memory(memory_store):
    """Test searching memory"""
    await memory_store.add("Python is great")
    await memory_store.add("JavaScript is popular")
    await memory_store.add("Rust is fast")

    results = await memory_store.search("Python", limit=5)
    assert len(results) > 0
