/**
 * ShopMate - Frontend Interaction Engine
 * ---------------------------------------------------
 * Manages chat UI state, API communications, typing indicator,
 * dynamic quick replies, markdown rendering, and human escalation.
 */

document.addEventListener('DOMContentLoaded', () => {
    // Session State
    let sessionId = localStorage.getItem('smartshop_session_id') || null;
    let isWaitingResponse = false;

    // DOM Elements
    const chatMessages = document.getElementById('chatMessages');
    const chatForm = document.getElementById('chatForm');
    const userInput = document.getElementById('userInput');
    const sendBtn = document.getElementById('sendBtn');
    const typingIndicator = document.getElementById('typingIndicator');
    const floatingQuickReplies = document.getElementById('floatingQuickReplies');
    const clearChatBtn = document.getElementById('clearChatBtn');
    const escalateBtn = document.getElementById('escalateBtn');
    
    // Status Elements
    const aiStatusText = document.getElementById('aiStatusText');
    const faqCountLabel = document.getElementById('faqCountLabel');
    const ordersCountLabel = document.getElementById('ordersCountLabel');
    const categoryList = document.getElementById('categoryList');
    
    // Sidebar Mobile Controls
    const sidebar = document.getElementById('sidebar');
    const openSidebarBtn = document.getElementById('openSidebarBtn');
    const closeSidebarBtn = document.getElementById('closeSidebarBtn');

    // Modal Elements
    const escalationModal = document.getElementById('escalationModal');
    const closeModalBtn = document.getElementById('closeModalBtn');
    const cancelModalBtn = document.getElementById('cancelModalBtn');
    const escalationForm = document.getElementById('escalationForm');
    const escalationReason = document.getElementById('escalationReason');
    const escalationNotes = document.getElementById('escalationNotes');

    // Initial Welcome Timestamp
    const welcomeTimestamp = document.getElementById('welcomeTimestamp');
    if (welcomeTimestamp) {
        welcomeTimestamp.textContent = formatTime(new Date());
    }

    // Initialize application
    init();

    async function init() {
        await loadSystemStatus();
        await loadCategories();
        setupEventListeners();
    }

    function setupEventListeners() {
        // Chat Form Submit
        chatForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const text = userInput.value.trim();
            if (text && !isWaitingResponse) {
                sendMessage(text);
            }
        });

        // Clear Chat
        clearChatBtn.addEventListener('click', () => {
            if (confirm('Are you sure you want to clear this conversation history?')) {
                resetChatSession();
            }
        });

        // Escalate to Human Support Modal
        escalateBtn.addEventListener('click', () => {
            openEscalationModal();
        });

        closeModalBtn.addEventListener('click', closeEscalationModal);
        cancelModalBtn.addEventListener('click', closeEscalationModal);

        escalationForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const reason = escalationReason.value;
            const notes = escalationNotes.value.trim() || 'User requested escalation via dashboard button.';
            submitEscalation(reason, notes);
        });

        // Mobile Sidebar Controls
        if (openSidebarBtn) {
            openSidebarBtn.addEventListener('click', () => {
                sidebar.classList.add('open');
            });
        }
        if (closeSidebarBtn) {
            closeSidebarBtn.addEventListener('click', () => {
                sidebar.classList.remove('open');
            });
        }

        // Sample Prototype Order Chips Click
        document.querySelectorAll('.order-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                const orderId = chip.getAttribute('data-order');
                if (orderId) {
                    userInput.value = `Track order ${orderId}`;
                    sendMessage(`Track order ${orderId}`);
                    if (window.innerWidth <= 860) {
                        sidebar.classList.remove('open');
                    }
                }
            });
        });

        // Initial Suggested Pills Click
        document.querySelectorAll('.suggestion-pill').forEach(pill => {
            pill.addEventListener('click', () => {
                const query = pill.getAttribute('data-query');
                if (query) {
                    sendMessage(query);
                }
            });
        });
    }

    /**
     * Load Backend Status (AI Mode, FAQs count, Model)
     */
    async function loadSystemStatus() {
        try {
            const res = await fetch('/api/status');
            const data = await res.json();
            if (data.status === 'online') {
                aiStatusText.textContent = data.ai_engine;
                faqCountLabel.textContent = `${data.faqs_loaded} FAQs Loaded`;
                ordersCountLabel.textContent = `${data.sample_orders_loaded} Demo Orders`;
            }
        } catch (err) {
            console.warn('Status check failed:', err);
            aiStatusText.textContent = 'Rule-Based Fallback Mode';
        }
    }

    /**
     * Load FAQ Categories in Sidebar
     */
    async function loadCategories() {
        try {
            const res = await fetch('/api/faq/categories');
            const data = await res.json();
            if (data.success && data.categories) {
                categoryList.innerHTML = '';
                data.categories.forEach(cat => {
                    const btn = document.createElement('button');
                    btn.className = 'category-item';
                    btn.innerHTML = `
                        <span>${cat.label}</span>
                        <span class="cat-count">${cat.count}</span>
                    `;
                    btn.addEventListener('click', () => {
                        handleCategoryClick(cat.id, cat.label);
                    });
                    categoryList.appendChild(btn);
                });
            }
        } catch (err) {
            console.error('Failed to load categories:', err);
            categoryList.innerHTML = '<div class="text-subtle">Categories available offline</div>';
        }
    }

    async function handleCategoryClick(catId, catLabel) {
        if (window.innerWidth <= 860) {
            sidebar.classList.remove('open');
        }

        setLoadingState(true);
        try {
            const response = await fetch(`/api/faq?category=${encodeURIComponent(catId)}`);
            if (!response.ok) {
                throw new Error(`FAQ request failed with status ${response.status}`);
            }

            const data = await response.json();
            if (!data.success || !Array.isArray(data.faqs)) {
                throw new Error('FAQ response was invalid');
            }

            appendMessage('bot', `Here are common questions for **${catLabel}**. Select one to ask:`);
            renderFloatingQuickReplies(data.faqs.map(faq => faq.question));
        } catch (err) {
            console.error('Failed to load category FAQs:', err);
            appendMessage('bot', `Unable to load ${catLabel} questions right now. Please try again.`);
        } finally {
            setLoadingState(false);
        }
    }

    /**
     * Send User Message to Backend
     */
    async function sendMessage(text) {
        if (!text.trim() || isWaitingResponse) return;

        // Hide initial suggestions once chat starts
        const initialSuggestions = document.getElementById('initialSuggestions');
        if (initialSuggestions) {
            initialSuggestions.style.display = 'none';
        }

        // Render customer message
        appendMessage('user', text);
        userInput.value = '';
        userInput.focus();
        clearFloatingQuickReplies();

        // Show typing indicator
        setLoadingState(true);

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: text,
                    session_id: sessionId
                })
            });

            const data = await response.json();

            setLoadingState(false);

            if (data.success) {
                if (data.session_id) {
                    sessionId = data.session_id;
                    localStorage.setItem('smartshop_session_id', sessionId);
                }

                // Render assistant response
                appendMessage('bot', data.response, {
                    intent: data.intent,
                    isEscalation: data.is_escalation,
                    ticket: data.ticket,
                    canEscalate: data.can_escalate
                });

                // Resolution check or quick replies
                if (data.resolved_check) {
                    renderResolutionCheck();
                } else if (data.quick_replies && data.quick_replies.length > 0) {
                    renderFloatingQuickReplies(data.quick_replies);
                }
            } else {
                appendMessage('bot', `⚠️ ${data.error || 'Something went wrong. Please try again.'}`);
            }
        } catch (err) {
            setLoadingState(false);
            console.error('Chat error:', err);
            appendMessage('bot', '⚠️ Connection error. Please ensure the backend server is running on http://127.0.0.1:5000 and try again.');
        }
    }

    /**
     * Submit Human Agent Escalation
     */
    async function submitEscalation(reason, notes) {
        closeEscalationModal();
        setLoadingState(true);

        try {
            const res = await fetch('/api/escalate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    reason: reason,
                    summary: notes,
                    session_id: sessionId
                })
            });
            const data = await res.json();
            setLoadingState(false);

            if (data.success) {
                appendMessage('bot', data.response, { isEscalation: true, ticket: data.ticket });
                clearFloatingQuickReplies();
            }
        } catch (err) {
            setLoadingState(false);
            console.error('Escalation failed:', err);
            appendMessage('bot', 'Failed to generate escalation ticket. Please call our toll-free support line at 1-800-SMART-SHOP.');
        }
    }

    /**
     * Reset and Clear Chat
     */
    async function resetChatSession() {
        try {
            const res = await fetch('/api/session/clear', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sessionId })
            });
            const data = await res.json();
            if (data.success && data.session_id) {
                sessionId = data.session_id;
                localStorage.setItem('smartshop_session_id', sessionId);
            }
        } catch (err) {
            console.warn('Clear session remote failed, resetting local state:', err);
        }

        // Reset Chat UI
        chatMessages.innerHTML = `
            <div class="message-group bot-message">
                <div class="bubble-avatar">🤖</div>
                <div class="bubble-content">
                    <div class="bubble-header">
                        <span class="author">ShopMate</span>
                        <span class="timestamp">${formatTime(new Date())}</span>
                    </div>
                    <div class="bubble-body">
                        <p>Chat cleared! I'm <strong>ShopMate</strong>, ready to help with your SmartShop questions. How can I assist you today?</p>
                    </div>
                </div>
            </div>
            <div class="quick-suggestions-block" id="initialSuggestions">
                <div class="suggestion-title">Frequently asked questions:</div>
                <div class="suggestion-pills">
                    <button class="suggestion-pill" data-query="Where is my order?">📦 Where is my order?</button>
                    <button class="suggestion-pill" data-query="How can I cancel my order?">❌ How can I cancel my order?</button>
                    <button class="suggestion-pill" data-query="How long does a refund take?">💰 How long does a refund take?</button>
                    <button class="suggestion-pill" data-query="My payment failed, but money was deducted.">💳 Payment failed but deducted</button>
                    <button class="suggestion-pill" data-query="I received a damaged product.">⚠️ Damaged product help</button>
                    <button class="suggestion-pill" data-query="I want to exchange for another size.">🔄 Size exchange process</button>
                </div>
            </div>
        `;

        clearFloatingQuickReplies();

        // Re-bind suggestion clicks
        document.querySelectorAll('.suggestion-pill').forEach(pill => {
            pill.addEventListener('click', () => {
                const query = pill.getAttribute('data-query');
                if (query) sendMessage(query);
            });
        });
    }

    /**
     * Render Message Bubble
     */
    function appendMessage(role, text, metadata = {}) {
        const group = document.createElement('div');
        group.className = `message-group ${role === 'user' ? 'user-message' : 'bot-message'}`;

        const avatar = document.createElement('div');
        avatar.className = 'bubble-avatar';
        avatar.textContent = role === 'user' ? '👤' : '🤖';

        const content = document.createElement('div');
        content.className = 'bubble-content';

        const header = document.createElement('div');
        header.className = 'bubble-header';
        header.innerHTML = `
            <span class="author">${role === 'user' ? 'You (Customer)' : 'ShopMate'}</span>
            <span class="timestamp">${formatTime(new Date())}</span>
        `;

        const body = document.createElement('div');
        body.className = 'bubble-body';
        body.innerHTML = renderMarkdown(text);

        content.appendChild(header);
        content.appendChild(body);

        // If message has escalation ticket details, render nice badge
        if (metadata.ticket) {
            const ticketCard = document.createElement('div');
            ticketCard.className = 'ticket-card';
            ticketCard.innerHTML = `
                <div class="ticket-header">
                    <span class="ticket-id">Ticket #${metadata.ticket.ticket_id}</span>
                    <span class="ticket-badge">${metadata.ticket.priority} Priority</span>
                </div>
                <div class="ticket-details">
                    <strong>Reason:</strong> ${metadata.ticket.escalation_reason}<br>
                    <strong>Estimated Wait Time:</strong> ${metadata.ticket.estimated_wait_time} (Queue: #${metadata.ticket.queue_position})
                </div>
            `;
            content.appendChild(ticketCard);
        }

        group.appendChild(avatar);
        group.appendChild(content);

        chatMessages.appendChild(group);
        scrollToBottom();
    }

    /**
     * Resolution Check Prompt (Step 8 & 9)
     */
    function renderResolutionCheck() {
        const checkContainer = document.createElement('div');
        checkContainer.className = 'quick-suggestions-block';
        checkContainer.style.marginLeft = '46px';
        checkContainer.style.marginTop = '4px';
        checkContainer.innerHTML = `
            <div class="suggestion-title">Did this answer resolve your question?</div>
            <div class="suggestion-pills">
                <button class="suggestion-pill" style="border-color: var(--success); color: var(--success);" data-res="yes">✅ Yes, resolved!</button>
                <button class="suggestion-pill" style="border-color: var(--warning); color: var(--warning);" data-res="no">❌ No, I need more help</button>
                <button class="suggestion-pill" style="border-color: var(--primary); color: var(--primary);" data-res="human">🎧 Connect to Human Agent</button>
            </div>
        `;

        checkContainer.querySelectorAll('button').forEach(btn => {
            btn.addEventListener('click', () => {
                const action = btn.getAttribute('data-res');
                checkContainer.remove();
                if (action === 'yes') {
                    sendMessage('Yes, resolved');
                } else if (action === 'no') {
                    sendMessage('No, not resolved');
                } else if (action === 'human') {
                    openEscalationModal();
                }
            });
        });

        chatMessages.appendChild(checkContainer);
        scrollToBottom();
    }

    /**
     * Render Interactive Floating Quick Replies
     */
    function renderFloatingQuickReplies(replies) {
        floatingQuickReplies.innerHTML = '';
        replies.forEach(reply => {
            const btn = document.createElement('button');
            btn.className = 'quick-reply-btn';
            btn.textContent = reply;
            btn.addEventListener('click', () => {
                clearFloatingQuickReplies();
                if (reply === 'Connect to Human Agent') {
                    openEscalationModal();
                } else {
                    sendMessage(reply);
                }
            });
            floatingQuickReplies.appendChild(btn);
        });
    }

    function clearFloatingQuickReplies() {
        floatingQuickReplies.innerHTML = '';
    }

    /**
     * Loading / Typing indicator state
     */
    function setLoadingState(loading) {
        isWaitingResponse = loading;
        sendBtn.disabled = loading;
        typingIndicator.style.display = loading ? 'flex' : 'none';
        if (loading) scrollToBottom();
    }

    function scrollToBottom() {
        setTimeout(() => {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }, 50);
    }

    function formatTime(date) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    function openEscalationModal() {
        escalationModal.style.display = 'flex';
    }

    function closeEscalationModal() {
        escalationModal.style.display = 'none';
    }

    /**
     * Simple Lightweight Markdown Parser
     */
    function renderMarkdown(md) {
        if (!md) return '';
        let html = md;

        // Escape dangerous HTML tags
        html = html.replace(/</g, '&lt;').replace(/>/g, '&gt;');

        // Restore safe markdown blockquotes
        html = html.replace(/^&gt; (.*$)/gim, '<blockquote>$1</blockquote>');

        // Headers
        html = html.replace(/^### (.*$)/gim, '<h4 style="font-size:0.95rem;font-weight:700;margin:6px 0;">$1</h4>');
        html = html.replace(/^## (.*$)/gim, '<h3 style="font-size:1.05rem;font-weight:700;margin:8px 0;">$1</h3>');

        // Bold & Italic
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');

        // Inline Code
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

        // Unordered lists
        html = html.replace(/^\s*[-•]\s+(.*$)/gim, '<li>$1</li>');
        html = html.replace(/(<li>.*<\/li>)/gms, '<ul>$1</ul>');

        // Ordered lists
        html = html.replace(/^\s*\d+\.\s+(.*$)/gim, '<li>$1</li>');

        // Tables: simple markdown table support
        if (html.includes('|')) {
            const lines = html.split('\n');
            let inTable = false;
            let tableHtml = '<table>';
            let newLines = [];

            for (let line of lines) {
                if (line.trim().startsWith('|') && line.trim().endsWith('|')) {
                    if (line.includes('---')) continue; // separator line
                    if (!inTable) {
                        inTable = true;
                        tableHtml = '<table>';
                    }
                    const cells = line.split('|').filter(c => c.trim().length > 0);
                    tableHtml += '<tr>' + cells.map(c => `<td>${c.trim()}</td>`).join('') + '</tr>';
                } else {
                    if (inTable) {
                        tableHtml += '</table>';
                        newLines.push(tableHtml);
                        inTable = false;
                    }
                    newLines.push(line);
                }
            }
            if (inTable) {
                tableHtml += '</table>';
                newLines.push(tableHtml);
            }
            html = newLines.join('\n');
        }

        // Paragraph breaks
        html = html.split('\n\n').map(p => {
            if (p.startsWith('<ul>') || p.startsWith('<table>') || p.startsWith('<blockquote>') || p.startsWith('<h')) {
                return p;
            }
            return `<p>${p.replace(/\n/g, '<br>')}</p>`;
        }).join('');

        return html;
    }
});
