
// --- Configuration ---
const API_GATEWAY = ""; // Relative path for Nginx proxy
const JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJwbGF0Zm9ybS1qd3QtaXNzdWVyIiwic3ViIjoidmVyaWZpY2F0aW9uLWRhc2hib2FyZC11c2VyIiwibmFtZSI6IkFkbWluIFVzZXIiLCJyb2xlIjoiYWRtaW4iLCJleHAiOjE3OTcyNDQ1ODF9.lNPCvGnwUjVPBTK8-c9Fgbx9olWuO4Fpc6knbGDTz2A"; // Generated Dev Token
const USER_ID = "verification-dashboard-user";

// --- State ---
const state = {
    currentService: 'chat-section',
    documents: []
};

// --- API Client ---
async function apiCall(endpoint, method = 'GET', body = null, isFileUpload = false) {
    const headers = {
        'Authorization': `Bearer ${JWT_TOKEN}`
    };

    if (!isFileUpload) {
        headers['Content-Type'] = 'application/json';
    }

    const config = {
        method,
        headers,
    };

    if (body) {
        config.body = isFileUpload ? body : JSON.stringify(body);
    }

    try {
        const response = await fetch(`${API_GATEWAY}${endpoint}`, config);
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'API Request Failed');
        }
        return await response.json();
    } catch (err) {
        console.error("API Error:", err);
        alert(`Error: ${err.message}`);
        return null;
    }
}

// --- UI Navigation ---
document.querySelectorAll('.sidebar li').forEach(item => {
    item.addEventListener('click', () => {
        // Remove active class from all
        document.querySelectorAll('.sidebar li').forEach(li => li.classList.remove('active'));
        document.querySelectorAll('section').forEach(sec => sec.classList.remove('active'));

        // Add active to clicked
        item.classList.add('active');
        const targetId = item.getAttribute('data-target');
        document.getElementById(targetId).classList.add('active');

        state.currentService = targetId;
        if (targetId === 'chat-section') loadChatHistory();
        if (targetId === 'docs-section') loadDocuments();
        if (targetId === 'quiz-section') loadDocumentsForQuiz();
    });
});

// --- Chat Service ---
const chatInput = document.getElementById('chat-input');
const sendChatBtn = document.getElementById('send-chat-btn');
const chatHistory = document.getElementById('chat-history');

async function loadChatHistory() {
    try {
        const response = await apiCall(`/api/chat/conversations/${USER_ID}`);
        if (response && response.length > 0) {
            // Clear existing messages except welcome
            chatHistory.innerHTML = '';
            response.forEach(msg => {
                appendMessage(msg.message, msg.role);
            });
        }
    } catch (e) {
        console.log("No chat history yet");
    }
}

