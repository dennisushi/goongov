// Global variables
let currentTraceData = null;
let culpritData = null;
let originalUserQuery = null;  // Store the original query that generated the trace

// Backend API URL - can be overridden by setting window.API_BASE_URL
// If running frontend separately, set this to 'http://localhost:5000'
const API_BASE_URL = window.API_BASE_URL || '';

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Check if trace data is provided via global variable
    if (window.initialTraceData) {
        console.log('Loading initial trace data...');
        loadTraceData(window.initialTraceData);
    } else {
        console.log('Trace Analysis UI loaded. No initial trace data.');
        // Show message to user
        const container = document.getElementById('graph-container');
        container.innerHTML = '<div class="empty-state"><p>No trace data loaded. Enter a query above to generate a trace, or use the API to load a trace.</p></div>';
    }
});

/**
 * Generate execution trace from user query
 */
async function generateTrace() {
    const queryInput = document.getElementById('user-query-input');
    const modelSelect = document.getElementById('model-select');
    const generateBtn = document.getElementById('generate-trace-btn');
    const loadingDiv = document.getElementById('trace-generation-loading');
    const graphContainer = document.getElementById('graph-container');
    const graphLoading = document.getElementById('graph-loading');
    
    const userQuery = queryInput.value.trim();
    const modelName = modelSelect.value;
    
    if (!userQuery) {
        alert('Please enter a query for the agent');
        return;
    }
    
    // Show loading state
    generateBtn.disabled = true;
    loadingDiv.style.display = 'block';
    graphLoading.style.display = 'block';
    graphContainer.innerHTML = '';
    
    // Clear previous analysis
    document.getElementById('summary').innerHTML = '';
    document.getElementById('culprits-list').innerHTML = '<div class="empty-state"><p>No analysis performed yet. Enter a query and click "Analyze Trace" to identify culprits.</p></div>';
    document.getElementById('query-input').value = '';
    culpritData = null;
    
    try {
        // Send trace generation request
        const response = await fetch(`${API_BASE_URL}/api/generate-trace`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                user_query: userQuery,
                model_name: modelName
            })
        });
        
        if (!response.ok) {
            let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
            try {
                const errorData = await response.json();
                errorMessage = errorData.error || errorMessage;
            } catch (e) {
                // If response is not JSON, use status text
                errorMessage = `HTTP ${response.status}: ${response.statusText}`;
            }
            throw new Error(errorMessage);
        }
        
        const data = await response.json();
        
        // Check for error in response
        if (data.error) {
            throw new Error(data.error);
        }
        
        // Load the generated trace
        if (data.trace) {
            console.log('Trace generated successfully:', data.trace_id);
            loadTraceData(data.trace);
            
            // Store original user query
            originalUserQuery = data.original_user_query || userQuery;
            if (data.trace.metadata && data.trace.metadata.original_user_query) {
                originalUserQuery = data.trace.metadata.original_user_query;
            }
            
            // Show success message
            const successMsg = document.createElement('div');
            successMsg.className = 'success-message';
            successMsg.textContent = `✓ Trace generated successfully! (ID: ${data.trace_id.substring(0, 8)}...)`;
            successMsg.style.cssText = 'color: #10b981; padding: 8px; margin-top: 8px; font-size: 14px;';
            loadingDiv.parentElement.appendChild(successMsg);
            setTimeout(() => successMsg.remove(), 5000);
        } else {
            throw new Error('No trace data in response');
        }
        
    } catch (error) {
        console.error('Error generating trace:', error);
        console.error('Error details:', error.stack);
        let errorMsg = 'Error generating trace: ' + error.message;
        if (error.message.includes('Failed to fetch')) {
            errorMsg += '\n\nPossible causes:\n- Server is not running\n- CORS issue\n- Network error\n\nCheck the browser console and server logs for more details.';
        } else if (error.message.includes('404') || error.message.includes('NOT FOUND')) {
            errorMsg += '\n\nThe /api/generate-trace endpoint was not found. Make sure the Flask server is running and the route is registered.';
        }
        alert(errorMsg);
        graphContainer.innerHTML = `<div class="empty-state"><p style="color: #ef4444;">Error: ${error.message}</p><p style="color: #94A3B8; font-size: 0.9em; margin-top: 8px;">Check the browser console for more details.</p></div>`;
    } finally {
        generateBtn.disabled = false;
        loadingDiv.style.display = 'none';
        graphLoading.style.display = 'none';
    }
}

