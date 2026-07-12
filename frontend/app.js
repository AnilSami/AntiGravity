// API base URL resolution (priority order):
//   1. window.CLIPMIND_API_URL — injected by Cloudflare Pages env var via _worker.js or _headers
//   2. Same-origin — when served directly from the FastAPI backend
//   3. Localhost fallback — for local file:// development
const BACKEND_URL = window.CLIPMIND_API_URL
    || (window.location.origin.startsWith('file:') ? 'http://127.0.0.1:8000' : window.location.origin);

// Global YouTube OAuth Connection State
window.youtubeConnected = false;
window.youtubeChannelName = '';

async function checkYoutubeStatus() {
    try {
        const response = await fetch(`${BACKEND_URL}/api/youtube/status`);
        const data = await response.json();
        const connectedChanged = (window.youtubeConnected !== data.connected);
        window.youtubeConnected = data.connected;
        window.youtubeChannelName = data.channel_name;
        
        // Update connection status bar
        const globalStatusBar = document.getElementById('youtube-global-status-bar');
        if (globalStatusBar) {
            globalStatusBar.style.display = 'block';
            if (window.youtubeConnected) {
                globalStatusBar.style.background = 'rgba(46, 213, 115, 0.15)';
                globalStatusBar.style.border = '1px solid rgba(46, 213, 115, 0.3)';
                globalStatusBar.style.color = '#2ed573';
                globalStatusBar.innerHTML = `YouTube: ✅ Connected as <strong>${escapeHtml(window.youtubeChannelName)}</strong>`;
            } else {
                globalStatusBar.style.background = 'rgba(255, 71, 87, 0.15)';
                globalStatusBar.style.border = '1px solid rgba(255, 71, 87, 0.3)';
                globalStatusBar.style.color = '#ff4757';
                globalStatusBar.innerHTML = `YouTube: ❌ Not connected — <a href="#" class="btn-connect-popup" style="color: #ff4757; text-decoration: underline; font-weight: bold;">Connect now</a>`;
            }
        }
        
        // If connection status toggled, update all clip cards in the DOM!
        if (connectedChanged) {
            updateAllClipCardButtons();
        }
    } catch (err) {
        console.error('Error checking YouTube status:', err);
    }
}

function updateAllClipCardButtons() {
    const containers = document.querySelectorAll('.youtube-upload-container');
    containers.forEach(container => {
        const clipId = container.id.replace('yt-container-', '');
        // Do not overwrite if already uploaded
        if (container.querySelector('a[href*="youtu.be"]')) return;
        
        if (window.youtubeConnected) {
            container.innerHTML = `
                <button type="button" class="btn btn-primary btn-small btn-upload-youtube" data-clip-id="${clipId}" style="flex: 1; justify-content: center; background: #ff0000; border-color: #ff0000;">
                    Upload to YouTube ▶
                </button>
            `;
        } else {
            container.innerHTML = `
                <button type="button" class="btn btn-secondary btn-small btn-connect-popup" style="flex: 1; justify-content: center;">
                    Connect YouTube
                </button>
            `;
        }
    });
}


// DOM Elements
const form = document.getElementById('extractor-form');
const youtubeUrlInput = document.getElementById('youtube-url');
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

// Subtitle Style & Creator Preset Selects
const subtitleStyleSelect = document.getElementById('subtitle-style');
const creatorPresetSelect = document.getElementById('creator-preset');
const debugCameraTrackingCheckbox = document.getElementById('debug-camera-tracking');
const forceRefreshCheckbox = document.getElementById('force-refresh');
const bypassCameraQaCheckbox = document.getElementById('bypass-camera-qa');
const numClipsSelect = document.getElementById('num-clips');

// Load saved selections from localStorage
if (subtitleStyleSelect) {
    const savedStyle = localStorage.getItem('subtitle-style');
    if (savedStyle) subtitleStyleSelect.value = savedStyle;
    subtitleStyleSelect.addEventListener('change', () => {
        localStorage.setItem('subtitle-style', subtitleStyleSelect.value);
    });
}
if (creatorPresetSelect) {
    const savedPreset = localStorage.getItem('creator-preset');
    if (savedPreset) creatorPresetSelect.value = savedPreset;
    creatorPresetSelect.addEventListener('change', () => {
        localStorage.setItem('creator-preset', creatorPresetSelect.value);
    });
}
if (debugCameraTrackingCheckbox) {
    const savedDebug = localStorage.getItem('debug-camera-tracking');
    if (savedDebug) debugCameraTrackingCheckbox.checked = (savedDebug === 'true');
    debugCameraTrackingCheckbox.addEventListener('change', () => {
        localStorage.setItem('debug-camera-tracking', debugCameraTrackingCheckbox.checked);
    });
}
if (forceRefreshCheckbox) {
    const savedForce = localStorage.getItem('force-refresh');
    if (savedForce) forceRefreshCheckbox.checked = (savedForce === 'true');
    forceRefreshCheckbox.addEventListener('change', () => {
        localStorage.setItem('force-refresh', forceRefreshCheckbox.checked);
    });
}
if (bypassCameraQaCheckbox) {
    const savedBypass = localStorage.getItem('bypass-camera-qa');
    if (savedBypass) bypassCameraQaCheckbox.checked = (savedBypass === 'true');
    bypassCameraQaCheckbox.addEventListener('change', () => {
        localStorage.setItem('bypass-camera-qa', bypassCameraQaCheckbox.checked);
    });
}
if (numClipsSelect) {
    const savedNumClips = localStorage.getItem('num-clips');
    if (savedNumClips) numClipsSelect.value = savedNumClips;
    numClipsSelect.addEventListener('change', () => {
        localStorage.setItem('num-clips', numClipsSelect.value);
    });
}

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

const CREATOR_PRESETS = {
    hormozi: {
        font_name: "Anton",
        font_size: 75,
        pop_scale: 1.25,
        pop_duration: 260,
        primary_color: "#FFFFFF",
        highlight_color: "#FFD400",
        outline_color: "#000000",
        outline_thickness: 5,
        shadow_depth: 2
    },
    abdaal: {
        font_name: "Montserrat ExtraBold",
        font_size: 70,
        pop_scale: 1.10,
        pop_duration: 200,
        primary_color: "#FFFFFF",
        highlight_color: "#FFD400",
        outline_color: "#000000",
        outline_thickness: 3,
        shadow_depth: 1
    },
    ceo: {
        font_name: "Bebas Neue",
        font_size: 78,
        pop_scale: 1.15,
        pop_duration: 240,
        primary_color: "#FFFFFF",
        highlight_color: "#FFD400",
        outline_color: "#000000",
        outline_thickness: 4,
        shadow_depth: 2
    },
    minimal: {
        font_name: "Montserrat ExtraBold",
        font_size: 65,
        pop_scale: 1.00,
        pop_duration: 0,
        primary_color: "#FFFFFF",
        highlight_color: "#FFFFFF",
        outline_color: "#000000",
        outline_thickness: 2,
        shadow_depth: 0
    },
    custom: {
        font_name: "Anton",
        font_size: 75,
        pop_scale: 1.18,
        pop_duration: 260,
        primary_color: "#FFFFFF",
        highlight_color: "#FFD400",
        outline_color: "#000000",
        outline_thickness: 4,
        shadow_depth: 2
    }
};

