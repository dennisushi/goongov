// Global variables
let currentTraceData = null;
let culpritData = null;

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
        container.innerHTML = '<div class="empty-state"><p>No trace data loaded. Use the API to load a trace.</p></div>';
    }
});

/**
 * Analyze trace with user query
 */
async function analyzeTrace() {
    const queryInput = document.getElementById('query-input');
    const query = queryInput.value.trim();
    
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
    
    try {
        // Send analysis request
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                trace: currentTraceData,
                query: query,
                confidence_threshold: 0.5
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: `HTTP ${response.status}: ${response.statusText}` }));
            throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Check for error in response
        if (data.error) {
            throw new Error(data.error);
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
        // Show more detailed error message
        let errorMsg = 'Error analyzing trace: ' + error.message;
        if (error.message.includes('Failed to fetch')) {
            errorMsg += '\n\nPossible causes:\n- Server is not running\n- CORS issue\n- Network error\n\nCheck the browser console and server logs for more details.';
        }
        alert(errorMsg);
    } finally {
        analyzeBtn.disabled = false;
        loadingDiv.style.display = 'none';
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
        <p><strong>Culprits Found:</strong> ${summary.culprits_found || 0}</p>
        <p><strong>Confidence Threshold:</strong> ${(summary.confidence_threshold || 0).toFixed(2)}</p>
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
        
        html += `
            <div class="culprit-item ${confidenceClass}" data-culprit-id="${culprit.id || `culprit_${index}`}">
                <div class="culprit-header">
                    <span class="culprit-type">${culprit.type || 'Unknown'}</span>
                    <span class="confidence-badge">${(confidence * 100).toFixed(0)}%</span>
                </div>
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
        
        // Check if this is a culprit
        const culprit = culpritData ? culpritData.find(c => c.id === msgId) : null;
        const isCulprit = culprit != null; // Check for both null and undefined
        
        // Create message bubble
        const messageBubble = document.createElement('div');
        messageBubble.className = `message-bubble ${msgType}-message`;
        messageBubble.setAttribute('data-msg-id', msgId);
        
        if (isCulprit && culprit) {
            messageBubble.classList.add('culprit-message');
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
            const culpritBadge = document.createElement('span');
            culpritBadge.className = 'culprit-badge';
            const confidence = (culprit && culprit.confidence) ? culprit.confidence : 0;
            culpritBadge.textContent = `⚠️ CULPRIT (${Math.round(confidence * 100)}%)`;
            header.appendChild(culpritBadge);
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
            
            // Check if this is a system prompt (very long, contains instructions)
            const isSystemPrompt = content.length > 1000 && (
                content.toLowerCase().includes('you are') || 
                content.toLowerCase().includes('your goal is') ||
                content.toLowerCase().includes('follow this pattern')
            );
            
            if (isSystemPrompt) {
                // Collapse system prompts by default
                const preview = content.substring(0, 150).trim() + '...';
                textDiv.textContent = preview;
                textDiv.style.fontStyle = 'italic';
                textDiv.style.color = '#94A3B8';
                
                const expandBtn = document.createElement('button');
                expandBtn.className = 'expand-btn';
                expandBtn.textContent = 'Show full instructions';
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
    analyzeTrace: analyzeTrace
};

