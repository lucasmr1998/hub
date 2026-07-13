/*
 * Render dos blocos de um slide de deck.
 *
 * DEPENDE de static/relatorios/echarts_option.js (motor compartilhado), que deve
 * ser carregado ANTES e expoe: montarOptionEcharts, PALETTE, fmtNum, fmtValor,
 * fmtCompacto, esc. A paleta sai da MARCA do tenant (window.CHART_PALETTE).
 *
 * Mesmo caminho de render no editor (dados ao vivo) e no Apresentar (snapshot).
 */
(function (global) {
  'use strict';

  function funilMacroHtml(macro) {
    const cardCss = 'flex:1;min-width:110px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:14px 10px;text-align:center;';
    const labelCss = 'font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:.4px;';
    const valorCss = 'font-size:26px;font-weight:800;color:#0f172a;line-height:1.2;';
    const seta = '<i class="bi bi-arrow-right" style="font-size:18px;color:#94a3b8;flex:0 0 auto;"></i>';
    const etapas = (macro.etapas || []).map(e =>
      `<div style="${cardCss}"><div style="${labelCss}">${esc(e.label)}</div><div style="${valorCss}">${fmtNum(e.valor)}</div>${e.pct != null ? `<div style="font-size:11px;font-weight:600;color:#059669;">${e.pct}% da anterior</div>` : ''}</div>`
    ).join(seta);
    const v = macro.vendas || { valor: 0, pct: 0 }, p = macro.perdidas || { valor: 0, pct: 0 };
    const fork = `<div style="flex:1;min-width:130px;display:flex;flex-direction:column;gap:6px;"><div style="background:#ecfdf5;border:1px solid #a7f3d0;border-radius:10px;padding:8px 10px;text-align:center;"><div style="${labelCss}color:#047857;">Vendas</div><div style="font-size:20px;font-weight:800;color:#047857;">${fmtNum(v.valor)} <span style="font-size:11px;font-weight:600;">(${v.pct}%)</span></div></div><div style="background:#fef2f2;border:1px solid #fecaca;border-radius:10px;padding:8px 10px;text-align:center;"><div style="${labelCss}color:#b91c1c;">Perdidas</div><div style="font-size:20px;font-weight:800;color:#b91c1c;">${fmtNum(p.valor)} <span style="font-size:11px;font-weight:600;">(${p.pct}%)</span></div></div></div>`;
    return `<div style="display:flex;align-items:center;gap:8px;width:100%;height:100%;overflow-x:auto;padding:8px;">${etapas}${seta}${fork}</div>`;
  }

  // container: onde renderiza. bloco: {tipo, conteudo, estilo, widget_id}.
  // dados: retorno do builder {labels, series, total, meta} (null p/ nao-widget).
  function renderBloco(container, bloco, dados) {
    container.innerHTML = '';
    if (container._chart) { try { container._chart.dispose(); } catch (e) {} container._chart = null; }
    const conteudo = bloco.conteudo || {};
    const estilo = bloco.estilo || {};
    container.style.background = estilo.cor_fundo || '';
    container.style.color = estilo.cor_texto || '';

    if (bloco.tipo === 'titulo_secao') {
      container.innerHTML = `<div class="deck-secao"><h2>${esc(conteudo.texto || 'Titulo')}</h2>${conteudo.subtitulo ? `<p>${esc(conteudo.subtitulo)}</p>` : ''}</div>`;
      return;
    }
    if (bloco.tipo === 'texto') {
      container.innerHTML = `<div class="deck-texto" style="text-align:${esc(conteudo.align || 'left')};font-size:${Number(conteudo.tamanho) || 16}px;">${esc(conteudo.texto || '')}</div>`;
      return;
    }
    if (bloco.tipo === 'kpi') {
      container.innerHTML = `<div class="deck-kpi"><div class="deck-kpi-label">${esc(conteudo.label || '')}</div><div class="deck-kpi-valor">${esc((conteudo.prefixo || '') + (conteudo.valor != null ? conteudo.valor : '') + (conteudo.sufixo || ''))}</div></div>`;
      return;
    }
    if (bloco.tipo === 'imagem') {
      container.innerHTML = conteudo.url
        ? `<img src="${esc(conteudo.url)}" style="width:100%;height:100%;object-fit:${esc(conteudo.fit || 'contain')};" alt="">`
        : '<div class="deck-placeholder">Sem imagem</div>';
      return;
    }

    // tipo === 'widget'
    // Slot vazio (veio de um modelo de slide): o editor deixa clicar pra escolher.
    if (!bloco.widget_id) {
      container.innerHTML = '<div class="deck-placeholder deck-slot-vazio"><i class="bi bi-bar-chart"></i><span>Escolher widget</span></div>';
      return;
    }
    if (!dados || dados.ok === false) {
      container.innerHTML = `<div class="deck-placeholder">${dados && dados.error ? esc(dados.error) : 'Widget sem dados (congele o deck)'}</div>`;
      return;
    }
    const viz = (dados.meta && dados.meta.visualizacao) || 'barra';
    const labels = dados.labels || [];
    const valores = (dados.series && dados.series[0] && dados.series[0].data) || [];
    const seriesName = (dados.series && dados.series[0] && dados.series[0].name) || 'Total';
    const tituloBloco = conteudo.titulo_override || bloco.widget_titulo || '';

    if (viz === 'numero') {
      const formato = (dados.meta && dados.meta.formato) || '';
      const valor = dados.total != null ? dados.total : (valores.length ? valores[0] : null);
      const comp = dados.meta && dados.meta.comparativo;
      let deltaHtml = '';
      if (comp && comp.direcao) {
        const seta = comp.direcao === 'subiu' ? '▲' : (comp.direcao === 'desceu' ? '▼' : '▬');
        const cor = comp.positivo === true ? '#16a34a' : (comp.positivo === false ? '#dc2626' : '#94a3b8');
        const pct = comp.delta_pct == null ? 'novo' : Math.abs(comp.delta_pct).toLocaleString('pt-BR', { maximumFractionDigits: 1 }) + '%';
        deltaHtml = `<div class="deck-kpi-delta" style="color:${cor};">${seta} ${pct}</div>`;
      }
      container.innerHTML = `<div class="deck-kpi">${tituloBloco ? `<div class="deck-kpi-label">${esc(tituloBloco)}</div>` : ''}<div class="deck-kpi-valor">${fmtValor(valor, formato)}</div>${deltaHtml}</div>`;
      return;
    }
    if (viz === 'tabela') {
      let html = tituloBloco ? `<div class="deck-bloco-titulo">${esc(tituloBloco)}</div>` : '';
      html += '<table class="deck-tabela"><thead><tr><th>Categoria</th><th style="text-align:right;">Valor</th></tr></thead><tbody>';
      labels.forEach((l, i) => { html += `<tr><td>${esc(l)}</td><td style="text-align:right;">${fmtNum(valores[i])}</td></tr>`; });
      container.innerHTML = html + '</tbody></table>';
      return;
    }
    if (viz === 'funil' && dados.meta && dados.meta.macro) {
      container.innerHTML = (tituloBloco ? `<div class="deck-bloco-titulo">${esc(tituloBloco)}</div>` : '') + funilMacroHtml(dados.meta.macro);
      return;
    }

    // ECharts (reusa o motor compartilhado)
    const wrap = document.createElement('div');
    wrap.style.cssText = 'width:100%;height:100%;display:flex;flex-direction:column;';
    if (tituloBloco) {
      const t = document.createElement('div');
      t.className = 'deck-bloco-titulo';
      t.textContent = tituloBloco;
      wrap.appendChild(t);
    }
    const chartDiv = document.createElement('div');
    chartDiv.style.cssText = 'flex:1;min-height:0;width:100%;';
    wrap.appendChild(chartDiv);
    container.appendChild(wrap);
    if (typeof echarts === 'undefined' || typeof montarOptionEcharts !== 'function') {
      chartDiv.innerHTML = '<div class="deck-placeholder">Motor de grafico nao carregado</div>';
      return;
    }
    const chart = echarts.init(chartDiv, null, { renderer: 'canvas' });
    container._chart = chart;
    chart.setOption(montarOptionEcharts(viz, labels, valores, seriesName));
    if (!container._resizeObs) {
      const ro = new ResizeObserver(() => { try { chart.resize(); } catch (e) {} });
      ro.observe(chartDiv);
      container._resizeObs = ro;
    }
  }

  global.DeckRender = { renderBloco };
})(window);
