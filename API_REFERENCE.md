# API Reference 📖

Complete API documentation for the Real-Time TTS API.

## Base URL

```
http://localhost:8000
```

---

## Endpoints

### 1. Health Check

Check if the server is running and get model info.

**Endpoint**: `GET /health`

**Response**:
```json
{
  "status": "healthy",
  "model": "tts_models/en/ljspeech/vits",
  "device": "cuda",
  "version": "1.0.0"
}
```

**Example**:
```bash
curl http://localhost:8000/health
```

---

### 2. Text-to-Speech (REST)

Generate complete audio file.

**Endpoint**: `POST /api/tts`

**Request Body**:
```json
{
  "text": "Text to convert to speech",
  "language": "en",
  "speaker_wav": null
}
```

**Parameters**:
- `text` (string, required): Text to synthesize
- `language` (string, optional): Language code (default: "en")
  - Only used with multi-lingual models (XTTS v2)
- `speaker_wav` (string, optional): Path to speaker audio file for voice cloning
  - Only works with XTTS v2 model

**Response**: WAV audio file (binary)

**Headers**:
- `Content-Type: audio/wav`

**Example (Python)**:
```python
import requests

response = requests.post(
    "http://localhost:8000/api/tts",
    json={
        "text": "Hello, how are you today?",
        "language": "en"
    }
)

with open("output.wav", "wb") as f:
    f.write(response.content)
```

**Example (curl)**:
```bash
curl -X POST "http://localhost:8000/api/tts" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world!", "language": "en"}' \
  --output audio.wav
```

---

### 3. Streaming TTS

Stream audio chunks as they're generated (progressive synthesis).

**Endpoint**: `POST /api/tts/stream`

**Request Body**: Same as REST endpoint

**Response**: Streaming WAV audio chunks

**Use Case**: Long texts where you want to start playing audio before synthesis completes

**Example (Python)**:
```python
import requests

response = requests.post(
    "http://localhost:8000/api/tts/stream",
    json={
        "text": "This is a long text that will be streamed as it's generated...",
        "language": "en"
    },
    stream=True
)

# Save or play chunks as they arrive
with open("output.wav", "wb") as f:
    for chunk in response.iter_content(chunk_size=4096):
        if chunk:
            f.write(chunk)
            # Or play chunk immediately
```

---

### 4. WebSocket TTS

Real-time bi-directional streaming with immediate playback.

**Endpoint**: `ws://localhost:8000/ws/tts`

**Protocol**:

1. **Client → Server** (JSON):
```json
{
  "text": "Text to synthesize",
  "language": "en",
  "speaker_wav": null
}
```

2. **Server → Client** (Binary): Audio chunks as bytes

3. **Server → Client** (JSON): Status messages
```json
{"status": "processing"}
{"status": "complete", "chunks_sent": 150}
```

**Use Case**: Interactive applications, real-time voice generation, minimal latency

**Example (Python)**:
```python
import asyncio
import websockets
import json

async def tts_realtime():
    uri = "ws://localhost:8000/ws/tts"
    
    async with websockets.connect(uri) as websocket:
        # Send request
        await websocket.send(json.dumps({
            "text": "Real-time text-to-speech!",
            "language": "en"
        }))
        
        audio_chunks = []
        
        # Receive chunks
        while True:
            message = await websocket.recv()
            
            if isinstance(message, bytes):
                # Audio chunk - play or save
                audio_chunks.append(message)
            else:
                # Status message
                status = json.loads(message)
                print(f"Status: {status}")
                
                if status.get("status") == "complete":
                    break
        
        # Save complete audio
        with open("output.wav", "wb") as f:
            for chunk in audio_chunks:
                f.write(chunk)

asyncio.run(tts_realtime())
```

**Example (JavaScript)**:
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/tts');

ws.onopen = () => {
  ws.send(JSON.stringify({
    text: "Hello from JavaScript!",
    language: "en"
  }));
};

