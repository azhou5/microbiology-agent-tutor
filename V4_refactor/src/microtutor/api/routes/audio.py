"""Audio serving API endpoints for MicroTutor."""

import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.responses import StreamingResponse
import mimetypes
import os

logger = logging.getLogger(__name__)
router = APIRouter()

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
AUDIO_BASE_PATH = PROJECT_ROOT / "data" / "respiratory_sounds"

@router.get(
    "/respiratory/{filename}",
    summary="Get respiratory sound audio file",
    description="Stream a respiratory sound audio file for playback in the frontend"
)
async def get_respiratory_audio(filename: str) -> FileResponse:
    """Serve respiratory sound audio files.
    
    Args:
        filename: Name of the audio file to serve
        
    Returns:
        FileResponse with the audio file
        
    Raises:
        HTTPException: If file not found or access denied
    """
    try:
        # Security: Only allow specific file extensions
        allowed_extensions = {'.wav', '.mp3', '.m4a', '.flac'}
        file_path = Path(filename)
        
        if file_path.suffix.lower() not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file extension. Only audio files are allowed."
            )
        
        # Construct full file path
        full_path = AUDIO_BASE_PATH / filename
        
        # Security: Ensure file is within the audio directory
        try:
            full_path = full_path.resolve()
            AUDIO_BASE_PATH_RESOLVED = AUDIO_BASE_PATH.resolve()
            full_path.relative_to(AUDIO_BASE_PATH_RESOLVED)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: File path outside allowed directory"
            )
        
        # Check if file exists
        if not full_path.exists():
            logger.warning(f"Audio file not found: {filename}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Audio file not found: {filename}"
            )
        
        # Get MIME type
        mime_type, _ = mimetypes.guess_type(str(full_path))
        if not mime_type:
            mime_type = "audio/wav"  # Default for WAV files
        
        logger.info(f"Serving audio file: {filename}")
        
        return FileResponse(
            path=str(full_path),
            media_type=mime_type,
            filename=filename,
            headers={
                "Content-Disposition": f"inline; filename={filename}",
                "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET",
                "Access-Control-Allow-Headers": "Range"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving audio file {filename}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error serving audio file: {str(e)}"
        )

@router.get(
    "/respiratory/",
    summary="List available respiratory audio files",
    description="Get a list of available respiratory sound audio files"
)
async def list_respiratory_audio() -> dict:
    """List available respiratory sound audio files.
    
    Returns:
        Dictionary with list of available audio files
    """
    try:
        if not AUDIO_BASE_PATH.exists():
            logger.warning(f"Audio directory not found: {AUDIO_BASE_PATH}")
            return {"files": [], "message": "Audio directory not found"}
        
        # Find all audio files
        audio_files = []
        allowed_extensions = {'.wav', '.mp3', '.m4a', '.flac'}
        
        for file_path in AUDIO_BASE_PATH.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in allowed_extensions:
                relative_path = file_path.relative_to(AUDIO_BASE_PATH)
                audio_files.append({
                    "filename": file_path.name,
                    "relative_path": str(relative_path),
                    "size": file_path.stat().st_size,
                    "extension": file_path.suffix.lower()
                })
        
        logger.info(f"Found {len(audio_files)} audio files")
        
        return {
            "files": audio_files,
            "total_count": len(audio_files),
            "base_path": str(AUDIO_BASE_PATH)
        }
        
    except Exception as e:
        logger.error(f"Error listing audio files: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing audio files: {str(e)}"
        )

@router.get(
    "/health",
    summary="Audio service health check",
    description="Check if the audio service is working properly"
)
async def audio_health_check() -> dict:
    """Check audio service health.
    
    Returns:
        Dictionary with health status
    """
    try:
        # Check if audio directory exists
        audio_dir_exists = AUDIO_BASE_PATH.exists()
        
        # Count audio files if directory exists
        audio_file_count = 0
        if audio_dir_exists:
            allowed_extensions = {'.wav', '.mp3', '.m4a', '.flac'}
            audio_file_count = len([
                f for f in AUDIO_BASE_PATH.rglob("*") 
                if f.is_file() and f.suffix.lower() in allowed_extensions
            ])
        
        return {
            "status": "healthy" if audio_dir_exists else "unhealthy",
            "audio_directory_exists": audio_dir_exists,
            "audio_file_count": audio_file_count,
            "base_path": str(AUDIO_BASE_PATH)
        }
        
    except Exception as e:
        logger.error(f"Error in audio health check: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }
