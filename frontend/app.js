/**
 * CityConcierge - Voice Interface
 * Handles voice recording, backend communication, and audio playback
 */

console.log("App.js loaded (web v2)");
window.onerror = function(msg, url, line) {
    console.error("JS Error: " + msg + " at line " + line);
};

// API_BASE_URL is now in shared.js, but we need it here too for voice calls
const VOICE_API = window.location.hostname === 'localhost'
    ? 'http://localhost:8000'
    : '';

// DOM Elements — Desktop Stitch layout
const micButton = document.getElementById('mic-button');
const micLabel = document.getElementById('mic-label');
const micContainer = document.getElementById('mic-container');
const micPulseOuter = document.getElementById('mic-pulse-outer');

// State containers
const stateIdle = document.getElementById('state-idle');
const stateRecording = document.getElementById('state-recording');
const stateLoading = document.getElementById('state-loading');

// Response elements (inside the response card)
const greetingText = document.getElementById('greeting-text');
const responseText = document.getElementById('response-text');
const transcriptContainer = document.getElementById('transcript-container');
const transcriptText = document.getElementById('transcript-text');
const againButton = document.getElementById('again-button');
const actionChips = document.getElementById('action-chips');
const loadingText = document.getElementById('loading-text');
const statusText = document.getElementById('status-text');

// State
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;
let sessionId = null;

// Initialize
async function init() {
    console.log("Init running");
    console.log("Mic button found:", !!micButton);
    
    if (!micButton) {
        console.error("Mic button not found in DOM!");
        statusText.textContent = 'Hata: Mikrofon butonu bulunamadı';
        return;
    }

    // Check for microphone permission on init
    try {
        console.log("Requesting mic permission...");
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        stream.getTracks().forEach(track => track.stop());
        console.log('Microphone access granted');
    } catch (err) {
        console.error('Microphone access denied:', err);
        statusText.textContent = '🎤 Mikrofon erişimi gerekli. Lütfen tarayıcı ayarlarından izin verin.';
        micButton.disabled = true;
        micButton.style.opacity = '0.5';
        return;
    }

    // Event listeners - BOTH mouse and touch for cross-device support
    micButton.addEventListener('mousedown', (e) => {
        console.log("Mouse down detected");
        e.preventDefault();
        startRecording();
    });
    
    micButton.addEventListener('mouseup', (e) => {
        console.log("Mouse up detected");
        e.preventDefault();
        stopRecording();
    });
    
    micButton.addEventListener('mouseleave', (e) => {
        console.log("Mouse leave detected");
        if (isRecording) {
            e.preventDefault();
            stopRecording();
        }
    });
    
    // Touch events for mobile
    micButton.addEventListener('touchstart', (e) => {
        console.log("Touch start detected");
        e.preventDefault();
        e.stopPropagation();
        startRecording();
    }, { passive: false });
    
    micButton.addEventListener('touchend', (e) => {
        console.log("Touch end detected");
        e.preventDefault();
        e.stopPropagation();
        stopRecording();
    }, { passive: false });

    againButton.addEventListener('click', resetUI);
    
    console.log("Event listeners attached successfully");
}

async function startRecording() {
    if (isRecording) {
        console.log("Already recording, ignoring");
        return;
    }
    
    console.log("Starting recording...");
    
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ 
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                sampleRate: 44100
            }
        });
        console.log("Media stream obtained");

        // Check for supported mime types
        const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') 
            ? 'audio/webm;codecs=opus' 
            : MediaRecorder.isTypeSupported('audio/webm')
            ? 'audio/webm'
            : 'audio/mp4';
        
        console.log("Using mime type:", mimeType);

        mediaRecorder = new MediaRecorder(stream, { mimeType });
        console.log("MediaRecorder created");

        audioChunks = [];

        mediaRecorder.ondataavailable = (event) => {
            console.log("Data available:", event.data.size, "bytes");
            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }
        };

        mediaRecorder.onstop = async () => {
            console.log("MediaRecorder stopped");
            const audioBlob = new Blob(audioChunks, { type: mimeType });
            console.log("Audio blob created:", audioBlob.size, "bytes");
            
            // Stop all tracks
            stream.getTracks().forEach(track => track.stop());
            
            // Show loading AFTER recording stops
            showLoading();
            
            // Send to backend
            await sendToBackend(audioBlob);
        };

        mediaRecorder.onerror = (e) => {
            console.error("MediaRecorder error:", e);
            statusText.textContent = 'Kayıt hatası. Tekrar deneyin.';
            isRecording = false;
            micButton.classList.remove('recording');
        };

        mediaRecorder.start();
        isRecording = true;
        console.log("Recording started");

        // Update UI during recording - NO spinner, just visual feedback
        micButton.classList.add('recording');
        stateIdle.classList.add('hidden');
        stateLoading.classList.add('hidden');
        stateRecording.classList.remove('hidden');
        micLabel.textContent = 'Bırakınca gönderilecek...';
        micPulseOuter.classList.remove('hidden');
        micButton.classList.add('mic-glow-active');
        micButton.classList.remove('mic-glow');
        
    } catch (err) {
        console.error('Error starting recording:', err);
        statusText.textContent = 'Mikrofon başlatılamadı. Tekrar deneyin.';
        micButton.classList.remove('recording');
        micLabel.textContent = 'Sormak için basılı tut';
    }
}

