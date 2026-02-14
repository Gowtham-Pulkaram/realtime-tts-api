# Real-Time TTS API 🎙️

A high-performance, real-time Text-to-Speech API built with **Coqui TTS** and **FastAPI**. Features progressive streaming, low latency (~1-2s), and support for multiple TTS models.

## ✨ Features

- 🚀 **Ultra-Fast Synthesis**: 6-8x real-time factor with GPU acceleration
- 🎵 **Real-Time Streaming**: Progressive audio playback as text is synthesized
- 🌍 **Multi-Model Support**: Works with XTTS v2, VITS, Tacotron2, and other Coqui models
- 📡 **Multiple APIs**: REST, HTTP Streaming, and WebSocket endpoints
- 🎯 **Low Latency**: Audio starts playing in 1-2 seconds
- 📊 **Performance Metrics**: Built-in latency tracking and RTF monitoring
- 🔧 **Easy Configuration**: Simple YAML-based settings

## 🎯 Quick Start

### Prerequisites

- Python 3.8+
- CUDA-capable GPU (optional, but recommended for best performance)
- Windows (espeak-ng required)

### Installation

1. **Clone the repository**
```bash
git clone <your-repo-url>
cd TTS-coquii
```

2. **Install espeak-ng** (required for TTS)
   - Download from: https://github.com/espeak-ng/espeak-ng/releases
   - Install to default location (`C:\Program Files\eSpeak NG`)

3. **Create virtual environment**
```bash
python -m venv .venv
.venv\Scripts\activate
```

4. **Install dependencies**
```bash
pip install -r requirements.txt
```

### Running the Server

```bash
# Navigate to TTS-coquii directory
cd RealtimeTTS

# Start the server
python tts_api.py
```

Server will start at `http://localhost:8000`

## 📚 API Usage

### 1. REST API (Simple)

**Endpoint**: `POST /api/tts`

```bash
curl -X POST "http://localhost:8000/api/tts" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world!", "language": "en"}' \
  --output audio.wav
```

**Python example**:
```python
import requests

response = requests.post(
    "http://localhost:8000/api/tts",
    json={"text": "Hello world!", "language": "en"}
)

with open("output.wav", "wb") as f:
    f.write(response.content)
```

### 2. HTTP Streaming (Progressive)

**Endpoint**: `POST /api/tts/stream`

```python
import requests

response = requests.post(
    "http://localhost:8000/api/tts/stream",
    json={"text": "Long text here...", "language": "en"},
    stream=True
)

# Stream audio chunks as they arrive
with open("output.wav", "wb") as f:
    for chunk in response.iter_content(chunk_size=4096):
        if chunk:
            f.write(chunk)
```

### 3. WebSocket (Real-Time)

**Endpoint**: `ws://localhost:8000/ws/tts`

```python
import asyncio
import websockets
import json

async def tts_websocket():
    uri = "ws://localhost:8000/ws/tts"
    
    async with websockets.connect(uri) as websocket:
        # Send text
        await websocket.send(json.dumps({
            "text": "Hello from WebSocket!",
            "language": "en"
        }))
        
        # Receive and play audio chunks
        while True:
            message = await websocket.recv()
            
            if isinstance(message, bytes):
                # Audio chunk - play or save
                process_audio(message)
            else:
                # Status message
                status = json.loads(message)
                if status.get("status") == "complete":
                    break

asyncio.run(tts_websocket())
```

## 🧪 Using the Test Client

We provide a comprehensive test client:

```bash
# REST API
python test_client.py --mode rest --text "Hello world!"

# Streaming
python test_client.py --mode stream --text "This is streaming audio"

# WebSocket (real-time playback)
python test_client.py --mode websocket --text "Real-time TTS streaming"

# Health check
python test_client.py --mode health
```

### Phone Number Example

For digit-by-digit pronunciation:

```bash
# Option 1: Comma-separated (best pauses)
python test_client.py --mode websocket --text "8, 1, 2, 5, 9, 0, 4, 8, 4, 4"

# Option 2: Grouped
python test_client.py --mode websocket --text "8 1 2, 5 9 0, 4 8 4 4"

# Option 3: Words (clearest)
python test_client.py --mode websocket --text "eight, one, two, five, nine, zero, four, eight, four, four"
```

