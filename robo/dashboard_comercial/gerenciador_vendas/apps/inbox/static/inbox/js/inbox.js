/**
 * Inbox App — Chatwoot-style Three-Panel Chat Interface
 */
(function() {
    'use strict';

    const POLL_INTERVAL = 5000;
    const CSRF_TOKEN = document.querySelector('[name=csrfmiddlewaretoken]')?.value
        || document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';

    let state = {
        conversas: [],
        currentConversaId: null,
        agenteFilter: '',
        statusFilter: '',
        sortOrder: 'desc', // 'desc' = mais recente, 'asc' = mais antiga
        searchQuery: '',
        inputMode: 'reply', // 'reply' ou 'note'
        respostasRapidas: [],
        pollTimer: null,
        messagePollTimer: null,
        ws: null,
        wsConnected: false,
    };

    // ── Utilidades ────────────────────────────────────────────────────

    function fetchJSON(url, opts = {}) {
        const defaults = {
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
        };
        return fetch(url, { ...defaults, ...opts }).then(r => r.json()).catch(e => ({ error: e.message }));
    }

    function formatTime(isoStr) {
        if (!isoStr) return '';
        const d = new Date(isoStr), now = new Date(), diff = now - d;
        if (diff < 60000) return 'agora';
        if (diff < 3600000) return Math.floor(diff / 60000) + 'min';
        if (diff < 86400000) return d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
        const dias = Math.floor(diff / 86400000);
        if (dias === 1) return '1d';
        if (dias < 30) return dias + 'd';
        return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
    }

    function formatFullTime(iso) {
        if (!iso) return '';
        const d = new Date(iso);
        return d.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' }) + ', ' +
               d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) + ' PM';
    }

    function formatDate(iso) {
        if (!iso) return '';
        return new Date(iso).toLocaleDateString('pt-BR', { day: '2-digit', month: 'long', year: 'numeric' });
    }

    function getInitials(name) {
        if (!name) return '?';
        const p = name.trim().split(/\s+/);
        return p.length >= 2 ? (p[0][0] + p[p.length-1][0]).toUpperCase() : p[0][0].toUpperCase();
    }

    function esc(s) {
        const d = document.createElement('div'); d.textContent = s; return d.innerHTML;
    }

    // Safe getElementById — returns element or no-op proxy to avoid null crashes
    function $(id) {
        return document.getElementById(id) || { addEventListener: () => {}, style: {}, classList: { toggle: () => {}, add: () => {}, remove: () => {} }, value: '', textContent: '', innerHTML: '', dataset: {} };
    }

    // ── Carregar conversas ────────────────────────────────────────────

    function loadConversas() {
        let url = '/inbox/api/conversas/?';
        if (state.agenteFilter) url += 'agente=' + state.agenteFilter + '&';
        if (state.statusFilter) url += 'status=' + state.statusFilter + '&';
        if (state.sortOrder) url += 'ordem=' + state.sortOrder + '&';
        if (state.searchQuery) url += 'q=' + encodeURIComponent(state.searchQuery) + '&';

        fetchJSON(url).then(data => {
            if (data.error) return;
            state.conversas = data.conversas || [];
            renderConversaList();
            updateCounts();
        });
    }

    function updateCounts() {
        const all = state.conversas.length;
        document.getElementById('countAll').textContent = all;
        // Counts are approximate from current loaded list
        const mine = state.conversas.filter(c => c.agente_id).length;
        const unassigned = state.conversas.filter(c => !c.agente_id).length;
        document.getElementById('countMine').textContent = mine;
        document.getElementById('countUnassigned').textContent = unassigned;
    }

    function renderConversaList() {
        const container = document.getElementById('conversationList');
        if (!state.conversas.length) {
            container.innerHTML = '<div class="inbox-loading"><i class="fas fa-inbox" style="opacity:.3;font-size:32px;"></i><p>Nenhuma conversa</p></div>';
            return;
        }

        container.innerHTML = state.conversas.map(c => {
            const isActive = c.id === state.currentConversaId;
            const canalLabel = c.canal_tipo === 'whatsapp' ? 'WhatsApp' : c.canal_tipo;
            return `
            <div class="conv-card ${isActive ? 'active' : ''}" data-id="${c.id}">
                <div class="conv-avatar" style="background:${c.canal_tipo === 'whatsapp' ? '#25D366' : '#3b82f6'}">${getInitials(c.contato_nome)}</div>
                <div class="conv-body">
                    <div class="conv-top">
                        <span class="conv-inbox-label">${esc(canalLabel)}</span>
                        ${c.agente_nome ? `<span class="conv-agent-name"><i class="fas fa-user" style="font-size:9px;margin-right:2px;"></i>${esc(c.agente_nome)}</span>` : ''}
                    </div>
                    <div class="conv-name">${esc(c.contato_nome || c.contato_telefone || '#' + c.numero)}</div>
                    <div class="conv-preview">
                        <span class="reply-icon"><i class="fas fa-reply"></i></span>
                        ${esc(c.ultima_mensagem_preview || '')}
                    </div>
                </div>
                <div class="conv-meta">
                    <span class="conv-time">${formatTime(c.ultima_mensagem_em)}</span>
                    ${c.mensagens_nao_lidas > 0 ? `<span class="conv-badge">${c.mensagens_nao_lidas}</span>` : ''}
                </div>
            </div>`;
        }).join('');

        container.querySelectorAll('.conv-card').forEach(el => {
            el.addEventListener('click', () => selectConversa(parseInt(el.dataset.id)));
        });
    }

    // ── Selecionar conversa ───────────────────────────────────────────

    function selectConversa(id) {
        state.currentConversaId = id;
        document.querySelectorAll('.conv-card').forEach(el => {
            el.classList.toggle('active', parseInt(el.dataset.id) === id);
        });

        document.getElementById('emptyState').style.display = 'none';
        document.getElementById('chatHeader').style.display = 'flex';
        document.getElementById('messageList').style.display = 'flex';
        document.getElementById('inputArea').style.display = 'block';
        document.getElementById('inboxSidebar')?.classList.add('hidden-mobile');

        wsSend({ action: 'join_conversa', conversa_id: id });
        loadConversaDetalhe(id);
        loadMensagens(id);
        if (!state.wsConnected) startMessagePoll(id);
    }

    function loadConversaDetalhe(id) {
        fetchJSON('/inbox/api/conversas/' + id + '/').then(data => {
            if (data.error) return;

            // Chat header
            document.getElementById('chatName').textContent = data.contato_nome || data.contato_telefone || '#' + data.numero;
            document.getElementById('chatMeta').textContent = (data.canal_tipo || '') + (data.contato_telefone ? ' · ' + data.contato_telefone : '');
            document.getElementById('chatAvatar').textContent = getInitials(data.contato_nome);

            // Context panel — contact
            document.getElementById('ctxAvatar').textContent = getInitials(data.contato_nome);
            document.getElementById('ctxName').textContent = data.contato_nome || data.contato_telefone || '#' + data.numero;
            document.getElementById('ctxPhone').textContent = data.contato_telefone || '—';
            document.getElementById('ctxEmail').textContent = data.contato_email || '—';

            // Agent, Equipe, Prioridade
            document.getElementById('agentSelect').value = data.agente_id || '';
            document.getElementById('teamSelect').value = data.equipe_id || '';
            document.getElementById('prioritySelect').value = data.prioridade || 'normal';

            // Labels
            const chipDiv = document.getElementById('labelChips');
            if (data.etiquetas && data.etiquetas.length) {
                chipDiv.innerHTML = data.etiquetas.map(e =>
                    `<span class="label-chip" data-id="${e.id}" style="background:${e.cor_hex}">${esc(e.nome)}</span>`
                ).join('');
            } else {
                chipDiv.innerHTML = '';
            }

            // Lead info
            const leadDiv = document.getElementById('ctxLeadInfo');
            if (data.lead_info) {
                const l = data.lead_info;
                leadDiv.innerHTML = `
                    <div class="ctx-info-row"><span class="ctx-info-label">Nome</span><span class="ctx-info-value">${esc(l.nome)}</span></div>
                    <div class="ctx-info-row"><span class="ctx-info-label">Origem</span><span class="ctx-info-value">${esc(l.origem)}</span></div>
                    <div class="ctx-info-row"><span class="ctx-info-label">Score</span><span class="ctx-info-value">${l.score || '—'}</span></div>
                `;
                if (data.oportunidade_info) {
                    const op = data.oportunidade_info;
                    leadDiv.innerHTML += `
                        <div class="ctx-info-row"><span class="ctx-info-label">CRM</span><span class="ctx-info-value">${esc(op.titulo)}</span></div>
                        <div class="ctx-info-row"><span class="ctx-info-label">Estágio</span><span class="ctx-info-value">${esc(op.estagio)}</span></div>
                        <div class="ctx-info-row"><span class="ctx-info-label">Valor</span><span class="ctx-info-value">R$ ${op.valor_estimado}</span></div>
                    `;
                }
            } else {
                leadDiv.innerHTML = '<p class="ctx-empty">Lead não vinculado</p>';
            }

            // Ticket
            const ticketInfo = document.getElementById('ticketInfo');
            const ticketBtn = document.getElementById('createTicketBtn');
            if (data.ticket_info) {
                ticketInfo.style.display = 'block';
                ticketInfo.innerHTML = `<div class="ctx-info-row"><span class="ctx-info-label">#${data.ticket_info.numero}</span><span class="ctx-info-value">${esc(data.ticket_info.titulo)}</span></div>`;
                ticketBtn.style.display = 'none';
            } else {
                ticketInfo.style.display = 'none';
                ticketBtn.style.display = 'inline-flex';
            }

            // Conversas anteriores
            const prevDiv = document.getElementById('previousConversations');
            if (prevDiv) {
                const prev = data.conversas_anteriores || [];
                if (prev.length) {
                    prevDiv.innerHTML = prev.map(c => {
                        const statusBadge = c.status === 'resolvida' ? '✅' : c.status === 'aberta' ? '🔵' : '⏳';
                        const dataStr = c.data_abertura ? new Date(c.data_abertura).toLocaleDateString('pt-BR') : '';
                        return `<div style="padding:8px 0;border-bottom:1px solid var(--border-light,#f1f5f9);font-size:12px;">
                            <div style="display:flex;justify-content:space-between;align-items:center;">
                                <span style="font-weight:600;color:var(--text-main);">${statusBadge} #${c.numero}</span>
                                <span style="color:var(--text-muted);font-size:11px;">${dataStr}</span>
                            </div>
                            <div style="color:var(--text-muted);margin-top:2px;">${esc(c.preview || 'Sem preview')}</div>
                            ${c.agente ? `<div style="color:var(--text-muted);font-size:10px;margin-top:2px;"><i class="fas fa-user" style="font-size:9px;"></i> ${esc(c.agente)} · ${c.total_mensagens} msg</div>` : ''}
                        </div>`;
                    }).join('');
                } else {
                    prevDiv.innerHTML = '<p style="font-size:12px;color:var(--text-muted);">Nenhuma conversa anterior.</p>';
                }
            }

            // Notes
            renderNotas(data.notas || []);
            loadConversas();
        });
    }

    // ── Mensagens ─────────────────────────────────────────────────────

    function loadMensagens(id) {
        fetchJSON('/inbox/api/conversas/' + id + '/mensagens/').then(data => {
            if (data.error) return;
            renderMensagens(data.mensagens || []);
        });
    }

    function renderMensagens(msgs) {
        const container = document.getElementById('messageList');
        if (!msgs.length) {
            container.innerHTML = '<div class="inbox-loading"><p>Nenhuma mensagem</p></div>';
            return;
        }

        let html = '', lastDate = '';
        msgs.forEach(m => {
            const d = formatDate(m.data_envio);
            if (d !== lastDate) { lastDate = d; html += `<div class="msg-date-sep"><span>${d}</span></div>`; }

            const t = m.remetente_tipo;
            let statusIcon = '';
            if (t === 'agente') {
                statusIcon = m.data_leitura ? '<i class="fas fa-check-double" style="color:#22c55e;"></i>'
                    : m.data_entrega ? '<i class="fas fa-check-double"></i>'
                    : '<i class="fas fa-check"></i>';
            }

            html += `<div class="msg-bubble ${t}">`;
            if (t === 'contato' || t === 'bot') html += `<div class="msg-sender">${esc(m.remetente_nome)}</div>`;
            html += `<div>${esc(m.conteudo)}</div>`;
            if (m.arquivo_url) html += `<div style="margin-top:4px;"><a href="${esc(m.arquivo_url)}" target="_blank" style="color:inherit;text-decoration:underline;font-size:12px;"><i class="fas fa-paperclip"></i> ${esc(m.arquivo_nome || 'Arquivo')}</a></div>`;
            html += `<div class="msg-time">${formatFullTime(m.data_envio)} <span class="msg-status">${statusIcon}</span></div>`;
            if (m.erro_envio) html += `<div style="font-size:10px;color:#ef4444;margin-top:2px;"><i class="fas fa-exclamation-triangle"></i> ${esc(m.erro_envio)}</div>`;
            html += '</div>';
        });

        container.innerHTML = html;
        container.scrollTop = container.scrollHeight;
    }

    function startMessagePoll(id) {
        if (state.messagePollTimer) clearInterval(state.messagePollTimer);
        state.messagePollTimer = setInterval(() => {
            if (state.currentConversaId === id) loadMensagens(id);
        }, POLL_INTERVAL);
    }

    // ── Enviar mensagem / nota ────────────────────────────────────────

    function sendMessage() {
        const input = document.getElementById('messageInput');
        const conteudo = input.value.trim();
        if (!conteudo || !state.currentConversaId) return;
        input.value = '';
        autoResize(input);

        if (state.inputMode === 'note') {
            fetchJSON('/inbox/api/conversas/' + state.currentConversaId + '/notas/', {
                method: 'POST', body: JSON.stringify({ conteudo }),
            }).then(d => { if (d.success) loadConversaDetalhe(state.currentConversaId); });
        } else {
            fetchJSON('/inbox/api/conversas/' + state.currentConversaId + '/enviar/', {
                method: 'POST', body: JSON.stringify({ conteudo }),
            }).then(d => { if (d.success) loadMensagens(state.currentConversaId); });
        }
    }

    // ── Respostas rápidas ─────────────────────────────────────────────

    function loadRespostasRapidas() {
        fetchJSON('/inbox/api/respostas-rapidas/').then(d => { state.respostasRapidas = d.respostas || []; });
    }

    function showQuickResponses(filter) {
        const dropdown = document.getElementById('quickResponseDropdown');
        const list = document.getElementById('quickResponseList');
        let items = state.respostasRapidas;
        if (filter) {
            const q = filter.toLowerCase();
            items = items.filter(r => r.titulo.toLowerCase().includes(q) || r.atalho.toLowerCase().includes(q));
        }
        if (!items.length) { dropdown.style.display = 'none'; return; }

        list.innerHTML = items.map(r => `
            <div class="quick-response-item" data-content="${esc(r.conteudo)}">
                <span class="quick-response-item-title">${esc(r.titulo)}</span>
                ${r.atalho ? `<span class="quick-response-item-shortcut">${esc(r.atalho)}</span>` : ''}
                <div class="quick-response-item-preview">${esc(r.conteudo.substring(0, 80))}</div>
            </div>`).join('');

        dropdown.style.display = 'block';
        list.querySelectorAll('.quick-response-item').forEach(el => {
            el.addEventListener('click', () => {
                document.getElementById('messageInput').value = el.dataset.content;
                dropdown.style.display = 'none';
                document.getElementById('messageInput').focus();
            });
        });
    }

    // ── Notas ─────────────────────────────────────────────────────────

    function renderNotas(notas) {
        document.getElementById('notesList').innerHTML = notas.map(n => `
            <div class="ctx-note-item">
                <div class="ctx-note-header"><span>${esc(n.autor)}</span><span>${formatTime(n.data)}</span></div>
                <div class="ctx-note-content">${esc(n.conteudo)}</div>
            </div>`).join('');
    }

    // ── Textarea auto-resize ──────────────────────────────────────────

    function autoResize(el) {
        el.style.height = 'auto';
        el.style.height = Math.min(el.scrollHeight, 120) + 'px';
    }

    // ── WebSocket ─────────────────────────────────────────────────────

    function connectWebSocket() {
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        try {
            state.ws = new WebSocket(protocol + '//' + location.host + '/ws/inbox/');
            state.ws.onopen = () => {
                state.wsConnected = true;
                if (state.pollTimer) { clearInterval(state.pollTimer); state.pollTimer = null; }
                if (state.messagePollTimer) { clearInterval(state.messagePollTimer); state.messagePollTimer = null; }
            };
            state.ws.onmessage = e => {
                try { handleWsMessage(JSON.parse(e.data)); } catch(err) {}
            };
            state.ws.onclose = () => {
                state.wsConnected = false;
                if (!state.pollTimer) state.pollTimer = setInterval(loadConversas, POLL_INTERVAL);
                setTimeout(connectWebSocket, 5000);
            };
            state.ws.onerror = () => {
                if (!state.pollTimer) state.pollTimer = setInterval(loadConversas, POLL_INTERVAL);
            };
        } catch(e) {
            state.pollTimer = setInterval(loadConversas, POLL_INTERVAL);
        }
    }

    function handleWsMessage(data) {
        if (data.type === 'nova_mensagem') {
            loadConversas();
            if (data.conversa_id === state.currentConversaId) loadMensagens(state.currentConversaId);
        } else if (data.type === 'conversa_atualizada') {
            loadConversas();
            if (data.conversa_id === state.currentConversaId) loadConversaDetalhe(state.currentConversaId);
        }
    }

    function wsSend(data) {
        if (state.ws && state.wsConnected) state.ws.send(JSON.stringify(data));
    }

    // ── Event Bindings ────────────────────────────────────────────────

    function init() {
        // Assign tabs (Minhas / Não atribuídas / Todas)
        document.querySelectorAll('.inbox-assign-tab').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.inbox-assign-tab').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                state.agenteFilter = btn.dataset.agente;
                loadConversas();
            });
        });

        // Filter button
        $('filterMenuBtn').addEventListener('click', function(e) {
            e.stopPropagation();
            const dd = document.getElementById('filterDropdown');
            dd.style.display = dd.style.display === 'none' ? 'block' : 'none';
        });
        document.querySelectorAll('.inbox-filter-opt').forEach(btn => {
            btn.addEventListener('click', function() {
                document.querySelectorAll('.inbox-filter-opt').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                state.statusFilter = this.dataset.status;
                document.getElementById('filterDropdown').style.display = 'none';
                $('filterMenuBtn').classList.toggle('active', !!state.statusFilter);
                loadConversas();
            });
        });

        // Sort button
        $('sortBtn').addEventListener('click', function() {
            state.sortOrder = state.sortOrder === 'desc' ? 'asc' : 'desc';
            this.classList.toggle('active', state.sortOrder === 'asc');
            this.title = state.sortOrder === 'desc' ? 'Mais recentes primeiro' : 'Mais antigas primeiro';
            loadConversas();
        });

        // Search
        let searchTimeout;
        $('inboxSearch').addEventListener('input', function() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => { state.searchQuery = this.value.trim(); loadConversas(); }, 300);
        });

        // Emoji picker
        const EMOJIS = ['😀','😂','😊','😍','🥰','😘','😎','🤔','👍','👎','❤️','🔥','✅','❌','⭐','🎉','📌','📎','💬','🙏','👋','🤝','💡','⚡','📞','📧','🕐','📅','✍️','🏠','🚀','💰','🎯','👀','🙂'];
        const pickerEl = document.getElementById('emojiPicker');
        if (pickerEl) {
            pickerEl.innerHTML = EMOJIS.map(e => `<button type="button" onclick="document.getElementById('messageInput').value+='${e}';document.getElementById('messageInput').focus();document.getElementById('emojiPicker').style.display='none';">${e}</button>`).join('');
        }
        $('emojiBtn').addEventListener('click', function(e) {
            e.stopPropagation();
            pickerEl.style.display = pickerEl.style.display === 'none' ? 'grid' : 'none';
        });

        // Anexar arquivo
        $('attachBtn').addEventListener('click', function() {
            document.getElementById('attachInput').click();
        });
        document.getElementById('attachInput')?.addEventListener('change', function() {
            if (!this.files.length || !state.currentConversaId) return;
            const file = this.files[0];
            const formData = new FormData();
            formData.append('arquivo', file);
            formData.append('conteudo', file.name);

            fetch('/inbox/api/conversas/' + state.currentConversaId + '/enviar/', {
                method: 'POST',
                headers: {'X-CSRFToken': CSRF_TOKEN},
                body: formData,
            })
            .then(r => r.json())
            .then(d => { if (d.success) loadMensagens(state.currentConversaId); })
            .catch(() => {});
            this.value = '';
        });

        // Send
        $('sendBtn').addEventListener('click', sendMessage);
        $('messageInput').addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && e.ctrlKey) { e.preventDefault(); sendMessage(); }
            if (e.key === '/' && this.value === '') { e.preventDefault(); showQuickResponses(''); }
        });
        $('messageInput').addEventListener('input', function() {
            autoResize(this);
            if (this.value.startsWith('/')) showQuickResponses(this.value.substring(1));
            else $('quickResponseDropdown').style.display = 'none';
        });

        // Input tabs (Responder / Nota Privada)
        document.querySelectorAll('.input-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.input-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                state.inputMode = tab.dataset.mode;
                const input = $('messageInput');
                input.placeholder = state.inputMode === 'note'
                    ? 'Adicionar nota privada (visível apenas para agentes)...'
                    : "Shift + Enter para nova linha. Comece com '/' para selecionar uma resposta pronta.";
                input.focus();
            });
        });

        // Resolve button group
        $('resolveBtn').addEventListener('click', () => {
            if (!state.currentConversaId) return;
            fetchJSON('/inbox/api/conversas/' + state.currentConversaId + '/resolver/', { method: 'POST' })
                .then(() => { loadConversas(); loadConversaDetalhe(state.currentConversaId); loadMensagens(state.currentConversaId); });
        });
        $('resolveDropdown').addEventListener('click', () => {
            const menu = $('resolveMenu');
            menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
        });
        document.querySelectorAll('#resolveMenu button').forEach(btn => {
            btn.addEventListener('click', () => {
                const action = btn.dataset.action;
                let endpoint = '';
                if (action === 'resolver') endpoint = '/resolver/';
                else if (action === 'pendente') endpoint = '/resolver/';
                else if (action === 'reabrir') endpoint = '/reabrir/';

                if (endpoint) {
                    fetchJSON('/inbox/api/conversas/' + state.currentConversaId + endpoint, { method: 'POST' })
                        .then(() => { loadConversas(); loadConversaDetalhe(state.currentConversaId); loadMensagens(state.currentConversaId); });
                }
                $('resolveMenu').style.display = 'none';
            });
        });

        // Agent select
        $('agentSelect').addEventListener('change', function() {
            if (!state.currentConversaId || !this.value) return;
            fetchJSON('/inbox/api/conversas/' + state.currentConversaId + '/atribuir/', {
                method: 'POST', body: JSON.stringify({ agente_id: parseInt(this.value) }),
            }).then(() => loadConversas());
        });

        // Assign to me
        $('ctxAssignMe').addEventListener('click', () => {
            if (!state.currentConversaId) return;
            // Pegar ID do user logado pelo select (primeira opção que não é vazio)
            const select = document.getElementById('agentSelect');
            // Buscar user ID via cookie ou tentar atribuir via endpoint
            fetchJSON('/inbox/api/conversas/' + state.currentConversaId + '/atribuir/', {
                method: 'POST', body: JSON.stringify({ agente_id: parseInt(select.value) || 0 }),
            });
        });

        // Equipe
        $('teamSelect').addEventListener('change', function() {
            if (!state.currentConversaId) return;
            fetchJSON('/inbox/api/conversas/' + state.currentConversaId + '/atualizar/', {
                method: 'POST', body: JSON.stringify({ equipe_id: this.value ? parseInt(this.value) : null }),
            }).then(() => loadConversas());
        });

        // Prioridade
        $('prioritySelect').addEventListener('change', function() {
            if (!state.currentConversaId) return;
            fetchJSON('/inbox/api/conversas/' + state.currentConversaId + '/atualizar/', {
                method: 'POST', body: JSON.stringify({ prioridade: this.value }),
            });
        });

        // Etiquetas
        $('labelSelect').addEventListener('change', function() {
            if (!state.currentConversaId || !this.value) return;
            const etiquetaId = parseInt(this.value);
            // Pegar etiquetas atuais e adicionar a nova
            const chips = document.getElementById('labelChips');
            const atuais = Array.from(chips.querySelectorAll('.label-chip')).map(c => parseInt(c.dataset.id)).filter(Boolean);
            if (!atuais.includes(etiquetaId)) atuais.push(etiquetaId);
            fetchJSON('/inbox/api/conversas/' + state.currentConversaId + '/atualizar/', {
                method: 'POST', body: JSON.stringify({ etiquetas: atuais }),
            }).then(() => loadConversaDetalhe(state.currentConversaId));
            this.value = '';
        });

        // Notes
        $('addNoteBtn').addEventListener('click', () => {
            const input = $('noteInput');
            const conteudo = input.value.trim();
            if (!conteudo || !state.currentConversaId) return;
            input.value = '';
            fetchJSON('/inbox/api/conversas/' + state.currentConversaId + '/notas/', {
                method: 'POST', body: JSON.stringify({ conteudo }),
            }).then(d => { if (d.success) loadConversaDetalhe(state.currentConversaId); });
        });

        // Context toggle
        $('toggleContextBtn').addEventListener('click', () => {
            const ctx = document.getElementById('inboxContext');
            if (ctx) { ctx.classList.toggle('collapsed'); ctx.classList.toggle('show-mobile'); }
        });

        // Back (mobile)
        $('chatBackBtn').addEventListener('click', () => {
            document.getElementById('inboxSidebar')?.classList.remove('hidden-mobile');
            $('emptyState').style.display = 'flex';
            $('chatHeader').style.display = 'none';
            $('messageList').style.display = 'none';
            $('inputArea').style.display = 'none';
            state.currentConversaId = null;
        });

        // Transfer modal
        $('transferBtn').addEventListener('click', () => { $('transferModal').style.display = 'flex'; });
        $('transferModalClose').addEventListener('click', () => { $('transferModal').style.display = 'none'; });
        $('transferCancelBtn').addEventListener('click', () => { $('transferModal').style.display = 'none'; });
        $('transferConfirmBtn').addEventListener('click', () => {
            if (!state.currentConversaId) return;
            const target = $('transferTarget').value;
            const motivo = $('transferMotivo').value.trim();
            if (!target) return;
            const [tipo, id] = target.split(':');
            const body = { motivo };
            if (tipo === 'agente') body.para_agente_id = parseInt(id);
            else if (tipo === 'equipe') body.para_equipe_id = parseInt(id);
            else if (tipo === 'fila') body.para_fila_id = parseInt(id);
            fetchJSON('/inbox/api/conversas/' + state.currentConversaId + '/transferir/', {
                method: 'POST', body: JSON.stringify(body),
            }).then(d => {
                if (d.success) {
                    $('transferModal').style.display = 'none';
                    $('transferMotivo').value = '';
                    loadConversas(); loadConversaDetalhe(state.currentConversaId); loadMensagens(state.currentConversaId);
                }
            });
        });

        // Ticket modal
        $('createTicketBtn').addEventListener('click', () => {
            $('ticketModal').style.display = 'flex';
            $('ticketTitulo').value = '';
            $('ticketTitulo').focus();
        });
        $('ticketModalClose').addEventListener('click', () => { $('ticketModal').style.display = 'none'; });
        $('ticketCancelBtn').addEventListener('click', () => { $('ticketModal').style.display = 'none'; });
        $('ticketConfirmBtn').addEventListener('click', () => {
            const titulo = $('ticketTitulo').value.trim();
            if (!titulo || !state.currentConversaId) return;
            fetchJSON('/inbox/api/conversas/' + state.currentConversaId + '/ticket/', {
                method: 'POST', body: JSON.stringify({ titulo }),
            }).then(d => {
                if (d.success) {
                    $('ticketModal').style.display = 'none';
                    loadConversaDetalhe(state.currentConversaId); loadMensagens(state.currentConversaId);
                }
            });
        });

        // Close dropdowns on outside click
        document.addEventListener('click', e => {
            const dd = document.getElementById('quickResponseDropdown');
            if (dd && !dd.contains(e.target)) dd.style.display = 'none';
            const rm = document.getElementById('resolveMenu');
            if (rm && !rm.contains(e.target) && !e.target.closest('.chat-resolve-group')) rm.style.display = 'none';
            const fd = document.getElementById('filterDropdown');
            if (fd && !fd.contains(e.target) && !e.target.closest('#filterMenuBtn')) fd.style.display = 'none';
            const ep = document.getElementById('emojiPicker');
            if (ep && !ep.contains(e.target) && !e.target.closest('#emojiBtn')) ep.style.display = 'none';
        });

        // Load
        loadConversas();
        loadRespostasRapidas();
        connectWebSocket();
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
