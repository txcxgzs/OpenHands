"""
pytest configuration
"""

import pytest
import asyncio


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_agent_config():
    """Sample agent config for testing"""
    from openhands import AgentConfig
    return AgentConfig.load()