## ⚙️ Configuration

Edit [config.py](RealtimeTTS/config.py):

```python
class TTSConfig:
    # Model Settings
    model_name: str = "tts_models/en/ljspeech/vits"  # Fast, English
    use_cuda: bool = True  # GPU acceleration
    
    # Audio Settings
    sample_rate: int = 22050
    audio_format: str = "wav"
    
    # Performance
    enable_text_splitting: bool = True
    max_text_length: int = 250  # Characters per chunk
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
```

### Available Models

| Model | Speed | Quality | Languages | Use Case |
|-------|-------|---------|-----------|----------|
| `tts_models/en/ljspeech/vits` | ⚡⚡⚡ Very Fast | 🌟🌟🌟 Good | English | **Recommended** - Best speed/quality |
| `tts_models/en/ljspeech/tacotron2-DDC` | ⚡⚡ Fast | 🌟🌟 Good | English | Fast synthesis |
| `tts_models/multilingual/multi-dataset/xtts_v2` | ⚡ Slower | 🌟🌟🌟🌟 Excellent | 17 languages | Multilingual, voice cloning |

To change models, update `model_name` in [config.py](RealtimeTTS/config.py) and restart the server.

## 📊 Performance Metrics

The API automatically tracks:

- **Synthesis Time**: How long TTS generation took
- **Audio Duration**: Length of generated audio
- **RTF (Real-Time Factor)**: Speed multiplier
  - RTF = 1.0 → Real-time speed
  - RTF = 5.0 → 5x faster than real-time
  - RTF = 10.0 → 10x faster than real-time

**Example log output**:
```
INFO:tts_service:Synthesis complete. Audio: 227600 samples (9.48s), Time: 1.21s, RTF: 7.84x
```

This means: Generated 9.48 seconds of audio in 1.21 seconds → **7.84x faster than real-time** 🚀

## 🏗️ Project Structure

```
TTS-coquii/
├── RealtimeTTS/
│   ├── tts_api.py          # FastAPI server
│   ├── tts_service.py      # TTS synthesis engine
│   ├── models.py           # Pydantic models
│   ├── config.py           # Configuration
│   └── test_client.py      # Test client
├── requirements.txt        # Dependencies
└── README.md              # This file
```

## 🔧 API Endpoints

### Health Check
```http
GET /health
```

Returns server status and model info.

### Text-to-Speech (REST)
```http
POST /api/tts
Content-Type: application/json

{
  "text": "Text to synthesize",
  "language": "en",
  "speaker_wav": null  // Optional: path to voice sample
}
```

### Streaming TTS
```http
POST /api/tts/stream
Content-Type: application/json

{
  "text": "Long text for streaming",
  "language": "en"
}
```

### WebSocket TTS
```
ws://localhost:8000/ws/tts

Send: {"text": "...", "language": "en"}
Receive: Binary audio chunks + JSON status messages
```

## 🚀 Performance Tips

1. **Use GPU**: Enable CUDA in config for 5-10x speedup
   ```python
   use_cuda: bool = True
   ```

2. **Choose the Right Model**:
   - Short texts → VITS (fastest)
   - Long texts → VITS with streaming
   - Multiple languages → XTTS v2

3. **Optimize Chunk Size**:
   ```python
   max_text_length: int = 250  # Smaller = faster first chunk
   ```

4. **Use WebSocket for Real-Time**: Best latency for interactive applications

## 🐛 Troubleshooting

### espeak-ng not found
```
Error: subprocess-exited-with-error
```
**Solution**: Install espeak-ng from https://github.com/espeak-ng/espeak-ng/releases

### CUDA not available
```
WARNING: CUDA not available, using CPU
```
**Solution**: 
- Install PyTorch with CUDA support
- Or set `use_cuda: bool = False` in config

### Model is not multi-lingual error
```
ERROR: Model is not multi-lingual but `language` is provided
```
**Solution**: Remove language parameter for single-language models, or use XTTS v2

### WebSocket timeout on long texts
**Solution**: Already fixed! WebSocket timeout increased to 60s.

## 📄 License

[Your License Here]

## 🤝 Contributing

Contributions welcome! Please open an issue or PR.

## 📧 Contact

[Your Contact Info]

---

**Built with ❤️ using Coqui TTS and FastAPI**
