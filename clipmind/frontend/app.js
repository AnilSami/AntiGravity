const BACKEND_URL = window.location.origin.startsWith('file:') 
    ? 'http://127.0.0.1:8000' 
    : window.location.origin;

// DOM Elements
const form = document.getElementById('extractor-form');
const youtubeUrlInput = document.getElementById('youtube-url');
const numClipsInput = document.getElementById('num-clips');
const apiKeyInput = document.getElementById('api-key');
const toggleKeyVisibilityBtn = document.getElementById('toggle-key-visibility');
const submitBtn = document.getElementById('submit-btn');
const submitBtnText = submitBtn.querySelector('.btn-text');
const submitBtnSpinner = submitBtn.querySelector('.spinner');

const errorContainer = document.getElementById('error-container');
const errorMessage = document.getElementById('error-message');
const errorDismissBtn = document.getElementById('error-dismiss-btn');
const keyBadgeContainer = document.getElementById('key-badge-container');
const keyTypeBadge = document.getElementById('key-type-badge');
const tryMockBtn = document.getElementById('try-mock-btn');

const progressSection = document.getElementById('progress-section');
const statusMessage = document.getElementById('status-message');
const progressFill = document.getElementById('progress-fill');
const progressPercent = document.getElementById('progress-percent');

// Stepper Elements
const stepFetching = document.getElementById('step-fetching');
const stepAnalyzing = document.getElementById('step-analyzing');
const stepDownloading = document.getElementById('step-downloading');
const stepClipping = document.getElementById('step-clipping');
const steps = [stepFetching, stepAnalyzing, stepDownloading, stepClipping];

const resultsSection = document.getElementById('results-section');
const clipsCount = document.getElementById('clips-count');
const clipsGrid = document.getElementById('clips-grid');

let eventSource = null;

// Toggle API Key Visibility
toggleKeyVisibilityBtn.addEventListener('click', () => {
    if (apiKeyInput.type === 'password') {
        apiKeyInput.type = 'text';
        toggleKeyVisibilityBtn.textContent = '🙈';
    } else {
        apiKeyInput.type = 'password';
        toggleKeyVisibilityBtn.textContent = '👁️';
    }
});

// Dismiss Error
errorDismissBtn.addEventListener('click', () => {
    errorContainer.classList.add('hidden');
});

// Try Mock Mode Handler
tryMockBtn.addEventListener('click', () => {
    apiKeyInput.value = 'mock';
    apiKeyInput.dispatchEvent(new Event('input'));
    errorContainer.classList.add('hidden');
    form.dispatchEvent(new Event('submit'));
});

// API Key Live Diagnostics
apiKeyInput.addEventListener('input', () => {
    const key = apiKeyInput.value.trim();
    if (!key) {
        keyBadgeContainer.classList.add('hidden');
        return;
    }
    keyBadgeContainer.classList.remove('hidden');
    keyTypeBadge.className = 'badge';
    if (key.startsWith('sk-')) {
        keyTypeBadge.textContent = 'OpenAI Key 🔑';
        keyTypeBadge.classList.add('badge-openai');
    } else if (key.startsWith('mock')) {
        keyTypeBadge.textContent = 'Mock Mode 🧪';
        keyTypeBadge.classList.add('badge-mock');
    } else if (key.length > 15) {
        keyTypeBadge.textContent = 'Gemini Key 🔑';
        keyTypeBadge.classList.add('badge-gemini');
    } else {
        keyTypeBadge.textContent = 'Invalid / Short Key';
        keyTypeBadge.classList.add('badge-invalid');
    }
});

// Helper: Format seconds to M:SS
function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// Form Submit Handler
form.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const url = youtubeUrlInput.value.trim();
    const numClips = parseInt(numClipsInput.value, 10) || 5;
    const apiKey = apiKeyInput.value.trim();
    
    if (!url) return;

    // Reset UI states
    resetUI();
    setLoadingState(true);

    try {
        const response = await fetch(`${BACKEND_URL}/api/analyze`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                url: url,
                num_clips: numClips,
                gemini_api_key: apiKey || null
            })
        });

        const data = await response.json();

        if (!response.ok) {
            let errorMsg = 'Failed to start video analysis.';
            if (data && data.detail) {
                if (typeof data.detail === 'string') {
                    errorMsg = data.detail;
                } else if (Array.isArray(data.detail)) {
                    errorMsg = data.detail.map(d => {
                        const fieldName = d.loc && d.loc.length > 0 ? d.loc[d.loc.length - 1] : 'Field';
                        return `${fieldName}: ${d.msg}`;
                    }).join(', ');
                }
            }
            throw new Error(errorMsg);
        }

        const jobId = data.job_id;
        progressSection.classList.remove('hidden');
        listenProgress(jobId);

    } catch (err) {
        showError(err.message);
        setLoadingState(false);
    }
});
// Set button loading state

