"""Voice API routes for speech-to-text and text-to-speech."""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from microtutor.api.dependencies import get_tutor_service, get_voice_service
from microtutor.models.requests import ChatRequest
from microtutor.models.responses import VoiceTranscriptionResponse, VoiceChatResponse
from microtutor.services.tutor_service import TutorService
from microtutor.services.voice_service import VoiceService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["voice"])


@router.post(
    "/transcribe",
    response_model=VoiceTranscriptionResponse,
    summary="Transcribe audio to text",
    description="Upload an audio file and get the transcribed text using OpenAI Whisper.",
)
async def transcribe_audio(
    audio: UploadFile = File(..., description="Audio file (mp3, wav, m4a, webm, etc.)"),
    language: str = Form("en", description="ISO-639-1 language code (e.g., 'en', 'es'). Defaults to 'en' for better accuracy."),
    voice_service: VoiceService = Depends(get_voice_service),
) -> VoiceTranscriptionResponse:
    """Transcribe audio to text.
    
    Accepts audio files in various formats and returns transcribed text.
    Uses medical terminology prompt for better accuracy with medical terms.
    
    Args:
        audio: Audio file upload.
        language: Optional language code.
        voice_service: Injected voice service.
    
    Returns:
        VoiceTranscriptionResponse with transcribed text.
    
    Raises:
        HTTPException: If transcription fails.
    """
    try:
        # Read audio file
        audio_bytes = await audio.read()
        filename = audio.filename or "audio.mp3"
        
        # Validate file size
        if len(audio_bytes) == 0:
            raise HTTPException(
                status_code=400,
                detail="Audio file is empty (0 bytes)"
            )
        
        if len(audio_bytes) > 25 * 1024 * 1024:  # 25MB limit
            raise HTTPException(
                status_code=413,
                detail=f"Audio file too large: {len(audio_bytes)} bytes (max 25MB)"
            )
        
        # Transcribe with medical terminology prompt
        from microtutor.services.voice_service import VoiceConfig
        
        transcribed_text = await voice_service.transcribe_audio(
            audio_file=audio_bytes,
            filename=filename,
            language=language,
            prompt=VoiceConfig.MEDICAL_PROMPT,
            response_format="text",
        )
        
        return VoiceTranscriptionResponse(
            text=transcribed_text,
            language=language,
        )
        
    except ValueError as e:
        # Validation errors -> 400
        logger.error(f"Transcription validation error: {e}")
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # API errors -> 500
        logger.error(f"Transcription endpoint failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Transcription failed: {str(e)}"
        )


@router.post(
    "/synthesize",
    response_class=Response,
    summary="Synthesize speech from text",
    description="Convert text to speech with selectable voice (tutor or patient).",
)
async def synthesize_speech(
    text: str = Form(..., description="Text to synthesize"),
    speaker: Literal["tutor", "patient"] = Form("tutor", description="Speaker type (tutor or patient)"),
    speed: float = Form(1.0, ge=0.25, le=4.0, description="Speech speed (0.25 to 4.0)"),
    audio_format: str = Form("mp3", description="Audio format (mp3, opus, aac, flac, wav, pcm)"),
    voice_service: VoiceService = Depends(get_voice_service),
) -> Response:
    """Synthesize speech from text.
    
    Converts text to natural-sounding speech using different voices for
    tutor vs. patient responses.
    
    Args:
        text: Text to synthesize.
        speaker: Speaker type (tutor or patient).
        speed: Speech speed multiplier.
        audio_format: Audio format.
        voice_service: Injected voice service.
    
    Returns:
        Audio file as binary response.
    
    Raises:
        HTTPException: If synthesis fails.
    """
    try:
        audio_bytes = await voice_service.synthesize_speech(
            text=text,
            speaker=speaker,
            audio_format=audio_format,  # type: ignore
            speed=speed,
        )
        
        # Return audio with appropriate content type
        content_type_map = {
            "mp3": "audio/mpeg",
            "opus": "audio/opus",
            "aac": "audio/aac",
            "flac": "audio/flac",
            "wav": "audio/wav",
            "pcm": "audio/pcm",
        }
        
        return Response(
            content=audio_bytes,
            media_type=content_type_map.get(audio_format, "audio/mpeg"),
            headers={
                "Content-Disposition": f'attachment; filename="speech.{audio_format}"'
            }
        )
        
    except Exception as e:
        logger.error(f"Speech synthesis endpoint failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Speech synthesis failed: {str(e)}"
        )


