"""
Core TTS Service using Coqui TTS XTTSv2
Handles model initialization, synthesis, and streaming
"""
import torch
import numpy as np
from TTS.api import TTS
from typing import Generator, Optional, Tuple
import logging
import io
import soundfile as sf
from pathlib import Path
from config import config
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TTSService:
    """
    TTS Service managing Coqui TTS XTTSv2 model
    Provides synthesis and streaming capabilities
    """
    
    def __init__(self):
        self.model = None
        self.device = None
        self.model_loaded = False
        self.default_speaker_embedding = None  # Cache for default speaker
        self.speaker_cache = {}  # Cache for multiple speakers
        
    def initialize(self):
        """Initialize the TTS model"""
        try:
            logger.info(f"Initializing TTS model: {config.model_name}")
            
            # Determine device
            self.device = "cuda" if config.use_cuda and torch.cuda.is_available() else "cpu"
            logger.info(f"Using device: {self.device}")
            
            # Initialize TTS model
            self.model = TTS(config.model_name).to(self.device)
            
            # Pre-load default speaker audio into memory
            if config.default_speaker_wav:
                self._cache_default_speaker()
            
            self.model_loaded = True
            logger.info("TTS model initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize TTS model: {e}")
            raise
    
    def _cache_default_speaker(self):
        """Pre-load and cache the default speaker audio"""
        try:
            speaker_path = Path(config.default_speaker_wav)
            if speaker_path.exists():
                logger.info(f"Caching default speaker audio: {config.default_speaker_wav}")
                
                # Store the path in cache for quick access
                self.speaker_cache['default'] = str(speaker_path.absolute())
                
                logger.info("Default speaker cached successfully")
            else:
                logger.warning(f"Default speaker file not found: {config.default_speaker_wav}")
        except Exception as e:
            logger.error(f"Failed to cache default speaker: {e}")
    
    def synthesize(
        self, 
        text: str, 
        language: str = "en",
        speaker_wav: Optional[str] = None,
        speed: float = 1.0
    ) -> Tuple[np.ndarray, int, dict]:
        """
        Synthesize speech from text
        
        Args:
            text: Text to convert to speech
            language: Language code
            speaker_wav: Path to speaker audio for voice cloning
            speed: Speech speed multiplier
            
        Returns:
            Tuple of (audio_array, sample_rate, metrics)
        """
        if not self.model_loaded:
            raise RuntimeError("TTS model not initialized. Call initialize() first.")
        
        start_time = time.time()
        metrics = {}
        
        try:
            logger.info(f"Synthesizing text (length: {len(text)}, language: {language})")
            
            # Use provided speaker_wav, or fall back to cached default
            if not speaker_wav:
                if 'default' in self.speaker_cache:
                    speaker_wav = self.speaker_cache['default']
                    logger.info(f"Using cached default speaker")
                elif config.default_speaker_wav:
                    speaker_wav = config.default_speaker_wav
                    logger.info(f"Using default speaker: {speaker_wav}")
            
            # Check model capabilities based on model name
            model_name = config.model_name.lower()
            is_multi_lingual = "xtts" in model_name or "multilingual" in model_name
            
            # Build TTS parameters based on model capabilities
            tts_params = {"text": text, "speed": speed}
            
            # Add language only for multi-lingual models
            if is_multi_lingual:
                tts_params["language"] = language
                logger.info(f"Multi-lingual model detected, adding language: {language}")
            
            # Add speaker_wav if available (for voice cloning models)
            if speaker_wav and Path(speaker_wav).exists():
                tts_params["speaker_wav"] = speaker_wav
                logger.info(f"Using speaker audio: {speaker_wav}")
            
            synthesis_start = time.time()
            logger.info(f"TTS call parameters: {list(tts_params.keys())}")
            wav = self.model.tts(**tts_params)
            synthesis_time = time.time() - synthesis_start
            
            # Convert to numpy array if needed
            if isinstance(wav, list):
                wav = np.array(wav)
            
            total_time = time.time() - start_time
            audio_duration = len(wav) / config.sample_rate
            real_time_factor = audio_duration / synthesis_time if synthesis_time > 0 else 0
            
            metrics = {
                "synthesis_time_ms": round(synthesis_time * 1000, 2),
                "total_time_ms": round(total_time * 1000, 2),
                "audio_duration_s": round(audio_duration, 2),
                "real_time_factor": round(real_time_factor, 2),
                "text_length": len(text)
            }
            
            logger.info(
                f"Synthesis complete. Audio: {len(wav)} samples ({audio_duration:.2f}s), "
                f"Time: {synthesis_time:.2f}s, RTF: {real_time_factor:.2f}x"
            )
            return wav, config.sample_rate, metrics
            
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            raise
    
    def synthesize_streaming(
        self,
        text: str,
        language: str = "en",
        speaker_wav: Optional[str] = None,
        chunk_size: int = 4096
    ) -> Generator[bytes, None, None]:
        """
        Synthesize speech with streaming output
        
        Args:
            text: Text to convert to speech
            language: Language code
            speaker_wav: Path to speaker audio
            chunk_size: Size of audio chunks to yield
            
        Yields:
            Audio chunks as bytes (first chunk includes WAV header, rest is raw PCM)
        """
        if not self.model_loaded:
            raise RuntimeError("TTS model not initialized")
        
        try:
            logger.info(f"Starting streaming synthesis for text length: {len(text)}")
            
            # Split text into sentences for progressive synthesis
            sentences = self._split_text(text)
            
            # Track if we've sent the header
            header_sent = False
            
            for i, sentence in enumerate(sentences):
                if not sentence.strip():
                    continue
                
                logger.info(f"Synthesizing chunk {i+1}/{len(sentences)}")
                
                # Synthesize sentence
                wav, sample_rate, _ = self.synthesize(
                    text=sentence,
                    language=language,
                    speaker_wav=speaker_wav
                )
                
                # For first chunk: send with WAV header
                # For subsequent chunks: send raw PCM data only
                if not header_sent:
                    audio_bytes = self._audio_to_bytes(wav, sample_rate)
                    header_sent = True
                else:
                    # Convert to raw PCM bytes (16-bit)
                    audio_bytes = (wav * 32767).astype(np.int16).tobytes()
                
                # Yield chunks
                for chunk_start in range(0, len(audio_bytes), chunk_size):
                    chunk = audio_bytes[chunk_start:chunk_start + chunk_size]
                    yield chunk
                    
        except Exception as e:
            logger.error(f"Streaming synthesis failed: {e}")
            raise
    
    def _split_text(self, text: str, max_length: int = None) -> list:
        """
        Split text into manageable chunks for streaming
        
        Args:
            text: Input text
            max_length: Maximum length per chunk
            
        Returns:
            List of text chunks
        """
        if max_length is None:
            max_length = config.max_text_length
        
        # Split by sentences for progressive streaming
        import re
        # Split on sentence endings (. ! ?)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        chunks = []
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            # If sentence is too long, split it further
            if len(sentence) > max_length:
                # Split on commas or semicolons
                sub_chunks = re.split(r'(?<=[,;])\s+', sentence)
                for sub in sub_chunks:
                    sub = sub.strip()
                    if sub:
                        chunks.append(sub)
            else:
                chunks.append(sentence)
        
        return chunks if chunks else [text]
    
    def _audio_to_bytes(self, audio: np.ndarray, sample_rate: int) -> bytes:
        """
        Convert numpy audio array to bytes
        
        Args:
            audio: Audio as numpy array
            sample_rate: Sample rate
            
        Returns:
            Audio as bytes (WAV format)
        """
        buffer = io.BytesIO()
        sf.write(buffer, audio, sample_rate, format='WAV')
        buffer.seek(0)
        return buffer.read()
    
    def save_audio(self, audio: np.ndarray, sample_rate: int, output_path: str):
        """
        Save audio to file
        
        Args:
            audio: Audio array
            sample_rate: Sample rate
            output_path: Output file path
        """
        sf.write(output_path, audio, sample_rate)
        logger.info(f"Audio saved to: {output_path}")
    
    def is_ready(self) -> bool:
        """Check if service is ready"""
        return self.model_loaded
    
    def get_device(self) -> str:
        """Get current device"""
        return self.device if self.device else "not initialized"


# Global service instance
tts_service = TTSService()