// Form Submit Handler
form.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const url = youtubeUrlInput.value.trim();
    const apiKey = apiKeyInput.value.trim();
    
    if (!url) return;

    // Reset UI states
    resetUI();
    setLoadingState(true);

    const subStyle = subtitleStyleSelect ? subtitleStyleSelect.value : 'kinetic';
    const presetName = creatorPresetSelect ? creatorPresetSelect.value : 'custom';
    const preset = CREATOR_PRESETS[presetName] || CREATOR_PRESETS.custom;
    const rawNumClips = numClipsSelect ? numClipsSelect.value : '1';
    const numClips = rawNumClips === 'dynamic' ? null : parseInt(rawNumClips, 10);

    try {
        const response = await fetch(`${BACKEND_URL}/api/analyze`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                url: url,
                gemini_api_key: apiKey || null,
                num_clips: numClips,
                subtitle_style: subStyle,
                creator_preset: presetName,
                font_name: preset.font_name,
                font_size: preset.font_size,
                pop_scale: preset.pop_scale,
                pop_duration: preset.pop_duration,
                primary_color: preset.primary_color,
                highlight_color: preset.highlight_color,
                outline_color: preset.outline_color,
                outline_thickness: preset.outline_thickness,
                shadow_depth: preset.shadow_depth,
                debug_camera_tracking: debugCameraTrackingCheckbox ? debugCameraTrackingCheckbox.checked : false,
                force_refresh: forceRefreshCheckbox ? forceRefreshCheckbox.checked : false,
                bypass_camera_qa: bypassCameraQaCheckbox ? bypassCameraQaCheckbox.checked : false
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
    stopPolling();
    sseRetryCount = 0;
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

    if (status === 'fetching_transcript' || status === 'transcribing_local') {
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

// Connect to EventSource (SSE) for progress streaming with retry + polling fallback
let sseRetryCount = 0;
const SSE_MAX_RETRIES = 5;
let pollingInterval = null;

function listenProgress(jobId) {
    sseRetryCount = 0;
    connectSSE(jobId);
}

function connectSSE(jobId) {
    if (eventSource) {
        try { eventSource.close(); } catch (_) {}
    }
    eventSource = new EventSource(`${BACKEND_URL}/api/progress/${jobId}`);

    eventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            sseRetryCount = 0; // Reset retries on successful message
            
            // Guard against undefined/null progress
            const progress = (data.progress !== undefined && data.progress !== null) ? data.progress : 0;
            const message = data.message || 'Processing...';
            
            // Update UI elements
            statusMessage.textContent = message;
            progressFill.style.width = `${progress}%`;
            progressPercent.textContent = `${progress}%`;
            
            updateStepper(data.status);

            if (data.status === 'completed') {
                eventSource.close();
                stopPolling();
                fetchResults(jobId);
            } else if (data.status === 'failed') {
                eventSource.close();
                stopPolling();
                showError(data.error || 'Pipeline execution failed.');
                setLoadingState(false);
            }
        } catch (e) {
            console.error('Error parsing SSE event:', e);
        }
    };

    eventSource.onerror = (err) => {
        console.error('SSE Error (attempt ' + (sseRetryCount + 1) + '/' + SSE_MAX_RETRIES + '):', err);
        eventSource.close();
        sseRetryCount++;

        if (sseRetryCount < SSE_MAX_RETRIES) {
            // Exponential backoff: 1s, 2s, 4s, 8s, 16s
            const delay = Math.min(1000 * Math.pow(2, sseRetryCount - 1), 16000);
            console.log(`Retrying SSE in ${delay}ms...`);
            setTimeout(() => connectSSE(jobId), delay);
        } else {
            // SSE failed after max retries — fall back to manual polling
            console.warn('SSE failed after max retries, falling back to polling.');
            startPolling(jobId);
        }
    };
}

function startPolling(jobId) {
    stopPolling();
    statusMessage.textContent = 'Reconnecting to server...';

    pollingInterval = setInterval(async () => {
        try {
            const resp = await fetch(`${BACKEND_URL}/api/job/${jobId}`);
            if (!resp.ok) {
                // Job might not exist or server issue
                if (resp.status === 404) {
                    stopPolling();
                    showError('Job not found. It may have expired.');
                    setLoadingState(false);
                }
                return;
            }
            
            const data = await resp.json();
            
            const progress = (data.progress !== undefined && data.progress !== null) ? data.progress : 0;
            const message = data.message || 'Processing...';
            
            statusMessage.textContent = message;
            progressFill.style.width = `${progress}%`;
            progressPercent.textContent = `${progress}%`;
            updateStepper(data.status);
            
            if (data.status === 'completed') {
                stopPolling();
                fetchResults(jobId);
            } else if (data.status === 'failed') {
                stopPolling();
                showError(data.error || 'Pipeline execution failed.');
                setLoadingState(false);
            }
        } catch (e) {
            console.error('Polling error:', e);
        }
    }, 3000);

    // Safety: stop polling after 10 minutes
    setTimeout(() => {
        if (pollingInterval) {
            stopPolling();
            showError('Job timed out. Please refresh and try again.');
            setLoadingState(false);
        }
    }, 600000);
}

function stopPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
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

        let uploadPackageHtml = '';
        let fullPackageText = '';

        // Phase 24: Music card
        let musicCardHtml = '';
        const originalVideoUrl = `${BACKEND_URL}/api/video/${jobId}/${clip.filename}`;
        // Derive the original (no-music) clip filename: replace _with_music.mp4 → clip_{id}.mp4
        const originalClipFilename = clip.filename.includes('_with_music')
            ? `clip_${clip.id}.mp4`
            : clip.filename;
        const originalClipUrl = `${BACKEND_URL}/api/video/${jobId}/${originalClipFilename}`;

        if (clip.upload_package) {
            const pkg = clip.upload_package;
            const titles = pkg.titles || [];
            const desc = pkg.description || '';
            const hashtags = pkg.hashtags || [];
            const thumb = pkg.thumbnail_text || '';
            const post_time = pkg.best_time_to_post || '';
            const audience = pkg.target_audience || '';
            const hook_anal = pkg.hook_analysis || '';
            const keywords = pkg.keywords || [];
            const category = pkg.category || '';
            const language = pkg.language || '';
            const intent = pkg.search_intent || '';
            
            fullPackageText = `=== YOUTUBE UPLOAD PACKAGE ===
Clip: ${clip.title}
Duration: ${Math.round(clip.duration)}s | Virality: ${clip.virality_score}/10

TITLE OPTIONS (ranked):
1. ${titles[0] || ''} ← RECOMMENDED
2. ${titles[1] || ''}
3. ${titles[2] || ''}

DESCRIPTION:
${desc}

HASHTAGS:
${hashtags.join(' ')}

KEYWORDS:
${keywords.join(', ')}

THUMBNAIL TEXT: ${thumb}

BEST TIME TO POST: ${post_time}

TARGET AUDIENCE: ${audience}

HOOK ANALYSIS: ${hook_anal}

CATEGORY: ${category}
LANGUAGE: ${language}
SEARCH INTENT: ${intent}`;

            let altTitlesHtml = '';
            if (titles.length > 1 && titles[1]) {
                altTitlesHtml += `
                    <div class="seo-field">
                        <div class="seo-field-header">
                            <span class="seo-field-label">Alternative Title #1</span>
                            <button class="btn-copy" data-copy-text="${escapeHtml(titles[1])}">Copy</button>
                        </div>
                        <div class="seo-field-value">${escapeHtml(titles[1])}</div>
                    </div>
                `;
            }
            if (titles.length > 2 && titles[2]) {
                altTitlesHtml += `
                    <div class="seo-field">
                        <div class="seo-field-header">
                            <span class="seo-field-label">Alternative Title #2</span>
                            <button class="btn-copy" data-copy-text="${escapeHtml(titles[2])}">Copy</button>
                        </div>
                        <div class="seo-field-value">${escapeHtml(titles[2])}</div>
                    </div>
                `;
            }

            uploadPackageHtml = `
                <div class="upload-package-container">
                    <h4 class="seo-section-title">📦 Claude Upload Package</h4>
                    
                    <div class="seo-field">
                        <div class="seo-field-header">
                            <span class="seo-field-label">Recommended Title (#1)</span>
                            <button class="btn-copy" data-copy-text="${escapeHtml(titles[0] || '')}">Copy</button>
                        </div>
                        <div class="seo-field-value">${escapeHtml(titles[0] || '')}</div>
                    </div>
                    
                    ${altTitlesHtml}
                    
                    <div class="seo-field">
                        <div class="seo-field-header">
                            <span class="seo-field-label">Description</span>
                            <button class="btn-copy" data-copy-text="${escapeHtml(desc)}">Copy</button>
                        </div>
                        <div class="seo-field-value text-area-style">${escapeHtml(desc)}</div>
                    </div>
                    
                    <div class="seo-field">
                        <div class="seo-field-header">
                            <span class="seo-field-label">Hashtags</span>
                            <button class="btn-copy" data-copy-text="${escapeHtml(hashtags.join(' '))}">Copy</button>
                        </div>
                        <div class="seo-field-value">${escapeHtml(hashtags.join(' '))}</div>
                    </div>
                    
                    <div class="seo-field">
                        <div class="seo-field-header">
                            <span class="seo-field-label">Thumbnail Text</span>
                            <button class="btn-copy" data-copy-text="${escapeHtml(thumb)}">Copy</button>
                        </div>
                        <div class="seo-field-value" style="font-weight: bold; text-transform: uppercase;">${escapeHtml(thumb)}</div>
                    </div>
                    
                    <div class="seo-field">
                        <div class="seo-field-header">
                            <span class="seo-field-label">Keywords</span>
                            <button class="btn-copy" data-copy-text="${escapeHtml(keywords.join(', '))}">Copy</button>
                        </div>
                        <div class="seo-field-value">${escapeHtml(keywords.join(', '))}</div>
                    </div>

                    <div style="display: flex; gap: 0.5rem;">
                        <div class="seo-field" style="flex: 1;">
                            <div class="seo-field-header">
                                <span class="seo-field-label">Category</span>
                            </div>
                            <div class="seo-field-value">${escapeHtml(category)}</div>
                        </div>
                        <div class="seo-field" style="flex: 1;">
                            <div class="seo-field-header">
                                <span class="seo-field-label">Language</span>
                            </div>
                            <div class="seo-field-value">${escapeHtml(language)}</div>
                        </div>
                        <div class="seo-field" style="flex: 1;">
                            <div class="seo-field-header">
                                <span class="seo-field-label">Search Intent</span>
                            </div>
                            <div class="seo-field-value">${escapeHtml(intent)}</div>
                        </div>
                    </div>

                    <textarea class="hidden-package-text" style="display:none;">${escapeHtml(fullPackageText)}</textarea>

                    <div style="display: flex; gap: 0.5rem; margin-top: 1rem; margin-bottom: 1rem;">
                        <button class="btn btn-secondary btn-small btn-copy-all" style="flex: 1; justify-content: center; font-size: 0.75rem;">
                            📋 Copy All
                        </button>
                        <button class="btn btn-secondary btn-small btn-download-txt" style="flex: 1; justify-content: center; font-size: 0.75rem;">
                            📄 Download .txt
                        </button>
                    </div>
                </div>
            `;
        }

        // Build music card HTML (Phase 24)
        if (clip.has_music && clip.emotion) {
            const energyLevel = clip.energy_level || 5;
            const energyPct = Math.round((energyLevel / 10) * 100);
            const musicDesc = clip.music_description || '';
            const volPct = clip.volume_pct || 15;
            const musicSrc = clip.music_source || 'none';
            const sourceLabel = musicSrc === 'elevenlabs' ? '⚡ ElevenLabs' :
                                musicSrc === 'freesound'  ? '🌊 Freesound'  : '— None';
            const emotion = clip.emotion || 'motivational';
            // Emoji map for emotion
            const emotionEmoji = {
                triumphant: '🏆', motivational: '🔥', tense: '⚡', melancholic: '🌧️',
                energetic: '⚡', calm: '🌊', inspirational: '✨', dramatic: '🎭',
                urgent: '🚨', uplifting: '🌟'
            }[emotion] || '🎵';
            // Phase 25: cinematic layer badges
            const audioLayers = clip.audio_layers || [];
            const impactCount = clip.impact_moments || 0;

            musicCardHtml = `
                <div class="music-card">
                    <div class="music-card-header">
                        <span class="music-card-title">🎵 Cinematic Audio Engine</span>
                        <span class="emotion-badge">${emotionEmoji} ${escapeHtml(emotion)}</span>
                    </div>

                    <div class="music-meta-grid">
                        <div class="music-meta-item">
                            <div class="music-meta-label">Energy Level</div>
                            <div class="music-energy-bar-container">
                                <div class="music-energy-bar">
                                    <div class="music-energy-fill" style="width: ${energyPct}%;"></div>
                                </div>
                                <span class="music-meta-value" style="min-width:2.2rem;text-align:right;">${energyLevel}/10</span>
                            </div>
                        </div>
                        <div class="music-meta-item">
                            <div class="music-meta-label">Music Style</div>
                            <div class="music-meta-value">${escapeHtml(musicDesc)}</div>
                        </div>
                        <div class="music-meta-item">
                            <div class="music-meta-label">Volume Applied</div>
                            <div class="music-meta-value">${volPct}%</div>
                        </div>
                        <div class="music-meta-item">
                            <div class="music-meta-label">Music Source</div>
                            <span class="music-source-badge ${escapeHtml(musicSrc)}">${sourceLabel}</span>
                        </div>
                    </div>

                    <!-- Phase 25: Cinematic Layer Badges -->
                    <div class="music-layers">
                        ${(audioLayers.includes('ducking')) ? '<span class="layer-badge layer-ducking">🎚️ Dynamic Ducking</span>' : ''}
                        ${(audioLayers.includes('intro_build')) ? '<span class="layer-badge layer-intro">🎬 Intro Build</span>' : ''}
                        ${(audioLayers.includes('impact_sfx')) ? `<span class="layer-badge layer-impact">💥 Impact SFX &times;${impactCount}</span>` : ''}
                    </div>

                    <div class="music-toggle">
                        <button class="toggle-music-btn active"
                            data-clip-id="${escapeHtml(clip.id)}"
                            data-mode="with"
                            data-with-url="${escapeHtml(originalVideoUrl)}"
                            data-original-url="${escapeHtml(originalClipUrl)}">
                            🎵 With Music
                        </button>
                        <button class="toggle-music-btn"
                            data-clip-id="${escapeHtml(clip.id)}"
                            data-mode="without"
                            data-with-url="${escapeHtml(originalVideoUrl)}"
                            data-original-url="${escapeHtml(originalClipUrl)}">
                            🔇 Without Music
                        </button>
                    </div>
                </div>
            `;
        }

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
                
                ${uploadPackageHtml}

                ${musicCardHtml}

                <div style="display: flex; gap: 0.5rem; margin-top: 1rem;">
                    <a href="${videoUrl}" download="${clip.title.replace(/[^a-z0-9]/gi, '_').toLowerCase()}.mp4" class="btn btn-secondary btn-small btn-download" style="flex: 1; text-align: center; justify-content: center;">
                        📥 Download
                    </a>
                    <div class="youtube-upload-container" id="yt-container-${clip.id}" style="flex: 1; display: flex;">
                        ${clip.youtube_video_id ? `
                            <a href="${escapeHtml(clip.youtube_url)}" target="_blank" rel="noopener noreferrer" class="btn btn-secondary btn-small" style="flex: 1; text-align: center; justify-content: center; color: #00bcd4; font-weight: bold;">
                                View on YouTube 🚀
                            </a>
                        ` : (window.youtubeConnected ? `
                            <button type="button" class="btn btn-primary btn-small btn-upload-youtube" data-clip-id="${clip.id}" style="flex: 1; justify-content: center; background: #ff0000; border-color: #ff0000;">
                                Upload to YouTube ▶
                            </button>
                        ` : `
                            <button type="button" class="btn btn-secondary btn-small btn-connect-popup" style="flex: 1; justify-content: center;">
                                Connect YouTube
                            </button>
                        `)}
                    </div>
                </div>
            </div>
        `;
        clipsGrid.appendChild(card);
    });

    resultsSection.classList.remove('hidden');
    resultsSection.scrollIntoView({ behavior: 'smooth' });
}

// Event Delegation for Copy & Action Buttons
clipsGrid.addEventListener('click', async (e) => {
    // 1. Individual Field Copy
    const copyBtn = e.target.closest('.btn-copy');
    if (copyBtn) {
        const textToCopy = copyBtn.getAttribute('data-copy-text');
        if (!textToCopy) return;

        try {
            await navigator.clipboard.writeText(textToCopy);
            const originalText = copyBtn.textContent;
            copyBtn.textContent = 'Copied! ✓';
            copyBtn.classList.add('copied');
            setTimeout(() => {
                copyBtn.textContent = originalText;
                copyBtn.classList.remove('copied');
            }, 1500);
        } catch (err) {
            console.error('Failed to copy text: ', err);
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
            } catch (e2) {
                console.error('Fallback copy failed: ', e2);
            }
            document.body.removeChild(textarea);
        }
        return;
    }

    // 2. Copy All Button
    const copyAllBtn = e.target.closest('.btn-copy-all');
    if (copyAllBtn) {
        const card = copyAllBtn.closest('.clip-card');
        const textarea = card.querySelector('.hidden-package-text');
        if (textarea) {
            try {
                await navigator.clipboard.writeText(textarea.value);
                const originalText = copyAllBtn.innerHTML;
                copyAllBtn.innerHTML = '✅ Copied!';
                setTimeout(() => {
                    copyAllBtn.innerHTML = originalText;
                }, 2000);
            } catch (err) {
                console.error('Failed to copy full package:', err);
            }
        }
        return;
    }

    // 3. Download .txt Button
    const downloadTxtBtn = e.target.closest('.btn-download-txt');
    if (downloadTxtBtn) {
        const card = downloadTxtBtn.closest('.clip-card');
        const titleText = card.querySelector('.clip-title').textContent;
        const textarea = card.querySelector('.hidden-package-text');
        if (textarea) {
            const blob = new Blob([textarea.value], { type: 'text/plain;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${titleText.replace(/[^a-z0-9]/gi, '_').toLowerCase()}_upload_package.txt`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }
        return;
    }

    // 4. With / Without Music Toggle (Phase 24)
    const musicToggleBtn = e.target.closest('.toggle-music-btn');
    if (musicToggleBtn) {
        const mode = musicToggleBtn.getAttribute('data-mode');
        const withUrl = musicToggleBtn.getAttribute('data-with-url');
        const originalUrl = musicToggleBtn.getAttribute('data-original-url');
        const targetUrl = mode === 'with' ? withUrl : originalUrl;

        // Find the video element in the same clip-card
        const card = musicToggleBtn.closest('.clip-card');
        if (card) {
            const videoEl = card.querySelector('video');
            const sourceEl = card.querySelector('video source');
            if (videoEl && sourceEl) {
                sourceEl.src = targetUrl;
                videoEl.load();
            }

            // Update toggle active states
            const allToggles = card.querySelectorAll('.toggle-music-btn');
            allToggles.forEach(btn => {
                btn.classList.toggle('active', btn.getAttribute('data-mode') === mode);
            });
        }
        return;
    }

    // 5. YouTube Connect Popup Handler
    const connectPopupBtn = e.target.closest('.btn-connect-popup');
    if (connectPopupBtn) {
        e.preventDefault();
        const popup = window.open('', 'Connect YouTube', 'width=600,height=600');
        if (popup) {
            popup.document.write('<div style="font-family: sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh;"><h3>Connecting to YouTube...</h3><p>Please wait while we set up your secure session.</p></div>');
            fetch(`${BACKEND_URL}/api/youtube/auth`)
                .then(r => {
                    if (!r.ok) throw new Error(`HTTP error! status: ${r.status}`);
                    return r.json();
                })
                .then(data => {
                    if (data.auth_url) {
                        popup.location.href = data.auth_url;
                    } else {
                        popup.document.body.innerHTML = '<div style="font-family: sans-serif; text-align: center; margin-top: 50px; color: #ff4757;"><h3>Authentication Error</h3><p>Invalid response received from the server.</p></div>';
                    }
                })
                .catch(err => {
                    console.error("Failed to connect to YouTube", err);
                    popup.document.body.innerHTML = '<div style="font-family: sans-serif; text-align: center; margin-top: 50px; color: #ff4757;"><h3>Connection Failed</h3><p>Could not reach the authentication server. Please try again.</p></div>';
                });
        }
        return;
    }

    // 6. YouTube Upload Handler
    const uploadYoutubeBtn = e.target.closest('.btn-upload-youtube');
    if (uploadYoutubeBtn) {
        e.preventDefault();
        const clipId = uploadYoutubeBtn.getAttribute('data-clip-id');
        const container = document.getElementById(`yt-container-${clipId}`);
        if (!container) return;

        // Disable button and start progress
        uploadYoutubeBtn.disabled = true;
        uploadYoutubeBtn.textContent = 'Uploading... 0%';

        let pollInterval = null;
        
        // Start polling the progress endpoint
        pollInterval = setInterval(async () => {
            try {
                const res = await fetch(`${BACKEND_URL}/api/youtube/upload/progress/${clipId}`);
                const data = await res.json();
                if (uploadYoutubeBtn && uploadYoutubeBtn.disabled) {
                    uploadYoutubeBtn.textContent = `Uploading... ${data.progress}%`;
                }
            } catch (err) {
                console.error('Error polling upload progress:', err);
            }
        }, 300);

        try {
            const response = await fetch(`${BACKEND_URL}/api/youtube/upload/${clipId}`, {
                method: 'POST'
            });
            const data = await response.json();
            clearInterval(pollInterval);
            
            if (!response.ok) throw new Error(data.detail || 'Upload failed.');

            // Success
            container.innerHTML = `
                <a href="${escapeHtml(data.youtube_url)}" target="_blank" rel="noopener noreferrer" class="btn btn-secondary btn-small" style="flex: 1; text-align: center; justify-content: center; color: #00bcd4; font-weight: bold;">
                    View on YouTube 🚀
                </a>
            `;
        } catch (err) {
            clearInterval(pollInterval);
            console.error('Upload error:', err);
            container.innerHTML = `
                <div style="display: flex; flex-direction: column; gap: 0.25rem; width: 100%;">
                    <span style="color: #ff4757; font-size: 0.75rem; text-align: center;">Error: ${escapeHtml(err.message)}</span>
                    <button type="button" class="btn btn-primary btn-small btn-upload-youtube" data-clip-id="${clipId}" style="width: 100%; justify-content: center; background: #ff0000; border-color: #ff0000;">
                        Retry Upload ▶
                    </button>
                </div>
            `;
        }
        return;
    }
});

