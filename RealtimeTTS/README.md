# Coqui TTS Real-Time API

A high-performance, real-time Text-to-Speech API built with Coqui TTS XTTSv2 and FastAPI. Designed for real-time call scenarios with <200ms latency.

## Features

- ✨ **Real-time Streaming**: WebSocket support for low-latency TTS (<200ms)
- 🎤 **Voice Cloning**: Clone voices with just 6 seconds of audio
- 🌍 **17 Languages**: Multiple language support
- 🚀 **High Performance**: Optimized for real-time applications
- 📡 **Multiple Endpoints**: REST, HTTP streaming, and WebSocket
- 🔧 **Easy Integration**: Simple API for telephony and voice applications

## Supported Languages

`en`, `es`, `fr`, `de`, `it`, `pt`, `pl`, `tr`, `ru`, `nl`, `cs`, `ar`, `zh-cn`, `ja`, `hu`, `ko`, `hi`

## Installation

### Prerequisites

- Python 3.8 - 3.11 (Coqui TTS compatibility requirement)
- CUDA-capable GPU (optional, for faster processing)

### Setup

1. **Install PyTorch** (must be installed separately):

```bash
# For CUDA 11.8
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118

# For CPU only
pip install torch torchaudio
```

2. **Install dependencies**:

```bash
pip install -r requirements.txt
```

3. **First run** (downloads model - ~2GB):

The XTTSv2 model will be automatically downloaded on first run to `~/.cache/tts/`

## Quick Start

### Start the API Server

```bash
python tts_api.py
```

The server will start on `http://localhost:8000`

### Test the API

```bash
# Health check
python test_client.py --mode health

# Basic TTS (REST)
python test_client.py --mode rest --text "Hello, this is a test!"

# Streaming TTS
python test_client.py --mode stream --text "This is streaming audio generation."

# Real-time WebSocket
python test_client.py --mode websocket --text "Real-time speech synthesis!"
```

## API Endpoints

### 1. Health Check

**GET** `/health`

