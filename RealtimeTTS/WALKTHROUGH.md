# RealtimeTTS API Walkthrough

This walkthrough demonstrates how to set up, run, and use the Coqui TTS Real-Time API for text-to-speech applications.

## 🎯 What You'll Learn

- How to install and configure the TTS API
- How to start the server and verify it's working
- How to use all available endpoints (REST, streaming, WebSocket)
- How to clone voices for custom speech
- How to integrate the API into your applications

---

## 📋 Prerequisites

Before starting, ensure you have:

- **Python 3.8 - 3.11** installed (Coqui TTS compatibility requirement)
- **pip** package manager
- **~2GB disk space** for the TTS model (downloads automatically on first run)
- **CUDA-capable GPU** (optional, but recommended for better performance)

Check your Python version:
```bash
python --version
```

---

## 🚀 Step 1: Installation

### 1.1 Install PyTorch

PyTorch must be installed separately before other dependencies.

**For GPU (CUDA 11.8):**
```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118
```

**For CPU only:**
```bash
pip install torch torchaudio
```

### 1.2 Install Dependencies

Navigate to the project directory and install requirements:

```bash
cd d:\Python-project\RealtimeTTS
pip install -r requirements.txt
```

This installs:
- TTS (Coqui TTS library)
- FastAPI & Uvicorn (web server)
- WebSockets support
- Audio processing libraries

### 1.3 Verify Installation

Check if CUDA is available (optional):
```bash
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
```

**Expected output:**
- `CUDA available: True` (if you have a compatible GPU)
- `CUDA available: False` (if using CPU only - this is fine!)

---

## ⚙️ Step 2: Configuration (Optional)

The API works with default settings, but you can customize it.

### Option A: Environment Variables

Copy the example environment file:
```bash
copy .env.example .env
```

Edit `.env` to customize settings:
```env
TTS_USE_CUDA=true          # Set to false for CPU-only
TTS_PORT=8000              # Change server port
TTS_DEFAULT_LANGUAGE=en    # Default language
```

### Option B: Edit config.py

