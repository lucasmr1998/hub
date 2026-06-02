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
        modoFilter: 'humano', // 'bot', 'humano', '' (todas)
        sortOrder: 'desc', // 'desc' = mais recente, 'asc' = mais antiga
        searchQuery: '',
        inputMode: 'reply', // 'reply' ou 'note'
        respostasRapidas: [],
        pollTimer: null,
        messagePollTimer: null,
        ws: null,
        wsConnected: false,
        iaCards: {},  // map msgId -> { sugestoes, lead_id } pra sobreviver ao polling
    };

    // Status dos agentes (injetado pelo template)
    const AGENTES_STATUS = window.AGENTES_STATUS || {};
    function _agenteStatusDot(agenteId) {
        const s = AGENTES_STATUS[agenteId];
        if (!s) return '<i class="fas fa-user" style="font-size:9px;margin-right:2px;"></i>';
        const cor = s === 'online' ? '#22c55e' : s === 'ausente' ? '#f59e0b' : '#94a3b8';
        return `<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:${cor};margin-right:3px;"></span>`;
    }

    // ── Utilidades ────────────────────────────────────────────────────

    function fetchJSON(url, opts = {}) {
        const defaults = {
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
        };
        return fetch(url, { ...defaults, ...opts }).then(r => r.json()).catch(e => ({ error: e.message }));
    }

    // Salva edicao inline de campo do Lead/CRM (nome do lead, titulo da oport)
    // Exposta no window porque os inputs usam onblur inline.
    window.inboxSalvarCampo = function (inputEl) {
        const target = inputEl.dataset.editTarget;
        const field = inputEl.dataset.field;
        const val = (inputEl.value || '').trim();
        const original = inputEl.dataset.original || '';
        if (val === original) return;
        if (!val) { inputEl.value = original; return; }
        let url;
        if (target === 'lead')      url = '/api/leads/' + inputEl.dataset.leadId + '/editar/';
        else if (target === 'oport') url = '/crm/oportunidades/' + inputEl.dataset.opId + '/editar/';
        else return;
        inputEl.disabled = true;
        fetchJSON(url, {
            method: 'PUT',
            body: JSON.stringify({ [field]: val }),
        }).then(d => {
            if (d && !d.error) {
                inputEl.dataset.original = val;
                if (typeof toast === 'function') toast('Atualizado', field + ': ' + val, 'success');
            } else {
                inputEl.value = original;
                const msg = (d && d.error) || 'Falha ao atualizar';
                if (typeof toast === 'function') toast('Erro', msg, 'danger');
                else alert(msg);
            }
        }).finally(() => { inputEl.disabled = false; });
    };

    // Movimentar estagio da oportunidade direto do painel Lead/CRM do Inbox.
    // Exposta no window porque o select usa onchange inline.
    window.inboxMoverEstagio = function (selectEl) {
        const opId = selectEl.dataset.opId;
        const novoId = selectEl.value;
        const current = selectEl.dataset.current;
        if (!opId || !novoId || novoId === current) return;
        const nomeNovo = selectEl.options[selectEl.selectedIndex].text;
        selectEl.disabled = true;
        fetchJSON('/crm/pipeline/mover/', {
            method: 'POST',
            body: JSON.stringify({
                oportunidade_id: opId,
                estagio_id: novoId,
                motivo: 'Movido pelo Inbox',
            }),
        }).then(d => {
            if (d && (d.ok || d.success)) {
                selectEl.dataset.current = novoId;
                if (typeof toast === 'function') toast('Estagio atualizado', 'Movido pra ' + nomeNovo, 'success');
            } else {
                selectEl.value = current;
                const msg = (d && (d.erro || d.error)) || 'Falha ao mover estagio';
                if (typeof toast === 'function') toast('Erro', msg, 'danger');
                else alert(msg);
            }
        }).finally(() => { selectEl.disabled = false; });
    };

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
               d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
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

    // Nome curto do agente: primeiro nome + inicial do sobrenome (ex: "Flavia M.")
    function nomeAgenteCurto(name) {
        if (!name) return '';
        const p = name.trim().split(/\s+/);
        if (p.length < 2) return p[0];
        return p[0] + ' ' + p[1][0].toUpperCase() + '.';
    }

    function esc(s) {
        const d = document.createElement('div'); d.textContent = s; return d.innerHTML;
    }

    function formatWA(s) {
        if (!s) return '';
        let t = esc(s);
        t = t.replace(/\*([^*]+)\*/g, '<strong>$1</strong>');
        t = t.replace(/\b_([^_]+)_\b/g, '<em>$1</em>');
        t = t.replace(/~([^~]+)~/g, '<del>$1</del>');
        t = t.replace(/```([^`]+)```/g, '<code>$1</code>');
        t = t.replace(/\n/g, '<br>');
        return t;
    }

    // URLs .enc do WhatsApp sao criptografadas e nao abrem no navegador.
    function midiaUsavel(url) {
        return !!url && !/\.enc(\?|$)/i.test(url) && !/whatsapp\.net/i.test(url);
    }

    // Renderiza o corpo da mensagem conforme o tipo de conteudo.
    function renderConteudo(m) {
        const tipo = m.tipo_conteudo || 'texto';
        const url = m.arquivo_url || '';
        const usavel = midiaUsavel(url);
        // Legenda real (ignora labels genericos tipo "📷 Imagem")
        const legenda = /^[📷📎🎤🎥]/.test(m.conteudo || '') ? '' : (m.conteudo || '');
        const cap = legenda ? `<div>${formatWA(legenda)}</div>` : '';

        if (tipo === 'imagem') {
            if (usavel) {
                return `<div class="msg-media"><img src="${esc(url)}" class="msg-media-img" `
                    + `loading="lazy" onclick="window.open(this.src,'_blank')" `
                    + `onerror="this.outerHTML='📷 Imagem'"></div>` + cap;
            }
            return `<div class="msg-file"><i class="fas fa-image"></i> Imagem</div>` + cap;
        }
        if (tipo === 'audio') {
            if (usavel) return `<audio controls src="${esc(url)}" class="msg-media-audio"></audio>`;
            return `<div class="msg-file"><i class="fas fa-microphone"></i> Áudio</div>`;
        }
        if (tipo === 'video') {
            if (usavel) return `<video controls src="${esc(url)}" class="msg-media-img"></video>` + cap;
            return `<div class="msg-file"><i class="fas fa-video"></i> Vídeo</div>` + cap;
        }
        if (tipo === 'arquivo' || tipo === 'documento') {
            const nome = m.arquivo_nome || (m.conteudo || '').replace(/^📎\s*/, '') || 'Documento';
            const card = `<div class="msg-file"><i class="fas fa-file-alt"></i> <span>${esc(nome)}</span></div>`;
            return usavel ? `<a href="${esc(url)}" target="_blank" class="msg-file-link">${card}</a>` : card;
        }
        return `<div>${formatWA(m.conteudo)}</div>`;
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
        if (state.modoFilter) url += 'modo=' + state.modoFilter + '&';
        if (state.sortOrder) url += 'ordem=' + state.sortOrder + '&';
        if (state.searchQuery) url += 'q=' + encodeURIComponent(state.searchQuery) + '&';

        fetchJSON(url).then(data => {
            if (data.error) return;
            state.conversas = data.conversas || [];
            renderConversaList();
            updateCounts(data.counts);
        });
    }

    function updateCounts(counts) {
        // Usa as contagens autoritativas do backend (Minhas = atribuidas a mim,
        // nao "qualquer agente"). Fallback pro tamanho da lista se nao vierem.
        if (counts) {
            document.getElementById('countAll').textContent = counts.todas;
            document.getElementById('countMine').textContent = counts.minhas;
            document.getElementById('countUnassigned').textContent = counts.nao_atribuidas;
        } else {
            document.getElementById('countAll').textContent = state.conversas.length;
        }
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
            <div class="conv-card ${isActive ? 'active' : ''} ${c.alerta_inatividade ? 'has-alerta' : ''}" data-id="${c.id}">
                <div class="conv-avatar" style="background:${c.canal_tipo === 'whatsapp' ? '#25D366' : '#3b82f6'}">${getInitials(c.contato_nome)}</div>
                <div class="conv-body">
                    <div class="conv-top">
                        <span class="conv-inbox-label">${esc(canalLabel)}</span>
                        ${c.modo_atendimento === 'bot' ? '<span class="conv-inbox-label" style="background:#f3e8ff;color:#6b21a8;"><i class="fas fa-robot" style="font-size:9px;margin-right:2px;"></i>Bot</span>' : ''}
                        ${c.alerta_inatividade ? '<span class="conv-inbox-label" style="background:#fee2e2;color:#991b1b;"><i class="fas fa-exclamation-triangle" style="font-size:9px;margin-right:2px;"></i>Inativo</span>' : ''}
                        ${c.agente_nome && c.modo_atendimento !== 'bot' ? `<span class="conv-agent-name">${_agenteStatusDot(c.agente_id)}${esc(nomeAgenteCurto(c.agente_nome))}</span>` : ''}
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

    function _aplicarEstadoAssumida(assumida) {
        const banner = document.getElementById('assumirBanner');
        const input  = document.getElementById('inputArea');
        const msgs   = document.getElementById('messageList');
        banner.style.display = assumida ? 'none' : 'flex';
        msgs.style.display   = assumida ? 'flex'  : 'none';
        input.style.display  = assumida ? 'block' : 'none';
    }

    function selectConversa(id) {
        state.currentConversaId = id;
        document.querySelectorAll('.conv-card').forEach(el => {
            el.classList.toggle('active', parseInt(el.dataset.id) === id);
        });

        document.getElementById('emptyState').style.display = 'none';
        document.getElementById('chatHeader').style.display = 'flex';
        document.getElementById('assumirBanner').style.display = 'none';
        document.getElementById('messageList').style.display = 'flex';
        document.getElementById('inputArea').style.display = 'block';
        document.getElementById('inboxSidebar')?.classList.add('hidden-mobile');
        document.getElementById('inboxChat')?.classList.add('show-mobile');

        wsSend({ action: 'join_conversa', conversa_id: id });
        loadConversaDetalhe(id);
        loadMensagens(id, true);
        loadRespostasRapidas();
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

            // Botao Resolver/Reabrir muda conforme status da conversa
            state.currentConversaStatus = data.status || 'aberta';
            // T148 — guardar oportunidade vinculada pra decidir se mostra bloco no modal de resolver
            state.currentConversaOportunidadeId = (data.oportunidade_info && data.oportunidade_info.id) || null;
            const rb = document.getElementById('resolveBtn');
            if (rb) {
                if (state.currentConversaStatus === 'resolvida') {
                    rb.textContent = 'Reabrir';
                    rb.classList.add('is-reopened');
                } else {
                    rb.textContent = 'Resolver';
                    rb.classList.remove('is-reopened');
                }
            }

            // Estado assumida — controla banner + visibilidade histórico e input
            _aplicarEstadoAssumida(data.assumida !== false);

            // Labels
            const chipDiv = document.getElementById('labelChips');
            if (data.etiquetas && data.etiquetas.length) {
                chipDiv.innerHTML = data.etiquetas.map(e =>
                    `<span class="label-chip" data-id="${e.id}" style="background:${e.cor_hex}">${esc(e.nome)}</span>`
                ).join('');
            } else {
                chipDiv.innerHTML = '';
            }

            // Lead info + Oportunidade editavel (estagio + tags + atalho CRM)
            const leadDiv = document.getElementById('ctxLeadInfo');
            if (data.lead_info) {
                const l = data.lead_info;
                let html = `
                    <div class="ctx-info-row"><span class="ctx-info-label">Nome</span><input class="ctx-editable-input ctx-info-value" data-edit-target="lead" data-lead-id="${l.id}" data-field="nome_razaosocial" data-original="${esc(l.nome)}" value="${esc(l.nome)}" onblur="inboxSalvarCampo(this)" onkeydown="if(event.key==='Enter'){event.preventDefault();this.blur();}else if(event.key==='Escape'){this.value=this.dataset.original;this.blur();}"></div>
                    <div class="ctx-info-row"><span class="ctx-info-label">Origem</span><span class="ctx-info-value">${esc(l.origem)}</span></div>
                    <div class="ctx-info-row"><span class="ctx-info-label">Score</span><span class="ctx-info-value">${l.score || '—'}</span></div>
                `;
                if (data.oportunidade_info) {
                    const op = data.oportunidade_info;
                    const estagiosList = op.estagios_disponiveis || [];
                    let estagioCell;
                    if (estagiosList.length) {
                        const opts = estagiosList.map(e => {
                            const sel = e.id === op.estagio_id ? ' selected' : '';
                            return `<option value="${e.id}"${sel}>${esc(e.nome)}</option>`;
                        }).join('');
                        estagioCell = `<select class="ctx-stage-select" data-op-id="${op.id}" data-current="${op.estagio_id}" onchange="inboxMoverEstagio(this)">${opts}</select>`;
                    } else {
                        estagioCell = `<span class="ctx-info-value">${esc(op.estagio || '—')}</span>`;
                    }
                    const tagsHtml = (op.tags || []).map(t =>
                        `<span class="ctx-tag-chip" style="background:${esc(t.cor_hex || '#94a3b8')};">${esc(t.nome)}</span>`
                    ).join('');
                    html += `
                        <div class="ctx-info-row"><span class="ctx-info-label">Oport. #${op.id}</span><input class="ctx-editable-input ctx-info-value" data-edit-target="oport" data-op-id="${op.id}" data-field="titulo" data-original="${esc(op.titulo)}" value="${esc(op.titulo)}" onblur="inboxSalvarCampo(this)" onkeydown="if(event.key==='Enter'){event.preventDefault();this.blur();}else if(event.key==='Escape'){this.value=this.dataset.original;this.blur();}"></div>
                        <div class="ctx-info-row"><span class="ctx-info-label">Valor</span><span class="ctx-info-value">R$ ${op.valor_estimado}</span></div>
                        <div class="ctx-info-row ctx-stage-row"><span class="ctx-info-label">Estágio</span>${estagioCell}</div>
                        ${tagsHtml ? `<div class="ctx-tags-row">${tagsHtml}</div>` : ''}
                        <a class="ctx-crm-link" href="/crm/oportunidades/${op.id}/" target="_blank" rel="noopener">
                            Abrir no CRM <i class="fas fa-external-link-alt"></i>
                        </a>
                    `;
                }
                leadDiv.innerHTML = html;
            } else {
                leadDiv.innerHTML = '<p class="ctx-empty">Lead não vinculado</p>';
            }

            // Ticket
            const ticketInfo = document.getElementById('ticketInfo');
            const ticketBtn = document.getElementById('createTicketBtn');
            if (ticketInfo && ticketBtn) {
                if (data.ticket_info) {
                    ticketInfo.style.display = 'block';
                    ticketInfo.innerHTML = `<div class="ctx-info-row"><span class="ctx-info-label">#${data.ticket_info.numero}</span><span class="ctx-info-value">${esc(data.ticket_info.titulo)}</span></div>`;
                    ticketBtn.style.display = 'none';
                } else {
                    ticketInfo.style.display = 'none';
                    ticketBtn.style.display = 'inline-flex';
                }
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

    function loadMensagens(id, forceScroll) {
        fetchJSON('/inbox/api/conversas/' + id + '/mensagens/').then(data => {
            if (data.error) return;
            renderMensagens(data.mensagens || [], forceScroll);
        });
    }

    function renderMensagens(msgs, forceScroll) {
        const container = document.getElementById('messageList');
        if (!msgs.length) {
            container.innerHTML = '<div class="inbox-loading"><p>Nenhuma mensagem</p></div>';
            return;
        }

        // Preserva a posicao do scroll. So rola pro fim se foi pedido
        // explicitamente (abriu a conversa) ou se o usuario ja estava perto
        // do fim — senao o polling jogaria a tela pra baixo enquanto le.
        const prevTop = container.scrollTop;
        const stickBottom = forceScroll ||
            (container.scrollHeight - prevTop - container.clientHeight < 120);

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

            html += `<div class="msg-bubble ${t}" data-msg-id="${m.id}">`;
            if (t === 'contato' || t === 'bot') html += `<div class="msg-sender">${esc(m.remetente_nome)}</div>`;
            html += renderConteudo(m);
            html += `<div class="msg-time">${formatFullTime(m.data_envio)} <span class="msg-status">${statusIcon}</span></div>`;
            if (m.erro_envio) html += `<div style="font-size:10px;color:#ef4444;margin-top:2px;"><i class="fas fa-exclamation-triangle"></i> ${esc(m.erro_envio)}</div>`;
            if (t === 'contato' && (m.conteudo || '').trim().length > 3) {
                html += `<button type="button" class="msg-ia-btn" data-msg-id="${m.id}" title="Sugerir campos para preenchimento via IA">
                    <i class="fas fa-magic"></i> Extrair dados
                </button>`;
            }
            html += `</div>`;
            html += `<div class="ia-suggest-slot" data-slot-msg="${m.id}"></div>`;
        });

        container.innerHTML = html;
        // Restaura cards IA abertos que sobreviveram ao polling
        _rerenderAllIACards();
        if (stickBottom) {
            container.scrollTop = container.scrollHeight;
            // imagens carregam async e mudam a altura — re-fixa no fim.
            container.querySelectorAll('img').forEach(img => {
                if (!img.complete) {
                    img.addEventListener('load', () => {
                        container.scrollTop = container.scrollHeight;
                    }, { once: true });
                }
            });
        } else {
            container.scrollTop = prevTop;
        }
    }

    // ── Sugestoes IA de campos (v1, manual) ───────────────────────────

    function _findSlot(msgId) {
        return document.querySelector(`.ia-suggest-slot[data-slot-msg="${msgId}"]`);
    }

    function extrairCamposIA(msgId) {
        const slot = _findSlot(msgId);
        const btn = document.querySelector(`.msg-ia-btn[data-msg-id="${msgId}"]`);
        if (!slot) return;
        // Toggle: se ja tem card aberto, fecha
        if (state.iaCards[msgId]) {
            delete state.iaCards[msgId];
            slot.innerHTML = '';
            return;
        }
        state.iaCards[msgId] = { loading: true };
        slot.innerHTML = '<div class="ia-card ia-loading"><i class="fas fa-spinner fa-spin"></i> Analisando mensagem...</div>';
        if (btn) btn.disabled = true;

        fetchJSON(`/inbox/api/mensagens/${msgId}/sugerir-campos/`, { method: 'POST', body: '{}' })
            .then(d => {
                const b = document.querySelector(`.msg-ia-btn[data-msg-id="${msgId}"]`);
                if (b) b.disabled = false;
                if (d.error) {
                    state.iaCards[msgId] = { error: d.error };
                } else {
                    state.iaCards[msgId] = {
                        sugestoes: d.sugestoes || [],
                        rejeitadas: d.rejeitadas || [],
                        lead_id: d.lead_id,
                    };
                }
                _rerenderIACard(msgId);
            })
            .catch(err => {
                const b = document.querySelector(`.msg-ia-btn[data-msg-id="${msgId}"]`);
                if (b) b.disabled = false;
                state.iaCards[msgId] = { error: String(err) };
                _rerenderIACard(msgId);
            });
    }

    function _rerenderIACard(msgId) {
        const slot = _findSlot(msgId);
        if (!slot) return;
        const st = state.iaCards[msgId];
        if (!st) { slot.innerHTML = ''; return; }
        if (st.loading) {
            slot.innerHTML = '<div class="ia-card ia-loading"><i class="fas fa-spinner fa-spin"></i> Analisando mensagem...</div>';
            return;
        }
        if (st.error) {
            slot.innerHTML = `<div class="ia-card ia-error"><i class="fas fa-exclamation-triangle"></i> ${esc(st.error)}</div>`;
            return;
        }
        renderCardSugestoes(slot, st, msgId);
    }

    function _rerenderAllIACards() {
        Object.keys(state.iaCards).forEach(mid => _rerenderIACard(parseInt(mid)));
    }

    const CAMPO_LABELS = {
        nome_razaosocial: 'Nome',
        cpf_cnpj: 'CPF/CNPJ',
        email: 'E-mail',
        data_nascimento: 'Nascimento',
        rg: 'RG',
        cep: 'CEP',
        cidade: 'Cidade',
        estado: 'UF',
        nome_mae: 'Nome da mãe',
        endereco: 'Endereço',
        observacoes: 'Observações',
    };

    const MOTIVO_REJEICAO_LABELS = {
        'cpf checksum': 'CPF com dígitos verificadores inválidos — confirme com o cliente',
        'cpf/cnpj tamanho': 'CPF/CNPJ não tem o tamanho esperado',
        'cep tamanho': 'CEP precisa ter 8 dígitos',
        'regex email': 'Formato de e-mail inválido',
        'regex data_nascimento': 'Data fora do formato esperado',
        'regex estado': 'UF deve ter 2 letras maiúsculas',
        'confianca <0.7': 'Baixa confiança da IA',
        'trecho nao bate no texto': 'Trecho não confere com a mensagem',
        'campo invalido': 'Campo fora do catálogo',
        'sem trecho_origem': 'IA não citou o trecho de origem',
        'valor curto': 'Valor muito curto',
    };
    function _labelMotivo(m) { return MOTIVO_REJEICAO_LABELS[m] || m; }

    function renderCardSugestoes(slot, st, msgId) {
        const sugs = st.sugestoes || [];
        const rejs = st.rejeitadas || [];
        const leadId = st.lead_id;
        if (!sugs.length && !rejs.length) {
            slot.innerHTML = `<div class="ia-card ia-empty"><i class="fas fa-info-circle"></i> Nenhum campo identificado nesta mensagem. <span class="ia-card-close" data-msg-close="${msgId}">×</span></div>`;
            return;
        }
        if (sugs.length && !leadId) {
            slot.innerHTML = `<div class="ia-card ia-error"><i class="fas fa-exclamation-triangle"></i> Conversa sem lead vinculado — nao da pra aplicar.</div>`;
            return;
        }
        let html = `<div class="ia-card">
            <div class="ia-card-head"><i class="fas fa-magic"></i> ${sugs.length} dado(s) identificado(s)${rejs.length ? ` · ${rejs.length} a verificar` : ''} <span class="ia-card-close" data-msg-close="${msgId}">×</span></div>
            <div class="ia-card-body">`;
        sugs.forEach((s, i) => {
            const label = CAMPO_LABELS[s.campo] || s.campo;
            const conf = Math.round(s.confianca * 100);
            const checked = (st.unchecked && st.unchecked.includes(i)) ? '' : 'checked';
            html += `<label class="ia-sug-item">
                <input type="checkbox" class="ia-sug-check" data-i="${i}" data-msg="${msgId}" ${checked}>
                <div class="ia-sug-info">
                    <span class="ia-sug-label">${esc(label)}:</span>
                    <span class="ia-sug-valor">${esc(s.valor)}</span>
                    <span class="ia-sug-trecho" title="Trecho original">"${esc(s.trecho_origem)}"</span>
                    <span class="ia-sug-conf">${conf}%</span>
                </div>
            </label>`;
        });
        html += `</div>`;

        if (rejs.length) {
            html += `<div class="ia-card-rejeitadas">
                <div class="ia-rej-head"><i class="fas fa-exclamation-triangle"></i> Identificado mas rejeitado pelo validador (confirme manualmente):</div>`;
            rejs.forEach(r => {
                const label = CAMPO_LABELS[r.campo] || r.campo;
                const motivos = (r.motivos || []).map(_labelMotivo).join(' · ');
                html += `<div class="ia-rej-item">
                    <span class="ia-rej-label">${esc(label)}:</span>
                    <span class="ia-rej-valor">${esc(r.valor || '')}</span>
                    ${r.trecho_origem ? `<span class="ia-sug-trecho">"${esc(r.trecho_origem)}"</span>` : ''}
                    <div class="ia-rej-motivo">${esc(motivos)}</div>
                </div>`;
            });
            html += `</div>`;
        }

        if (sugs.length && leadId) {
            html += `<div class="ia-card-actions">
                <button type="button" class="ia-btn ia-btn-primary" data-apply="${msgId}">
                    <i class="fas fa-check"></i> Aplicar selecionados no Lead
                </button>
                <button type="button" class="ia-btn ia-btn-ghost" data-cancel="${msgId}">Cancelar</button>
            </div>`;
        } else {
            html += `<div class="ia-card-actions">
                <button type="button" class="ia-btn ia-btn-ghost" data-cancel="${msgId}">Fechar</button>
            </div>`;
        }
        html += `</div>`;
        slot.innerHTML = html;
    }

    function aplicarSugestoesIA(msgId) {
        const slot = _findSlot(msgId);
        const st = state.iaCards[msgId];
        if (!slot || !st || !st.sugestoes) return;
        const sugs = st.sugestoes;
        const leadId = st.lead_id;
        const checks = slot.querySelectorAll('.ia-sug-check');
        const selecionadas = [];
        checks.forEach(c => { if (c.checked) selecionadas.push({campo: sugs[+c.dataset.i].campo, valor: sugs[+c.dataset.i].valor}); });
        if (!selecionadas.length) {
            delete state.iaCards[msgId];
            slot.innerHTML = '';
            return;
        }

        const applyBtn = slot.querySelector('[data-apply]');
        if (applyBtn) { applyBtn.disabled = true; applyBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Aplicando...'; }

        fetchJSON(`/inbox/api/leads/${leadId}/aplicar-sugestoes/`, {
            method: 'POST', body: JSON.stringify({sugestoes: selecionadas}),
        }).then(d => {
            if (d.error) {
                state.iaCards[msgId] = { error: 'Aplicar: ' + d.error };
                _rerenderIACard(msgId);
                return;
            }
            const okN = (d.aplicados || []).length;
            const igN = (d.ignorados || []).length;
            delete state.iaCards[msgId];
            const s = _findSlot(msgId);
            if (s) s.innerHTML = `<div class="ia-card ia-success"><i class="fas fa-check-circle"></i> ${okN} campo(s) atualizado(s) no Lead${igN ? ` (${igN} ignorado(s))` : ''}.</div>`;
            if (typeof loadConversaDetalhe === 'function' && state.currentConversaId) {
                loadConversaDetalhe(state.currentConversaId);
            }
        }).catch(err => {
            state.iaCards[msgId] = { error: String(err) };
            _rerenderIACard(msgId);
        });
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
        // Se houver conversa ativa, pede o servidor pra renderizar as variáveis
        const url = state.currentConversaId
            ? '/inbox/api/respostas-rapidas/?conversa=' + state.currentConversaId
            : '/inbox/api/respostas-rapidas/';
        fetchJSON(url).then(d => { state.respostasRapidas = d.respostas || []; });
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

        list.innerHTML = items.map(r => {
            // Usa renderizado se disponível (conversa ativa); senão, conteudo cru
            const previewText = r.conteudo_renderizado || r.conteudo;
            const insertText = r.conteudo_renderizado || r.conteudo;
            const hasVars = r.conteudo.includes('{{');
            return `
                <div class="quick-response-item" data-content="${esc(insertText)}">
                    <span class="quick-response-item-title">${esc(r.titulo)}${hasVars && r.conteudo_renderizado ? ' <span style="font-size:10px;color:#10B981;">●</span>' : ''}</span>
                    ${r.atalho ? `<span class="quick-response-item-shortcut">${esc(r.atalho)}</span>` : ''}
                    <div class="quick-response-item-preview">${esc(previewText.substring(0, 80))}</div>
                </div>`;
        }).join('');

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
        // WebSocket requer ASGI server (Daphne/Uvicorn).
        // Em dev com runserver, usa polling.
        // Tenta uma vez, se falhar usa polling silenciosamente.
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
                // Não reconecta automaticamente em dev
            };
            state.ws.onerror = () => {
                state.wsConnected = false;
                if (!state.pollTimer) state.pollTimer = setInterval(loadConversas, POLL_INTERVAL);
            };
        } catch(e) {
            state.pollTimer = setInterval(loadConversas, POLL_INTERVAL);
        }
    }

    function _notificarNovaMsg(conversaId) {
        // Som de notificação
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.frequency.value = 880;
            osc.type = 'sine';
            gain.gain.setValueAtTime(0.15, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
            osc.start(ctx.currentTime);
            osc.stop(ctx.currentTime + 0.3);
        } catch (_) {}

        // Notificação do browser (se permitida)
        if ('Notification' in window && Notification.permission === 'granted') {
            new Notification('Nova mensagem — Hubtrix', { body: 'Você tem uma nova mensagem no Inbox.', icon: '/static/sistema/img/logo.png' });
        } else if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }

        // Badge no título da página
        document.title = '● ' + document.title.replace(/^● /, '');
    }

    function handleWsMessage(data) {
        if (data.type === 'nova_mensagem') {
            loadConversas();
            if (data.conversa_id === state.currentConversaId) {
                loadMensagens(state.currentConversaId);
            } else {
                _notificarNovaMsg(data.conversa_id);
            }
        } else if (data.type === 'conversa_atualizada') {
            loadConversas();
            if (data.conversa_id === state.currentConversaId) loadConversaDetalhe(state.currentConversaId);
        }
    }

    // Remove badge do título ao focar na aba
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) document.title = document.title.replace(/^● /, '');
    });

    function wsSend(data) {
        if (state.ws && state.wsConnected) state.ws.send(JSON.stringify(data));
    }

    // ── Event Bindings ────────────────────────────────────────────────

    // Faz o container do inbox preencher exatamente da sua posicao real ate o
    // fim da viewport. Sem isso, o CSS usa calc(100vh - 52px) fixo; se a topbar
    // tiver outra altura, a area de envio (botao Enviar) fica cortada embaixo.
    function ajustarAlturaInbox() {
        const c = document.getElementById('inboxApp');
        if (!c) return;
        const top = c.getBoundingClientRect().top + window.scrollY;
        c.style.height = Math.max(240, window.innerHeight - top) + 'px';
    }

    function init() {
        ajustarAlturaInbox();
        window.addEventListener('resize', ajustarAlturaInbox);

        // Heartbeat — pinga o backend a cada 60s pra manter agente "online"
        // Cron marca offline quem nao pinga ha >5min
        function _ping() {
            try { fetchJSON('/inbox/api/agente/heartbeat/', { method: 'POST', body: '{}' }); } catch (e) {}
        }
        _ping();
        setInterval(_ping, 60000);

        // Delegation pros botoes de sugestoes IA dentro de #messageList
        const msgList = document.getElementById('messageList');
        if (msgList) {
            msgList.addEventListener('click', function(e) {
                const ext = e.target.closest('.msg-ia-btn');
                if (ext) { e.stopPropagation(); extrairCamposIA(parseInt(ext.dataset.msgId)); return; }
                const apply = e.target.closest('[data-apply]');
                if (apply) { e.stopPropagation(); aplicarSugestoesIA(parseInt(apply.dataset.apply)); return; }
                const cancel = e.target.closest('[data-cancel]');
                if (cancel) { e.stopPropagation(); const mid = parseInt(cancel.dataset.cancel); delete state.iaCards[mid]; const slot = _findSlot(mid); if (slot) slot.innerHTML = ''; return; }
                const close = e.target.closest('[data-msg-close]');
                if (close) { e.stopPropagation(); const mid = parseInt(close.dataset.msgClose); delete state.iaCards[mid]; const slot = _findSlot(mid); if (slot) slot.innerHTML = ''; return; }
            });
        }

        // Modo tabs (Bot / Humano / Todas) — admin only
        document.querySelectorAll('.inbox-modo-tab').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.inbox-modo-tab').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                state.modoFilter = btn.dataset.modo;
                loadConversas();
            });
        });

        // Assign tabs (Minhas / Não atribuídas / Todas)
        document.querySelectorAll('.inbox-atrib-tab').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.inbox-atrib-tab').forEach(b => b.classList.remove('active'));
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

        // Resolve button group — alterna entre Resolver e Reabrir conforme status atual
        const reloadAfterResolve = () => {
            loadConversas();
            loadConversaDetalhe(state.currentConversaId);
            loadMensagens(state.currentConversaId);
        };
        const abrirModalMotivo = () => {
            const sel = $('resolveMotivoSelect');
            if (sel) sel.value = '';
            // T148 — reset bloco oportunidade
            const opEstagio = $('resolveOpEstagio');
            if (opEstagio) opEstagio.value = '';
            const opMP = $('resolveOpMotivoPerda'); if (opMP) opMP.value = '';
            const opCon = $('resolveOpConcorrente'); if (opCon) opCon.value = '';
            const opObs = $('resolveOpObs'); if (opObs) opObs.value = '';
            const opPerda = $('resolveOpPerdaFields'); if (opPerda) opPerda.style.display = 'none';
            // Bloco visivel so se conversa atual tem oportunidade
            const opBlock = $('resolveOpBlock');
            if (opBlock) opBlock.style.display = state.currentConversaOportunidadeId ? 'block' : 'none';
            $('resolveMotivoModal').style.display = 'flex';
        };
        const fecharModalMotivo = () => { $('resolveMotivoModal').style.display = 'none'; };

        // T148 — Mostra/oculta campos de perda conforme estagio destino
        const opEstagioSel = document.getElementById('resolveOpEstagio');
        if (opEstagioSel) {
            opEstagioSel.addEventListener('change', () => {
                const opt = opEstagioSel.options[opEstagioSel.selectedIndex];
                const ehPerdido = opt && opt.dataset.perdido === '1';
                const perdaFields = document.getElementById('resolveOpPerdaFields');
                if (perdaFields) perdaFields.style.display = ehPerdido ? 'block' : 'none';
            });
        }

        $('resolveBtn').addEventListener('click', () => {
            if (!state.currentConversaId) return;
            if (state.currentConversaStatus === 'resolvida') {
                fetchJSON('/inbox/api/conversas/' + state.currentConversaId + '/reabrir/', { method: 'POST' })
                    .then(reloadAfterResolve);
            } else {
                abrirModalMotivo();
            }
        });
        // Modal motivo: confirm/cancel
        ['resolveMotivoCancel', 'resolveMotivoClose'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.addEventListener('click', fecharModalMotivo);
        });
        const motivoConfirmBtn = document.getElementById('resolveMotivoConfirm');
        if (motivoConfirmBtn) {
            motivoConfirmBtn.addEventListener('click', () => {
                if (!state.currentConversaId) return;
                const payload = {};
                const motivoId = $('resolveMotivoSelect').value || null;
                if (motivoId) payload.motivo_id = parseInt(motivoId);

                // T148 — Campos opcionais de oportunidade (so se conversa tem opp e user escolheu estagio)
                if (state.currentConversaOportunidadeId) {
                    const opEstagioId = $('resolveOpEstagio')?.value || null;
                    if (opEstagioId) {
                        payload.oportunidade_estagio_id = parseInt(opEstagioId);
                        const opt = $('resolveOpEstagio').options[$('resolveOpEstagio').selectedIndex];
                        if (opt && opt.dataset.perdido === '1') {
                            const mpId = $('resolveOpMotivoPerda')?.value || null;
                            const conc = $('resolveOpConcorrente')?.value.trim() || null;
                            const obs = $('resolveOpObs')?.value.trim() || null;
                            if (mpId) payload.oportunidade_motivo_perda_ref_id = parseInt(mpId);
                            if (conc) payload.oportunidade_concorrente = conc;
                            if (obs) payload.oportunidade_motivo_perda_texto = obs;
                        }
                    }
                }
                fetchJSON('/inbox/api/conversas/' + state.currentConversaId + '/resolver/', {
                    method: 'POST', body: JSON.stringify(payload),
                }).then(() => { fecharModalMotivo(); reloadAfterResolve(); });
            });
        }

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

        // Assumir conversa
        $('assumirBtn').addEventListener('click', () => {
            if (!state.currentConversaId) return;
            fetchJSON('/inbox/api/conversas/' + state.currentConversaId + '/assumir/', { method: 'POST' })
                .then(data => {
                    if (data.success) {
                        _aplicarEstadoAssumida(true);
                        loadConversaDetalhe(state.currentConversaId);
                        loadMensagens(state.currentConversaId, true);
                    } else {
                        alert(data.error || 'Não foi possível assumir a conversa.');
                    }
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
            document.getElementById('inboxChat')?.classList.remove('show-mobile');
            $('emptyState').style.display = 'flex';
            $('chatHeader').style.display = 'none';
            $('messageList').style.display = 'none';
            $('inputArea').style.display = 'none';
            state.currentConversaId = null;
        });

        // Resumir conversa via IA
        const resumirBtn = $('resumirBtn');
        if (resumirBtn) {
            resumirBtn.addEventListener('click', () => {
                if (!state.currentConversaId) return;
                resumirBtn.disabled = true;
                const original = resumirBtn.innerHTML;
                resumirBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
                fetch('/inbox/api/conversas/' + state.currentConversaId + '/resumir/')
                    .then(r => r.json())
                    .then(d => {
                        if (d.error) { alert('Erro: ' + d.error); return; }
                        const cacheTag = d.from_cache ? ' (cache)' : '';
                        const titulo = '✦ Resumo da conversa' + cacheTag;
                        const corpo = (d.resumo || '').replace(/\n/g, '<br>');
                        const html = `
                            <div style="position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:white;
                                        padding:24px;border-radius:12px;max-width:540px;width:90%;
                                        box-shadow:0 20px 60px rgba(0,0,0,0.25);z-index:10000;">
                                <h3 style="margin:0 0 12px;font-size:16px;color:#252020;">${titulo}</h3>
                                <div style="font-size:13px;line-height:1.6;color:#475569;white-space:pre-wrap;">${corpo}</div>
                                <p style="font-size:11px;color:#94A3B8;margin:16px 0 8px;">
                                    Gerado por IA · ${d.mensagens_processadas || 0} mensagens analisadas · Cache 1h
                                </p>
                                <div style="text-align:right;">
                                    <button onclick="this.closest('div[style*=position]').remove();document.getElementById('__resumoBg').remove();"
                                            style="padding:8px 16px;background:#252020;color:white;border:none;border-radius:6px;cursor:pointer;">
                                        Fechar
                                    </button>
                                </div>
                            </div>
                            <div id="__resumoBg" onclick="this.remove();this.previousElementSibling.remove();"
                                 style="position:fixed;inset:0;background:rgba(0,0,0,0.4);z-index:9999;"></div>`;
                        document.body.insertAdjacentHTML('beforeend', html);
                    })
                    .catch(err => alert('Falha ao gerar resumo: ' + err.message))
                    .finally(() => { resumirBtn.disabled = false; resumirBtn.innerHTML = original; });
            });
        }

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

        // Base de Conhecimento - busca rápida
        let kbTimeout;
        const kbInput = document.getElementById('kbSearch');
        if (kbInput) {
            kbInput.addEventListener('input', function() {
                clearTimeout(kbTimeout);
                const q = this.value.trim();
                if (q.length < 2) { document.getElementById('kbResults').innerHTML = ''; return; }
                kbTimeout = setTimeout(() => {
                    fetchJSON('/suporte/conhecimento/api/buscar/?q=' + encodeURIComponent(q))
                    .then(d => {
                        const container = document.getElementById('kbResults');
                        if (!d.artigos || !d.artigos.length) {
                            container.innerHTML = '<p style="font-size:11px;color:var(--text-muted);padding:4px;">Nenhum artigo encontrado.</p>';
                            return;
                        }
                        container.innerHTML = d.artigos.map(a =>
                            `<div style="padding:6px 0;border-bottom:1px solid var(--border-light,#f1f5f9);">
                                <a href="/suporte/conhecimento/artigo/${a.slug}/" target="_blank" style="font-size:12px;font-weight:600;color:var(--text-main);text-decoration:none;">${esc(a.titulo)}</a>
                                <div style="font-size:11px;color:var(--text-muted);">${esc(a.categoria__nome || '')} ${a.resumo ? '· ' + esc(a.resumo.substring(0, 60)) : ''}</div>
                            </div>`
                        ).join('');
                    });
                }, 300);
            });
        }

        // Close dropdowns on outside click
        document.addEventListener('click', e => {
            const dd = document.getElementById('quickResponseDropdown');
            if (dd && !dd.contains(e.target)) dd.style.display = 'none';
            const fd = document.getElementById('filterDropdown');
            if (fd && !fd.contains(e.target) && !e.target.closest('#filterMenuBtn')) fd.style.display = 'none';
            const ep = document.getElementById('emojiPicker');
            if (ep && !ep.contains(e.target) && !e.target.closest('#emojiBtn')) ep.style.display = 'none';
        });

        // Load
        loadConversas();
        loadRespostasRapidas();
        connectWebSocket();

        // Abrir conversa especifica via ?conversa=<id> na URL
        // (ex: notificacao redireciona pra /inbox/?conversa=189)
        const params = new URLSearchParams(window.location.search);
        const conversaId = parseInt(params.get('conversa') || '', 10);
        if (conversaId && !isNaN(conversaId)) {
            selectConversa(conversaId);
        }
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
