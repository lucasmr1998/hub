/**
 * Aurora Chat Widget — Embeddable chat for ISP websites
 *
 * Usage: <script src="https://app.auroraisp.com/static/inbox/widget/aurora-chat.js" data-token="UUID"></script>
 *
 * Self-contained: zero dependencies, inline CSS, Shadow DOM isolation.
 * Three tabs: Home (welcome + FAQ), Messages (chat), Help (FAQ browser).
 */
(function() {
    'use strict';

    // ── Bootstrap ─────────────────────────────────────────────────────
    var scriptTag = document.currentScript || document.querySelector('script[data-token]');
    if (!scriptTag) return;

    var TOKEN = scriptTag.getAttribute('data-token');
    if (!TOKEN) return;

    var BASE_URL = scriptTag.src.replace(/\/static\/inbox\/widget\/aurora-chat\.js.*/, '');
    var API = BASE_URL + '/api/public/widget';
    var POLL_MS = 5000;

    // ── State ─────────────────────────────────────────────────────────
    var state = {
        config: null,
        open: false,
        tab: 'home',
        visitorId: localStorage.getItem('aurora_visitor_id') || generateUUID(),
        visitorData: JSON.parse(localStorage.getItem('aurora_visitor_data') || 'null'),
        conversas: [],
        currentConversa: null,
        mensagens: [],
        faqCategoria: null,
        faqArtigo: null,
        faqBusca: [],
        pollTimer: null,
    };
    localStorage.setItem('aurora_visitor_id', state.visitorId);

    function generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            var r = Math.random() * 16 | 0;
            return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
        });
    }

    // ── API helpers ───────────────────────────────────────────────────
    function api(path, opts) {
        var sep = path.indexOf('?') >= 0 ? '&' : '?';
        var url = API + path + sep + 'token=' + TOKEN;
        var defaults = { headers: { 'Content-Type': 'application/json' } };
        return fetch(url, Object.assign(defaults, opts || {}))
            .then(function(r) { return r.json(); })
            .catch(function() { return { error: 'network' }; });
    }

    // ── CSS ───────────────────────────────────────────────────────────
    var CSS = `
    .aw-btn{position:fixed;z-index:99999;width:60px;height:60px;border-radius:50%;border:none;cursor:pointer;box-shadow:0 4px 16px rgba(0,0,0,.2);display:flex;align-items:center;justify-content:center;transition:transform .2s}
    .aw-btn:hover{transform:scale(1.1)}
    .aw-btn svg{width:28px;height:28px;fill:#fff}
    .aw-panel{position:fixed;z-index:99999;width:380px;height:560px;border-radius:16px;box-shadow:0 8px 40px rgba(0,0,0,.2);display:flex;flex-direction:column;overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-size:14px;color:#1e293b;background:#fff;transition:opacity .2s,transform .2s;opacity:0;transform:translateY(20px);pointer-events:none}
    .aw-panel.aw-open{opacity:1;transform:translateY(0);pointer-events:auto}
    .aw-header{padding:24px 20px 16px;color:#fff;position:relative}
    .aw-header h2{margin:0 0 4px;font-size:22px;font-weight:700}
    .aw-header p{margin:0;font-size:14px;opacity:.9}
    .aw-close{position:absolute;top:12px;right:12px;background:rgba(255,255,255,.2);border:none;border-radius:50%;width:28px;height:28px;cursor:pointer;color:#fff;font-size:16px;display:flex;align-items:center;justify-content:center}
    .aw-body{flex:1;overflow-y:auto;background:#fff}
    .aw-tabs{display:flex;border-top:1px solid #e2e8f0;background:#fff;flex-shrink:0}
    .aw-tab{flex:1;padding:10px 0;text-align:center;border:none;background:none;cursor:pointer;font-size:11px;color:#94a3b8;font-family:inherit;display:flex;flex-direction:column;align-items:center;gap:2px;transition:color .2s}
    .aw-tab.active{color:#3b82f6}
    .aw-tab svg{width:20px;height:20px;fill:currentColor}
    .aw-section{display:none;height:100%;flex-direction:column}
    .aw-section.active{display:flex}
    .aw-cta{display:flex;align-items:center;padding:14px 20px;margin:12px 16px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;cursor:pointer;transition:background .2s;gap:12px}
    .aw-cta:hover{background:#f1f5f9}
    .aw-cta-text{flex:1;font-size:14px;color:#64748b}
    .aw-cta-arrow{color:#3b82f6;font-size:18px;font-weight:700}
    .aw-search{margin:8px 16px;position:relative}
    .aw-search input{width:100%;padding:10px 12px;border:1px solid #e2e8f0;border-radius:10px;font-size:13px;font-family:inherit;outline:none;box-sizing:border-box}
    .aw-search input:focus{border-color:#3b82f6}
    .aw-faq-item{display:flex;align-items:center;justify-content:space-between;padding:12px 20px;border-bottom:1px solid #f1f5f9;cursor:pointer;transition:background .15s}
    .aw-faq-item:hover{background:#f8fafc}
    .aw-faq-title{font-size:14px;color:#1e293b}
    .aw-faq-arrow{color:#94a3b8;font-size:14px}
    .aw-faq-cat{display:flex;align-items:center;gap:10px;padding:12px 20px;border-bottom:1px solid #f1f5f9;cursor:pointer;transition:background .15s}
    .aw-faq-cat:hover{background:#f8fafc}
    .aw-faq-cat-icon{width:32px;height:32px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:14px;color:#fff}
    .aw-faq-cat-info{flex:1}
    .aw-faq-cat-name{font-size:14px;font-weight:600}
    .aw-faq-cat-count{font-size:12px;color:#94a3b8}
    .aw-article{padding:20px;line-height:1.6}
    .aw-article h3{margin:0 0 12px;font-size:16px}
    .aw-back{display:flex;align-items:center;gap:6px;padding:10px 16px;font-size:13px;color:#3b82f6;cursor:pointer;border-bottom:1px solid #f1f5f9}
    .aw-form{padding:20px}
    .aw-form label{display:block;font-size:12px;font-weight:600;color:#64748b;margin-bottom:4px}
    .aw-form input,.aw-form textarea{width:100%;padding:8px 12px;border:1px solid #e2e8f0;border-radius:8px;font-size:13px;font-family:inherit;outline:none;margin-bottom:12px;box-sizing:border-box}
    .aw-form button{width:100%;padding:10px;border:none;border-radius:8px;color:#fff;font-size:14px;font-weight:600;cursor:pointer;font-family:inherit}
    .aw-conv-item{padding:14px 20px;border-bottom:1px solid #f1f5f9;cursor:pointer;transition:background .15s}
    .aw-conv-item:hover{background:#f8fafc}
    .aw-conv-preview{font-size:13px;color:#64748b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .aw-conv-meta{font-size:11px;color:#94a3b8;margin-top:2px}
    .aw-chat{display:flex;flex-direction:column;height:100%;overflow:hidden}
    .aw-messages{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:8px;background:#f8fafc;min-height:0}
    .aw-input-area{flex-shrink:0}
    .aw-msg{max-width:80%;padding:10px 14px;border-radius:16px;font-size:13px;line-height:1.5;word-break:break-word}
    .aw-msg.contact{align-self:flex-end;background:#3b82f6;color:#fff;border-bottom-right-radius:4px}
    .aw-msg.agent,.aw-msg.bot{align-self:flex-start;background:#fff;border:1px solid #e2e8f0;border-bottom-left-radius:4px}
    .aw-msg-name{font-size:11px;font-weight:600;opacity:.7;margin-bottom:2px}
    .aw-msg-time{font-size:10px;opacity:.6;margin-top:4px}
    .aw-input-area{display:flex;gap:8px;padding:12px 16px;border-top:1px solid #e2e8f0;background:#fff;align-items:center}
    .aw-input-area input{flex:1;padding:10px 14px;border:1px solid #e2e8f0;border-radius:20px;font-size:13px;font-family:inherit;outline:none;box-sizing:border-box}
    .aw-input-area input:focus{border-color:#3b82f6;box-shadow:0 0 0 2px rgba(59,130,246,.1)}
    .aw-input-area button{background:#3b82f6;color:#fff;border:none;border-radius:50%;width:40px;height:40px;min-width:40px;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:background .15s}
    .aw-input-area button:hover{opacity:.9}
    .aw-input-area button svg{width:18px;height:18px;fill:#fff}
    .aw-empty{padding:40px 20px;text-align:center;color:#94a3b8;font-size:13px}
    .aw-new-btn{display:block;margin:12px 16px;padding:10px;border:1px solid #e2e8f0;border-radius:10px;text-align:center;font-size:13px;color:#3b82f6;cursor:pointer;background:#fff;font-family:inherit}
    .aw-new-btn:hover{background:#f8fafc}
    @media(max-width:480px){.aw-panel{width:100%;height:100%;border-radius:0;top:0;left:0;right:0;bottom:0}}
    `;

    // ── SVG Icons ─────────────────────────────────────────────────────
    var ICONS = {
        chat: '<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.2L4 17.2V4h16v12z"/></svg>',
        close: '×',
        send: '<svg viewBox="0 0 24 24"><path d="M2 21l21-9L2 3v7l15 2-15 2v7z"/></svg>',
        home: '<svg viewBox="0 0 24 24"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg>',
        messages: '<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/></svg>',
        help: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2"/><path d="M9 9a3 3 0 116 0c0 2-3 2-3 4m0 4h.01" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
        arrow: '›',
        back: '‹',
    };

    // ── Render ─────────────────────────────────────────────────────────
    function init() {
        api('/config/').then(function(cfg) {
            if (cfg.error) return;
            state.config = cfg;
            render();
        });
    }

    function render() {
        var cfg = state.config;
        var pos = cfg.posicao === 'bottom-left' ? 'left:20px' : 'right:20px';

        // Container
        var container = document.createElement('div');
        container.id = 'aurora-widget-root';

        // Style
        var style = document.createElement('style');
        style.textContent = CSS;
        container.appendChild(style);

        // Button
        var btn = document.createElement('button');
        btn.className = 'aw-btn';
        btn.setAttribute('style', 'bottom:20px;' + pos + ';background:' + cfg.cor_primaria);
        btn.innerHTML = ICONS.chat;
        btn.onclick = function() { togglePanel(); };
        container.appendChild(btn);

        // Panel
        var panel = document.createElement('div');
        panel.className = 'aw-panel';
        panel.id = 'aw-panel';
        panel.setAttribute('style', 'bottom:90px;' + pos);
        panel.innerHTML = buildPanelHTML(cfg);
        container.appendChild(panel);

        document.body.appendChild(container);
        bindEvents();
    }

    function buildPanelHTML(cfg) {
        return '' +
        '<div class="aw-header" style="background:linear-gradient(135deg,' + cfg.cor_header + ',' + cfg.cor_primaria + ')">' +
            '<button class="aw-close" id="aw-close">' + ICONS.close + '</button>' +
            '<p>' + escapeHtml(cfg.mensagem_boas_vindas) + '</p>' +
            '<h2>' + escapeHtml(cfg.titulo) + '</h2>' +
        '</div>' +
        '<div class="aw-body" id="aw-body">' +
            '<div class="aw-section active" id="aw-tab-home">' + buildHomeTab(cfg) + '</div>' +
            '<div class="aw-section" id="aw-tab-messages">' + buildMessagesTab() + '</div>' +
            '<div class="aw-section" id="aw-tab-help">' + buildHelpTab(cfg) + '</div>' +
        '</div>' +
        '<div class="aw-tabs">' +
            '<button class="aw-tab active" data-tab="home">' + ICONS.home + 'Início</button>' +
            '<button class="aw-tab" data-tab="messages">' + ICONS.messages + 'Mensagens</button>' +
            '<button class="aw-tab" data-tab="help">' + ICONS.help + 'Ajuda</button>' +
        '</div>';
    }

    function buildHomeTab(cfg) {
        var html = '<div class="aw-cta" id="aw-start-chat">' +
            '<span class="aw-cta-text">Envie uma mensagem</span>' +
            '<span class="aw-cta-arrow">' + ICONS.arrow + '</span></div>';

        if (cfg.mostrar_faq && cfg.categorias && cfg.categorias.length) {
            html += '<div class="aw-search"><input type="text" id="aw-home-search" placeholder="Qual é a sua dúvida?"></div>';
            html += '<div id="aw-home-faq">';
            cfg.categorias.forEach(function(c) {
                html += '<div class="aw-faq-item" data-slug="' + c.slug + '">' +
                    '<span class="aw-faq-title">' + escapeHtml(c.nome) + '</span>' +
                    '<span class="aw-faq-arrow">' + ICONS.arrow + '</span></div>';
            });
            html += '</div><div id="aw-home-results" style="display:none"></div>';
        }
        return html;
    }

    function buildMessagesTab() {
        return '<div id="aw-msg-content"><div class="aw-empty">Carregando...</div></div>';
    }

    function buildHelpTab(cfg) {
        if (!cfg.mostrar_faq) return '<div class="aw-empty">Nenhum artigo disponível</div>';
        var html = '<div id="aw-help-content"><div class="aw-search"><input type="text" id="aw-help-search" placeholder="Buscar artigos..."></div>';
        if (cfg.categorias) {
            cfg.categorias.forEach(function(c) {
                html += '<div class="aw-faq-cat" data-slug="' + c.slug + '">' +
                    '<div class="aw-faq-cat-icon" style="background:' + c.cor + '"><i class="fas ' + c.icone + '"></i></div>' +
                    '<div class="aw-faq-cat-info"><div class="aw-faq-cat-name">' + escapeHtml(c.nome) + '</div>' +
                    '<div class="aw-faq-cat-count">' + c.artigos_count + ' artigos</div></div>' +
                    '<span class="aw-faq-arrow">' + ICONS.arrow + '</span></div>';
            });
        }
        html += '</div><div id="aw-help-detail" style="display:none"></div>';
        return html;
    }

    // ── Toggle & Navigation ───────────────────────────────────────────
    function togglePanel() {
        state.open = !state.open;
        var panel = document.getElementById('aw-panel');
        if (panel) panel.classList.toggle('aw-open', state.open);
    }

    function switchTab(tab) {
        state.tab = tab;
        document.querySelectorAll('#aurora-widget-root .aw-tab').forEach(function(t) {
            t.classList.toggle('active', t.getAttribute('data-tab') === tab);
        });
        document.querySelectorAll('#aurora-widget-root .aw-section').forEach(function(s) {
            s.classList.toggle('active', s.id === 'aw-tab-' + tab);
        });

        if (tab === 'messages') loadConversas();
    }

    // ── Events ────────────────────────────────────────────────────────
    function bindEvents() {
        var root = document.getElementById('aurora-widget-root');

        root.querySelector('#aw-close').onclick = togglePanel;

        // Tabs
        root.querySelectorAll('.aw-tab').forEach(function(t) {
            t.onclick = function() { switchTab(t.getAttribute('data-tab')); };
        });

        // Start chat CTA
        var startBtn = root.querySelector('#aw-start-chat');
        if (startBtn) startBtn.onclick = function() {
            switchTab('messages');
            startNewConversation();
        };

        // Home FAQ items
        root.querySelectorAll('#aw-tab-home .aw-faq-item').forEach(function(el) {
            el.onclick = function() { loadFaqCategory(el.getAttribute('data-slug'), 'home'); };
        });

        // Home search
        var homeSearch = root.querySelector('#aw-home-search');
        if (homeSearch) {
            var timer;
            homeSearch.oninput = function() {
                clearTimeout(timer);
                timer = setTimeout(function() { searchFaq(homeSearch.value, 'home'); }, 300);
            };
        }

        // Help categories
        root.querySelectorAll('#aw-tab-help .aw-faq-cat').forEach(function(el) {
            el.onclick = function() { loadFaqCategory(el.getAttribute('data-slug'), 'help'); };
        });

        // Help search
        var helpSearch = root.querySelector('#aw-help-search');
        if (helpSearch) {
            var timer2;
            helpSearch.oninput = function() {
                clearTimeout(timer2);
                timer2 = setTimeout(function() { searchFaq(helpSearch.value, 'help'); }, 300);
            };
        }
    }

    // ── FAQ ───────────────────────────────────────────────────────────
    function loadFaqCategory(slug, tabContext) {
        api('/faq/?categoria=' + slug).then(function(data) {
            if (data.error) return;
            var container = tabContext === 'home'
                ? document.getElementById('aw-home-faq')
                : document.getElementById('aw-help-content');

            var html = '<div class="aw-back" id="aw-faq-back-' + tabContext + '">' + ICONS.back + ' Voltar</div>';
            (data.artigos || []).forEach(function(a) {
                html += '<div class="aw-faq-item" data-artigo-id="' + a.id + '" data-context="' + tabContext + '">' +
                    '<span class="aw-faq-title">' + escapeHtml(a.titulo) + '</span>' +
                    '<span class="aw-faq-arrow">' + ICONS.arrow + '</span></div>';
            });
            if (!data.artigos || !data.artigos.length) html += '<div class="aw-empty">Nenhum artigo nesta categoria</div>';

            container.innerHTML = html;
            state['_faqArtigos_' + tabContext] = data.artigos;

            // Bind back
            var backBtn = document.getElementById('aw-faq-back-' + tabContext);
            if (backBtn) backBtn.onclick = function() { resetFaqView(tabContext); };

            // Bind article click
            container.querySelectorAll('.aw-faq-item').forEach(function(el) {
                el.onclick = function() {
                    var id = parseInt(el.getAttribute('data-artigo-id'));
                    var artigos = state['_faqArtigos_' + tabContext] || [];
                    var artigo = artigos.find(function(a) { return a.id === id; });
                    if (artigo) showArticle(artigo, tabContext);
                };
            });
        });
    }

    function showArticle(artigo, tabContext) {
        var container = tabContext === 'home'
            ? document.getElementById('aw-home-faq')
            : document.getElementById('aw-help-content');

        container.innerHTML = '<div class="aw-back" id="aw-art-back-' + tabContext + '">' + ICONS.back + ' Voltar</div>' +
            '<div class="aw-article"><h3>' + escapeHtml(artigo.titulo) + '</h3><div>' + artigo.conteudo + '</div></div>';

        document.getElementById('aw-art-back-' + tabContext).onclick = function() { resetFaqView(tabContext); };
    }

    function resetFaqView(tabContext) {
        // Re-render the tab from config
        if (tabContext === 'home') {
            document.getElementById('aw-tab-home').innerHTML = buildHomeTab(state.config);
            // Re-bind events
            document.querySelectorAll('#aw-tab-home .aw-faq-item').forEach(function(el) {
                el.onclick = function() { loadFaqCategory(el.getAttribute('data-slug'), 'home'); };
            });
            var startBtn = document.querySelector('#aw-start-chat');
            if (startBtn) startBtn.onclick = function() { switchTab('messages'); startNewConversation(); };
            var homeSearch = document.querySelector('#aw-home-search');
            if (homeSearch) {
                var timer;
                homeSearch.oninput = function() {
                    clearTimeout(timer);
                    timer = setTimeout(function() { searchFaq(homeSearch.value, 'home'); }, 300);
                };
            }
        } else {
            document.getElementById('aw-help-content').innerHTML = buildHelpTab(state.config).replace(/<div id="aw-help-detail".*/, '');
            document.querySelectorAll('#aw-help-content .aw-faq-cat').forEach(function(el) {
                el.onclick = function() { loadFaqCategory(el.getAttribute('data-slug'), 'help'); };
            });
        }
    }

    function searchFaq(query, tabContext) {
        if (!query || query.length < 2) {
            if (tabContext === 'home') {
                var resultsDiv = document.getElementById('aw-home-results');
                var faqDiv = document.getElementById('aw-home-faq');
                if (resultsDiv) resultsDiv.style.display = 'none';
                if (faqDiv) faqDiv.style.display = '';
            }
            return;
        }
        api('/faq/buscar/?q=' + encodeURIComponent(query)).then(function(data) {
            if (data.error) return;
            var html = '';
            (data.artigos || []).forEach(function(a) {
                html += '<div class="aw-faq-item" data-search-artigo><span class="aw-faq-title">' +
                    escapeHtml(a.titulo) + '</span><span class="aw-faq-arrow">' + ICONS.arrow + '</span></div>';
            });
            if (!data.artigos || !data.artigos.length) html = '<div class="aw-empty">Nenhum resultado</div>';

            if (tabContext === 'home') {
                var resultsDiv = document.getElementById('aw-home-results');
                var faqDiv = document.getElementById('aw-home-faq');
                if (resultsDiv) { resultsDiv.innerHTML = html; resultsDiv.style.display = ''; }
                if (faqDiv) faqDiv.style.display = 'none';
            }
        });
    }

    // ── Conversations ─────────────────────────────────────────────────
    function loadConversas() {
        api('/conversas/?visitor_id=' + state.visitorId).then(function(data) {
            if (data.error) return;
            state.conversas = data.conversas || [];
            renderConversasList();
        });
    }

    function renderConversasList() {
        var container = document.getElementById('aw-msg-content');
        if (!container) return;

        var html = '<div class="aw-new-btn" id="aw-new-conv">+ Nova conversa</div>';

        if (!state.conversas.length) {
            html += '<div class="aw-empty">Nenhuma conversa ainda</div>';
        } else {
            state.conversas.forEach(function(c) {
                html += '<div class="aw-conv-item" data-conv-id="' + c.id + '">' +
                    '<div class="aw-conv-preview">' + escapeHtml(c.ultima_mensagem_preview || 'Conversa #' + c.id) + '</div>' +
                    '<div class="aw-conv-meta">' + formatTime(c.ultima_mensagem_em) + '</div></div>';
            });
        }

        container.innerHTML = html;

        document.getElementById('aw-new-conv').onclick = startNewConversation;
        container.querySelectorAll('.aw-conv-item').forEach(function(el) {
            el.onclick = function() { openConversa(parseInt(el.getAttribute('data-conv-id'))); };
        });
    }

    function startNewConversation() {
        var cfg = state.config;
        var container = document.getElementById('aw-msg-content');
        if (!container) return;

        if (cfg.pedir_dados_antes && !state.visitorData) {
            var campos = cfg.campos_obrigatorios || ['nome', 'email'];
            var html = '<div class="aw-form"><h3 style="margin:0 0 16px;font-size:16px;">Antes de começar</h3>';
            if (campos.indexOf('nome') >= 0) html += '<label>Nome</label><input type="text" id="aw-f-nome" placeholder="Seu nome">';
            if (campos.indexOf('email') >= 0) html += '<label>E-mail</label><input type="email" id="aw-f-email" placeholder="seu@email.com">';
            if (campos.indexOf('telefone') >= 0) html += '<label>Telefone</label><input type="tel" id="aw-f-telefone" placeholder="(00) 00000-0000">';
            html += '<label>Mensagem</label><textarea id="aw-f-msg" rows="3" placeholder="Como podemos ajudar?"></textarea>';
            html += '<button id="aw-f-submit" style="background:' + cfg.cor_primaria + '">Iniciar conversa</button></div>';
            container.innerHTML = html;

            document.getElementById('aw-f-submit').onclick = function() {
                var nome = (document.getElementById('aw-f-nome') || {}).value || '';
                var email = (document.getElementById('aw-f-email') || {}).value || '';
                var telefone = (document.getElementById('aw-f-telefone') || {}).value || '';
                var msg = (document.getElementById('aw-f-msg') || {}).value || '';
                if (!msg.trim()) return;

                state.visitorData = { nome: nome, email: email, telefone: telefone };
                localStorage.setItem('aurora_visitor_data', JSON.stringify(state.visitorData));
                submitNewConversation(nome, email, telefone, msg);
            };
        } else {
            // Show direct input
            var vd = state.visitorData || {};
            container.innerHTML = '<div class="aw-form"><label>Mensagem</label>' +
                '<textarea id="aw-f-msg" rows="3" placeholder="Como podemos ajudar?"></textarea>' +
                '<button id="aw-f-submit" style="background:' + cfg.cor_primaria + '">Enviar</button></div>';

            document.getElementById('aw-f-submit').onclick = function() {
                var msg = document.getElementById('aw-f-msg').value || '';
                if (!msg.trim()) return;
                submitNewConversation(vd.nome || 'Visitante', vd.email || '', vd.telefone || '', msg);
            };
        }
    }

    function submitNewConversation(nome, email, telefone, mensagem) {
        api('/conversa/iniciar/', {
            method: 'POST',
            body: JSON.stringify({
                token: TOKEN,
                visitor_id: state.visitorId,
                nome: nome,
                email: email,
                telefone: telefone,
                mensagem: mensagem,
            }),
        }).then(function(data) {
            if (data.error) return;
            state.currentConversa = data.conversa_id;
            state.mensagens = data.mensagens || [];
            renderChat();
            startPolling();
        });
    }

    function openConversa(conversaId) {
        state.currentConversa = conversaId;
        loadMensagens();
        startPolling();
    }

    function loadMensagens() {
        if (!state.currentConversa) return;
        api('/conversa/' + state.currentConversa + '/mensagens/?visitor_id=' + state.visitorId).then(function(data) {
            if (data.error) return;
            state.mensagens = data.mensagens || [];
            renderChat();
        });
    }

    function renderChat() {
        var container = document.getElementById('aw-msg-content');
        if (!container) return;
        var cfg = state.config;

        var html = '<div class="aw-chat">' +
            '<div class="aw-back" id="aw-chat-back">' + ICONS.back + ' Voltar</div>' +
            '<div class="aw-messages" id="aw-chat-msgs">';

        state.mensagens.forEach(function(m) {
            var cls = m.remetente_tipo === 'contato' ? 'contact' : (m.remetente_tipo === 'bot' ? 'bot' : 'agent');
            html += '<div class="aw-msg ' + cls + '">';
            if (cls !== 'contact') html += '<div class="aw-msg-name">' + escapeHtml(m.remetente_nome) + '</div>';
            html += '<div>' + escapeHtml(m.conteudo) + '</div>';
            html += '<div class="aw-msg-time">' + formatTime(m.data_envio) + '</div></div>';
        });

        html += '</div><div class="aw-input-area">' +
            '<input type="text" id="aw-chat-input" placeholder="Digite sua mensagem...">' +
            '<button id="aw-chat-send" style="background:' + cfg.cor_primaria + '">' + ICONS.send + '</button>' +
            '</div></div>';

        container.innerHTML = html;

        // Scroll to bottom
        var msgs = document.getElementById('aw-chat-msgs');
        if (msgs) msgs.scrollTop = msgs.scrollHeight;

        // Bind
        document.getElementById('aw-chat-back').onclick = function() {
            stopPolling();
            state.currentConversa = null;
            loadConversas();
        };
        document.getElementById('aw-chat-send').onclick = sendMessage;
        document.getElementById('aw-chat-input').onkeydown = function(e) {
            if (e.key === 'Enter') { e.preventDefault(); sendMessage(); }
        };
    }

    function sendMessage() {
        var input = document.getElementById('aw-chat-input');
        if (!input) return;
        var msg = input.value.trim();
        if (!msg || !state.currentConversa) return;

        input.value = '';

        api('/conversa/' + state.currentConversa + '/enviar/', {
            method: 'POST',
            body: JSON.stringify({
                token: TOKEN,
                visitor_id: state.visitorId,
                conteudo: msg,
            }),
        }).then(function() {
            loadMensagens();
        });
    }

    // ── Polling ───────────────────────────────────────────────────────
    function startPolling() {
        stopPolling();
        state.pollTimer = setInterval(function() {
            if (state.currentConversa) loadMensagens();
        }, POLL_MS);
    }

    function stopPolling() {
        if (state.pollTimer) { clearInterval(state.pollTimer); state.pollTimer = null; }
    }

    // ── Utils ─────────────────────────────────────────────────────────
    function escapeHtml(str) {
        if (!str) return '';
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function formatTime(isoStr) {
        if (!isoStr) return '';
        var d = new Date(isoStr);
        return d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    }

    // ── Start ─────────────────────────────────────────────────────────
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