Alternatively, edit [config.py](file:///d:/Python-project/RealtimeTTS/config.py) directly for more control.

---

## 🎬 Step 3: Start the Server

### 3.1 Launch the API

Start the TTS API server:
```bash
python tts_api.py
```

**What happens on first run:**
1. Downloads XTTSv2 model (~2GB) to `~/.cache/tts/`
2. Loads the model into memory
3. Starts the FastAPI server

**Expected output:**
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

> [!TIP]
> The first run takes 5-10 minutes to download the model. Subsequent runs start in ~10-30 seconds.

### 3.2 Verify Server is Running

Open your browser and visit:
- **Interactive API Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc

Or test with curl:
```bash
curl http://localhost:8000/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "model_loaded": true,
  "cuda_available": true,
  "supported_languages": ["en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl", "cs", "ar", "zh-cn", "ja", "hu", "ko", "hi"]
}
```

---

## 🧪 Step 4: Test the API

The included `test_client.py` demonstrates all API features.

### 4.1 Health Check

Verify the API is ready:
```bash
python test_client.py --mode health
```

**Output:**
```json
{
  "status": "healthy",
  "model_loaded": true,
  "cuda_available": true,
  "supported_languages": [...]
}
```

### 4.2 Basic TTS (REST Endpoint)

Convert text to speech and play it:
```bash
python test_client.py --mode rest --text "Hello! This is a test of the TTS API."
```

**What happens:**
1. Sends text to the API
2. API generates speech and saves it
3. Returns a URL to download the audio
4. Client downloads and plays the audio

**Output:**
```
Converting text to speech: 'Hello! This is a test of the TTS API.'
Success! Audio URL: /audio/tts_20260210_001234_a1b2c3d4.wav
Duration: 2.35s
Playing audio...
```

### 4.3 Streaming TTS

Get lower latency with streaming:
```bash
python test_client.py --mode stream --text "Streaming allows faster playback by processing audio in chunks."
```

**Benefits:**
- Starts playing audio faster
- Lower perceived latency
- Better for longer texts

**Output:**
```
Streaming TTS for: 'Streaming allows faster playback...'
Audio saved to: stream_output.wav
Playing audio...
```

### 4.4 WebSocket Real-Time TTS

Lowest latency option for real-time applications:
```bash
python test_client.py --mode websocket --text "WebSocket provides the lowest latency for real-time calls."
```

**Output:**
```
WebSocket TTS for: 'WebSocket provides the lowest latency...'
Receiving audio chunks...
..........
Status: {'status': 'complete', 'chunks_sent': 10}
Audio saved to: websocket_output.wav
Playing audio...
```

**Latency comparison:**
- REST: ~500ms - 2s
- Streaming: ~200-500ms
- WebSocket: <200ms ⚡

### 4.5 Test Different Languages

Try different supported languages:

**Spanish:**
```bash
python test_client.py --mode rest --text "Hola, ¿cómo estás?" --language es
```

**French:**
```bash
python test_client.py --mode rest --text "Bonjour, comment allez-vous?" --language fr
```

**Japanese:**
```bash
python test_client.py --mode rest --text "こんにちは、お元気ですか？" --language ja
```

---

## 🎤 Step 5: Voice Cloning (Advanced)

Clone a voice using a reference audio sample.

### 5.1 Prepare Reference Audio

Create a voice samples directory:
```bash
mkdir voice_samples
```

**Requirements for reference audio:**
- **Duration**: 6-30 seconds
- **Format**: WAV, MP3, or FLAC
- **Quality**: Clear speech, minimal background noise
- **Content**: Single speaker only

> [!IMPORTANT]
> You need to provide your own voice sample. Record yourself or someone saying a few sentences clearly.

### 5.2 Clone a Voice

Assuming you have `voice_samples/my_voice.wav`:

```bash
python test_client.py --mode clone --speaker "./voice_samples/my_voice.wav" --text "This will sound like the reference voice!"
```

**Output:**
```
Voice cloning with speaker: ./voice_samples/my_voice.wav
Success! Audio URL: /audio/cloned_20260210_001234.wav
Playing cloned voice audio...
```

---

## 🔌 Step 6: Integration Examples

### 6.1 Simple Python Integration

```python
import requests

def text_to_speech(text, language="en"):
    # Generate speech
    response = requests.post(
        "http://localhost:8000/api/tts",
        json={"text": text, "language": language}
    )
    result = response.json()
    
    # Download audio
    audio_url = f"http://localhost:8000{result['audio_url']}"
    audio_data = requests.get(audio_url).content
    
    # Save to file
    with open("output.wav", "wb") as f:
        f.write(audio_data)
    
    print(f"Audio saved! Duration: {result['duration']:.2f}s")
    return "output.wav"

# Use it
audio_file = text_to_speech("Hello from Python!")
```

### 6.2 WebSocket Streaming (Real-time Applications)

```python
import asyncio
import websockets
import json

async def realtime_tts(text, language="en"):
    uri = "ws://localhost:8000/ws/tts"
    
    async with websockets.connect(uri) as websocket:
        # Send text
        await websocket.send(json.dumps({
            "text": text,
            "language": language
        }))
        
        # Receive audio chunks
        audio_chunks = []
        while True:
            message = await websocket.recv()
            
            if isinstance(message, bytes):
                # Audio chunk
                audio_chunks.append(message)
            else:
                # Status message
                status = json.loads(message)
                if status.get("status") == "complete":
                    break
        
        # Save combined audio
        with open("realtime_output.wav", "wb") as f:
            for chunk in audio_chunks:
                f.write(chunk)
        
        print("Real-time TTS complete!")

# Use it
asyncio.run(realtime_tts("Hello from WebSocket!"))
```

### 6.3 Using cURL

**Basic TTS:**
```bash
curl -X POST http://localhost:8000/api/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello from cURL!", "language": "en"}'
```

**Download audio directly:**
```bash
curl -X POST http://localhost:8000/api/tts/stream \
  -H "Content-Type: application/json" \
  -d '{"text": "Streaming from cURL", "language": "en"}' \
  --output speech.wav
```

---

## 📊 Step 7: Performance Monitoring

### 7.1 Check GPU Usage (if available)

While the server is running, open another terminal:

```bash
# On Windows with NVIDIA GPU
nvidia-smi
```

You should see Python using GPU memory when generating speech.

### 7.2 Test Latency

Use Python's time module:

```python
import requests
import time

text = "Testing latency measurement"
start = time.time()

response = requests.post(
    "http://localhost:8000/api/tts",
    json={"text": text, "language": "en"}
)

end = time.time()
print(f"Total time: {end - start:.2f}s")
```

**Expected times:**
- **With GPU**: 0.5 - 2s (depending on text length)
- **Without GPU**: 2 - 10s (slower but still usable)

---

## 🛠️ Troubleshooting

### Issue: Model Download Fails

**Solution:** Manually download the model:
```bash
python -c "from TTS.api import TTS; TTS('tts_models/multilingual/multi-dataset/xtts_v2')"
```

### Issue: CUDA Out of Memory

**Solution 1:** Use CPU instead (edit [config.py](file:///d:/Python-project/RealtimeTTS/config.py)):
```python
use_cuda = False
```

**Solution 2:** Close other GPU applications

### Issue: Audio Playback Fails

The test client might fail to play audio but the file is still saved.

**Check generated audio files:**
```bash
dir generated_audio
```

**Play manually:**
- Use Windows Media Player
- Use VLC
- Or any audio player

### Issue: Port 8000 Already in Use

**Change the port** in [config.py](file:///d:/Python-project/RealtimeTTS/config.py):
```python
port = 8001  # Use a different port
```

### Issue: Slow First Request

This is normal! The model initializes on first request. Subsequent requests are much faster.

---

## 🌟 Next Steps

### Production Deployment

1. **Add Authentication**: Implement API keys or JWT tokens
2. **Rate Limiting**: Prevent abuse with request limits
3. **Caching**: Cache frequently used phrases
4. **Load Balancing**: Run multiple workers for high traffic
5. **Monitoring**: Add logging and metrics (Prometheus, Grafana)

### Advanced Features

1. **Custom Voices**: Train your own TTS models
2. **SSML Support**: Add prosody control (pitch, speed, emphasis)
3. **Batch Processing**: Process multiple texts simultaneously
4. **Audio Post-processing**: Add effects, normalize volume

### Integration Ideas

- **Call Centers**: Real-time voice responses
- **Voice Assistants**: Natural voice interactions
- **Accessibility**: Text-to-speech for visually impaired users
- **Content Creation**: Automated narration for videos
- **Language Learning**: Pronunciation examples

---

## 📚 API Reference Quick Guide

| Endpoint | Method | Purpose | Latency |
|----------|--------|---------|---------|
| `/health` | GET | Health check | Instant |
| `/api/tts` | POST | Basic TTS | Medium |
| `/api/tts/stream` | POST | Streaming TTS | Low |
| `/ws/tts` | WebSocket | Real-time TTS | Lowest |
| `/api/voice-clone` | POST | Voice cloning | Medium |
| `/audio/{filename}` | GET | Download audio | Instant |

**Full documentation**: http://localhost:8000/docs

---

## ✅ Summary

You've successfully:

- ✅ Installed and configured the RealtimeTTS API
- ✅ Started the server and verified it's working
- ✅ Tested REST, streaming, and WebSocket endpoints
- ✅ Learned about voice cloning capabilities
- ✅ Explored integration examples
- ✅ Understood performance characteristics

The API is now ready for integration into your applications! For more details, see the [README.md](file:///d:/Python-project/RealtimeTTS/README.md).

---

**Happy coding! 🎉**