// Safe string escape helper
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ==========================================
// PHASE 10: TAB SWITCHING & EXPERIMENTATION
// ==========================================

const tabButtons = document.querySelectorAll('.tab-btn');
const tabContents = document.querySelectorAll('.tab-content');

tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
        const targetTab = btn.getAttribute('data-tab');
        
        // Update active tab buttons
        tabButtons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        
        // Toggle tab content displays
        tabContents.forEach(content => {
            if (content.id === targetTab) {
                content.classList.remove('hidden');
            } else {
                content.classList.add('hidden');
            }
        });
        
        // Trigger data fetch if switched to specific tab
        if (targetTab === 'experiment-tab') {
            fetchExperimentDashboard();
        } else if (targetTab === 'youtube-tab') {
            fetchYoutubeDashboard();
        }
    });
});

// Fetch A/B experiment data and update UI
async function fetchExperimentDashboard() {
    try {
        const response = await fetch(`${BACKEND_URL}/api/analytics/experiments`);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || 'Failed to fetch experiment statistics.');
        }
        
        const exp = data.experiments;
        
        // 1. Update Sample Size
        document.getElementById('val-n-a').textContent = exp.sample_size_A;
        document.getElementById('val-n-b').textContent = exp.sample_size_B;
        
        // 2. Update Composite Averages
        const meanA = exp.mean_composite_A || 0.00;
        const meanB = exp.mean_composite_B || 0.00;
        document.getElementById('val-mean-a').textContent = meanA.toFixed(2);
        document.getElementById('val-mean-b').textContent = meanB.toFixed(2);
        
        // 3. Update comparison bar widths (Scale is 0-10)
        document.getElementById('bar-mean-a').style.width = `${(meanA / 10) * 100}%`;
        document.getElementById('bar-mean-b').style.width = `${(meanB / 10) * 100}%`;
        
        // 4. Update t-test metrics
        document.getElementById('stat-t').textContent = exp.t_statistic !== undefined ? exp.t_statistic.toFixed(4) : '0.0000';
        document.getElementById('stat-p').textContent = exp.p_value !== undefined ? exp.p_value.toFixed(4) : '1.0000';
        document.getElementById('stat-conf').textContent = `${exp.confidence_level !== undefined ? exp.confidence_level.toFixed(2) : '0.00'}%`;
        
        const winnerBadge = document.getElementById('stat-winner');
        winnerBadge.textContent = exp.winner || 'None';
        if (exp.winner) {
            winnerBadge.className = 'stat-val badge badge-winner';
        } else {
            winnerBadge.className = 'stat-val badge badge-tag';
        }
        
        // 5. Update Status Banner Style
        const statusBanner = document.getElementById('experiment-status-banner');
        const statusIcon = document.getElementById('experiment-status-icon');
        const statusText = document.getElementById('experiment-status-text');
        
        statusText.textContent = exp.status;
        
        if (exp.winner) {
            statusBanner.className = 'status-banner winner-declared';
            statusIcon.textContent = '🟢';
        } else {
            statusBanner.className = 'status-banner running';
            statusIcon.textContent = '🟡';
        }
        
    } catch (err) {
        console.error('Error fetching experiment metrics: ', err);
    }
}