@router.post(
    "/chat",
    response_model=VoiceChatResponse,
    summary="Voice-to-voice chat",
    description="Complete voice pipeline: upload audio, get transcribed text and synthesized response audio.",
)
async def voice_chat(
    audio: UploadFile = File(..., description="Audio file with user's message"),
    case_id: str = Form(..., description="Case ID"),
    organism_key: str = Form(..., description="Organism key"),
    history: str = Form("[]", description="Chat history as JSON string"),
    voice_service: VoiceService = Depends(get_voice_service),
    tutor_service: TutorService = Depends(get_tutor_service),
) -> VoiceChatResponse:
    """Complete voice-to-voice chat interaction.
    
    This endpoint provides the full voice pipeline:
    1. Transcribes user's audio to text
    2. Processes through tutor service
    3. Returns both text and audio responses
    
    Args:
        audio: User's audio file.
        case_id: Current case ID.
        organism_key: Organism being studied.
        history: Chat history as JSON string.
        voice_service: Injected voice service.
        tutor_service: Injected tutor service.
    
    Returns:
        VoiceChatResponse with transcribed text, response text, and audio URL.
    
    Raises:
        HTTPException: If any step fails.
    """
    try:
        import json
        import base64
        
        # Step 1: Transcribe user audio
        audio_bytes = await audio.read()
        filename = audio.filename or "audio.webm"
        
        logger.info(f"Received audio: {filename}, size: {len(audio_bytes)} bytes")
        
        # OpenAI Whisper supports: mp3, mp4, mpeg, mpga, m4a, wav, and webm
        # No conversion needed!
        
        if len(audio_bytes) == 0:
            raise ValueError("Audio file is empty (0 bytes)")
        
        if len(audio_bytes) > 25 * 1024 * 1024:  # 25MB limit
            raise ValueError(f"Audio file too large: {len(audio_bytes)} bytes (max 25MB)")
        
        from microtutor.services.voice_service import VoiceConfig
        user_text = await voice_service.transcribe_audio(
            audio_file=audio_bytes,
            filename=filename,
            language="en",  # Improves accuracy & latency for English medical terms
            prompt=VoiceConfig.MEDICAL_PROMPT,
            response_format="text",  # Simple string response
        )
        
        logger.info(f"User audio transcribed: '{user_text[:100]}...'")
        
        # Step 2: Process through tutor
        history_list = json.loads(history) if history != "[]" else []
        
        # Create tutor context (use model from tutor_service config)
        from microtutor.models.domain import TutorContext
        context = TutorContext(
            case_id=case_id,
            organism=organism_key,
            conversation_history=history_list,
            model_name=tutor_service.model_name,  # Use configured model
        )
        
        # Get tutor response using process_message
        tutor_response = await tutor_service.process_message(
            message=user_text,
            context=context,
        )
        
        # Step 3: Determine speaker and synthesize
        # Check if tools_used contains "patient" to determine voice
        speaker = "patient" if "patient" in tutor_response.tools_used else "tutor"
        
        response_audio = await voice_service.synthesize_speech(
            text=tutor_response.content,
            speaker=speaker,
        )
        
        # Encode audio as base64 for JSON response
        audio_base64 = base64.b64encode(response_audio).decode("utf-8")
        
        logger.info(f"Voice chat complete - Speaker: {speaker}, Tools: {tutor_response.tools_used}")
        
        # Get updated history from context
        updated_history = context.conversation_history
        
        return VoiceChatResponse(
            transcribed_text=user_text,
            response_text=tutor_response.content,
            audio_base64=audio_base64,
            speaker=speaker,
            tool_name=tutor_response.tools_used[0] if tutor_response.tools_used else "tutor",
            history=updated_history,
        )
        
    except Exception as e:
        logger.error(f"Voice chat endpoint failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Voice chat failed: {str(e)}"
        )

