# Developer Documentation 📚

Complete technical documentation for the Real-Time TTS API codebase.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Starting & Stopping the Server](#starting--stopping-the-server)
3. [Module Documentation](#module-documentation)
4. [Function Reference](#function-reference)
5. [Code Flow](#code-flow)
6. [Configuration](#configuration)
7. [Development Guide](#development-guide)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Layer                          │
│  (REST, HTTP Streaming, WebSocket, Test Client)             │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                    FastAPI Server                            │
│                   (tts_api.py)                               │
│  ┌────────────┐  ┌────────────┐  ┌──────────────┐          │
│  │ REST       │  │ Streaming  │  │ WebSocket    │          │
│  │ /api/tts   │  │ /api/tts/  │  │ /ws/tts      │          │
│  │            │  │ stream     │  │              │          │
│  └────────────┘  └────────────┘  └──────────────┘          │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   TTS Service Layer                          │
│                  (tts_service.py)                            │
│  ┌──────────────────────────────────────────────────┐       │
│  │ TTSService                                       │       │
│  │  - initialize()                                  │       │
│  │  - synthesize()                                  │       │
│  │  - synthesize_streaming()                        │       │
│  │  - _split_text()                                 │       │
│  │  - _audio_to_bytes()                             │       │
│  └──────────────────────────────────────────────────┘       │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                  Coqui TTS Engine                            │
│           (VITS / Tacotron2 / XTTS v2)                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                 PyTorch (CUDA/CPU)                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Starting & Stopping the Server

### Starting the Server

**Method 1: Direct Python**
```bash
cd d:\Python-project\TTS-coquii\RealtimeTTS
python tts_api.py
```

**Method 2: With Uvicorn (Production)**
```bash
uvicorn tts_api:app --host 0.0.0.0 --port 8000 --reload
```

**Expected Output:**
```
INFO:     Started server process [PID]
INFO:     Waiting for application startup.
INFO:tts_api:Starting TTS API server...
INFO:tts_service:Initializing TTS model: tts_models/en/ljspeech/vits
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### Stopping the Server

**Method 1: Keyboard Interrupt**
```
Press CTRL+C in the terminal
```

**Method 2: Kill Process (Windows)**
```bash
# Find process ID
tasklist | findstr python

# Kill process
taskkill /PID <process_id> /F
```

**Method 3: Kill Process (Linux/Mac)**
```bash
# Find process
ps aux | grep tts_api

# Kill process
kill <process_id>
```

### Graceful Shutdown

The server handles graceful shutdown automatically:
1. Stops accepting new connections
2. Completes in-progress requests
3. Releases GPU memory
4. Closes file handles

---

## Module Documentation

### 1. `tts_api.py` - FastAPI Server

**Purpose**: Main HTTP/WebSocket server handling client requests

**Key Components**:
- FastAPI app initialization
- CORS middleware
- Health check endpoint
- Three TTS endpoints (REST, Streaming, WebSocket)
- Startup/shutdown event handlers

**Dependencies**:
```python
from fastapi import FastAPI, WebSocket
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
```

---

### 2. `tts_service.py` - TTS Engine

**Purpose**: Core text-to-speech synthesis logic

**Key Components**:
- `TTSService` class - Main synthesis engine
- Model initialization and management
- Audio synthesis (single and streaming)
- Text preprocessing and splitting
- Performance metrics tracking

**Dependencies**:
```python
import torch
import numpy as np
from TTS.api import TTS
import soundfile as sf
```

---

### 3. `models.py` - Data Models

**Purpose**: Pydantic models for request/response validation

**Models**:
- `TTSRequest` - Request schema
- `HealthResponse` - Health check response

**Dependencies**:
```python
from pydantic import BaseModel, Field
```

---

### 4. `config.py` - Configuration

**Purpose**: Centralized configuration using Pydantic Settings

**Configuration Sections**:
- Model settings
- Audio settings
- Performance tuning
- Server settings

**Dependencies**:
```python
from pydantic_settings import BaseSettings
```

---

### 5. `test_client.py` - Test Client

**Purpose**: Comprehensive test client for all API endpoints

**Features**:
- REST API testing
- HTTP streaming testing
- WebSocket real-time testing
- Voice cloning testing
- Health check

---

## Function Reference

### `tts_api.py`

#### `startup_event()`
**Purpose**: Initialize TTS service on server startup

**Process**:
```python
@app.on_event("startup")
async def startup_event():
    1. Log initialization message
    2. Call tts_service.initialize()
    3. Load model into memory
    4. Warm up GPU (if CUDA enabled)
```

**Returns**: None

**Side Effects**:
- Loads TTS model into memory (~500MB-2GB)
- Initializes CUDA if available
- Creates model cache directory

---

#### `health_check()`
**Endpoint**: `GET /health`

**Purpose**: Return server health status and model info

**Returns**:
```json
{
  "status": "healthy",
  "model": "tts_models/en/ljspeech/vits",
  "device": "cuda",
  "version": "1.0.0"
}
```

**Use Case**: Monitoring, load balancer health checks

---

#### `text_to_speech(request: TTSRequest)`
**Endpoint**: `POST /api/tts`

**Purpose**: Synchronous TTS - generate complete audio file

**Parameters**:
- `request.text` (str): Text to synthesize
- `request.language` (str): Language code
- `request.speaker_wav` (str): Optional speaker file

**Process**:
1. Validate request
2. Call `tts_service.synthesize()`
3. Convert audio to WAV bytes
4. Return as StreamingResponse

**Returns**: WAV audio file (binary)

**Performance**: ~1-2 seconds for typical sentence

---

#### `text_to_speech_stream(request: TTSRequest)`
**Endpoint**: `POST /api/tts/stream`

**Purpose**: Progressive streaming - start playback before completion

**Process**:
1. Validate request
2. Call `tts_service.synthesize_streaming()`
3. Yield audio chunks as generated
4. Client can start playing immediately

**Returns**: Streaming WAV chunks

**Use Case**: Long texts, reduced perceived latency

---

#### `websocket_tts(websocket: WebSocket)`
**Endpoint**: `ws://localhost:8000/ws/tts`

**Purpose**: Real-time bidirectional streaming

**Process**:
1. Accept WebSocket connection
2. Configure ping timeout (60s)
3. Receive JSON request
4. Stream audio chunks as bytes
5. Send status updates as JSON
6. Close connection on completion

**Protocol**:
- Client → Server: JSON with text
- Server → Client: Binary audio chunks
- Server → Client: JSON status messages

**Configuration**:
```python
websocket.client_state.ping_timeout = 60  # Prevent timeout
```

---

### `tts_service.py`

#### `TTSService.initialize()`
**Purpose**: Load and initialize TTS model

**Process**:
1. Detect CUDA availability
2. Set device (cuda/cpu)
3. Load model from cache or download
4. Store model in memory
5. Set model_loaded flag

**Side Effects**:
- Downloads model if not cached (~500MB-2GB)
- Allocates GPU memory
- Creates `~/.local/share/tts/` directory

**Time**: 5-30 seconds (first run), 1-5 seconds (cached)

---

#### `TTSService.synthesize(text, language, speaker_wav)`
**Purpose**: Generate complete audio for text

**Parameters**:
- `text` (str): Input text
- `language` (str): Language code
- `speaker_wav` (str): Optional voice sample

**Process**:
1. Detect model capabilities (multi-lingual, multi-speaker)
2. Build TTS parameters based on model
3. Call `model.tts()` for synthesis
4. Calculate performance metrics (RTF)
5. Return audio array + metrics

**Returns**:
```python
(
    wav: np.ndarray,        # Audio samples
    sample_rate: int,       # Sampling rate (22050)
    metrics: dict          # Performance data
)
```

**Metrics**:
```python
{
    "synthesis_time": 1.21,    # seconds
    "audio_duration": 9.48,    # seconds
    "rtf": 7.84,              # Real-time factor
    "model": "vits"
}
```

---

#### `TTSService.synthesize_streaming(text, language, speaker_wav, chunk_size)`
**Purpose**: Progressive synthesis with chunked output

**Process**:
1. Split text into sentences (`_split_text()`)
2. For each sentence:
   - Synthesize audio
   - Convert to bytes
   - Yield in 4KB chunks
3. Track header vs PCM data
4. Ensure only first chunk has WAV header

**Yields**: Audio bytes (4096 byte chunks)

**Key Feature**: First chunk includes WAV header, rest is raw PCM

**Use Case**: Real-time playback during synthesis

---

#### `TTSService._split_text(text, max_length)`
**Purpose**: Split text into synthesizable chunks

**Algorithm**:
1. Split on sentence endings (`.`, `!`, `?`)
2. If sentence > max_length, split on commas/semicolons
3. Return list of chunks

**Parameters**:
- `text` (str): Input text
- `max_length` (int): Max characters per chunk (default: 250)

**Returns**: `list[str]` - Text chunks

**Example**:
```python
Input: "Hello world. How are you?"
Output: ["Hello world.", "How are you?"]
```

---

#### `TTSService._audio_to_bytes(audio, sample_rate)`
**Purpose**: Convert numpy audio to WAV bytes

**Process**:
1. Create BytesIO buffer
2. Write audio using soundfile
3. Add WAV header
4. Return bytes

**Returns**: `bytes` - Complete WAV file

---

### `models.py`

#### `TTSRequest`
**Purpose**: Validate incoming TTS requests

**Fields**:
```python
class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    language: str = Field(default="en")
    speaker_wav: Optional[str] = None
```

**Validation**:
- Text required, 1-5000 characters
- Language defaults to "en"
- Speaker WAV optional

---

#### `HealthResponse`
**Purpose**: Format health check response

**Fields**:
```python
class HealthResponse(BaseModel):
    status: str
    model: str
    device: str
    version: str
```

---

### `config.py`

#### `TTSConfig`
**Purpose**: Centralized configuration management

**Key Settings**:

**Model Settings**:
```python
model_name: str = "tts_models/en/ljspeech/vits"
use_cuda: bool = True
```

**Audio Settings**:
```python
sample_rate: int = 22050
audio_format: str = "wav"
```

**Performance**:
```python
enable_text_splitting: bool = True
max_text_length: int = 250  # Characters per chunk
```

**Server**:
```python
host: str = "0.0.0.0"
port: int = 8000
log_level: str = "info"
```

**Environment Variables**:
Can override via `TTS_` prefix:
```bash
TTS_MODEL_NAME=tts_models/multilingual/multi-dataset/xtts_v2
TTS_USE_CUDA=False
```

---

## Code Flow

### 1. REST API Flow

```
Client Request
    ↓
POST /api/tts
    ↓
tts_api.text_to_speech()
    ↓
Validate request (TTSRequest)
    ↓
tts_service.synthesize()
    ↓
Load text into model
    ↓
Model generates audio (numpy array)
    ↓
Convert to WAV bytes
    ↓
Return StreamingResponse
    ↓
Client receives complete audio file
```

---

### 2. WebSocket Streaming Flow

```
Client Connects
    ↓
WS /ws/tts
    ↓
Accept connection + Set ping timeout
    ↓
Receive JSON request
    ↓
tts_service.synthesize_streaming()
    ↓
Split text into sentences
    ↓
For each sentence:
    ├─> Synthesize audio
    ├─> Convert to bytes
    ├─> Send chunks via WebSocket
    └─> Client plays immediately
    ↓
Send completion status
    ↓
Close connection
```

---

### 3. Server Startup Flow

```
python tts_api.py
    ↓
Load config.py
    ↓
Initialize FastAPI app
    ↓
Add CORS middleware
    ↓
Register routes
    ↓
startup_event() triggered
    ↓
tts_service.initialize()
    ↓
Detect CUDA
    ↓
Load TTS model from cache/download
    ↓
Allocate GPU memory
    ↓
Mark model as ready
    ↓
Start Uvicorn server
    ↓
Listen on 0.0.0.0:8000
```

---

## Configuration

### Changing TTS Model

Edit `config.py`:

```python
# Fast English model (recommended)
model_name: str = "tts_models/en/ljspeech/vits"

# Multi-lingual with voice cloning
model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2"

# Fast Tacotron2
model_name: str = "tts_models/en/ljspeech/tacotron2-DDC"
```

Restart server for changes to take effect.

---

### Performance Tuning

**For Lower Latency**:
```python
max_text_length: int = 150  # Smaller chunks
```

**For Better Quality**:
```python
max_text_length: int = 500  # Larger chunks
```

**For Multi-Language**:
```python
model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2"
```

---

### GPU Configuration

**Enable CUDA**:
```python
use_cuda: bool = True
```

**Force CPU**:
```python
use_cuda: bool = False
```

---

## Development Guide

### Adding a New Endpoint

1. **Define Route** in `tts_api.py`:
```python
@app.post("/api/new-endpoint")
async def new_endpoint(request: TTSRequest):
    # Your logic here
    pass
```

2. **Add to Test Client** in `test_client.py`:
```python
def test_new_endpoint(self, text: str):
    response = requests.post(
        f"{self.base_url}/api/new-endpoint",
        json={"text": text}
    )
    return response
```

3. **Update Documentation** in `API_REFERENCE.md`

---

### Debugging

**Enable Debug Logging**:
```python
# config.py
log_level: str = "debug"
```

**View Logs**:
```bash
# Logs show synthesis time, RTF, model info
INFO:tts_service:Synthesis complete. Audio: 227600 samples (9.48s), Time: 1.21s, RTF: 7.84x
```

**Common Issues**:

| Issue | Solution |
|-------|----------|
| CUDA out of memory | Reduce `max_text_length` or disable CUDA |
| Slow synthesis | Enable CUDA, use VITS model |
| Model download fails | Check internet, clear cache |

---

### Testing

**Run Test Client**:
```bash
# Test all endpoints
python test_client.py --mode health
python test_client.py --mode rest --text "Test"
python test_client.py --mode stream --text "Test"
python test_client.py --mode websocket --text "Test"
```

**Manual Testing**:
```bash
# REST
curl -X POST http://localhost:8000/api/tts \
  -H "Content-Type: application/json" \
  -d '{"text":"test"}' --output test.wav

# Health
curl http://localhost:8000/health
```

---

## Performance Benchmarks

### VITS Model (GPU - RTX 2050)

| Text Length | Synthesis Time | Audio Duration | RTF |
|-------------|----------------|----------------|-----|
| 50 chars    | 0.66s          | 4.47s          | 6.76x |
| 150 chars   | 1.21s          | 9.48s          | 7.84x |
| 300 chars   | 1.51s          | 11.78s         | 7.77x |
| 600 chars   | 5.05s          | 37s            | 7.3x |

**Average RTF**: 7.4x (7.4 times faster than real-time)

---

## API Response Times

| Endpoint | First Byte | Complete Response |
|----------|------------|-------------------|
| REST     | 1-2s       | 1-2s             |
| Streaming| 0.5-1s     | Progressive      |
| WebSocket| 0.5-1s     | Progressive      |

---

This documentation covers the complete codebase structure and functionality. For specific questions, refer to the inline code comments in each module.
