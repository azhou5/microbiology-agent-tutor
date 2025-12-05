"""Voice service for speech-to-text and text-to-speech functionality.

This service integrates OpenAI's Whisper API for transcription and TTS API
for speech synthesis, enabling voice-to-voice interactions with the tutor.
"""

import asyncio
import logging
from pathlib import Path
from typing import Literal, Optional

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


VoiceType = Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
TTSModel = Literal["tts-1", "tts-1-hd"]
AudioFormat = Literal["mp3", "opus", "aac", "flac", "wav", "pcm"]


class VoiceService:
    """Service for handling speech-to-text and text-to-speech operations.
    
    Uses OpenAI's Whisper API for transcription and TTS API for synthesis.
    Supports different voices for different speakers (tutor vs. patient).
    
    Attributes:
        client: AsyncOpenAI client for API calls.
        tutor_voice: Voice to use for tutor responses.
        patient_voice: Voice to use for patient responses.
        tts_model: TTS model to use (tts-1 or tts-1-hd).
        default_format: Default audio format for synthesis.
    
    Example:
        >>> voice_service = VoiceService(api_key="your-key")
        >>> 
        >>> # Transcribe user audio
        >>> with open("user_question.mp3", "rb") as audio:
        ...     text = await voice_service.transcribe_audio(audio)
        >>> 
        >>> # Synthesize tutor response
        >>> audio_bytes = await voice_service.synthesize_speech(
        ...     "Let's discuss the patient's symptoms.",
        ...     speaker="tutor"
        ... )
    """
    
    def __init__(
        self,
        api_key: str,
        tutor_voice: VoiceType = "nova",  # Professional, clear female voice
        patient_voice: VoiceType = "echo",  # Slightly different, male voice
        tts_model: TTSModel = "tts-1",  # Use tts-1-hd for higher quality
        default_format: AudioFormat = "mp3",
    ) -> None:
        """Initialize the voice service.
        
        Args:
            api_key: OpenAI API key.
            tutor_voice: Voice to use for tutor responses (default: nova).
            patient_voice: Voice to use for patient responses (default: echo).
            tts_model: TTS model quality (tts-1 for speed, tts-1-hd for quality).
            default_format: Default audio format (mp3 recommended for web).
        """
        self.client = AsyncOpenAI(api_key=api_key)
        self.tutor_voice = tutor_voice
        self.patient_voice = patient_voice
        self.tts_model = tts_model
        self.default_format = default_format
        
        logger.info(
            f"Voice service initialized - Tutor: {tutor_voice}, "
            f"Patient: {patient_voice}, Model: {tts_model}"
        )
    
    async def transcribe_audio(
        self,
        audio_file: bytes,
        filename: str = "audio.mp3",
        language: Optional[str] = None,
        prompt: Optional[str] = None,
        response_format: str = "text",
    ) -> str:
        """Transcribe audio to text using OpenAI Whisper API.
        
        Follows OpenAI Speech-to-Text API best practices:
        - Supports: mp3, mp4, mpeg, mpga, m4a, wav, webm
        - Max file size: 25 MB (~30 minutes of audio)
        - Uses whisper-1 model
        
        Args:
            audio_file: Audio file bytes.
            filename: Filename (with extension) for the audio. Extension hints at format.
            language: Optional ISO-639-1 language code (e.g., "en", "es"). 
                     Auto-detected if None. Providing it improves accuracy and latency.
            prompt: Optional prompt to guide transcription style/vocabulary.
                   Useful for medical terminology. Max 224 tokens.
            response_format: Output format. Options: "text" (default), "json", 
                           "verbose_json", "srt", "vtt".
        
        Returns:
            Transcribed text string.
        
        Raises:
            ValueError: If file is empty or too large.
            Exception: If OpenAI API call fails.
        
        Example:
            >>> audio_bytes = Path("question.mp3").read_bytes()
            >>> text = await voice_service.transcribe_audio(
            ...     audio_bytes,
            ...     filename="question.mp3",
            ...     language="en",
            ...     prompt="Medical terms: staphylococcus, streptococcus"
            ... )
        
        References:
            https://platform.openai.com/docs/guides/speech-to-text
        """
        try:
            # Validate file size (OpenAI limit: ~25MB)
            file_size_mb = len(audio_file) / (1024 * 1024)
            if len(audio_file) == 0:
                raise ValueError("Audio file is empty (0 bytes)")
            if file_size_mb > 25:
                raise ValueError(
                    f"Audio file too large: {file_size_mb:.2f}MB (max 25MB). "
                    "Consider splitting into smaller chunks."
                )
            
            logger.info(
                f"Transcribing audio: {filename} "
                f"({file_size_mb:.2f}MB, lang={language or 'auto'})"
            )
            
            # Create a file-like object from bytes
            # The .name attribute helps OpenAI determine the format
            from io import BytesIO
            audio_buffer = BytesIO(audio_file)
            audio_buffer.name = filename
            
            # Call OpenAI Whisper API
            # Note: response_format="text" returns a string directly
            # Other formats return objects with more structure
            transcript = await self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_buffer,
                language=language,
                prompt=prompt,
                response_format=response_format,
            )
            
            # Extract text based on response format
            if response_format == "text":
                transcribed_text = transcript  # Direct string for "text" format
            elif hasattr(transcript, "text"):
                transcribed_text = transcript.text  # For json/verbose_json
            else:
                transcribed_text = str(transcript)  # Fallback
            
            logger.info(f"✅ Transcription successful: '{transcribed_text[:100]}...'")
            
            return transcribed_text
            
        except ValueError as e:
            # Re-raise validation errors as-is
            logger.error(f"Transcription validation error: {e}")
            raise
        except Exception as e:
            # Log and re-raise API errors
            logger.error(f"❌ Transcription failed: {e}", exc_info=True)
            raise Exception(f"Transcription error: {str(e)}") from e
    
    async def synthesize_speech(
        self,
        text: str,
        speaker: Literal["tutor", "patient"] = "tutor",
        voice: Optional[VoiceType] = None,
        audio_format: Optional[AudioFormat] = None,
        speed: float = 1.0,
    ) -> bytes:
        """Synthesize speech from text using OpenAI TTS API.
        
        Args:
            text: Text to synthesize.
            speaker: Speaker type - "tutor" or "patient" (selects appropriate voice).
            voice: Optional voice override (uses configured voice if None).
            audio_format: Audio format (uses default if None).
            speed: Speech speed (0.25 to 4.0, default 1.0).
        
        Returns:
            Audio bytes in the specified format.
        
        Raises:
            Exception: If synthesis fails.
        
        Example:
            >>> # Tutor speaks
            >>> audio = await voice_service.synthesize_speech(
            ...     "What questions would you like to ask the patient?",
            ...     speaker="tutor"
            ... )
            >>> 
            >>> # Patient speaks
            >>> audio = await voice_service.synthesize_speech(
            ...     "I've been experiencing fever and chills for 3 days.",
            ...     speaker="patient"
            ... )
        """
        try:
            # Select voice based on speaker
            if voice is None:
                voice = self.tutor_voice if speaker == "tutor" else self.patient_voice
            
            format_to_use = audio_format or self.default_format
            
            logger.info(
                f"Synthesizing speech - Speaker: {speaker}, Voice: {voice}, "
                f"Format: {format_to_use}, Length: {len(text)} chars"
            )
            
            # Call TTS API
            response = await self.client.audio.speech.create(
                model=self.tts_model,
                voice=voice,
                input=text,
                response_format=format_to_use,
                speed=speed,
            )
            
            # Get audio bytes
            audio_bytes = response.content
            
            logger.info(f"Speech synthesis successful: {len(audio_bytes)} bytes")
            
            return audio_bytes
            
        except Exception as e:
            logger.error(f"Speech synthesis failed: {e}")
            raise
    
    async def transcribe_and_chat(
        self,
        audio_file: bytes,
        filename: str,
        chat_callback: callable,  # Function to handle the transcribed text
    ) -> tuple[str, bytes]:
        """Convenience method: transcribe audio, process with chat, and synthesize response.
        
        This is a complete voice-to-voice pipeline:
        1. Transcribe user's audio to text
        2. Process through chat system (via callback)
        3. Synthesize response to audio
        
        Args:
            audio_file: User's audio bytes.
            filename: Audio filename.
            chat_callback: Async function that takes transcribed text and returns
                          (response_text, speaker_type) tuple.
        
        Returns:
            Tuple of (transcribed_text, response_audio_bytes).
        
        Example:
            >>> async def process_chat(user_text: str) -> tuple[str, str]:
            ...     # Call your tutor service
            ...     response = await tutor_service.chat(user_text, ...)
            ...     speaker = "patient" if response.tool == "patient" else "tutor"
            ...     return (response.text, speaker)
            >>> 
            >>> text, audio = await voice_service.transcribe_and_chat(
            ...     audio_bytes,
            ...     "question.mp3",
            ...     process_chat
            ... )
        """
        # Step 1: Transcribe user audio
        user_text = await self.transcribe_audio(audio_file, filename)
        
        # Step 2: Process through chat
        response_text, speaker = await chat_callback(user_text)
        
        # Step 3: Synthesize response
        response_audio = await self.synthesize_speech(
            response_text,
            speaker=speaker
        )
        
        return user_text, response_audio


class VoiceConfig:
    """Configuration for voice service.
    
    This can be extended to load from environment variables or config files.
    """
    
    # Voice options for tutor (clear, professional, educational)
    TUTOR_VOICE_OPTIONS: list[VoiceType] = ["nova", "shimmer", "alloy"]
    
    # Voice options for patient (more casual, human)
    PATIENT_VOICE_OPTIONS: list[VoiceType] = ["echo", "fable", "onyx"]
    
    # Recommended voice pairings (tutor, patient)
    RECOMMENDED_PAIRS = [
        ("nova", "echo"),      # Female tutor, male patient
        ("alloy", "fable"),    # Neutral tutor, warm patient
        ("shimmer", "onyx"),   # Warm tutor, deep patient
    ]
    
    # Medical terminology prompt for better transcription
    MEDICAL_PROMPT = (
        "Medical terminology including: microbiology, bacteria, "
        "staphylococcus, streptococcus, symptoms, diagnosis, treatment, "
        "infection, fever, antibiotics"
    )

