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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d | %(levelname)-5s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


class TTSService:
    """
    TTS Service managing dual Coqui TTS models:
    - Tacotron2-DDC for fast streaming TTS
    - XTTSv2 for voice cloning
    """
    
    def __init__(self):
        self.tts_model = None          # Fast TTS (Tacotron2-DDC)
        self.clone_model = None        # Voice cloning (XTTSv2)
        self.device = None
        self.tts_model_loaded = False
        self.clone_model_loaded = False
        self.default_speaker_embedding = None
        self.speaker_cache = {}
        
    def initialize(self):
        """Initialize both TTS models"""
        try:
            # Determine device
            self.device = "cuda" if config.use_cuda and torch.cuda.is_available() else "cpu"
            logger.info(f"Using device: {self.device}")
            
            # Load fast TTS model (Tacotron2-DDC)
            logger.info(f"Loading TTS model: {config.tts_model_name}")
            self.tts_model = TTS(config.tts_model_name).to(self.device)
            self.tts_model_loaded = True
            logger.info("TTS model loaded successfully")
            
            # Load voice cloning model (XTTSv2) if enabled
            if config.enable_clone_model:
                logger.info(f"Loading clone model: {config.clone_model_name}")
                self.clone_model = TTS(config.clone_model_name).to(self.device)
                self.clone_model_loaded = True
                logger.info("Clone model loaded successfully")
            else:
                logger.info("Clone model disabled (enable_clone_model=False)")
            
            # Pre-load default speaker audio
            if config.default_speaker_wav:
                self._cache_default_speaker()
            
            logger.info("All models initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize TTS models: {e}")
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
        speed: float = 1.0,
        use_clone_model: bool = False
    ) -> Tuple[np.ndarray, int, dict]:
        """
        Synthesize speech from text
        
        Args:
            text: Text to convert to speech
            language: Language code
            speaker_wav: Path to speaker audio for voice cloning
            speed: Speech speed multiplier
            use_clone_model: If True, use XTTSv2 for voice cloning; else use Tacotron2-DDC
            
        Returns:
            Tuple of (audio_array, sample_rate, metrics)
        """
        # Select the appropriate model
        if use_clone_model:
            if not self.clone_model_loaded:
                raise RuntimeError("Clone model (XTTSv2) not initialized.")
            model = self.clone_model
            model_label = "CLONE/XTTSv2"
        else:
            if not self.tts_model_loaded:
                raise RuntimeError("TTS model (Tacotron2-DDC) not initialized.")
            model = self.tts_model
            model_label = "TTS/Tacotron2"
        
        start_time = time.time()
        metrics = {}
        
        try:
            logger.info(f"[{model_label}] Synthesizing text (length: {len(text)}, language: {language})")
            
            # Use provided speaker_wav, or fall back to cached default
            if not speaker_wav:
                if 'default' in self.speaker_cache:
                    speaker_wav = self.speaker_cache['default']
                    logger.info(f"Using cached default speaker")
                elif config.default_speaker_wav:
                    speaker_wav = config.default_speaker_wav
                    logger.info(f"Using default speaker: {speaker_wav}")
            
            # Build TTS parameters based on model type
            tts_params = {"text": text, "speed": speed}
            
            if use_clone_model:
                # XTTSv2 requires language and speaker_wav
                tts_params["language"] = language
                if speaker_wav and Path(speaker_wav).exists():
                    tts_params["speaker_wav"] = speaker_wav
                    logger.info(f"Using speaker audio: {speaker_wav}")
            
            synthesis_start = time.time()
            logger.info(f"[{model_label}] TTS params: {list(tts_params.keys())}")
            wav = model.tts(**tts_params)
            synthesis_time = time.time() - synthesis_start
            
            # Convert to numpy array if needed
            if isinstance(wav, list):
                wav = np.array(wav)
            
            # Safeguard: truncate runaway audio (Tacotron2 attention failure)
            # Normal speech: ~10-15 chars/second. Allow max 0.5s per character.
            max_duration_s = max(len(text) * 0.5, 2.0)  # at least 2 seconds
            max_samples = int(max_duration_s * config.sample_rate)
            if len(wav) > max_samples:
                actual_duration = len(wav) / config.sample_rate
                logger.warning(
                    f"[{model_label}] Audio truncated: {actual_duration:.1f}s -> {max_duration_s:.1f}s "
                    f"(text: {len(text)} chars, likely attention failure)"
                )
                wav = wav[:max_samples]
            
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
                f"[{model_label}] Complete: {len(wav)} samples ({audio_duration:.2f}s), "
                f"Time: {synthesis_time:.2f}s, RTF: {real_time_factor:.2f}x"
            )
            return wav, config.sample_rate, metrics
            
        except Exception as e:
            logger.error(f"[{model_label}] Synthesis failed: {e}")
            raise
    
    def synthesize_streaming(
        self,
        text: str,
        language: str = "en",
        speaker_wav: Optional[str] = None,
        chunk_size: int = 4096,
        use_clone_model: bool = False
    ) -> Generator[bytes, None, None]:
        """
        Synthesize speech with streaming output
        
        Args:
            text: Text to convert to speech
            language: Language code
            speaker_wav: Path to speaker audio
            chunk_size: Size of audio chunks to yield
            use_clone_model: If True, use XTTSv2; else Tacotron2-DDC
            
        Yields:
            Audio chunks as bytes (first chunk includes WAV header, rest is raw PCM)
        """
        try:
            model_label = "CLONE" if use_clone_model else "TTS"
            logger.info(f"[{model_label}] Starting streaming synthesis for text length: {len(text)}")
            
            # Split text into sentences for progressive synthesis
            sentences = self._split_text(text)
            
            # Track if we've sent the header
            header_sent = False
            
            for i, sentence in enumerate(sentences):
                if not sentence.strip():
                    continue
                
                logger.info(f"[{model_label}] Synthesizing chunk {i+1}/{len(sentences)}")
                
                # Synthesize sentence using the appropriate model
                wav, sample_rate, _ = self.synthesize(
                    text=sentence,
                    language=language,
                    speaker_wav=speaker_wav,
                    use_clone_model=use_clone_model
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
        """Check if at least one model is ready"""
        return self.tts_model_loaded or self.clone_model_loaded
    
    def is_clone_ready(self) -> bool:
        """Check if clone model is ready"""
        return self.clone_model_loaded
    
    def get_device(self) -> str:
        """Get current device"""
        return self.device if self.device else "not initialized"


# Global service instance
tts_service = TTSService()