function setLoadingState(isLoading) {
    if (isLoading) {
        submitBtn.disabled = true;
        submitBtnText.textContent = 'Processing...';
        submitBtnSpinner.classList.remove('hidden');
    } else {
        submitBtn.disabled = false;
        submitBtnText.textContent = 'Extract Clips ✨';
        submitBtnSpinner.classList.add('hidden');
    }
}

// Reset all dynamic sections
function resetUI() {
    errorContainer.classList.add('hidden');
    progressSection.classList.add('hidden');
    resultsSection.classList.add('hidden');
    clipsGrid.innerHTML = '';
    progressFill.style.width = '0%';
    progressPercent.textContent = '0%';
    statusMessage.textContent = 'Initializing...';
    
    // Clear stepper states
    steps.forEach(step => {
        step.classList.remove('active', 'completed', 'failed');
    });

    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
}

// Show Error Banner
function showError(msg) {
    errorMessage.textContent = msg;
    errorContainer.classList.remove('hidden');
    
    // Detect if this is a quota or rate-limit issue
    const lowercaseMsg = msg.toLowerCase();
    if (lowercaseMsg.includes('quota') || lowercaseMsg.includes('429') || lowercaseMsg.includes('rate limit') || lowercaseMsg.includes('limit exceeded') || lowercaseMsg.includes('key is missing') || lowercaseMsg.includes('api key')) {
        tryMockBtn.classList.remove('hidden');
    } else {
        tryMockBtn.classList.add('hidden');
    }
    
    // Mark current active step as failed
    const activeStep = steps.find(step => step.classList.contains('active'));
    if (activeStep) {
        activeStep.classList.remove('active');
        activeStep.classList.add('failed');
    }
    
    errorContainer.scrollIntoView({ behavior: 'smooth' });
}

// Update Stepper Visuals based on pipeline status
function updateStepper(status) {
    // Reset all
    steps.forEach(step => step.classList.remove('active', 'completed'));

    if (status === 'fetching_transcript') {
        stepFetching.classList.add('active');
    } else if (status === 'analyzing') {
        stepFetching.classList.add('completed');
        stepAnalyzing.classList.add('active');
    } else if (status === 'downloading') {
        stepFetching.classList.add('completed');
        stepAnalyzing.classList.add('completed');
        stepDownloading.classList.add('active');
    } else if (status === 'clipping') {
        stepFetching.classList.add('completed');
        stepAnalyzing.classList.add('completed');
        stepDownloading.classList.add('completed');
        stepClipping.classList.add('active');
    } else if (status === 'completed') {
        steps.forEach(step => step.classList.add('completed'));
    }
}

// Connect to EventSource (SSE) for progress streaming
function listenProgress(jobId) {
    eventSource = new EventSource(`${BACKEND_URL}/api/progress/${jobId}`);

    eventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            
            // Update UI elements
            statusMessage.textContent = data.message;
            progressFill.style.width = `${data.progress}%`;
            progressPercent.textContent = `${data.progress}%`;
            
            updateStepper(data.status);

            if (data.status === 'completed') {
                eventSource.close();
                fetchResults(jobId);
            } else if (data.status === 'failed') {
                eventSource.close();
                showError(data.error || 'Pipeline execution failed.');
                setLoadingState(false);
            }
        } catch (e) {
            console.error('Error parsing SSE event:', e);
        }
    };

    eventSource.onerror = (err) => {
        console.error('SSE Error:', err);
        eventSource.close();
        showError('Lost connection to progress monitoring. Checking job state manually...');
        setLoadingState(false);
    };
}

// Fetch clips after completion
async function fetchResults(jobId) {
    try {
        const response = await fetch(`${BACKEND_URL}/api/clips/${jobId}`);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || 'Failed to fetch clips list.');
        }

        renderClips(jobId, data.clips);
    } catch (err) {
        showError(err.message);
    } finally {
        setLoadingState(false);
    }
}

