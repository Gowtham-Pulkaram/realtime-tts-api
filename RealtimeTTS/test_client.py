"""
Test client for TTS API
Demonstrates usage of REST, streaming, and WebSocket endpoints
"""
import requests
import asyncio
import websockets
import json
import argparse
from pathlib import Path
from typing import Optional
import sounddevice as sd
import soundfile as sf
import numpy as np
import io
import time


class TTSClient:
    """Client for interacting with TTS API"""
    
    #def __init__(self, base_url: str = "http://localhost:8000"):
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):

        self.base_url = base_url
        self.ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
    
    def health_check(self):
        """Check API health"""
        response = requests.get(f"{self.base_url}/health")
        print("Health Check:")
        print(json.dumps(response.json(), indent=2))
        return response.json()
    
    def tts_basic(self, text: str, language: str = "en", play: bool = True):
        """
        Basic TTS using REST endpoint
        
        Args:
            text: Text to convert
            language: Language code
            play: Whether to play the audio
        """
        print(f"\n[REST] Converting text to speech: '{text[:50]}...'")
        request_start = time.time()
        
        payload = {
            "text": text,
            "language": language,
            "speed": 1.0
        }
        
        response = requests.post(f"{self.base_url}/api/tts", json=payload)
        response_time = time.time() - request_start
        
        if response.status_code == 200:
            result = response.json()
            print(f"[REST] ✅ Success! Audio URL: {result['audio_url']}")
            print(f"[REST] 📊 Stats:")
            print(f"       Response time:  {response_time:.3f}s")
            print(f"       Audio duration: {result['duration']:.2f}s")
            if 'synthesis_time_ms' in result:
                print(f"       Synthesis time: {result['synthesis_time_ms']:.1f}ms")
            if 'real_time_factor' in result:
                print(f"       RTF:            {result['real_time_factor']:.2f}x")
            
            # Download and play audio
            if play:
                download_start = time.time()
                audio_url = f"{self.base_url}{result['audio_url']}"
                audio_response = requests.get(audio_url)
                download_time = time.time() - download_start
                
                if audio_response.status_code == 200:
                    print(f"       Download time:  {download_time:.3f}s ({len(audio_response.content) / 1024:.1f} KB)")
                    # Save to temp file
                    temp_file = "temp_audio.wav"
                    with open(temp_file, "wb") as f:
                        f.write(audio_response.content)
                    
                    print("[REST] 🔊 Playing audio...")
                    self._play_audio(temp_file)
                    
                    # Cleanup
                    Path(temp_file).unlink()
        else:
            print(f"[REST] ❌ Error: {response.status_code} (after {response_time:.3f}s)")
            print(response.text)
    
    def tts_streaming(self, text: str, language: str = "en", speaker_wav: Optional[str] = None, save_path: str = "stream_output.wav"):
        """
        Streaming TTS using REST streaming endpoint
        
        Args:
            text: Text to convert
            language: Language code
            speaker_wav: Path to speaker audio for voice cloning
            save_path: Where to save the audio
        """
        print(f"\n[STREAM] Streaming TTS for: '{text[:50]}...'")
        request_start = time.time()
        
        payload = {
            "text": text,
            "language": language,
            "speaker_wav": speaker_wav,
            "chunk_size": 4096
        }
        
        response = requests.post(
            f"{self.base_url}/api/tts/stream",
            json=payload,
            stream=True
        )
        if response.status_code == 200:
            chunk_count = 0
            total_bytes = 0
            first_byte_time = None
            
            # Save streamed audio
            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=4096):
                    if chunk:
                        chunk_count += 1
                        total_bytes += len(chunk)
                        if first_byte_time is None:
                            first_byte_time = time.time()
                            ttfb = first_byte_time - request_start
                            print(f"[STREAM] ⚡ TTFB: {ttfb:.3f}s")
                        f.write(chunk)
            
            # Fix WAV header sizes (header only knows first sentence's size)
            import struct
            with open(save_path, "r+b") as f:
                # Update RIFF chunk size (bytes 4-7): total file size - 8
                f.seek(0, 2)  # seek to end
                file_size = f.tell()
                f.seek(4)
                f.write(struct.pack('<I', file_size - 8))
                # Update data chunk size (bytes 40-43): total file size - 44
                f.seek(40)
                f.write(struct.pack('<I', file_size - 44))
            
            elapsed = time.time() - request_start
            print(f"[STREAM] ✅ Audio saved to: {save_path}")
            print(f"[STREAM] 📊 Stats:")
            print(f"         Chunks:     {chunk_count}")
            print(f"         Size:       {total_bytes / 1024:.1f} KB")
            print(f"         TTFB:       {(first_byte_time - request_start) * 1000:.1f}ms" if first_byte_time else "         TTFB:       N/A")
            print(f"         Total time: {elapsed:.3f}s")
            print("[STREAM] 🔊 Playing audio...")
            self._play_audio(save_path)
        else:
            print(f"[STREAM] ❌ Error: {response.status_code}")
            print(response.text)
    
    async def tts_websocket(self, text: str, language: str = "en", speaker_wav: Optional[str] = None, realtime_playback: bool = True):
        """
        Real-time TTS using WebSocket
        
        Args:
            text: Text to convert
            language: Language code
            speaker_wav: Path to speaker audio for voice cloning
            realtime_playback: If True, play audio as it streams in real-time
        """
        print(f"\n[WS] ══ WebSocket TTS for: '{text[:50]}...'")
        
        uri = f"{self.ws_url}/ws/tts"
        
        audio_chunks = []
        
        try:
            connect_start = time.time()
            async with websockets.connect(uri) as websocket:
                connect_time = time.time() - connect_start
                print(f"[WS] ✅ Connected in {connect_time * 1000:.1f}ms")
                
                # Send request
                request_start = time.time()
                await websocket.send(json.dumps({
                    "text": text,
                    "language": language,
                    "speaker_wav": speaker_wav
                }))
                print(f"[WS] 📤 Request sent ({len(text)} chars)")
                
                print("[WS] Receiving audio chunks...")
                if realtime_playback:
                    print("[WS] 🎵 Playing audio in real-time...")
                
                # For real-time playback
                stream = None
                sample_rate = 22050  # Default for Tacotron2
                header_parsed = False
                first_chunk_time = None
                chunk_count = 0
                total_bytes = 0
                
                while True:
                    message = await websocket.recv()
                    
                    # Check if it's a status message (JSON) or audio data (bytes)
                    if isinstance(message, bytes):
                        chunk_count += 1
                        total_bytes += len(message)
                        audio_chunks.append(message)
                        
                        if first_chunk_time is None:
                            first_chunk_time = time.time()
                            ttfb = first_chunk_time - request_start
                            print(f"\n[WS] ⚡ TTFB (time to first byte): {ttfb * 1000:.1f}ms")
                        
                        if realtime_playback:
                            # Parse WAV header from first chunk to get sample rate
                            if not header_parsed and len(message) > 44:
                                import struct
                                # Sample rate is at bytes 24-27 in WAV header
                                sample_rate = struct.unpack('<I', message[24:28])[0]
                                header_parsed = True
                                
                                # Start audio stream
                                stream = sd.OutputStream(
                                    samplerate=sample_rate,
                                    channels=1,
                                    dtype='int16'
                                )
                                stream.start()
                                
                                # Play first chunk (skip WAV header - 44 bytes)
                                pcm_data = np.frombuffer(message[44:], dtype=np.int16)
                                if len(pcm_data) > 0:
                                    stream.write(pcm_data)
                                print(".", end="", flush=True)
                            elif header_parsed:
                                # Play subsequent chunks (raw PCM)
                                pcm_data = np.frombuffer(message, dtype=np.int16)
                                if len(pcm_data) > 0:
                                    stream.write(pcm_data)
                                print(".", end="", flush=True)
                        else:
                            print(".", end="", flush=True)
                    else:
                        # JSON status message
                        status = json.loads(message)
                        
                        if status.get("status") == "processing":
                            print(f"[WS] ⏳ Server processing...")
                        elif status.get("status") == "complete":
                            elapsed = time.time() - request_start
                            transfer_rate = (total_bytes / 1024) / elapsed if elapsed > 0 else 0
                            
                            print(f"\n[WS] ✅ Complete!")
                            print(f"[WS] 📊 Client Stats:")
                            print(f"       Chunks received: {chunk_count}")
                            print(f"       Total size:      {total_bytes / 1024:.1f} KB")
                            if first_chunk_time:
                                print(f"       TTFB:            {(first_chunk_time - request_start) * 1000:.1f}ms")
                            print(f"       Total time:      {elapsed:.3f}s")
                            print(f"       Transfer rate:   {transfer_rate:.1f} KB/s")
                            if 'ttfb_ms' in status:
                                print(f"[WS] 📊 Server Stats:")
                                print(f"       Server TTFB:     {status['ttfb_ms']}ms")
                                print(f"       Server total:    {status['total_time_ms']}ms")
                                print(f"       Server bytes:    {status.get('total_bytes', 'N/A')}")
                            break
                        elif "error" in status:
                            print(f"\n[WS] ❌ Server error: {status['error']}")
                            break
                        else:
                            print(f"\n[WS] Status: {status}")
                
                # Stop and close the stream
                if stream:
                    stream.stop()
                    stream.close()
                    print("[WS] 🔊 Real-time playback complete!")
                
                # Save to file for later playback
                if audio_chunks:
                    output_file = "websocket_output.wav"
                    
                    # Concatenate all chunks
                    full_audio = b''.join(audio_chunks)
                    
                    # Fix WAV header size
                    import struct
                    
                    # Update file size (bytes 4-7)
                    file_size = len(full_audio) - 8
                    full_audio = full_audio[:4] + struct.pack('<I', file_size) + full_audio[8:]
                    
                    # Update data chunk size (bytes 40-43)
                    data_size = len(full_audio) - 44
                    full_audio = full_audio[:40] + struct.pack('<I', data_size) + full_audio[44:]
                    
                    # Write updated audio
                    with open(output_file, "wb") as f:
                        f.write(full_audio)
                    
                    print(f"[WS] 💾 Audio saved to: {output_file}")
        
        except Exception as e:
            print(f"[WS] ❌ WebSocket error: {e}")
    
    def voice_clone(self, text: str, speaker_audio: str, language: str = "en"):
        """
        Voice cloning
        
        Args:
            text: Text to convert
            speaker_audio: Path to reference audio (6+ seconds)
            language: Language code
        """
        print(f"\nVoice cloning with speaker: {speaker_audio}")
        
        if not Path(speaker_audio).exists():
            print(f"Error: Speaker audio file not found: {speaker_audio}")
            return
        
        payload = {
            "text": text,
            "speaker_audio_path": speaker_audio,
            "language": language
        }
        
        response = requests.post(f"{self.base_url}/api/voice-clone", json=payload)
        
        if response.status_code == 200:
            result = response.json()
            print(f"Success! Audio URL: {result['audio_url']}")
            
            # Download and play
            audio_url = f"{self.base_url}{result['audio_url']}"
            audio_response = requests.get(audio_url)
            
            if audio_response.status_code == 200:
                temp_file = "cloned_voice.wav"
                with open(temp_file, "wb") as f:
                    f.write(audio_response.content)
                
                print("Playing cloned voice audio...")
                self._play_audio(temp_file)
                
                Path(temp_file).unlink()
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
    
    def _play_audio(self, audio_path: str):
        """Play audio file using sounddevice"""
        try:
            data, sample_rate = sf.read(audio_path)
            sd.play(data, sample_rate)
            # Poll instead of sd.wait() — sd.wait() blocks Ctrl+C on Windows
            while sd.get_stream().active:
                time.sleep(0.1)
        except KeyboardInterrupt:
            sd.stop()
            print("\n[PLAYBACK] Stopped by user")
        except Exception as e:
            print(f"Could not play audio: {e}")
            print("(Audio file saved but playback failed)")


