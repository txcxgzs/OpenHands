"""
Media Generation Tools - Image, Audio, Video generation
"""

import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def register_tools(registry):
    """Register media generation tools"""

    @registry.register_tool(
        name="generate_image",
        description="Generate image from text prompt",
        toolset="media",
        parameters={
            "prompt": {"type": "string", "description": "Image description"},
            "size": {"type": "string", "description": "Size: 1024x1024, 1792x1024, etc."},
        },
    )
    async def generate_image(prompt: str, size: str = "1024x1024") -> str:
        try:
            from openai import AsyncOpenAI
            import os

            client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

            response = await client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size=size,
                n=1,
            )

            image_url = response.data[0].url
            return f"Generated image: {image_url}"
        except ImportError:
            return "Error: openai package not installed"
        except Exception as e:
            return f"Error: {e}"

    # 别名：image_generate 与系统提示词一致
    @registry.register_tool(
        name="image_generate",
        description="Generate image from text prompt",
        toolset="media",
        parameters={
            "prompt": {"type": "string", "description": "Image description"},
            "size": {"type": "string", "description": "Size: 1024x1024, 1792x1024, etc."},
        },
    )
    async def image_generate(prompt: str, size: str = "1024x1024") -> str:
        return await generate_image(prompt, size)

    @registry.register_tool(
        name="generate_image_local",
        description="Generate image using local model",
        toolset="media",
        parameters={
            "prompt": {"type": "string", "description": "Image description"},
        },
    )
    async def generate_image_local(prompt: str) -> str:
        try:
            from diffusers import StableDiffusionPipeline
            import torch

            pipe = StableDiffusionPipeline.from_pretrained(
                "stabilityai/stable-diffusion-2-1",
                torch_dtype=torch.float16,
            )
            pipe = pipe.to("cuda" if torch.cuda.is_available() else "cpu")

            image = pipe(prompt).images[0]

            Path("./data/media").mkdir(parents=True, exist_ok=True)
            output_path = f"./data/media/generated_{hash(prompt) % 100000}.png"
            image.save(output_path)

            return f"Generated image saved: {output_path}"
        except ImportError:
            return "Error: diffusers not installed. Run: pip install diffusers torch"
        except Exception as e:
            return f"Error: {e}"

    @registry.register_tool(
        name="transcribe_audio",
        description="Transcribe audio file to text",
        toolset="media",
        parameters={
            "audio_path": {"type": "string", "description": "Path to audio file"},
        },
    )
    async def transcribe_audio(audio_path: str) -> str:
        try:
            from openai import AsyncOpenAI
            import os

            client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

            with open(audio_path, "rb") as audio_file:
                response = await client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                )

            return f"Transcription: {response.text}"
        except Exception as e:
            return f"Error: {e}"

    # 别名：speech_to_text 与系统提示词一致
    @registry.register_tool(
        name="speech_to_text",
        description="Transcribe audio file to text",
        toolset="media",
        parameters={
            "audio_path": {"type": "string", "description": "Path to audio file"},
        },
    )
    async def speech_to_text(audio_path: str) -> str:
        return await transcribe_audio(audio_path)

    @registry.register_tool(
        name="generate_speech",
        description="Text to speech with OpenAI",
        toolset="media",
        parameters={
            "text": {"type": "string", "description": "Text to speak"},
            "voice": {"type": "string", "description": "Voice: alloy, echo, fable, onyx, nova, shimmer"},
        },
    )
    async def generate_speech(text: str, voice: str = "alloy") -> str:
        try:
            from openai import AsyncOpenAI
            import os

            client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

            response = await client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text,
            )

            Path("./data/media").mkdir(parents=True, exist_ok=True)
            output_path = f"./data/media/speech_{hash(text) % 100000}.mp3"

            with open(output_path, "wb") as f:
                f.write(response.content)

            return f"Speech saved: {output_path}"
        except Exception as e:
            return f"Error: {e}"

    # 别名：text_to_speech 与系统提示词一致
    @registry.register_tool(
        name="text_to_speech",
        description="Text to speech with OpenAI",
        toolset="media",
        parameters={
            "text": {"type": "string", "description": "Text to speak"},
            "voice": {"type": "string", "description": "Voice: alloy, echo, fable, onyx, nova, shimmer"},
        },
    )
    async def text_to_speech(text: str, voice: str = "alloy") -> str:
        return await generate_speech(text, voice)

    logger.debug("Media tools registered")