/**
 * Analyze trace with user query
 */
async function analyzeTrace() {
    // Try both possible input IDs
    const queryInput = document.getElementById('query-input') || document.getElementById('critic-query-input');
    const query = queryInput ? queryInput.value.trim() : '';
    
    if (!query) {
        alert('Please enter a query');
        return;
    }
    
    if (!currentTraceData) {
        alert('No trace data available. Please load a trace first.');
        return;
    }
    
    const analyzeBtn = document.getElementById('analyze-btn');
    const loadingDiv = document.getElementById('query-loading');
    const summaryDiv = document.getElementById('summary');
    const culpritsDiv = document.getElementById('culprits-list');
    
    // Show loading state
    analyzeBtn.disabled = true;
    loadingDiv.style.display = 'block';
    summaryDiv.innerHTML = '';
    culpritsDiv.innerHTML = '';
    
    // Get toggle states
    const useFindIssueOrigin = document.getElementById('toggle-find-issue-origin').checked;
    const useFailureAnalysis = document.getElementById('toggle-failure-analysis').checked;
    
    if (!useFindIssueOrigin && !useFailureAnalysis) {
        alert('Please enable at least one analysis method.');
        analyzeBtn.disabled = false;
        loadingDiv.style.display = 'none';
        return;
    }
    
    // Initialize progress bar (declare outside try-catch for scope)
    let progressFill = null;
    let progressText = null;
    let progressStages = null;
    let progressInterval = null;
    let currentProgress = 0;
    
    try {
        progressFill = document.getElementById('progress-fill');
        progressText = document.getElementById('progress-text');
        progressStages = document.getElementById('progress-stages');
    } catch (e) {
        console.warn('Progress bar elements not found:', e);
    }
    
    // Define analysis stages based on which methods are enabled
    const stages = [];
    if (useFindIssueOrigin) {
        stages.push({ name: 'Identifying relevant components...', progress: 20 });
        stages.push({ name: 'Analyzing messages for culprits...', progress: 50 });
    }
    if (useFailureAnalysis) {
        stages.push({ name: 'Finding responsible component...', progress: useFindIssueOrigin ? 70 : 40 });
        stages.push({ name: 'Detecting failures...', progress: useFindIssueOrigin ? 90 : 80 });
    }
    stages.push({ name: 'Finalizing results...', progress: 95 });
    
    // Display stages
    if (progressStages) {
        progressStages.innerHTML = stages.map((stage, idx) => 
            `<div class="progress-stage" data-stage="${idx}">${stage.name}</div>`
        ).join('');
    }
    
    // Update progress bar
    function updateProgress(targetProgress, stageText) {
        const duration = 500; // 500ms to animate to target
        const startProgress = currentProgress;
        const startTime = Date.now();
        
        function animate() {
            const elapsed = Date.now() - startTime;
            const progress = Math.min(elapsed / duration, 1);
            currentProgress = startProgress + (targetProgress - startProgress) * progress;
            
            if (progressFill) {
                progressFill.style.width = `${currentProgress}%`;
            }
            if (progressText && stageText) {
                progressText.textContent = stageText;
            }
            
            if (progress < 1) {
                requestAnimationFrame(animate);
            }
        }
        animate();
    }
    
    // Mark stage as complete
    function markStageComplete(stageIndex) {
        if (progressStages) {
            const stageEl = progressStages.querySelector(`[data-stage="${stageIndex}"]`);
            if (stageEl) {
                stageEl.classList.add('completed');
            }
        }
    }
    
    // Track if response has been received and interval for checking
    let responseReceived = false;
    let checkInterval = null;
    
    // Start progress simulation
    let stageIndex = 0;
    function simulateProgress() {
        if (stageIndex < stages.length) {
            const stage = stages[stageIndex];
            // Don't go to 100% until response is received
            const targetProgress = responseReceived ? stage.progress : Math.min(stage.progress, 90);
            updateProgress(targetProgress, stage.name);
            markStageComplete(stageIndex);
            stageIndex++;
            
            if (stageIndex < stages.length) {
                // Wait a bit before next stage (simulate processing time)
                setTimeout(simulateProgress, 800 + Math.random() * 500);
            } else {
                // Final stage - but wait for actual response
                if (responseReceived) {
                    updateProgress(100, 'Analysis complete!');
                } else {
                    updateProgress(90, 'Waiting for results...');
                    // Keep checking if response arrived
                    checkInterval = setInterval(() => {
                        if (responseReceived) {
                            if (checkInterval) {
                                clearInterval(checkInterval);
                                checkInterval = null;
                            }
                            updateProgress(100, 'Analysis complete!');
                        }
                    }, 100);
                }
            }
        }
    }
    
    // Start progress simulation
    if (progressFill && progressText && progressStages) {
        updateProgress(5, 'Starting analysis...');
        setTimeout(simulateProgress, 300);
    }
    
    // Get original user query from trace metadata or stored value
    let originalQuery = originalUserQuery;
    if (!originalQuery && currentTraceData) {
        if (currentTraceData.metadata && currentTraceData.metadata.original_user_query) {
            originalQuery = currentTraceData.metadata.original_user_query;
        } else {
            // Try to extract from first HumanMessage
            const messages = currentTraceData.messages || [];
            for (const msg of messages) {
                if (msg.type === 'human' || (msg.lc_kwargs && msg.lc_kwargs.type === 'human')) {
                    originalQuery = msg.content || msg.lc_kwargs?.content || '';
                    // Clean up if it contains system prompt
                    if (originalQuery && originalQuery.length > 500) {
                        const lines = originalQuery.split('\n');
                        for (const line of lines.reverse()) {
                            if (line.trim() && !line.trim().startsWith('You are')) {
                                originalQuery = line.trim();
                                break;
                            }
                        }
                    }
                    break;
                }
            }
        }
    }
    
    try {
        // Send analysis request
        const response = await fetch(`${API_BASE_URL}/api/analyze`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                trace: currentTraceData,
                query: query,
                original_user_query: originalQuery,
                confidence_threshold: 0.5,
                use_find_issue_origin: useFindIssueOrigin,
                use_failure_analysis: useFailureAnalysis
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: `HTTP ${response.status}: ${response.statusText}` }));
            throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Mark response as received
        responseReceived = true;
        
        // Check for error in response
        if (data.error) {
            throw new Error(data.error);
        }
        
        // Complete progress bar now that we have the response
        if (progressFill) {
            progressFill.style.width = '100%';
        }
        if (progressText) {
            progressText.textContent = 'Analysis complete!';
        }
        // Mark all remaining stages as complete
        if (progressStages) {
            const remainingStages = progressStages.querySelectorAll('.progress-stage:not(.completed)');
            remainingStages.forEach(stage => stage.classList.add('completed'));
        }
        
        // Display summary
        displaySummary(data.summary, data.culprits);
        
        // Store culprit data and update graph
        culpritData = data.culprits;
        
        // Display culprits
        displayCulprits(data.culprits);
        
        // Update graph with culprit highlighting
        updateGraphWithCulprits(data.culprits);
        
    } catch (error) {
        console.error('Error analyzing trace:', error);
        console.error('Error details:', error.stack);
        
        // Reset progress on error
        if (progressFill) {
            progressFill.style.width = '0%';
        }
        if (progressText) {
            progressText.textContent = 'Error occurred';
        }
        if (progressStages) {
            progressStages.innerHTML = '';
        }
        
        // Show more detailed error message
        let errorMsg = 'Error analyzing trace: ' + error.message;
        if (error.message.includes('Failed to fetch')) {
            errorMsg += '\n\nPossible causes:\n- Server is not running\n- CORS issue\n- Network error\n\nCheck the browser console and server logs for more details.';
        }
        alert(errorMsg);
    } finally {
        // Mark response as received (even on error)
        responseReceived = true;
        
        // Clean up check interval if it exists
        if (checkInterval) {
            clearInterval(checkInterval);
            checkInterval = null;
        }
        
        // Complete progress bar only if not already completed
        if (progressFill && progressFill.style.width !== '100%') {
            progressFill.style.width = '100%';
        }
        if (progressText && !progressText.textContent.includes('complete')) {
            progressText.textContent = 'Analysis complete!';
        }
        
        // Hide loading after a brief delay to show completion
        setTimeout(() => {
            analyzeBtn.disabled = false;
            loadingDiv.style.display = 'none';
            // Reset progress
            if (progressFill) {
                progressFill.style.width = '0%';
            }
            if (progressStages) {
                progressStages.innerHTML = '';
            }
            // Reset response flag
            responseReceived = false;
            checkInterval = null;
        }, 800);
    }
}

