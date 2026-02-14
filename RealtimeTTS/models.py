"""
Pydantic models for TTS API
Handles request validation and response formatting
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from config import SUPPORTED_LANGUAGES


class TTSRequest(BaseModel):
    """Request model for text-to-speech conversion"""
    text: str = Field(..., min_length=1, max_length=5000, description="Text to convert to speech")
    language: str = Field(default="en", description="Language code (e.g., 'en', 'es', 'fr')")
    speaker_wav: Optional[str] = Field(None, description="Path to speaker audio file for voice cloning")
    speed: float = Field(default=1.0, ge=0.5, le=2.0, description="Speech speed multiplier")
    
    @validator("language")
    def validate_language(cls, v):
        if v not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Language {v} not supported. Supported languages: {', '.join(SUPPORTED_LANGUAGES)}")
        return v


class TTSStreamRequest(BaseModel):
    """Request model for streaming TTS"""
    text: str = Field(..., min_length=1, description="Text to convert to speech")
    language: str = Field(default="en", description="Language code")
    speaker_wav: Optional[str] = Field(None, description="Path to speaker audio file")
    chunk_size: int = Field(default=4096, ge=1024, le=8192, description="Audio chunk size for streaming")
    
    @validator("language")
    def validate_language(cls, v):
        if v not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Language {v} not supported")
        return v


class TTSResponse(BaseModel):
    """Response model for TTS conversion"""
    success: bool
    message: str
    audio_url: Optional[str] = None
    duration: Optional[float] = None  # Audio duration in seconds
    sample_rate: int
    # Performance metrics
    synthesis_time_ms: Optional[float] = None
    total_time_ms: Optional[float] = None
    audio_duration_s: Optional[float] = None
    real_time_factor: Optional[float] = None
    text_length: Optional[int] = None


class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str
    model_loaded: bool
    cuda_available: bool
    supported_languages: List[str]


class VoiceCloneRequest(BaseModel):
    """Request for voice cloning"""
    text: str = Field(..., min_length=1, max_length=5000)
    speaker_audio_path: str = Field(..., description="Path to reference audio (6+ seconds)")
    language: str = Field(default="en")
    
    @validator("language")
    def validate_language(cls, v):
        if v not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Language {v} not supported")
        return v


class ErrorResponse(BaseModel):
    """Error response model"""
    success: bool = False
    error: str
    detail: Optional[str] = None