function stopRecording() {
    console.log("Stop recording called, isRecording:", isRecording);
    if (!isRecording || !mediaRecorder) {
        console.log("Not recording, ignoring stop");
        return;
    }
    
    console.log("Stopping recording...");
    mediaRecorder.stop();
    isRecording = false;
    micButton.classList.remove('recording');
    micLabel.textContent = 'Sormak için basılı tut';
    micPulseOuter.classList.add('hidden');
    micButton.classList.remove('mic-glow-active');
    micButton.classList.add('mic-glow');
}

function showLoading() {
    console.log("Showing loading state");
    stateIdle.classList.add('hidden');
    stateRecording.classList.add('hidden');
    stateLoading.classList.remove('hidden');
    micContainer.classList.add('hidden');
}

function renderResponseSafely(container, text) {
    // Clear previous content
    container.innerHTML = '';

    const phoneRegex = /(0\d{3})\s*(\d{3})\s*(\d{2})\s*(\d{2})/g;
    let lastIndex = 0;
    let match;

    while ((match = phoneRegex.exec(text)) !== null) {
        // Add text before the phone number as a text node (safe)
        if (match.index > lastIndex) {
            container.appendChild(document.createTextNode(text.slice(lastIndex, match.index)));
        }

        // Create a clickable link for the phone number
        const link = document.createElement('a');
        link.href = `tel:${match[1]}${match[2]}${match[3]}${match[4]}`;
        link.className = 'phone-link';
        link.textContent = `${match[1]} ${match[2]} ${match[3]} ${match[4]}`;
        container.appendChild(link);

        lastIndex = phoneRegex.lastIndex;
    }

    // Add remaining text after last phone number
    if (lastIndex < text.length) {
        container.appendChild(document.createTextNode(text.slice(lastIndex)));
    }
}

async function sendToBackend(audioBlob) {
    console.log("Sending to backend, blob size:", audioBlob.size);
    loadingText.textContent = 'Düşünüyorum...';

    try {
        const formData = new FormData();
        formData.append('audio', audioBlob, 'recording.webm');
        
        if (sessionId) {
            formData.append('session_id', sessionId);
        }

        console.log("Fetching from:", `${VOICE_API}/api/voice`);
        const response = await fetch(`${VOICE_API}/api/voice`, {
            method: 'POST',
            body: formData
        });

        console.log("Response status:", response.status);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log('Response data:', data);
        
        if (data.session_id) {
            sessionId = data.session_id;
        }

        // Hide loading, show idle
        stateLoading.classList.add('hidden');
        stateRecording.classList.add('hidden');
        stateIdle.classList.remove('hidden');
        micContainer.classList.remove('hidden');

        // Hide greeting, show response
        greetingText.classList.add('hidden');
        actionChips.classList.add('hidden');

        // Show user's transcript
        if (data.transcript) {
            transcriptText.textContent = data.transcript;
            transcriptContainer.classList.remove('hidden');
        }

        // Show response with clickable phone numbers
        responseText.classList.remove('hidden');
        renderResponseSafely(responseText, data.response);
        againButton.classList.remove('hidden');

        // Play audio response
        if (data.audio_url) {
            playAudioResponse(data.audio_url);
        }

    } catch (err) {
        console.error('Error sending to backend:', err);
        stateLoading.classList.add('hidden');
        stateRecording.classList.add('hidden');
        stateIdle.classList.remove('hidden');
        micContainer.classList.remove('hidden');
        statusText.textContent = 'Bir hata oluştu. Lütfen tekrar deneyin.';
    }
}

function playAudioResponse(audioUrl) {
    const fullUrl = `${VOICE_API}${audioUrl}`;
    console.log("Playing audio from:", fullUrl);
    const audio = new Audio(fullUrl);
    
    audio.play().catch(err => {
        console.error('Error playing audio:', err);
    });
}

function resetUI() {
    // Show greeting, hide response
    greetingText.classList.remove('hidden');
    actionChips.classList.remove('hidden');
    responseText.classList.add('hidden');
    transcriptContainer.classList.add('hidden');
    againButton.classList.add('hidden');

    // Ensure idle state
    stateIdle.classList.remove('hidden');
    stateRecording.classList.add('hidden');
    stateLoading.classList.add('hidden');

    // Reset mic
    micContainer.classList.remove('hidden');
    micLabel.textContent = 'Sormak için basılı tut';

    // Reset subtitle
    statusText.textContent = 'Size bugün nasıl yardımcı olabilirim?';
}

// Health check on load
async function checkBackend() {
    try {
        console.log("Checking backend at:", `${VOICE_API}/health`);
        const response = await fetch(`${VOICE_API}/health`);
        if (response.ok) {
            console.log('Backend is running');
        }
    } catch (err) {
        console.warn('Backend not available:', err);
        statusText.textContent = '⚠️ Sunucu bağlantısı yok. Backend başlatıldıktan sonra sayfayı yenileyin.';
    }
}

// Start
checkBackend();
init();