// Experiment seeder button action
const seedExpBtn = document.getElementById('seed-exp-btn');
const seedSuccessMsg = document.getElementById('seed-success-msg');

if (seedExpBtn) {
    seedExpBtn.addEventListener('click', async () => {
        seedExpBtn.disabled = true;
        const originalText = seedExpBtn.textContent;
        seedExpBtn.textContent = 'Seeding Data...';
        
        try {
            const response = await fetch(`${BACKEND_URL}/api/analytics/seed`, {
                method: 'POST'
            });
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || 'Seeding failed.');
            }
            
            // Show Success Notification
            seedSuccessMsg.classList.remove('hidden');
            
            // Reload dashboard after short delay
            setTimeout(() => {
                seedSuccessMsg.classList.add('hidden');
                seedExpBtn.disabled = false;
                seedExpBtn.textContent = originalText;
                fetchExperimentDashboard();
            }, 1500);
            
        } catch (err) {
            console.error('Failed to seed experiments:', err);
            seedExpBtn.disabled = false;
            seedExpBtn.textContent = originalText;
            alert(`Error seeding database: ${err.message}`);
        }
    });
}

// ==========================================
// PHASE 11A: YOUTUBE LEARNING LOOP
// ==========================================

async function redirectToYoutubeAuth() {
    try {
        const response = await fetch(`${BACKEND_URL}/api/youtube/auth`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        if (data.auth_url) {
            window.location.href = data.auth_url;
        } else {
            alert('Invalid authentication response from server.');
        }
    } catch (err) {
        console.error('Error fetching YouTube auth URL:', err);
        alert('Failed to connect to YouTube. Please check your internet connection.');
    }
}

const btnConnectYoutube = document.getElementById('btn-connect-youtube');
const btnSyncYoutube = document.getElementById('btn-sync-youtube');
const btnExportDataset = document.getElementById('btn-export-dataset');
const syncSuccessMsg = document.getElementById('sync-success-msg');

if (btnConnectYoutube) {
    btnConnectYoutube.addEventListener('click', redirectToYoutubeAuth);
}

if (btnSyncYoutube) {
    btnSyncYoutube.addEventListener('click', async () => {
        btnSyncYoutube.disabled = true;
        const spinner = btnSyncYoutube.querySelector('.spinner');
        const btnText = btnSyncYoutube.querySelector('.btn-text');
        if (spinner) spinner.classList.remove('hidden');
        if (btnText) btnText.textContent = 'Syncing...';
        
        try {
            const response = await fetch(`${BACKEND_URL}/api/youtube/sync`, {
                method: 'POST'
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Sync failed.');
            
            // Show Success Msg
            if (syncSuccessMsg) {
                syncSuccessMsg.classList.remove('hidden');
                setTimeout(() => syncSuccessMsg.classList.add('hidden'), 2000);
            }
            
            await fetchYoutubeDashboard();
        } catch (err) {
            console.error('Sync error:', err);
            alert(`Sync failed: ${err.message}`);
        } finally {
            if (spinner) spinner.classList.add('hidden');
            if (btnText) btnText.textContent = 'Sync YouTube Analytics 🔄';
            btnSyncYoutube.disabled = false;
        }
    });
}

if (btnExportDataset) {
    btnExportDataset.addEventListener('click', () => {
        window.open(`${BACKEND_URL}/api/youtube/export`, '_blank');
    });
}

// Draw dynamic SVG views growth chart over snapshots
function drawSVGChart(snapshots) {
    if (!snapshots || snapshots.length < 2) {
        return `<div class="text-center text-muted" style="padding-top: 2rem; font-size: 0.85rem;">Need at least 2 sync snapshots to show growth trend</div>`;
    }
    
    // Sort snapshots chronologically
    const sorted = [...snapshots].sort((a, b) => a.snapshot_time - b.snapshot_time);
    const views = sorted.map(s => s.views);
    const maxViews = Math.max(...views, 1);
    const minViews = Math.min(...views);
    const range = maxViews - minViews || 1;
    
    const width = 400;
    const height = 80;
    const padding = 10;
    
    const points = sorted.map((s, idx) => {
        const x = padding + (idx / (sorted.length - 1)) * (width - 2 * padding);
        const y = height - padding - ((s.views - minViews) / range) * (height - 2 * padding);
        return { x, y, views: s.views, date: new Date(s.snapshot_time * 1000).toLocaleTimeString() };
    });
    
    const pathData = points.map((p, idx) => `${idx === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
    const areaData = `${pathData} L ${points[points.length - 1].x.toFixed(1)} ${height} L ${points[0].x.toFixed(1)} ${height} Z`;
    
    // Unique ID for gradients to prevent overlap
    const gradId = `grad-${Math.random().toString(36).substr(2, 9)}`;
    const circles = points.map(p => `<circle class="point" cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="4"><title>Views: ${p.views} (${p.date})</title></circle>`).join('');
    
    return `
        <svg class="trend-chart" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
            <defs>
                <linearGradient id="${gradId}" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="var(--accent-primary)" stop-opacity="0.25"></stop>
                    <stop offset="100%" stop-color="var(--accent-primary)" stop-opacity="0.00"></stop>
                </linearGradient>
            </defs>
            <path class="area" d="${areaData}" fill="url(#${gradId})"></path>
            <path class="line" d="${pathData}"></path>
            ${circles}
        </svg>
    `;
}

async function fetchYoutubeDashboard() {
    try {
        const response = await fetch(`${BACKEND_URL}/api/youtube/dashboard`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'Failed to fetch dashboard data.');
        
        // 1. Connection Status Panel
        const statusContainer = document.getElementById('youtube-connection-status');
        if (data.connected) {
            statusContainer.innerHTML = `<span style="font-weight: 700; color: #059669; background: rgba(16, 185, 129, 0.1); padding: 0.5rem 1rem; border-radius: 8px; border: 1px solid rgba(16, 185, 129, 0.2);">Connected: ${escapeHtml(data.channel_name)} 🟢</span>`;
            if (btnSyncYoutube) btnSyncYoutube.disabled = false;
        } else {
            statusContainer.innerHTML = `<button id="btn-connect-youtube" class="btn btn-primary btn-small">Connect YouTube Channel 🔗</button>`;
            const newBtn = document.getElementById('btn-connect-youtube');
            if (newBtn) {
                newBtn.addEventListener('click', redirectToYoutubeAuth);
            }
            if (btnSyncYoutube) btnSyncYoutube.disabled = true;
        }
        
        // 2.5 Update Delay Note and Last Sync Time
        const delayNote = document.getElementById('youtube-delay-note');
        if (delayNote) {
            if (data.connected) {
                delayNote.style.display = 'block';
                const syncSpan = document.getElementById('yt-last-sync-time');
                if (syncSpan) {
                    if (data.last_sync_time && data.last_sync_time > 0) {
                        const dateObj = new Date(data.last_sync_time * 1000);
                        syncSpan.textContent = dateObj.toLocaleString();
                    } else {
                        syncSpan.textContent = 'Not synced yet';
                    }
                }
            } else {
                delayNote.style.display = 'none';
            }
        }
        
        // 2. Data visibility
        const statsGrid = document.getElementById('youtube-stats-grid');
        const dashboardMain = document.getElementById('youtube-dashboard-main');
        const noDataCard = document.getElementById('youtube-no-data');
        
        const clips = data.published_clips || [];
        if (clips.length === 0) {
            if (statsGrid) statsGrid.style.display = 'none';
            if (dashboardMain) dashboardMain.style.display = 'none';
            if (noDataCard) noDataCard.classList.remove('hidden');
            return;
        }
        
        if (noDataCard) noDataCard.classList.add('hidden');
        if (statsGrid) statsGrid.style.display = 'grid';
        if (dashboardMain) dashboardMain.style.display = 'grid';
        
        // Compute Summary Stats
        const totalViews = clips.reduce((sum, c) => sum + (c.views || 0), 0);
        const avgRetention = clips.reduce((sum, c) => sum + (c.retention || 0.0), 0.0) / clips.length;
        
        document.getElementById('yt-total-views').textContent = totalViews.toLocaleString();
        document.getElementById('yt-published-count').textContent = clips.length;
        document.getElementById('yt-avg-retention').textContent = `${avgRetention.toFixed(1)}%`;
        
        // 3. Render Clips List
        const listContainer = document.getElementById('published-clips-list');
        listContainer.innerHTML = '';
        
        clips.forEach(clip => {
            const card = document.createElement('div');
            card.className = 'published-clip-card';
            
            const dateStr = clip.upload_date ? `Published ${clip.upload_date}` : 'Publish date pending';
            const chartHtml = drawSVGChart(clip.snapshots);
            
            card.innerHTML = `
                <div class="published-clip-card-header">
                    <div>
                        <h4 class="published-clip-card-title">${escapeHtml(clip.title)}</h4>
                        <span class="published-clip-card-date">📅 ${dateStr}</span>
                    </div>
                    <span class="badge badge-tag" style="background: rgba(249, 115, 22, 0.1); color: var(--accent-primary);">AI Score: ${clip.virality_score.toFixed(1)}</span>
                </div>
                
                <div class="published-clip-card-stats">
                    <div class="published-clip-card-stat">
                        <span class="published-clip-card-stat-label">Views</span>
                        <span class="published-clip-card-stat-val">${(clip.views || 0).toLocaleString()}</span>
                    </div>
                    <div class="published-clip-card-stat">
                        <span class="published-clip-card-stat-label">Likes</span>
                        <span class="published-clip-card-stat-val">${(clip.likes || 0).toLocaleString()}</span>
                    </div>
                    <div class="published-clip-card-stat">
                        <span class="published-clip-card-stat-label">Comments</span>
                        <span class="published-clip-card-stat-val">${(clip.comments || 0).toLocaleString()}</span>
                    </div>
                    <div class="published-clip-card-stat">
                        <span class="published-clip-card-stat-label">Watch Time</span>
                        <span class="published-clip-card-stat-val">${(clip.watch_time || 0.0).toFixed(1)}h</span>
                    </div>
                    <div class="published-clip-card-stat">
                        <span class="published-clip-card-stat-label">Retention</span>
                        <span class="published-clip-card-stat-val">${(clip.retention || 0.0).toFixed(1)}%</span>
                    </div>
                </div>
                
                <div style="margin-top: 0.5rem;">
                    <span class="published-clip-card-stat-label" style="display:block; margin-bottom: 0.25rem;">Views growth timeline</span>
                    <div class="trend-chart-container">
                        ${chartHtml}
                    </div>
                </div>
            `;
            listContainer.appendChild(card);
        });
        
        // 4. Render Reports
        renderLearningReports(data.reports);

        // 5. Render Transcript Metrics
        await fetchTranscriptMetrics();
        
    } catch (err) {
        console.error('Error fetching YouTube Dashboard:', err);
    }
}

async function fetchTranscriptMetrics() {
    try {
        const response = await fetch(`${BACKEND_URL}/api/analytics/transcripts`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'Failed to fetch transcript metrics.');
        
        const container = document.getElementById('transcript-metrics-container');
        if (!container) return;
        
        const m = data.metrics;
        
        const sourceLabels = {
            "youtube_transcript_api": "YouTube API 🌐",
            "yt_dlp_manual": "yt-dlp Manual 📄",
            "yt_dlp_auto": "yt-dlp Auto 🤖",
            "faster_whisper": "Local Whisper 🎙️",
            "cache": "Local Cache 💾",
            "unknown": "Other / Unknown ❓"
        };
        
        let breakdownHtml = '';
        const breakdown = m.source_breakdown || {};
        const sources = ["youtube_transcript_api", "yt_dlp_manual", "yt_dlp_auto", "faster_whisper", "cache", "unknown"];
        
        sources.forEach(src => {
            const count = breakdown[src] || 0;
            if (count === 0 && src === "unknown") return;
            const pct = m.total_runs > 0 ? (count / m.total_runs * 100).toFixed(0) : 0;
            breakdownHtml += `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                    <span style="font-size: 0.85rem; color: #d1d5db;">${sourceLabels[src] || src}</span>
                    <span style="font-weight: 600; font-size: 0.85rem; color: #f3f4f6;">${count} (${pct}%)</span>
                </div>
                <div style="background: rgba(255, 255, 255, 0.05); border-radius: 4px; height: 6px; margin-bottom: 0.65rem; overflow: hidden;">
                    <div style="background: var(--accent-primary); width: ${pct}%; height: 100%; border-radius: 4px;"></div>
                </div>
            `;
        });
        
        container.innerHTML = `
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.25rem;">
                <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.05); padding: 0.65rem; border-radius: 8px; text-align: center;">
                    <span style="display: block; font-size: 0.75rem; color: #9ca3af; margin-bottom: 0.15rem;">Fallback Rate</span>
                    <span style="font-size: 1.15rem; font-weight: 700; color: #f97316;">${m.fallback_usage_percent.toFixed(1)}%</span>
                </div>
                <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.05); padding: 0.65rem; border-radius: 8px; text-align: center;">
                    <span style="display: block; font-size: 0.75rem; color: #9ca3af; margin-bottom: 0.15rem;">Avg Time</span>
                    <span style="font-size: 1.15rem; font-weight: 700; color: #3b82f6;">${m.average_transcription_time.toFixed(1)}s</span>
                </div>
            </div>
            
            <h4 style="font-size: 0.85rem; font-weight: 600; margin-bottom: 0.5rem; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.05em;">Source Distribution</h4>
            ${breakdownHtml}
            <div style="font-size: 0.75rem; color: #6b7280; text-align: right; margin-top: 0.5rem; border-top: 1px solid rgba(255, 255, 255, 0.05); padding-top: 0.5rem;">
                Total processed runs: ${m.total_runs}
            </div>
        `;
        
    } catch (err) {
        console.error('Error fetching transcript metrics:', err);
    }
}

function renderLearningReports(reports) {
    const weightsContainer = document.getElementById('weights-report-container');
    const disagreementContainer = document.getElementById('disagreement-report-container');
    
    // A. Weights and Correlation Report
    const imp = reports.model_improvement;
    if (imp.status === 'Insufficient Data') {
        weightsContainer.innerHTML = `<p class="text-muted text-center" style="padding: 2rem 0;">${imp.message}</p>`;
    } else {
        const matrix = imp.correlations;
        const currentW = imp.current_weights;
        const recomW = imp.recommended_weights;
        
        let tableRowsHtml = '';
        for (const factor in currentW) {
            const corrViews = matrix[factor]["views"];
            const corrRet = matrix[factor]["retention"];
            
            const currVal = currentW[factor];
            const recomVal = recomW[factor];
            const diff = recomVal - currVal;
            const diffClass = diff >= 0 ? 'weight-change-positive' : 'weight-change-negative';
            const diffSign = diff >= 0 ? '+' : '';
            
            tableRowsHtml += `
                <tr>
                    <td><strong>${escapeHtml(factor.replace(/_/g, ' '))}</strong></td>
                    <td class="text-center">${corrViews.toFixed(3)}</td>
                    <td class="text-center">${corrRet.toFixed(3)}</td>
                    <td class="text-center" style="font-weight:700;">${(currVal * 100).toFixed(0)}%</td>
                    <td class="text-center" style="font-weight:700; color:var(--accent-primary);">${(recomVal * 100).toFixed(0)}%</td>
                    <td class="text-center ${diffClass}">${diffSign}${(diff * 100).toFixed(1)}%</td>
                </tr>
            `;
        }
        
        weightsContainer.innerHTML = `
            <table class="report-table">
                <thead>
                    <tr>
                        <th>Factor</th>
                        <th class="text-center">Corr Views</th>
                        <th class="text-center">Corr Retention</th>
                        <th class="text-center">Current W</th>
                        <th class="text-center">Recom W</th>
                        <th class="text-center">Delta</th>
                    </tr>
                </thead>
                <tbody>
                    ${tableRowsHtml}
                </tbody>
            </table>
            
            <div style="margin-top: 1.25rem; background:rgba(249, 115, 22, 0.05); padding: 1rem; border-radius: 10px; border:1px solid rgba(249,115,22,0.1);">
                <p style="margin:0; font-size:0.9rem; line-height:1.45;">
                    💡 <strong>Insight</strong>: Pearson correlation $r$ indicates predictive performance. Recommended weights align scoring closer to factors displaying highest correlation with views and retention.
                </p>
            </div>
        `;
    }
    
    // B. Creator Disagreement Trends
    const disag = reports.creator_disagreement;
    const fp = disag.false_positives || [];
    const fn = disag.false_negatives || [];
    
    if (fp.length === 0 && fn.length === 0) {
        disagreementContainer.innerHTML = `<p class="text-muted text-center" style="padding: 2rem 0;">No significant scoring disagreements recorded.</p>`;
        return;
    }
    
    let disagreementHtml = '<div class="disagreement-list">';
    
    // Render False Positives
    fp.forEach(c => {
        disagreementHtml += `
            <div class="disagreement-item">
                <div class="disagreement-item-header">
                    <span class="disagreement-item-title">❌ Heuristically Overvalued: Clip ${escapeHtml(c.clip_id)}</span>
                    <span class="badge" style="background:#fee2e2; color:#ef4444; font-size:0.75rem; font-weight:800;">Rejected (Score ${c.virality_score.toFixed(1)})</span>
                </div>
                <div class="disagreement-cause">
                    <strong>Feedback</strong>: "${escapeHtml(c.feedback || 'None provided')}"<br>
                    <strong>Probable Cause</strong>: ${escapeHtml(c.probable_cause)}
                </div>
            </div>
        `;
    });
    
    // Render False Negatives
    fn.forEach(c => {
        disagreementHtml += `
            <div class="disagreement-item false-negative">
                <div class="disagreement-item-header">
                    <span class="disagreement-item-title">✅ Heuristically Undervalued: Clip ${escapeHtml(c.clip_id)}</span>
                    <span class="badge" style="background:#d1fae5; color:#10b981; font-size:0.75rem; font-weight:800;">Selected (Score ${c.virality_score.toFixed(1)})</span>
                </div>
                <div class="disagreement-cause">
                    <strong>Feedback</strong>: "${escapeHtml(c.feedback || 'None provided')}"<br>
                    <strong>Probable Cause</strong>: ${escapeHtml(c.probable_cause)}
                </div>
            </div>
        `;
    });
    
    disagreementHtml += '</div>';
    disagreementContainer.innerHTML = disagreementHtml;
}

// YouTube Upload Modal Event Listeners
const uploadModal = document.getElementById('youtube-upload-modal');
const closeUploadModalBtn = document.getElementById('btn-close-upload-modal');
const uploadForm = document.getElementById('youtube-upload-form');
const uploadClipIdInput = document.getElementById('upload-clip-id');
const uploadTitleInput = document.getElementById('upload-title');
const uploadDescriptionInput = document.getElementById('upload-description');
const uploadTagsInput = document.getElementById('upload-tags');
const submitUploadBtn = document.getElementById('btn-submit-upload');

// Grid Click Event Delegation to open Modal
clipsGrid.addEventListener('click', (e) => {
    const publishTrigger = e.target.closest('.btn-publish-trigger');
    if (!publishTrigger) return;
    
    const clipId = publishTrigger.getAttribute('data-clip-id');
    const title = publishTrigger.getAttribute('data-title');
    const desc = publishTrigger.getAttribute('data-desc');
    const tags = publishTrigger.getAttribute('data-tags');
    
    if (uploadClipIdInput) uploadClipIdInput.value = clipId;
    if (uploadTitleInput) uploadTitleInput.value = title;
    if (uploadDescriptionInput) uploadDescriptionInput.value = desc;
    if (uploadTagsInput) uploadTagsInput.value = tags;
    
    if (uploadModal) {
        uploadModal.classList.remove('hidden');
    }
});

// Close Modal
if (closeUploadModalBtn) {
    closeUploadModalBtn.addEventListener('click', () => {
        if (uploadModal) uploadModal.classList.add('hidden');
    });
}

// Close Modal by clicking outside content
if (uploadModal) {
    uploadModal.addEventListener('click', (e) => {
        if (e.target === uploadModal) {
            uploadModal.classList.add('hidden');
        }
    });
}

// Handle Upload Submission
if (uploadForm) {
    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const clipId = uploadClipIdInput.value;
        const title = uploadTitleInput.value.trim();
        const desc = uploadDescriptionInput.value.trim();
        const tagsRaw = uploadTagsInput.value;
        const tags = tagsRaw ? tagsRaw.split(',').map(t => t.trim()).filter(t => t.length > 0) : [];
        
        submitUploadBtn.disabled = true;
        const spinner = submitUploadBtn.querySelector('.spinner');
        const btnText = submitUploadBtn.querySelector('.btn-text');
        if (spinner) spinner.classList.remove('hidden');
        if (btnText) btnText.textContent = 'Publishing...';
        
        try {
            const response = await fetch(`${BACKEND_URL}/api/youtube/publish/${clipId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    title: title,
                    description: desc,
                    tags: tags
                })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Publish failed.');
            
            alert('Clip published successfully to YouTube!');
            if (uploadModal) uploadModal.classList.add('hidden');
            
            // Switch to YouTube tab to view performance
            const youtubeTabBtn = document.querySelector('.tab-btn[data-tab="youtube-tab"]');
            if (youtubeTabBtn) {
                youtubeTabBtn.click();
            }
        } catch (err) {
            console.error('Publish error:', err);
            alert(`Failed to publish: ${err.message}`);
        } finally {
            if (spinner) spinner.classList.add('hidden');
            if (btnText) btnText.textContent = 'Publish to YouTube Shorts 🚀';
            submitUploadBtn.disabled = false;
        }
    });
}

// Check URL Params on load to route active tab
window.addEventListener('DOMContentLoaded', () => {
    // Check global YouTube connection status
    checkYoutubeStatus();
    setInterval(checkYoutubeStatus, 2000);

    const urlParams = new URLSearchParams(window.location.search);
    const tabParam = urlParams.get('tab');
    const errorParam = urlParams.get('error');
    
    if (errorParam) {
        alert(`Authentication Error: ${errorParam}`);
        // Clean URL parameter
        window.history.replaceState({}, document.title, window.location.pathname);
    }
    
    if (tabParam) {
        const targetBtn = document.querySelector(`.tab-btn[data-tab="${tabParam}"]`);
        if (targetBtn) {
            // Trigger tab switch click
            targetBtn.click();
            // Clean URL parameter so reload doesn't force tab switch
            window.history.replaceState({}, document.title, window.location.pathname);
        }
    }
});