/**
 * Display analysis summary
 */
function displaySummary(summary, culprits) {
    const summaryDiv = document.getElementById('summary');
    
    if (!summary) {
        summaryDiv.innerHTML = '<p class="empty-state">No summary available</p>';
        return;
    }
    
    const html = `
        <h3>Analysis Summary</h3>
        <p><strong>Messages Checked:</strong> ${summary.total_messages_checked || 0}</p>
        <p><strong>Total Responsible Nodes Found:</strong> ${summary.culprits_found || 0}</p>
        ${summary.culprits_from_origin !== undefined ? `<p><strong>From Culprit Detection:</strong> ${summary.culprits_from_origin || 0}</p>` : ''}
        ${summary.culprits_from_failure !== undefined ? `<p><strong>From Error Detection:</strong> ${summary.culprits_from_failure || 0}</p>` : ''}
        <p><strong>Confidence Threshold:</strong> ${(summary.confidence_threshold || 0).toFixed(2)}</p>
        ${summary.primary_component ? `<p><strong>Primary Component (Culprit Detection):</strong> ${summary.primary_component}</p>` : ''}
        ${summary.component_breakdown ? `<p><strong>Component Breakdown:</strong> ${Object.entries(summary.component_breakdown).map(([k, v]) => `${k}: ${v}`).join(', ')}</p>` : ''}
        ${summary.responsible_component ? `<p><strong>Responsible Component (Error Detection):</strong> ${summary.responsible_component}</p>` : ''}
        ${summary.decisive_error_step_index !== undefined && summary.decisive_error_step_index !== null ? `<p><strong>Decisive Error Step:</strong> ${summary.decisive_error_step_index}</p>` : ''}
    `;
    
    summaryDiv.innerHTML = html;
}