async function appendMessage(text, sender) {
    const div = document.createElement('div');
    div.classList.add('message', sender);
    div.textContent = text;
    chatHistory.appendChild(div);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

sendChatBtn.addEventListener('click', async () => {
    const text = chatInput.value.trim();
    if (!text) return;

    appendMessage(text, 'user');
    chatInput.value = '';

    const response = await apiCall('/api/chat/message', 'POST', {
        user_id: USER_ID,
        message: text
    });

    if (response) {
        // In a real app, we'd wait for WebSocket or poll for reply. 
        // For now, just acknowledge.
        appendMessage("Message sent to backend (Async processing)", 'bot');
    }
});

// --- Document Service ---
const docUploadInput = document.getElementById('doc-upload-input');
const uploadDocBtn = document.getElementById('upload-doc-btn');
const docList = document.getElementById('doc-list');

async function loadDocuments() {
    docList.innerHTML = '<li>Loading...</li>';
    const docs = await apiCall('/api/documents');
    docList.innerHTML = '';

    if (docs && docs.length > 0) {
        state.documents = docs;
        docs.forEach(doc => {
            const li = document.createElement('li');
            li.innerHTML = `
                <span>${doc.filename}</span>
                <small>${new Date(doc.uploaded_at).toLocaleDateString()}</small>
            `;
            docList.appendChild(li);
        });
    } else {
        docList.innerHTML = '<li>No documents found.</li>';
    }
}

uploadDocBtn.addEventListener('click', async () => {
    const file = docUploadInput.files[0];
    if (!file) return alert("Please select a file");

    const formData = new FormData();
    formData.append('file', file);

    const result = await apiCall('/api/documents/upload', 'POST', formData, true);
    if (result) {
        alert("Upload successful!");
        docUploadInput.value = '';
        loadDocuments();
    }
});

// --- Quiz Service ---
const quizDocSelect = document.getElementById('quiz-doc-select');
const generateQuizBtn = document.getElementById('generate-quiz-btn');
const quizDisplay = document.getElementById('quiz-display');

async function loadDocumentsForQuiz() {
    quizDocSelect.innerHTML = '<option>Loading...</option>';
    const docs = await apiCall('/api/documents');
    quizDocSelect.innerHTML = '';

    if (docs && docs.length > 0) {
        docs.forEach(doc => {
            const opt = document.createElement('option');
            opt.value = doc.id;
            opt.textContent = doc.filename;
            quizDocSelect.appendChild(opt);
        });
    } else {
        quizDocSelect.innerHTML = '<option>No documents available</option>';
    }
}

generateQuizBtn.addEventListener('click', async () => {
    const docId = quizDocSelect.value;
    if (!docId) return alert("Select a document");

    const result = await apiCall('/api/quiz/generate', 'POST', { document_id: docId });
    if (result) {
        // Fetch the quiz details immediately for demo (usually async)
        // Since the backend provided is naive, we might need to wait or mock if it's purely async
        // For this verified codebase, the backend returns quiz_id.
        // Let's try to fetch it.
        setTimeout(async () => {
            try {
                // This might fail if Kafka is slow, but let's try
                alert(`Quiz Generation Triggered! ID: ${result.quiz_id}. Check backend logs.`);
            } catch (e) { console.error(e); }
        }, 1000);
    }
});

// --- Audio Services ---
// TTS
const ttsInput = document.getElementById('tts-input');
const ttsBtn = document.getElementById('tts-btn');
const ttsPlayerContainer = document.getElementById('tts-player-container');

ttsBtn.addEventListener('click', async () => {
    const text = ttsInput.value.trim();
    if (!text) return;

    ttsBtn.textContent = "Synthesizing...";
    ttsBtn.disabled = true;

    const result = await apiCall('/api/tts/synthesize', 'POST', { text });
    if (result && result.request_id) {
        // Wait a bit for S3 upload
        setTimeout(async () => {
            try {
                const audioRes = await apiCall(`/api/tts/audio/${result.request_id}`);
                console.log("Audio response:", audioRes);

                if (audioRes && audioRes.url) {
                    // Create audio player
                    ttsPlayerContainer.innerHTML = `
                        <audio controls autoplay style="width: 100%; margin-top: 10px;">
                            <source src="${audioRes.url}" type="audio/mpeg">
                            Your browser does not support the audio element.
                        </audio>
                        <p style="font-size: 0.8em; color: #4ade80; margin-top: 5px;">✓ Audio generated successfully</p>
                    `;
                } else {
                    ttsPlayerContainer.innerHTML = `<p style="color: #f87171;">Failed to get audio URL. Check logs.</p>`;
                }
            } catch (e) {
                console.error("TTS Error:", e);
                ttsPlayerContainer.innerHTML = `<p style="color: #f87171;">Error: ${e.message}</p>`;
            }
            ttsBtn.textContent = "Synthesize";
            ttsBtn.disabled = false;
        }, 1500);
    } else {
        ttsBtn.textContent = "Synthesize";
        ttsBtn.disabled = false;
    }
});

// STT
const sttInput = document.getElementById('stt-upload-input');
const sttBtn = document.getElementById('stt-btn');
const sttResult = document.getElementById('stt-result');

sttBtn.addEventListener('click', async () => {
    const file = sttInput.files[0];
    if (!file) return alert("Select audio file");

    const formData = new FormData();
    formData.append('file', file);

    const result = await apiCall('/api/stt/transcribe', 'POST', formData, true);
    if (result) {
        // The backend returns status success immediately and publishes event.
        // There is no explicit "get text" endpoint for the immediate result in the response,
        // but there is GET /api/stt/transcription/{id}

        sttBtn.textContent = "Transcribing...";

        // Poll for completion
        let attempts = 0;
        const interval = setInterval(async () => {
            attempts++;
            if (attempts > 5) {
                clearInterval(interval);
                sttBtn.textContent = "Transcribe";
                alert("Transcription timed out (or is async). Check history.");
                return;
            }

            try {
                const check = await apiCall(`/api/stt/transcription/${result.id}`);
                if (check && check.text && check.text !== "Simulated transcription for ...") {
                    // The backend code basically sets the text immediately in the specific implementation I saw earlier.
                    // "Simulated transcription for {filename}"
                    clearInterval(interval);
                    sttResult.innerHTML = `<p>${check.text}</p>`;
                    sttBtn.textContent = "Transcribe";
                }
            } catch (e) { }
        }, 1000);
    }
});

// --- Initialize on page load ---
loadChatHistory();
