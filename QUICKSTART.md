# Quick Start Guide 🚀

Get your Real-Time TTS API up and running in 5 minutes!

## Step 1: Install espeak-ng

**Required for Coqui TTS to work on Windows**

1. Download: [espeak-ng-X64.msi](https://github.com/espeak-ng/espeak-ng/releases)
2. Run installer (use default location: `C:\Program Files\eSpeak NG`)
3. Verify installation:
   ```bash
   espeak-ng --version
   ```

## Step 2: Setup Python Environment

```bash
# Navigate to project
cd TTS-coquii

# Create virtual environment
python -m venv .venv

# Activate it
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Step 3: Start the Server

```bash
cd RealtimeTTS
python tts_api.py
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:tts_service:Initializing TTS model: tts_models/en/ljspeech/vits
```

## Step 4: Test It!

**Option 1: Quick test with test client**
```bash
python test_client.py --mode websocket --text "Hello! This is real-time TTS!"
```

**Option 2: Test with curl**
```bash
curl -X POST "http://localhost:8000/api/tts" \
  -H "Content-Type: application/json" \
  -d "{\"text\": \"Hello world!\", \"language\": \"en\"}" \
  --output test.wav
```

**Option 3: Health check**
```bash
curl http://localhost:8000/health
```

## You're Done! 🎉

Your TTS API is now running at `http://localhost:8000`

## Next Steps

- Read the [README.md](../README.md) for full documentation
- Try different models in [config.py](RealtimeTTS/config.py)
- Explore the API endpoints with the test client

## Common Issues

**Issue**: `espeak-ng not found`  
**Fix**: Install espeak-ng (Step 1)

**Issue**: `CUDA not available`  
**Fix**: Set `use_cuda: bool = False` in config.py or install CUDA-enabled PyTorch

**Issue**: `Port 8000 already in use`  
**Fix**: Change port in config.py: `port: int = 8001`

---

Need help? Check the [Troubleshooting](../README.md#-troubleshooting) section in README.md