ws.onmessage = (event) => {
  if (event.data instanceof Blob) {
    // Audio chunk - play it
    playAudioChunk(event.data);
  } else {
    // Status message
    const status = JSON.parse(event.data);
    console.log('Status:', status);
  }
};
```

---

## Response Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad Request (invalid parameters) |
| 500 | Internal Server Error (synthesis failed) |

---

## Error Responses

**Format**:
```json
{
  "detail": "Error message describing what went wrong"
}
```

**Common Errors**:

1. **No text provided**:
```json
{"detail": "No text provided"}
```

2. **Model not multi-lingual**:
```json
{"detail": "Model is not multi-lingual but `language` is provided"}
```

3. **Synthesis failed**:
```json
{"detail": "Synthesis failed: [error details]"}
```

---

## Models & Languages

### Supported Models

Configure in `config.py`:

**VITS (Recommended)**:
```python
model_name = "tts_models/en/ljspeech/vits"
```
- **Speed**: ⚡⚡⚡ Very Fast (RTF: 7-10x)
- **Quality**: 🌟🌟🌟 Good
- **Languages**: English only
- **Best for**: General use, production

**Tacotron2-DDC**:
```python
model_name = "tts_models/en/ljspeech/tacotron2-DDC"
```
- **Speed**: ⚡⚡ Fast (RTF: 5-7x)
- **Quality**: 🌟🌟 Good
- **Languages**: English only
- **Best for**: Quick synthesis

**XTTS v2** (Multi-lingual + Voice Cloning):
```python
model_name = "tts_models/multilingual/multi-dataset/xtts_v2"
```
- **Speed**: ⚡ Slower (RTF: 2-4x)
- **Quality**: 🌟🌟🌟🌟 Excellent
- **Languages**: 17 languages
- **Best for**: Multi-lingual, voice cloning

### Supported Languages (XTTS v2 only)

`en`, `es`, `fr`, `de`, `it`, `pt`, `pl`, `tr`, `ru`, `nl`, `cs`, `ar`, `zh-cn`, `ja`, `hu`, `ko`, `hi`

---

## Performance Metrics

All endpoints return performance metrics in logs:

```
INFO:tts_service:Synthesis complete. Audio: 227600 samples (9.48s), Time: 1.21s, RTF: 7.84x
```

**Metrics explained**:
- **Samples**: Raw audio data points
- **Audio Duration**: Length of generated audio (seconds)
- **Time**: Synthesis time (seconds)
- **RTF (Real-Time Factor)**: Speed multiplier
  - RTF > 1.0 = Faster than real-time ✅
  - RTF = 5.0 = 5x faster than real-time
  - Higher is better!

---

## Rate Limiting

Currently no rate limiting. Consider adding in production:

```python
from slowapi import Limiter
```

---

## Authentication

Currently no authentication. For production, consider adding:
- API keys
- JWT tokens
- OAuth2

---

## Tips for Best Performance

1. **Use WebSocket** for lowest latency
2. **Enable CUDA** for GPU acceleration (5-10x speedup)
3. **Choose VITS model** for best speed/quality balance
4. **Reduce chunk size** (`max_text_length`) for faster first response
5. **Use streaming** for long texts

---

## Special Use Cases

### Phone Numbers

Format with commas for digit-by-digit pronunciation:

```json
{
  "text": "8, 1, 2, 5, 9, 0, 4, 8, 4, 4"
}
```

### Multiple Sentences

Text is automatically split by sentences for progressive synthesis.

### Voice Cloning (XTTS v2 only)

```json
{
  "text": "Clone my voice!",
  "language": "en",
  "speaker_wav": "/path/to/voice_sample.wav"
}
```

**Requirements**:
- Audio file: 6-10 seconds
- Format: WAV, MP3, or other common formats
- Quality: Clear, single speaker

---

For more examples, see the [test_client.py](RealtimeTTS/test_client.py) file.
