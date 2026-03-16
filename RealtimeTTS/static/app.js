/**
 * Voice Clone Studio — Client Application
 * Handles voice upload, TTS generation, audio playback, and history
 */

const API_BASE = '';  // Same origin

// ── State ──────────────────────────────────────────────
const state = {
    uploadedVoicePath: null,
    uploadedVoiceName: null,
    isGenerating: false,
    history: []
};

// ── DOM Elements ───────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const els = {
    statusDot: $('.status-dot'),
    statusText: $('.status-text'),
    dropZone: $('#dropZone'),
    dropContent: $('#dropContent'),
    uploadedInfo: $('#uploadedInfo'),
    uploadedName: $('#uploadedName'),
    uploadedSize: $('#uploadedSize'),
    voicePreview: $('#voicePreview'),
    changeVoiceBtn: $('#changeVoiceBtn'),
    fileInput: $('#fileInput'),
    voicesList: $('#voicesList'),
    existingVoices: $('#existingVoices'),
    textInput: $('#textInput'),
    charCount: $('#charCount'),
    languageSelect: $('#languageSelect'),
    generateBtn: $('#generateBtn'),
    btnContent: $('#btnContent'),
    btnLoading: $('#btnLoading'),
    outputPlaceholder: $('#outputPlaceholder'),
    outputResult: $('#outputResult'),
    outputAudio: $('#outputAudio'),
    outputStats: $('#outputStats'),
    downloadBtn: $('#downloadBtn'),
    historyList: $('#historyList'),
    historyEmpty: $('#historyEmpty'),
    clearHistoryBtn: $('#clearHistoryBtn')
};

// ── Init ───────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    checkHealth();
    loadExistingVoices();
    setupDropZone();
    setupTextInput();
    setupGenerate();
    setupHistory();
});

// ── Health Check ───────────────────────────────────────
async function checkHealth() {
    try {
        const res = await fetch(`${API_BASE}/health`);
        const data = await res.json();
        if (data.status === 'healthy') {
            els.statusDot.classList.add('connected');
            els.statusText.textContent = 'Server ready';
        } else {
            els.statusDot.classList.add('error');
            els.statusText.textContent = 'Server unhealthy';
        }
    } catch (e) {
        els.statusDot.classList.add('error');
        els.statusText.textContent = 'Server offline';
    }
}

// ── Existing Voices ────────────────────────────────────
async function loadExistingVoices() {
    try {
        const res = await fetch(`${API_BASE}/api/voices`);
        const data = await res.json();
        
        if (data.voices && data.voices.length > 0) {
            els.existingVoices.classList.remove('hidden');
            els.voicesList.innerHTML = '';
            
            data.voices.forEach(voice => {
                const chip = document.createElement('button');
                chip.className = 'voice-chip';
                chip.innerHTML = `<span class="voice-chip-icon">🎙️</span> ${voice.filename}`;
                chip.title = `${voice.size_kb} KB`;
                chip.addEventListener('click', () => selectExistingVoice(voice, chip));
                els.voicesList.appendChild(chip);
            });
        } else {
            els.existingVoices.classList.add('hidden');
        }
    } catch (e) {
        els.existingVoices.classList.add('hidden');
    }
}

function selectExistingVoice(voice, chipEl) {
    // Update UI
    $$('.voice-chip').forEach(c => c.classList.remove('active'));
    chipEl.classList.add('active');
    
    // Set state
    state.uploadedVoicePath = voice.path;
    state.uploadedVoiceName = voice.filename;
    
    // Show uploaded state in drop zone
    els.dropContent.classList.add('hidden');
    els.uploadedInfo.classList.remove('hidden');
    els.uploadedName.textContent = voice.filename;
    els.uploadedSize.textContent = `${voice.size_kb} KB`;
    els.voicePreview.classList.add('hidden');
    
    updateGenerateBtn();
    showToast(`Selected voice: ${voice.filename}`, 'success');
}

