"""
FastAPI TTS API Server
Provides REST and WebSocket endpoints for real-time text-to-speech
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
import asyncio
from pathlib import Path
import uuid
from datetime import datetime
import time
import queue  # thread-safe queue for WebSocket streaming

from models import (
    TTSRequest, TTSResponse, TTSStreamRequest, 
    HealthCheckResponse, VoiceCloneRequest, ErrorResponse
)
from tts_service import tts_service
from config import config, SUPPORTED_LANGUAGES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d | %(levelname)-5s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
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

# Create voice samples directory
VOICE_SAMPLES_DIR = Path("./voice_samples")
VOICE_SAMPLES_DIR.mkdir(exist_ok=True)

# Create static directory
STATIC_DIR = Path("./static")
STATIC_DIR.mkdir(exist_ok=True)


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


@app.get("/api/info", tags=["General"])
async def api_info():
    """API info endpoint"""
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
    request_start = time.time()
    try:
        logger.info(f"[REST] ── Request received: {len(request.text)} chars, language: {request.language}")
        
        # Generate unique filename
        file_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"tts_{timestamp}_{file_id}.wav"
        output_path = OUTPUT_DIR / output_filename
        
        # Synthesize speech
        synth_start = time.time()
        audio, sample_rate, metrics = tts_service.synthesize(
            text=request.text,
            language=request.language,
            speaker_wav=request.speaker_wav,
            speed=request.speed
        )
        synth_elapsed = time.time() - synth_start
        
        # Save audio file
        tts_service.save_audio(audio, sample_rate, str(output_path))
        
        # Calculate duration
        duration = len(audio) / sample_rate
        total_elapsed = time.time() - request_start
        
        # Log stats
        logger.info(
            f"[REST] ── Stats: "
            f"synthesis={synth_elapsed:.3f}s | "
            f"audio_duration={duration:.2f}s | "
            f"total_request={total_elapsed:.3f}s | "
            f"RTF={metrics.get('real_time_factor', 0):.2f}x"
        )
        
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
        logger.error(f"[REST] ── Error after {time.time() - request_start:.3f}s: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tts/stream", tags=["TTS"])
async def text_to_speech_stream(request: TTSStreamRequest):
    """
    Convert text to speech with streaming response
    Returns audio stream
    """
    try:
        logger.info(f"[STREAM] ── Request received: {len(request.text)} chars")
        stream_start = time.time()
        
        def generate():
            """Generator for streaming audio"""
            chunk_count = 0
            total_bytes = 0
            first_chunk_time = None
            for chunk in tts_service.synthesize_streaming(
                text=request.text,
                language=request.language,
                speaker_wav=request.speaker_wav,
                chunk_size=request.chunk_size
            ):
                chunk_count += 1
                total_bytes += len(chunk)
                if first_chunk_time is None:
                    first_chunk_time = time.time()
                    ttfb = first_chunk_time - stream_start
                    logger.info(f"[STREAM] ── TTFB (time to first byte): {ttfb:.3f}s")
                yield chunk
            
            elapsed = time.time() - stream_start
            logger.info(
                f"[STREAM] ── Complete: "
                f"{chunk_count} chunks | "
                f"{total_bytes / 1024:.1f} KB | "
                f"total={elapsed:.3f}s"
            )
        
        return StreamingResponse(
            generate(),
            media_type="audio/wav",
            headers={
                "Content-Disposition": "inline; filename=speech.wav",
                "Cache-Control": "no-cache"
            }
        )
        
    except Exception as e:
        logger.error(f"[STREAM] ── Error: {e}")
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
    connect_time = time.time()
    client_host = websocket.client.host if websocket.client else "unknown"
    logger.info(f"[WS] ══ Connected from {client_host}")
    request_count = 0
    try:
        while True:
            # Receive text from client
            data = await websocket.receive_json()
            request_count += 1
            request_start = time.time()
            
            text = data.get("text", "")
            language = data.get("language", "en")
            speaker_wav = data.get("speaker_wav", None)
            
            if not text:
                await websocket.send_json({"error": "No text provided"})
                continue
            
            logger.info(
                f"[WS] ── Request #{request_count}: "
                f"{len(text)} chars, language={language}, "
                f"speaker={'yes' if speaker_wav else 'default'}"
            )
            
            # Send status
            await websocket.send_json({"status": "processing"})
            
            # Stream audio chunks using a background thread
            # (synthesis is CPU-bound and would block the event loop,
            #  causing WebSocket ping/pong timeouts on long texts)
            chunk_count = 0
            total_bytes = 0
            first_chunk_time = None
            
            # Use thread-safe queue (asyncio.Queue is NOT thread-safe!)
            chunk_q = queue.Queue()
            
            def _run_synthesis():
                """Run blocking synthesis in a thread, push chunks to queue"""
                try:
                    for chunk in tts_service.synthesize_streaming(
                        text=text,
                        language=language,
                        speaker_wav=speaker_wav
                    ):
                        chunk_q.put(chunk)
                    chunk_q.put(None)  # sentinel: done
                except Exception as e:
                    chunk_q.put(e)  # push error
            
            # Start synthesis in background thread
            loop = asyncio.get_event_loop()
            synthesis_task = loop.run_in_executor(None, _run_synthesis)
            
            # Read chunks from queue and send over WebSocket
            while True:
                # Poll queue with short timeout to keep event loop responsive
                try:
                    chunk = await asyncio.wait_for(
                        loop.run_in_executor(None, lambda: chunk_q.get(timeout=1)),
                        timeout=120
                    )
                except queue.Empty:
                    continue  # no chunk yet, keep waiting
                
                if chunk is None:
                    break  # synthesis complete
                if isinstance(chunk, Exception):
                    raise chunk
                
                await websocket.send_bytes(chunk)
                chunk_count += 1
                total_bytes += len(chunk)
                
                if first_chunk_time is None:
                    first_chunk_time = time.time()
                    ttfb = first_chunk_time - request_start
                    logger.info(f"[WS] ── TTFB (time to first byte): {ttfb:.3f}s")
            
            await synthesis_task  # ensure thread is done
            
            elapsed = time.time() - request_start
            transfer_rate = (total_bytes / 1024) / elapsed if elapsed > 0 else 0
            
            # Send completion status with stats
            stats = {
                "status": "complete",
                "chunks_sent": chunk_count,
                "total_bytes": total_bytes,
                "ttfb_ms": round((first_chunk_time - request_start) * 1000, 1) if first_chunk_time else None,
                "total_time_ms": round(elapsed * 1000, 1),
            }
            await websocket.send_json(stats)
            
            logger.info(
                f"[WS] ── Complete: "
                f"{chunk_count} chunks | "
                f"{total_bytes / 1024:.1f} KB | "
                f"TTFB={stats['ttfb_ms']}ms | "
                f"total={elapsed:.3f}s | "
                f"rate={transfer_rate:.1f} KB/s"
            )
            
    except WebSocketDisconnect:
        session_duration = time.time() - connect_time
        logger.info(
            f"[WS] ══ Disconnected: {client_host} | "
            f"session={session_duration:.1f}s | "
            f"requests={request_count}"
        )
    except Exception as e:
        session_duration = time.time() - connect_time
        logger.error(
            f"[WS] ══ Error after {session_duration:.1f}s: {e}"
        )
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
        
        # Synthesize with voice cloning (uses XTTSv2)
        audio, sample_rate, _ = tts_service.synthesize(
            text=request.text,
            language=request.language,
            speaker_wav=request.speaker_audio_path,
            use_clone_model=True
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


# ── Voice Upload Endpoint ──────────────────────────────────────────

ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}
MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB


@app.post("/api/upload-voice", tags=["Voice Cloning"])
async def upload_voice(file: UploadFile = File(...)):
    """
    Upload a voice sample for cloning.
    Accepts WAV, MP3, FLAC, OGG files (max 20MB).
    Returns the saved filename for use with /api/voice-clone.
    """
    try:
        # Validate file extension
        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_AUDIO_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_AUDIO_EXTENSIONS)}"
            )

        # Read and validate size
        content = await file.read()
        if len(content) > MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large ({len(content) / 1024 / 1024:.1f}MB). Max: {MAX_UPLOAD_SIZE / 1024 / 1024:.0f}MB"
            )

        # Save with unique name
        file_id = str(uuid.uuid4())[:8]
        safe_name = f"voice_{file_id}{ext}"
        save_path = VOICE_SAMPLES_DIR / safe_name

        with open(save_path, "wb") as f:
            f.write(content)

        logger.info(f"[UPLOAD] Voice sample saved: {safe_name} ({len(content) / 1024:.1f} KB)")

        return {
            "success": True,
            "filename": safe_name,
            "path": str(save_path),
            "size_kb": round(len(content) / 1024, 1),
            "original_name": file.filename
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[UPLOAD] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/voices", tags=["Voice Cloning"])
async def list_voices():
    """List all uploaded voice samples"""
    voices = []
    for f in VOICE_SAMPLES_DIR.iterdir():
        if f.suffix.lower() in ALLOWED_AUDIO_EXTENSIONS:
            voices.append({
                "filename": f.name,
                "path": str(f),
                "size_kb": round(f.stat().st_size / 1024, 1)
            })
    return {"voices": voices}


# ── Serve Frontend ─────────────────────────────────────────────────
# Must be mounted LAST so API routes take priority
app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    # Run the server
    uvicorn.run(
        "tts_api:app",
        host=config.host,
        port=config.port,
        workers=config.workers,
        reload=False,
        ws="wsproto",               # Use wsproto (handles concurrent writes safely)
        ws_ping_interval=30,        # Send ping every 30s
        ws_ping_timeout=120,        # Wait up to 120s for pong
    )