Check API status and available features.

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "model_loaded": true,
  "cuda_available": true,
  "supported_languages": ["en", "es", "fr", ...]
}
```

---

### 2. Basic TTS (REST)

**POST** `/api/tts`

Convert text to speech and get a download URL.

**Request:**
```json
{
  "text": "Hello, how are you today?",
  "language": "en",
  "speaker_wav": null,
  "speed": 1.0
}
```

**Response:**
```json
{
  "success": true,
  "message": "Text-to-speech conversion successful",
  "audio_url": "/audio/tts_20260210_001234_a1b2c3d4.wav",
  "duration": 2.5,
  "sample_rate": 24000
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world!", "language": "en"}'
```

---

### 3. Streaming TTS

**POST** `/api/tts/stream`

Stream audio as it's generated (lower latency).

**Request:**
```json
{
  "text": "This is a longer text that will be streamed...",
  "language": "en",
  "chunk_size": 4096
}
```

**Response:** Audio stream (WAV format)

**Example:**
```bash
curl -X POST http://localhost:8000/api/tts/stream \
  -H "Content-Type: application/json" \
  -d '{"text": "Streaming audio example", "language": "en"}' \
  --output output.wav
```

---

### 4. WebSocket Real-Time TTS

**WebSocket** `/ws/tts`

Real-time TTS with <200ms latency for live applications.

**Protocol:**

1. Client connects to WebSocket
2. Client sends JSON request:
   ```json
   {
     "text": "Real-time speech",
     "language": "en",
     "speaker_wav": null
   }
   ```
3. Server sends status: `{"status": "processing"}`
4. Server streams audio chunks (binary data)
5. Server sends completion: `{"status": "complete", "chunks_sent": 42}`

**Example (JavaScript):**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/tts');

ws.onopen = () => {
  ws.send(JSON.stringify({
    text: "Hello from WebSocket!",
    language: "en"
  }));
};

ws.onmessage = (event) => {
  if (event.data instanceof Blob) {
    // Audio chunk - play or buffer
    playAudioChunk(event.data);
  } else {
    // Status message
    const status = JSON.parse(event.data);
    console.log(status);
  }
};
```

---

### 5. Voice Cloning

**POST** `/api/voice-clone`

Generate speech using a cloned voice (requires 6+ second audio sample).

**Request:**
```json
{
  "text": "This will sound like the reference voice",
  "speaker_audio_path": "./voice_samples/my_voice.wav",
  "language": "en"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Voice cloning successful",
  "audio_url": "/audio/cloned_20260210_001234.wav",
  "duration": 3.2,
  "sample_rate": 24000
}
```

---

### 6. Download Audio

**GET** `/audio/{filename}`

Download generated audio files.

```bash
curl http://localhost:8000/audio/tts_20260210_001234.wav --output speech.wav
```

## Configuration

Edit [`config.py`](file:///d:/Python-project/RealtimeTTS/config.py) or use environment variables:

```python
# Environment variables (prefix with TTS_)
TTS_MODEL_NAME=tts_models/multilingual/multi-dataset/xtts_v2
TTS_USE_CUDA=true
TTS_SAMPLE_RATE=24000
TTS_HOST=0.0.0.0
TTS_PORT=8000
TTS_DEFAULT_LANGUAGE=en
```

### Key Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `model_name` | `xtts_v2` | TTS model to use |
| `use_cuda` | `True` | Use GPU acceleration |
| `sample_rate` | `24000` | Audio sample rate (Hz) |
| `port` | `8000` | API server port |
| `max_text_length` | `500` | Max characters per chunk |
| `chunk_size` | `4096` | Streaming chunk size |

## Integration Examples

### Python Integration

```python
import requests

def text_to_speech(text, language="en"):
    response = requests.post(
        "http://localhost:8000/api/tts",
        json={"text": text, "language": language}
    )
    result = response.json()
    
    # Download audio
    audio_response = requests.get(f"http://localhost:8000{result['audio_url']}")
    with open("output.wav", "wb") as f:
        f.write(audio_response.content)
    
    return "output.wav"
```

### Twilio Integration

```python
from twilio.twiml.voice_response import VoiceResponse, Play

def handle_call():
    # Generate speech
    tts_result = requests.post(
        "http://localhost:8000/api/tts",
        json={"text": "Welcome to our service!", "language": "en"}
    ).json()
    
    # Create TwiML response
    response = VoiceResponse()
    response.play(f"https://your-domain.com{tts_result['audio_url']}")
    
    return str(response)
```

### WebSocket Streaming (Real-time Call)

```python
import asyncio
import websockets
import pyaudio

async def realtime_tts():
    uri = "ws://localhost:8000/ws/tts"
    
    async with websockets.connect(uri) as websocket:
        # Send text
        await websocket.send(json.dumps({
            "text": "This is real-time speech",
            "language": "en"
        }))
        
        # Stream audio to output device
        audio = pyaudio.PyAudio()
        stream = audio.open(format=pyaudio.paInt16, channels=1, 
                          rate=24000, output=True)
        
        while True:
            message = await websocket.recv()
            if isinstance(message, bytes):
                stream.write(message)
            else:
                status = json.loads(message)
                if status.get("status") == "complete":
                    break
        
        stream.close()
```

## Voice Cloning Guide

1. **Prepare reference audio**:
   - Duration: 6-30 seconds
   - Format: WAV, MP3, or FLAC
   - Quality: Clear speech, minimal background noise
   - Single speaker

2. **Save to voice samples directory**:
   ```bash
   mkdir -p voice_samples
   # Copy your audio file
   cp my_voice.wav voice_samples/
   ```

3. **Use in API**:
   ```bash
   python test_client.py --mode clone \
     --speaker ./voice_samples/my_voice.wav \
     --text "This will use the cloned voice"
   ```

## Performance Optimization

### GPU Acceleration

The API automatically uses CUDA if available. Verify GPU usage:

```python
import torch
print(f"CUDA available: {torch.cuda.is_available()}")
```

### Batch Processing

For multiple TTS requests, use the streaming endpoint to reduce overhead.

### Latency

- **REST endpoint**: ~500ms - 2s (depends on text length)
- **Streaming endpoint**: ~200-500ms (starts faster)
- **WebSocket**: <200ms (lowest latency)

## Troubleshooting

### Model Download Issues

If model download fails:
```bash
# Manually download
python -c "from TTS.api import TTS; TTS('tts_models/multilingual/multi-dataset/xtts_v2')"
```

### CUDA Out of Memory

Reduce batch size or use CPU:
```python
# In config.py
use_cuda = False
```

### Audio Quality Issues

Adjust sample rate or use different speaker reference:
```python
# In config.py
sample_rate = 22050  # Lower for smaller files
```

## API Documentation

Interactive API documentation available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Architecture

```
tts_api.py          # FastAPI application
├── tts_service.py  # Core TTS service (XTTSv2)
├── models.py       # Pydantic models
├── config.py       # Configuration
└── test_client.py  # Example client

generated_audio/    # Output directory (auto-created)
voice_samples/      # Voice cloning samples
```

## License

This project uses Coqui TTS, which is licensed under MPL 2.0.

## Support

For issues with:
- **This API**: Check logs and server status
- **Coqui TTS**: https://github.com/coqui-ai/TTS
- **Model performance**: Try different models or adjust settings

## Next Steps

1. **Deploy**: Use Docker or cloud hosting
2. **Scale**: Add Redis for caching, load balancer for multiple workers
3. **Monitor**: Add logging and metrics
4. **Secure**: Add authentication, rate limiting
5. **Enhance**: Add more endpoints, custom voices, etc.

---

**Made with ❤️ using Coqui TTS**