// ── Drop Zone ──────────────────────────────────────────
function setupDropZone() {
    const zone = els.dropZone;
    
    // Click to browse
    zone.addEventListener('click', (e) => {
        if (e.target === els.changeVoiceBtn || e.target.closest('#changeVoiceBtn')) return;
        if (e.target.closest('audio')) return;
        els.fileInput.click();
    });
    
    // File selected via input
    els.fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });
    
    // Change voice button
    els.changeVoiceBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        resetUpload();
        els.fileInput.click();
    });
    
    // Drag & drop
    zone.addEventListener('dragover', (e) => {
        e.preventDefault();
        zone.classList.add('drag-over');
    });
    
    zone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        zone.classList.remove('drag-over');
    });
    
    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('drag-over');
        if (e.dataTransfer.files.length > 0) {
            handleFile(e.dataTransfer.files[0]);
        }
    });
}

function resetUpload() {
    state.uploadedVoicePath = null;
    state.uploadedVoiceName = null;
    els.dropContent.classList.remove('hidden');
    els.uploadedInfo.classList.add('hidden');
    els.fileInput.value = '';
    $$('.voice-chip').forEach(c => c.classList.remove('active'));
    updateGenerateBtn();
}

async function handleFile(file) {
    // Validate
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    const allowed = ['.wav', '.mp3', '.flac', '.ogg', '.m4a'];
    
    if (!allowed.includes(ext)) {
        showToast(`Unsupported format: ${ext}`, 'error');
        return;
    }
    
    if (file.size > 20 * 1024 * 1024) {
        showToast('File too large (max 20MB)', 'error');
        return;
    }
    
    // Show uploading state
    els.dropContent.classList.add('hidden');
    els.uploadedInfo.classList.remove('hidden');
    els.uploadedName.textContent = 'Uploading...';
    els.uploadedSize.textContent = `${(file.size / 1024).toFixed(1)} KB`;
    els.voicePreview.classList.add('hidden');
    
    try {
        const formData = new FormData();
        formData.append('file', file);
        
        const res = await fetch(`${API_BASE}/api/upload-voice`, {
            method: 'POST',
            body: formData
        });
        
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Upload failed');
        }
        
        const data = await res.json();
        
        // Update state
        state.uploadedVoicePath = data.path;
        state.uploadedVoiceName = data.original_name;
        
        // Update UI
        els.uploadedName.textContent = data.original_name;
        els.uploadedSize.textContent = `${data.size_kb} KB`;
        
        // Audio preview
        const previewUrl = URL.createObjectURL(file);
        els.voicePreview.src = previewUrl;
        els.voicePreview.classList.remove('hidden');
        
        updateGenerateBtn();
        loadExistingVoices();
        showToast('Voice sample uploaded!', 'success');
        
    } catch (e) {
        resetUpload();
        showToast(`Upload failed: ${e.message}`, 'error');
    }
}

// ── Text Input ─────────────────────────────────────────
function setupTextInput() {
    els.textInput.addEventListener('input', () => {
        const len = els.textInput.value.length;
        els.charCount.textContent = `${len} / 5000`;
        updateGenerateBtn();
    });
}

// ── Generate Button State ──────────────────────────────
function updateGenerateBtn() {
    const hasVoice = state.uploadedVoicePath !== null;
    const hasText = els.textInput.value.trim().length > 0;
    els.generateBtn.disabled = !hasVoice || !hasText || state.isGenerating;
}

// ── Generate Speech ────────────────────────────────────
function setupGenerate() {
    els.generateBtn.addEventListener('click', generateSpeech);
}