/**
 * Display list of culprits
 */
function displayCulprits(culprits) {
    const culpritsDiv = document.getElementById('culprits-list');
    
    if (!culprits || culprits.length === 0) {
        culpritsDiv.innerHTML = '<div class="empty-state"><p>No culprits found above the confidence threshold.</p></div>';
        return;
    }
    
    let html = '';
    culprits.forEach((culprit, index) => {
        // Defensive check: skip if culprit is null/undefined
        if (!culprit) {
            console.warn(`Skipping invalid culprit at index ${index}`);
            return;
        }
        
        const confidence = (culprit && culprit.confidence != null) ? culprit.confidence : 0;
        let confidenceClass = 'low-confidence';
        if (confidence >= 0.8) {
            confidenceClass = 'high-confidence';
        } else if (confidence >= 0.6) {
            confidenceClass = 'medium-confidence';
        }
        
        const sources = culprit.sources || 'Unknown';
        const isResponsible = culprit.is_responsible_node || false;
        const isFailure = culprit.is_failure || false;
        const responsibleComponent = culprit.responsible_component || '';
        
        // Add "root-cause" class for extra styling if it's the first responsible node
        const isFirstResponsible = index === 0 && isResponsible;
        html += `
            <div class="culprit-item ${confidenceClass} ${isResponsible ? 'responsible-node' : ''} ${isFailure ? 'failure-node' : ''} ${isFirstResponsible ? 'root-cause' : ''}" data-culprit-id="${culprit.id || `culprit_${index}`}">
                <div class="culprit-header">
                    <span class="culprit-type">${culprit.type || 'Unknown'}</span>
                    <div class="badge-container">
                        ${isResponsible ? '<span class="responsible-badge">🎯 RESPONSIBLE</span>' : ''}
                        ${isFailure ? '<span class="failure-badge">❌ FAILURE</span>' : ''}
                    </div>
                    <span class="confidence-badge">${(confidence * 100).toFixed(0)}%</span>
                </div>
                ${sources ? `<div class="culprit-sources" style="font-size: 0.85em; color: #94A3B8; margin-bottom: 8px;">Source: ${escapeHtml(sources)}</div>` : ''}
                ${responsibleComponent ? `<div class="responsible-component" style="font-size: 0.85em; color: #F59E0B; margin-bottom: 8px; font-weight: 600;">Component: ${escapeHtml(responsibleComponent)}</div>` : ''}
                <div class="culprit-content">${escapeHtml(culprit.content || '')}</div>
                <div class="culprit-explanation">${escapeHtml(culprit.explanation || '')}</div>
            </div>
        `;
    });
    
    culpritsDiv.innerHTML = html;
    
    // Add click handlers to highlight messages in chat
    document.querySelectorAll('.culprit-item').forEach(item => {
        item.addEventListener('click', function() {
            const culpritId = this.getAttribute('data-culprit-id');
            highlightNode(culpritId);
            // Also highlight the item itself
            this.style.animation = 'highlight 1s ease-in-out';
            setTimeout(() => {
                this.style.animation = '';
            }, 1000);
        });
    });
}