// Render Clip Cards inside grid
function renderClips(jobId, clips) {
    clipsGrid.innerHTML = '';
    clipsCount.textContent = clips.length;

    if (clips.length === 0) {
        clipsGrid.innerHTML = '<p class="text-muted">No clips were generated for this video.</p>';
        resultsSection.classList.remove('hidden');
        resultsSection.scrollIntoView({ behavior: 'smooth' });
        return;
    }

    clips.forEach(clip => {
        const card = document.createElement('article');
        card.className = 'clip-card';

        const videoUrl = `${BACKEND_URL}/api/video/${jobId}/${clip.filename}`;
        
        const shortsTitle = clip.shorts_title || '';
        const shortsDescription = clip.shorts_description || '';
        const shortsTags = clip.shorts_tags || [];
        const tagsHtml = shortsTags.map(tag => `<span class="badge badge-tag">#${escapeHtml(tag)}</span>`).join(' ');

        card.innerHTML = `
            <div class="video-container">
                <video controls preload="metadata">
                    <source src="${videoUrl}" type="video/mp4">
                    Your browser does not support the video tag.
                </video>
            </div>
            <div class="clip-content">
                <div class="clip-badges">
                    <span class="badge badge-time">⏱️ ${formatTime(clip.start_time)} - ${formatTime(clip.end_time)}</span>
                    <span class="badge badge-duration">${Math.round(clip.duration)}s</span>
                </div>
                <h3 class="clip-title">${escapeHtml(clip.title)}</h3>
                <p class="clip-reason">${escapeHtml(clip.reason)}</p>
                
                <div class="seo-metadata-container">
                    <h4 class="seo-section-title">✨ YouTube Shorts SEO</h4>
                    
                    <div class="seo-field">
                        <div class="seo-field-header">
                            <span class="seo-field-label">Shorts Title</span>
                            <button class="btn-copy" data-copy-text="${escapeHtml(shortsTitle)}">Copy</button>
                        </div>
                        <div class="seo-field-value">${escapeHtml(shortsTitle)}</div>
                    </div>
                    
                    <div class="seo-field">
                        <div class="seo-field-header">
                            <span class="seo-field-label">Description</span>
                            <button class="btn-copy" data-copy-text="${escapeHtml(shortsDescription)}">Copy</button>
                        </div>
                        <div class="seo-field-value text-area-style">${escapeHtml(shortsDescription)}</div>
                    </div>
                    
                    <div class="seo-field">
                        <div class="seo-field-header">
                            <span class="seo-field-label">Tags</span>
                        </div>
                        <div class="seo-tags">
                            ${tagsHtml || '<span class="text-muted" style="font-size: 0.8rem;">No tags</span>'}
                        </div>
                    </div>
                </div>

                <a href="${videoUrl}" download="${clip.title.replace(/[^a-z0-9]/gi, '_').toLowerCase()}.mp4" class="btn btn-secondary btn-small btn-download">
                    📥 Download Clip
                </a>
            </div>
        `;
        clipsGrid.appendChild(card);
    });

    resultsSection.classList.remove('hidden');
    resultsSection.scrollIntoView({ behavior: 'smooth' });
}

// Event Delegation for Copy Buttons
clipsGrid.addEventListener('click', async (e) => {
    const copyBtn = e.target.closest('.btn-copy');
    if (!copyBtn) return;

    const textToCopy = copyBtn.getAttribute('data-copy-text');
    if (!textToCopy) return;

    try {
        await navigator.clipboard.writeText(textToCopy);
        
        // Success animation/feedback
        const originalText = copyBtn.textContent;
        copyBtn.textContent = 'Copied! ✓';
        copyBtn.classList.add('copied');
        
        setTimeout(() => {
            copyBtn.textContent = originalText;
            copyBtn.classList.remove('copied');
        }, 1500);
    } catch (err) {
        console.error('Failed to copy text: ', err);
        // Fallback for older browsers or non-secure contexts
        const textarea = document.createElement('textarea');
        textarea.value = textToCopy;
        textarea.style.position = 'fixed';
        document.body.appendChild(textarea);
        textarea.select();
        try {
            document.execCommand('copy');
            const originalText = copyBtn.textContent;
            copyBtn.textContent = 'Copied! ✓';
            copyBtn.classList.add('copied');
            setTimeout(() => {
                copyBtn.textContent = originalText;
                copyBtn.classList.remove('copied');
            }, 1500);
        } catch (e) {
            console.error('Fallback copy failed: ', e);
        }
        document.body.removeChild(textarea);
    }
});

// Safe string escape helper
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