async function generateSpeech() {
    if (state.isGenerating) return;
    
    const text = els.textInput.value.trim();
    const language = els.languageSelect.value;
    
    if (!text || !state.uploadedVoicePath) return;
    
    // Set loading state
    state.isGenerating = true;
    els.btnContent.classList.add('hidden');
    els.btnLoading.classList.remove('hidden');
    els.generateBtn.disabled = true;
    
    const startTime = Date.now();
    
    try {
        const res = await fetch(`${API_BASE}/api/voice-clone`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: text,
                speaker_audio_path: state.uploadedVoicePath,
                language: language
            })
        });
        
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Generation failed');
        }
        
        const data = await res.json();
        const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
        
        // Show result
        const audioUrl = `${API_BASE}${data.audio_url}`;
        els.outputAudio.src = audioUrl;
        els.downloadBtn.href = audioUrl;
        els.downloadBtn.download = `clone_${Date.now()}.wav`;
        
        // Stats
        els.outputStats.innerHTML = `
            <div class="stat-item">
                <span class="stat-label">Duration</span>
                <span class="stat-value">${data.duration?.toFixed(1) || '—'}s</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Synthesis Time</span>
                <span class="stat-value">${data.synthesis_time_ms ? (data.synthesis_time_ms / 1000).toFixed(1) + 's' : elapsed + 's'}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Real-Time Factor</span>
                <span class="stat-value">${data.real_time_factor?.toFixed(1) || '—'}x</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Language</span>
                <span class="stat-value">${language.toUpperCase()}</span>
            </div>
        `;
        
        els.outputPlaceholder.classList.add('hidden');
        els.outputResult.classList.remove('hidden');
        
        // Auto-play
        els.outputAudio.play();
        
        // Add to history
        addToHistory({
            text: text,
            audioUrl: audioUrl,
            duration: data.duration,
            language: language,
            voice: state.uploadedVoiceName,
            timestamp: new Date()
        });
        
        showToast('Speech generated!', 'success');
        
    } catch (e) {
        showToast(`Generation failed: ${e.message}`, 'error');
    } finally {
        state.isGenerating = false;
        els.btnContent.classList.remove('hidden');
        els.btnLoading.classList.add('hidden');
        updateGenerateBtn();
    }
}

// ── History ────────────────────────────────────────────
function setupHistory() {
    els.clearHistoryBtn.addEventListener('click', () => {
        state.history = [];
        renderHistory();
    });
}

function addToHistory(item) {
    state.history.unshift(item);
    if (state.history.length > 20) state.history.pop();
    renderHistory();
}

function renderHistory() {
    if (state.history.length === 0) {
        els.historyEmpty.classList.remove('hidden');
        els.historyList.innerHTML = '';
        els.historyList.appendChild(els.historyEmpty);
        return;
    }
    
    els.historyList.innerHTML = '';
    
    state.history.forEach((item, i) => {
        const el = document.createElement('div');
        el.className = 'history-item';
        
        const timeStr = item.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        
        el.innerHTML = `
            <button class="history-item-play" data-index="${i}" title="Play">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                    <polygon points="5 3 19 12 5 21 5 3"/>
                </svg>
            </button>
            <div class="history-item-info">
                <div class="history-item-text">${escapeHtml(item.text)}</div>
                <div class="history-item-meta">
                    ${timeStr} · ${item.duration?.toFixed(1) || '?'}s · ${item.language.toUpperCase()} · ${item.voice || 'default'}
                </div>
            </div>
        `;
        
        // Play on click
        el.querySelector('.history-item-play').addEventListener('click', (e) => {
            e.stopPropagation();
            els.outputAudio.src = item.audioUrl;
            els.outputAudio.play();
            els.outputPlaceholder.classList.add('hidden');
            els.outputResult.classList.remove('hidden');
        });
        
        els.historyList.appendChild(el);
    });
}

// ── Toast Notifications ────────────────────────────────
function showToast(message, type = 'info') {
    // Remove existing toasts
    document.querySelectorAll('.toast').forEach(t => t.remove());
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => toast.remove(), 3000);
}

// ── Utils ──────────────────────────────────────────────
function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
