
"""
Embedding Utilities - Reference for OpenClaw's vector system
"""

from typing import List, Optional
import math
import os


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Calculate cosine similarity between two vectors"""
    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)


async def get_embedding(text: str, model: str = "text-embedding-3-small") -> List[float]:
    """
    Get embedding for text
    Tries OpenAI, falls back to local simple embedding
    """
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = await client.embeddings.create(
            model=model,
            input=text,
        )
        return response.data[0].embedding
    except Exception:
        pass

    # Fallback: simple local embedding
    return _simple_embedding(text)


def _simple_embedding(text: str) -> List[float]:
    """Simple fallback embedding for testing"""
    import hashlib
    import struct

    vec = [0.0] * 128
    words = text.lower().split()

    for word in words:
        h = hashlib.sha256(word.encode()).digest()
        for i in range(min(32, len(h))):
            val = struct.unpack("B", h[i:i+1])[0] / 255.0 * 2 - 1
            vec[i % 128] += val

    # Normalize
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]

    return vec