/**
 * Update chat visualization with culprit highlighting
 */
function updateGraphWithCulprits(culprits) {
    culpritData = culprits;
    // Re-render the chat timeline with culprit highlighting
    if (currentTraceData) {
        initializeGraph(currentTraceData);
    }
}

/**
 * Highlight a specific message in the chat
 */
function highlightNode(nodeId) {
    const messageBubble = document.querySelector(`.message-bubble[data-msg-id="${nodeId}"]`);
    if (messageBubble) {
        messageBubble.scrollIntoView({ behavior: 'smooth', block: 'center' });
        messageBubble.style.animation = 'highlight 1s ease-in-out';
        setTimeout(() => {
            messageBubble.style.animation = '';
        }, 1000);
    }
}

/**
 * Initialize chat-style timeline visualization from trace data
 */
function initializeGraph(traceData) {
    currentTraceData = traceData;
    
    const container = document.getElementById('graph-container');
    const loadingDiv = document.getElementById('graph-loading');
    
    loadingDiv.style.display = 'block';
    
    // Extract messages from trace
    const messages = traceData.messages || [];
    
    // Clear container
    container.innerHTML = '';
    
    // Create chat timeline
    const chatTimeline = document.createElement('div');
    chatTimeline.className = 'chat-timeline';
    
    messages.forEach((msg, index) => {
        // Parse message
        let msgId, msgType, content, toolCalls, fullContent;
        
        if (typeof msg === 'object' && msg !== null) {
            if (msg.type || msg.lc_id || msg.lc_kwargs) {
                // Serialized dict
                msgId = msg.id || msg.lc_id || `msg_${index}`;
                // Handle different type formats: "HumanMessage", "human", "humanmessage", etc.
                let typeStr = msg.type || '';
                if (!typeStr && msg.lc_kwargs && msg.lc_kwargs.content_type) {
                    typeStr = msg.lc_kwargs.content_type;
                }
                // Normalize type string
                typeStr = typeStr.toLowerCase().replace(/message$/, '').replace(/^lc_/, '');
                msgType = typeStr || 'unknown';
                fullContent = msg.content || '';
                content = fullContent;
                toolCalls = msg.tool_calls || [];
            } else {
                // LangChain message object
                msgId = msg.id || `msg_${index}`;
                msgType = (msg.constructor?.name || 'Unknown').replace('Message', '').toLowerCase();
                fullContent = msg.content || '';
                content = fullContent;
                toolCalls = msg.tool_calls || [];
            }
        } else {
            msgId = `msg_${index}`;
            msgType = 'unknown';
            fullContent = String(msg);
            content = fullContent;
            toolCalls = [];
        }
        
        // Check if this is a responsible node or failure
        const culprit = culpritData ? culpritData.find(c => c.id === msgId) : null;
        const isCulprit = culprit != null; // Check for both null and undefined
        const isResponsible = culprit && culprit.is_responsible_node;
        const isFailure = culprit && culprit.is_failure;
        
        // Create message bubble
        const messageBubble = document.createElement('div');
        messageBubble.className = `message-bubble ${msgType}-message`;
        messageBubble.setAttribute('data-msg-id', msgId);
        
        if (isCulprit && culprit) {
            messageBubble.classList.add('culprit-message');
            if (isResponsible) {
                messageBubble.classList.add('responsible-node-message');
            }
            if (isFailure) {
                messageBubble.classList.add('failure-message');
            }
            const confidence = (culprit && culprit.confidence) ? culprit.confidence : 0;
            if (confidence >= 0.8) {
                messageBubble.classList.add('culprit-high');
            } else if (confidence >= 0.6) {
                messageBubble.classList.add('culprit-medium');
            } else {
                messageBubble.classList.add('culprit-low');
            }
        }
        
        // Create wrapper for label and content
        const messageWrapper = document.createElement('div');
        messageWrapper.className = 'message-wrapper';
        
        // Vertical label on the left
        const typeLabel = document.createElement('div');
        typeLabel.className = 'message-type-vertical';
        typeLabel.textContent = msgType.toUpperCase();
        
        // Content area on the right
        const contentArea = document.createElement('div');
        contentArea.className = 'message-content-area';
        
        // Header with culprit badge if needed
        if (isCulprit && culprit) {
            const header = document.createElement('div');
            header.className = 'message-header';
            const confidence = (culprit && culprit.confidence) ? culprit.confidence : 0;
            const isFailure = culprit && culprit.is_failure;
            
            // Create badge container
            const badgeContainer = document.createElement('div');
            badgeContainer.className = 'badge-container';
            
            if (isResponsible) {
                const responsibleBadge = document.createElement('span');
                responsibleBadge.className = 'responsible-badge';
                responsibleBadge.textContent = `🎯 RESPONSIBLE`;
                badgeContainer.appendChild(responsibleBadge);
            }
            
            if (isFailure) {
                const failureBadge = document.createElement('span');
                failureBadge.className = 'failure-badge';
                failureBadge.textContent = `❌ FAILURE`;
                badgeContainer.appendChild(failureBadge);
            }
            
            if (!isResponsible && !isFailure) {
                // Fallback for old data
                const culpritBadge = document.createElement('span');
                culpritBadge.className = 'culprit-badge';
                culpritBadge.textContent = `⚠️ CULPRIT (${Math.round(confidence * 100)}%)`;
                badgeContainer.appendChild(culpritBadge);
            }
            
            header.appendChild(badgeContainer);
            contentArea.appendChild(header);
        }
        
        messageWrapper.appendChild(typeLabel);
        messageWrapper.appendChild(contentArea);
        
        // Message content
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        // Handle tool calls - simplified display
        if (toolCalls && toolCalls.length > 0) {
            const toolCallsDiv = document.createElement('div');
            toolCallsDiv.className = 'tool-calls';
            toolCalls.forEach(tc => {
                const toolCallDiv = document.createElement('div');
                toolCallDiv.className = 'tool-call';
                const name = tc.name || (tc.function && tc.function.name) || 'unknown';
                const args = tc.args || (tc.function && tc.function.arguments) || {};
                
                // Simplify args display - show key-value pairs in readable format
                let argsDisplay = '';
                if (typeof args === 'string') {
                    try {
                        args = JSON.parse(args);
                    } catch (e) {
                        argsDisplay = args;
                    }
                }
                
                if (!argsDisplay && typeof args === 'object') {
                    const argPairs = Object.entries(args).map(([key, val]) => {
                        const valStr = typeof val === 'string' ? val : JSON.stringify(val);
                        return `${key}: ${valStr}`;
                    });
                    argsDisplay = argPairs.join(', ');
                } else if (!argsDisplay) {
                    argsDisplay = JSON.stringify(args);
                }
                
                toolCallDiv.innerHTML = `
                    <strong>🔧 ${name}</strong>
                    <div class="tool-args">${escapeHtml(argsDisplay)}</div>
                `;
                toolCallsDiv.appendChild(toolCallDiv);
            });
            contentDiv.appendChild(toolCallsDiv);
        }
        
        // Add text content - simplify display
        if (content && content.trim()) {
            const textDiv = document.createElement('div');
            textDiv.className = 'message-text';
            
            // Check if this is a system message or system prompt (very long, contains instructions)
            const isSystemMessage = msgType === 'system';
            const isSystemPrompt = !isSystemMessage && content.length > 1000 && (
                content.toLowerCase().includes('you are') || 
                content.toLowerCase().includes('your goal is') ||
                content.toLowerCase().includes('follow this pattern')
            );
            
            if (isSystemMessage || isSystemPrompt) {
                // Collapse system messages/prompts by default
                const preview = content.substring(0, 150).trim() + '...';
                textDiv.textContent = preview;
                textDiv.style.fontStyle = 'italic';
                textDiv.style.color = '#94A3B8';
                
                const expandBtn = document.createElement('button');
                expandBtn.className = 'expand-btn';
                expandBtn.textContent = isSystemMessage ? 'Show system prompt' : 'Show full instructions';
                expandBtn.onclick = () => {
                    textDiv.textContent = content;
                    textDiv.style.fontStyle = 'normal';
                    textDiv.style.color = '#CBD5E1';
                    expandBtn.remove();
                };
                textDiv.appendChild(expandBtn);
            } else if (content.length > 300) {
                // Truncate other long messages
                const truncated = content.substring(0, 300) + '...';
                textDiv.textContent = truncated;
                const expandBtn = document.createElement('button');
                expandBtn.className = 'expand-btn';
                expandBtn.textContent = 'Show more';
                expandBtn.onclick = () => {
                    textDiv.textContent = content;
                    textDiv.style.color = '#CBD5E1';
                    expandBtn.remove();
                };
                textDiv.appendChild(expandBtn);
            } else {
                textDiv.textContent = content;
            }
            contentDiv.appendChild(textDiv);
        } else if (!toolCalls || toolCalls.length === 0) {
            // Show subtle indicator for empty messages
            const emptyDiv = document.createElement('div');
            emptyDiv.className = 'message-text';
            emptyDiv.textContent = '(empty message)';
            emptyDiv.style.fontStyle = 'italic';
            emptyDiv.style.color = '#999';
            contentDiv.appendChild(emptyDiv);
        }
        
        // Add culprit explanation if present
        if (isCulprit && culprit.explanation) {
            const explanationDiv = document.createElement('div');
            explanationDiv.className = 'culprit-explanation-bubble';
            explanationDiv.innerHTML = `<br>${escapeHtml(culprit.explanation)}`;
            contentDiv.appendChild(explanationDiv);
        }
        
        contentArea.appendChild(contentDiv);
        messageBubble.appendChild(messageWrapper);
        
        // Add click handler to scroll to culprit in list
        if (isCulprit) {
            messageBubble.style.cursor = 'pointer';
            messageBubble.onclick = () => {
                const culpritItem = document.querySelector(`.culprit-item[data-culprit-id="${msgId}"]`);
                if (culpritItem) {
                    culpritItem.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    culpritItem.style.animation = 'highlight 1s ease-in-out';
                    setTimeout(() => {
                        culpritItem.style.animation = '';
                    }, 1000);
                }
            };
        }
        
        chatTimeline.appendChild(messageBubble);
    });
    
    container.appendChild(chatTimeline);
    loadingDiv.style.display = 'none';
    
    // Scroll to bottom
    container.scrollTop = container.scrollHeight;
}

/**
 * Load trace data (can be called from external scripts)
 */
function loadTraceData(traceData) {
    initializeGraph(traceData);
}

/**
 * Utility function to escape HTML
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Export for use in other scripts
window.traceAnalysis = {
    loadTraceData: loadTraceData,
    analyzeTrace: analyzeTrace,
    generateTrace: generateTrace
};

