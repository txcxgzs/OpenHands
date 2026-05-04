"""
Voice Tools - TTS and ASR
"""

import asyncio
import logging
from pathlib import Path
import base64

logger = logging.getLogger(__name__)


def register_tools(registry):
    """Register voice tools"""

    @registry.register_tool(
        name="tts_speak",
        description="Text to speech - speak text aloud",
        toolset="voice",
        parameters={
            "text": {"type": "string", "description": "Text to speak"},
            "voice": {"type": "string", "description": "Voice name (optional)"},
        },
    )
    async def tts_speak(text: str, voice: str = "default") -> str:
        try:
            from gtts import gTTS
            from datetime import datetime

            Path("./data/audio").mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"./data/audio/tts_{timestamp}.mp3"

            tts = gTTS(text=text, lang="en", slow=False)
            tts.save(filepath)

            try:
                import os
                os.system(f'mpv "{filepath}" --quiet' if os.name == "posix" else f'start "{filepath}"')
            except Exception:
                pass

            return f"Spoke text and saved to: {filepath}"
        except ImportError:
            return "Error: gTTS not installed. Run: pip install gTTS"
        except Exception as e:
            return f"Error: {e}"

    # 别名：speak 与系统提示词一致
    @registry.register_tool(
        name="speak",
        description="Text to speech - speak text aloud",
        toolset="voice",
        parameters={
            "text": {"type": "string", "description": "Text to speak"},
            "voice": {"type": "string", "description": "Voice name (optional)"},
        },
    )
    async def speak(text: str, voice: str = "default") -> str:
        return await tts_speak(text, voice)

    @registry.register_tool(
        name="tts_save",
        description="Save text as speech audio file",
        toolset="voice",
        parameters={
            "text": {"type": "string", "description": "Text to convert"},
            "output_path": {"type": "string", "description": "Output file path"},
            "lang": {"type": "string", "description": "Language code"},
        },
    )
    async def tts_save(text: str, output_path: str = "output.mp3", lang: str = "en") -> str:
        try:
            from gtts import gTTS

            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            tts = gTTS(text=text, lang=lang, slow=False)
            tts.save(output_path)

            return f"Audio saved to: {output_path}"
        except ImportError:
            return "Error: gTTS not installed"
        except Exception as e:
            return f"Error: {e}"

    @registry.register_tool(
        name="asr_transcribe",
        description="Speech to text - transcribe audio file",
        toolset="voice",
        parameters={
            "audio_path": {"type": "string", "description": "Path to audio file"},
        },
    )
    async def asr_transcribe(audio_path: str) -> str:
        try:
            import speech_recognition as sr

            r = sr.Recognizer()
            with sr.AudioFile(audio_path) as source:
                audio = r.record(source)
                text = r.recognize_google(audio)
                return f"Transcription: {text}"
        except ImportError:
            return "Error: SpeechRecognition not installed. Run: pip install SpeechRecognition"
        except Exception as e:
            return f"Error: {e}"

    # 别名
    @registry.register_tool(
        name="transcribe",
        description="Speech to text - transcribe audio file",
        toolset="voice",
        parameters={
            "audio_path": {"type": "string", "description": "Path to audio file"},
        },
    )
    async def transcribe(audio_path: str) -> str:
        return await asr_transcribe(audio_path)

    @registry.register_tool(
        name="asr_listen",
        description="Listen to microphone and transcribe",
        toolset="voice",
        parameters={
            "duration": {"type": "number", "description": "Duration in seconds"},
        },
    )
    async def asr_listen(duration: float = 5.0) -> str:
        try:
            import speech_recognition as sr

            r = sr.Recognizer()
            with sr.Microphone() as source:
                logger.info("Listening...")
                audio = r.listen(source, phrase_time_limit=duration)

            text = r.recognize_google(audio)
            return f"You said: {text}"
        except ImportError:
            return "Error: SpeechRecognition not installed"
        except Exception as e:
            return f"Error: {e}"

    # 别名
    @registry.register_tool(
        name="listen",
        description="Listen to microphone and transcribe",
        toolset="voice",
        parameters={
            "duration": {"type": "number", "description": "Duration in seconds"},
        },
    )
    async def listen(duration: float = 5.0) -> str:
        return await asr_listen(duration)

    logger.debug("Voice tools registered")
