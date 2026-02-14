"""
FastAPI TTS API Server
Provides REST and WebSocket endpoints for real-time text-to-speech
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
import asyncio
from pathlib import Path
import uuid
from datetime import datetime

from models import (
    TTSRequest, TTSResponse, TTSStreamRequest, 
    HealthCheckResponse, VoiceCloneRequest, ErrorResponse
)
from tts_service import tts_service
from config import config, SUPPORTED_LANGUAGES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Coqui TTS API",
    description="Real-time Text-to-Speech API using Coqui TTS XTTSv2",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create output directory for generated audio
OUTPUT_DIR = Path("./generated_audio")
OUTPUT_DIR.mkdir(exist_ok=True)


@app.on_event("startup")
async def startup_event():
    """Initialize TTS service on startup"""
    logger.info("Starting TTS API server...")
    try:
        tts_service.initialize()
        logger.info("TTS service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize TTS service: {e}")
        raise


@app.get("/", tags=["General"])
async def root():
    """Root endpoint"""
    return {
        "service": "Coqui TTS API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "tts": "/api/tts",
            "tts_stream": "/api/tts/stream",
            "websocket": "/ws/tts"
        }
    }


@app.get("/health", response_model=HealthCheckResponse, tags=["General"])
async def health_check():
    """Health check endpoint"""
    import torch
    
    return HealthCheckResponse(
        status="healthy" if tts_service.is_ready() else "unhealthy",
        model_loaded=tts_service.is_ready(),
        cuda_available=torch.cuda.is_available(),
        supported_languages=SUPPORTED_LANGUAGES
    )


@app.post("/api/tts", response_model=TTSResponse, tags=["TTS"])
async def text_to_speech(request: TTSRequest, background_tasks: BackgroundTasks):
    """
    Convert text to speech (REST endpoint)
    Returns audio file URL
    """
    try:
        logger.info(f"Received TTS request: {len(request.text)} characters, language: {request.language}")
        
        # Generate unique filename
        file_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"tts_{timestamp}_{file_id}.wav"
        output_path = OUTPUT_DIR / output_filename
        
        # Synthesize speech
        audio, sample_rate, metrics = tts_service.synthesize(
            text=request.text,
            language=request.language,
            speaker_wav=request.speaker_wav,
            speed=request.speed
        )
        
        # Save audio file
        tts_service.save_audio(audio, sample_rate, str(output_path))
        
        # Calculate duration
        duration = len(audio) / sample_rate
        
        # Log metrics
        logger.info(f"Synthesis metrics: {metrics}")
        
        # Schedule cleanup after 1 hour
        background_tasks.add_task(cleanup_file, output_path, delay=3600)
        
        return TTSResponse(
            success=True,
            message="Text-to-speech conversion successful",
            audio_url=f"/audio/{output_filename}",
            duration=duration,
            sample_rate=sample_rate,
            **metrics  # Include metrics in response
        )
        
    except Exception as e:
        logger.error(f"TTS conversion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tts/stream", tags=["TTS"])
async def text_to_speech_stream(request: TTSStreamRequest):
    """
    Convert text to speech with streaming response
    Returns audio stream
    """
    try:
        logger.info(f"Received streaming TTS request: {len(request.text)} characters")
        
        def generate():
            """Generator for streaming audio"""
            for chunk in tts_service.synthesize_streaming(
                text=request.text,
                language=request.language,
                speaker_wav=request.speaker_wav,
                chunk_size=request.chunk_size
            ):
                yield chunk
        
        return StreamingResponse(
            generate(),
            media_type="audio/wav",
            headers={
                "Content-Disposition": "inline; filename=speech.wav",
                "Cache-Control": "no-cache"
            }
        )
        
    except Exception as e:
        logger.error(f"Streaming TTS failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/tts")
async def websocket_tts(websocket: WebSocket):
    """
    WebSocket endpoint for real-time TTS
    
    Protocol:
    - Client sends: {"text": "...", "language": "en", "speaker_wav": null}
    - Server streams: audio chunks as binary data
    - Server sends: {"status": "complete"} when done
    """
    # Accept with longer ping timeout for long audio generation
    await websocket.accept()
    logger.info("WebSocket connection established")
    
    # Configure ping/pong parameters to prevent timeout during long synthesis
    # This prevents "keepalive ping failed" errors during real-time playback
    websocket.client_state.ping_timeout = 60  # Increase from default 20s to 60s
    
    try:
        while True:
            # Receive text from client
            data = await websocket.receive_json()
            
            text = data.get("text", "")
            language = data.get("language", "en")
            speaker_wav = data.get("speaker_wav", None)
            
            if not text:
                await websocket.send_json({"error": "No text provided"})
                continue
            
            logger.info(f"WebSocket TTS: {len(text)} characters, language: {language}")
            
            # Send status
            await websocket.send_json({"status": "processing"})
            
            # Stream audio chunks
            chunk_count = 0
            for chunk in tts_service.synthesize_streaming(
                text=text,
                language=language,
                speaker_wav=speaker_wav
            ):
                await websocket.send_bytes(chunk)
                chunk_count += 1
            
            # Send completion status
            await websocket.send_json({
                "status": "complete",
                "chunks_sent": chunk_count
            })
            logger.info(f"WebSocket TTS complete: {chunk_count} chunks sent")
            
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"error": str(e)})
        except:
            pass


@app.post("/api/voice-clone", response_model=TTSResponse, tags=["Voice Cloning"])
async def voice_clone(request: VoiceCloneRequest, background_tasks: BackgroundTasks):
    """
    Generate speech with voice cloning
    Requires reference audio file (6+ seconds)
    """
    try:
        # Verify speaker audio exists
        if not Path(request.speaker_audio_path).exists():
            raise HTTPException(
                status_code=400, 
                detail=f"Speaker audio file not found: {request.speaker_audio_path}"
            )
        
        logger.info(f"Voice cloning request with speaker: {request.speaker_audio_path}")
        
        # Generate output filename
        file_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"cloned_{timestamp}_{file_id}.wav"
        output_path = OUTPUT_DIR / output_filename
        
        # Synthesize with voice cloning
        audio, sample_rate, _ = tts_service.synthesize(
            text=request.text,
            language=request.language,
            speaker_wav=request.speaker_audio_path
        )
        
        # Save audio
        tts_service.save_audio(audio, sample_rate, str(output_path))
        
        duration = len(audio) / sample_rate
        
        # Schedule cleanup
        background_tasks.add_task(cleanup_file, output_path, delay=3600)
        
        return TTSResponse(
            success=True,
            message="Voice cloning successful",
            audio_url=f"/audio/{output_filename}",
            duration=duration,
            sample_rate=sample_rate
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice cloning failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/audio/{filename}", tags=["Audio"])
async def get_audio(filename: str):
    """
    Serve generated audio files
    """
    file_path = OUTPUT_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    return FileResponse(
        file_path,
        media_type="audio/wav",
        filename=filename
    )


async def cleanup_file(file_path: Path, delay: int = 0):
    """
    Clean up generated audio file after delay
    
    Args:
        file_path: Path to file
        delay: Delay in seconds before deletion
    """
    if delay > 0:
        await asyncio.sleep(delay)
    
    try:
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Cleaned up file: {file_path}")
    except Exception as e:
        logger.error(f"Failed to cleanup file {file_path}: {e}")


if __name__ == "__main__":
    # Run the server
    uvicorn.run(
        "tts_api:app",
        host=config.host,
        port=config.port,
        workers=config.workers,
        reload=False
    )