def main():
    parser = argparse.ArgumentParser(description="TTS API Test Client")
    parser.add_argument("--mode", choices=["rest", "stream", "websocket", "clone", "health"], 
                       default="rest", help="Test mode")
    parser.add_argument("--text", type=str, 
                       default="Hello! This is a test of the real-time text to speech API using Coqui TTS.",
                       help="Text to convert to speech")
    parser.add_argument("--language", type=str, default="en", help="Language code")
    parser.add_argument("--speaker", type=str, help="Speaker audio path for voice cloning")
    parser.add_argument("--url", type=str, default="http://127.0.0.1:8000", help="API base URL")
    
    args = parser.parse_args()
    
    client = TTSClient(base_url=args.url)
    
    if args.mode == "health":
        client.health_check()
    
    elif args.mode == "rest":
        client.tts_basic(args.text, args.language)
    
    elif args.mode == "stream":
        client.tts_streaming(args.text, args.language, args.speaker)
    
    elif args.mode == "websocket":
        asyncio.run(client.tts_websocket(args.text, args.language, args.speaker))
    
    elif args.mode == "clone":
        if not args.speaker:
            print("Error: --speaker required for voice cloning mode")
            return
        client.voice_clone(args.text, args.speaker, args.language)


if __name__ == "__main__":
    main()
