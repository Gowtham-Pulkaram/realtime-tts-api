"""
Configuration module for TTS API
Manages settings for models, audio, and server configuration
"""
from pydantic_settings import BaseSettings
from typing import Optional
import os


class TTSConfig(BaseSettings):
    """TTS API Configuration"""
    
    # Model Settings
    #model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    model_name: str = "tts_models/en/ljspeech/tacotron2-DDC"
    use_cuda: bool = True  # Use GPU if available
    
    # Audio Settings
    sample_rate: int = 24000  # XTTSv2 default sample rate
    audio_format: str = "wav"
    chunk_size: int = 4096  # For streaming
    
    # Server Settings
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1  # Keep at 1 for model consistency
    
    # Voice Settings
    default_language: str = "en"
    #default_speaker_wav: Optional[str] = "new.mp3"  # Default voice for cloning
    default_speaker_wav: Optional[str] = None  # Default voice for cloning
    
    # Paths
    model_cache_dir: str = os.path.join(os.path.expanduser("~"), ".cache", "tts")
    voice_samples_dir: str = "./voice_samples"
    
    # Performance
    enable_text_splitting: bool = True  # Split long texts for better streaming
    max_text_length: int = 500  # Characters per chunk
    
    class Config:
        env_prefix = "TTS_"
        env_file = ".env"


# Global config instance
config = TTSConfig()


# Predefined voice configurations
VOICE_PRESETS = {
    "default": {
        "language": "en",
        "speaker_wav": None,
    },
    "en_male": {
        "language": "en",
        "speaker_wav": "samples/male_voice.wav",
    },
    "en_female": {
        "language": "en",
        "speaker_wav": "samples/female_voice.wav",
    },
}


# Supported languages for XTTSv2
SUPPORTED_LANGUAGES = [
    "en", "es", "fr", "de", "it", "pt", "pl", "tr", 
    "ru", "nl", "cs", "ar", "zh-cn", "ja", "hu", "ko", "hi"
]
