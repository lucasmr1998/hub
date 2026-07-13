/*
 * Render dos blocos de um slide de deck. Reusa a lógica de gráfico do módulo
 * de relatórios (as funções puras foram COPIADAS de
 * apps/relatorios/templates/relatorios/dashboard_detalhe.html — montarOptionEcharts,
 * PALETTE, fmt*). Dívida conhecida: extrair pra um static compartilhado quando
 * for tocar o dashboard. Aqui roda igual no editor (dados ao vivo) e no
 * Apresentar (dados_snapshot).
 */
(function (global) {
  'use strict';

  // ---- copiado de relatorios (funções puras) ----
  const PALETTE = ['#7BB3F5', '#5EE3C5', '#FFB58C', '#B5A6F0', '#FFE49C', '#F4A6A6', '#A6D4E8', '#F8B6D2'];
  const PALETTE_RGB = ['123,179,245', '94,227,197', '255,181,140', '181,166,240', '255,228,156', '244,166,166', '166,212,232', '248,182,210'];
  const fmtCompacto = (v) => {
    const n = Number(v || 0);
    if (Math.abs(n) >= 1_000_000) return (n / 1_000_000).toLocaleString('pt-BR', { maximumFractionDigits: 1 }) + 'M';
    if (Math.abs(n) >= 1_000) return (n / 1_000).toLocaleString('pt-BR', { maximumFractionDigits: 1 }) + 'k';
    return n.toLocaleString('pt-BR', { maximumFractionDigits: 0 });
  };
  function fmtNum(n) {
    if (n == null) return '—';
    if (typeof n === 'number') return n.toLocaleString('pt-BR', { maximumFractionDigits: 2 });
    return n;
  }
  function fmtValor(n, formato) {
    if (n == null) return '—';
    const num = Number(n);
    if (Number.isNaN(num)) return '—';
    if (formato === 'moeda') {
      return Math.abs(num) >= 1000
        ? 'R$ ' + fmtCompacto(num)
        : 'R$ ' + num.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    if (formato === 'percentual') {
      return num.toLocaleString('pt-BR', { maximumFractionDigits: 1 }) + '%';
    }
    return Math.abs(num) >= 1000 ? fmtCompacto(num) : num.toLocaleString('pt-BR', { maximumFractionDigits: 0 });
  }
  function esc(s) { return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }

  function montarOptionEcharts(viz, labels, valores, seriesName) {
    const base = {
      color: PALETTE,
      tooltip: { trigger: 'item', backgroundColor: 'rgba(15,23,42,0.92)', borderWidth: 0, textStyle: { color: '#fff', fontSize: 12 }, padding: [8, 12] },
      grid: { left: 50, right: 20, top: 20, bottom: 50, containLabel: true },
      animation: true, animationDuration: 600, animationEasing: 'cubicOut',
    };
    if (viz === 'pizza') {
      const total = valores.reduce((a, b) => a + Number(b || 0), 0);
      return {
        ...base,
        tooltip: { ...base.tooltip, trigger: 'item', formatter: (p) => `${p.marker} <b>${p.name}</b><br/>${fmtCompacto(p.value)} (${p.percent}%)` },
        legend: { top: 0, left: 'center', type: 'scroll', textStyle: { fontSize: 11, color: '#475569' }, icon: 'circle', itemWidth: 8, itemHeight: 8, itemGap: 14 },
        graphic: total > 0 ? [
          { type: 'text', left: 'center', top: '50%', style: { text: fmtCompacto(total), fontSize: 18, fontWeight: 'bold', fill: '#0f172a', textAlign: 'center' } },
          { type: 'text', left: 'center', top: '58%', style: { text: 'Total', fontSize: 11, fill: '#94a3b8', textAlign: 'center' } },
        ] : [],
        series: [{
          type: 'pie', radius: ['48%', '72%'], center: ['50%', '58%'], avoidLabelOverlap: true,
          itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
          label: { show: true, position: 'outside', fontSize: 11, color: '#475569', formatter: (p) => `${p.percent}%\n${fmtCompacto(p.value)}` },
          labelLine: { show: true, length: 10, length2: 16, smooth: true, lineStyle: { color: '#cbd5e1', width: 1 } },
          emphasis: { scale: true, scaleSize: 6, label: { fontSize: 12, fontWeight: 'bold', color: '#0f172a' } },
          data: labels.map((l, i) => ({ name: String(l), value: Number(valores[i] || 0) })),
        }],
      };
    }
    if (viz === 'funil') {
      return {
        ...base, grid: undefined,
        tooltip: { ...base.tooltip, formatter: (p) => `${p.marker} <b>${p.name}</b><br/>${fmtCompacto(p.value)}` },
        series: [{
          type: 'funnel', left: '4%', right: '48%', top: 12, bottom: 12, minSize: '22%', maxSize: '100%', sort: 'none', gap: 4,
          itemStyle: { borderColor: '#ffffff', borderWidth: 1, borderRadius: 4 },
          label: {
            show: true, position: 'right', color: '#334155', fontSize: 12, fontWeight: 600,
            formatter: (p) => /[|(:]/.test(String(p.name)) ? String(p.name) : `${p.name}: ${fmtCompacto(p.value)}`,
          },
          labelLine: { show: true, length: 14, lineStyle: { color: '#cbd5e1', width: 1 } },
          data: labels.map((l, i) => ({ name: String(l), value: Number(valores[i] || 0) })),
        }],
      };
    }
    if (viz === 'linha') {
      return {
        ...base,
        tooltip: { ...base.tooltip, trigger: 'axis', formatter: (arr) => arr.map(p => `${p.marker} <b>${p.axisValueLabel}</b><br/>${p.seriesName}: ${fmtCompacto(p.value)}`).join('') },
        xAxis: { type: 'category', data: labels.map(String), axisTick: { show: false }, axisLine: { lineStyle: { color: '#e2e8f0' } }, axisLabel: { color: '#64748b', fontSize: 11 } },
        yAxis: { type: 'value', splitLine: { lineStyle: { color: '#f1f5f9' } }, axisLabel: { color: '#64748b', fontSize: 11, formatter: (v) => fmtCompacto(v) } },
        series: [{
          type: 'line', name: seriesName, data: valores.map(v => Number(v || 0)), smooth: true, symbol: 'circle', symbolSize: 8,
          lineStyle: { width: 3, color: PALETTE[0] }, itemStyle: { color: PALETTE[0], borderColor: '#fff', borderWidth: 2 },
          label: { show: true, position: 'top', fontSize: 11, fontWeight: 'bold', color: '#0f172a', formatter: (p) => fmtCompacto(p.value) },
          areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: `rgba(${PALETTE_RGB[0]},0.28)` }, { offset: 1, color: `rgba(${PALETTE_RGB[0]},0)` }] } },
        }],
      };
    }
    // BARRA (default) — horizontal quando ha muitas categorias ou rotulo longo
    const rotuloLongo = labels.some(l => String(l).length > 14);
    const horizontal = labels.length > 6 || rotuloLongo;
    const xAxis = horizontal
      ? { type: 'value', splitLine: { lineStyle: { color: '#f1f5f9' } }, axisLabel: { color: '#64748b', fontSize: 11, formatter: (v) => fmtCompacto(v) } }
      : { type: 'category', data: labels.map(String), axisTick: { show: false }, axisLine: { lineStyle: { color: '#e2e8f0' } }, axisLabel: { color: '#64748b', fontSize: 11, interval: 0, rotate: labels.length > 4 ? 30 : 0 } };
    const yAxis = horizontal
      ? { type: 'category', data: labels.map(String), axisTick: { show: false }, axisLine: { show: false }, axisLabel: { color: '#64748b', fontSize: 11 }, inverse: true }
      : { type: 'value', splitLine: { lineStyle: { color: '#f1f5f9' } }, axisLabel: { color: '#64748b', fontSize: 11, formatter: (v) => fmtCompacto(v) } };
    return {
      ...base,
      tooltip: { ...base.tooltip, trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: (arr) => arr.map(p => `${p.marker} <b>${p.axisValueLabel}</b><br/>${p.seriesName}: ${fmtCompacto(p.value)}`).join('') },
      xAxis, yAxis,
      series: [{
        type: 'bar', name: seriesName, data: valores.map(v => Number(v || 0)),
        itemStyle: { borderRadius: horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0], color: PALETTE[0] }, barMaxWidth: 40,
        label: { show: true, position: horizontal ? 'right' : 'top', fontSize: 11, fontWeight: 'bold', color: '#0f172a', formatter: (p) => fmtCompacto(p.value) },
      }],
    };
  }

  function funilMacroHtml(macro) {
    const cardCss = 'flex:1;min-width:110px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:14px 10px;text-align:center;';
    const labelCss = 'font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:.4px;';
    const valorCss = 'font-size:26px;font-weight:800;color:#0f172a;line-height:1.2;';
    const seta = '<i class="bi bi-arrow-right" style="font-size:18px;color:#94a3b8;flex:0 0 auto;"></i>';
    const etapas = (macro.etapas || []).map(e => {
      const quebra = (e.quebra && e.quebra.length) ? `<div style="display:flex;gap:6px;margin-top:8px;">${e.quebra.map(q => `<div style="flex:1;background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:5px 6px;"><div style="font-size:10px;font-weight:600;color:#64748b;text-transform:uppercase;">${esc(q.label)}</div><div style="font-size:14px;font-weight:800;color:#0f172a;">${fmtNum(q.valor)} <span style="font-size:10px;font-weight:600;color:#059669;">(${q.pct}%)</span></div></div>`).join('')}</div>` : '';
      return `<div style="${cardCss}"><div style="${labelCss}">${esc(e.label)}</div><div style="${valorCss}">${fmtNum(e.valor)}</div>${e.pct != null ? `<div style="font-size:11px;font-weight:600;color:#059669;">${e.pct}% da anterior</div>` : ''}${quebra}</div>`;
    }).join(seta);
    const v = macro.vendas || { valor: 0, pct: 0 }, p = macro.perdidas || { valor: 0, pct: 0 };
    const fork = `<div style="flex:1;min-width:130px;display:flex;flex-direction:column;gap:6px;"><div style="background:#ecfdf5;border:1px solid #a7f3d0;border-radius:10px;padding:8px 10px;text-align:center;"><div style="${labelCss}color:#047857;">Vendas</div><div style="font-size:20px;font-weight:800;color:#047857;">${fmtNum(v.valor)} <span style="font-size:11px;font-weight:600;">(${v.pct}%)</span></div></div><div style="background:#fef2f2;border:1px solid #fecaca;border-radius:10px;padding:8px 10px;text-align:center;"><div style="${labelCss}color:#b91c1c;">Perdidas</div><div style="font-size:20px;font-weight:800;color:#b91c1c;">${fmtNum(p.valor)} <span style="font-size:11px;font-weight:600;">(${p.pct}%)</span></div></div></div>`;
    return `<div style="display:flex;align-items:center;gap:8px;width:100%;height:100%;overflow-x:auto;padding:8px;">${etapas}${seta}${fork}</div>`;
  }

  // ---- render de um bloco ----
  // container: elemento onde renderiza. bloco: {tipo, conteudo, estilo}.
  // dados: resposta do builder {labels, series, total, meta} (null p/ nao-widget).
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
      container.innerHTML = conteudo.url ? `<img src="${esc(conteudo.url)}" style="width:100%;height:100%;object-fit:${esc(conteudo.fit || 'contain')};" alt="">` : '<div class="deck-placeholder">Sem imagem</div>';
      return;
    }

    // tipo === 'widget'
    if (!dados || dados.ok === false) {
      container.innerHTML = `<div class="deck-placeholder">${dados && dados.error ? esc(dados.error) : 'Widget sem dados (congele o deck)'}</div>`;
      return;
    }
    const viz = (dados.meta && dados.meta.visualizacao) || 'barra';
    const labels = dados.labels || [];
    const valores = (dados.series && dados.series[0] && dados.series[0].data) || [];
    const seriesName = (dados.series && dados.series[0] && dados.series[0].name) || 'Total';
    const tituloBloco = conteudo.titulo_override || (bloco.widget_titulo || '');

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
    // ECharts
    const wrap = document.createElement('div');
    wrap.style.cssText = 'width:100%;height:100%;display:flex;flex-direction:column;';
    if (tituloBloco) {
      const t = document.createElement('div'); t.className = 'deck-bloco-titulo'; t.textContent = tituloBloco; wrap.appendChild(t);
    }
    const chartDiv = document.createElement('div');
    chartDiv.style.cssText = 'flex:1;min-height:0;width:100%;';
    wrap.appendChild(chartDiv);
    container.appendChild(wrap);
    if (typeof echarts === 'undefined') { chartDiv.innerHTML = '<div class="deck-placeholder">ECharts nao carregado</div>'; return; }
    const chart = echarts.init(chartDiv, null, { renderer: 'canvas' });
    container._chart = chart;
    chart.setOption(montarOptionEcharts(viz, labels, valores, seriesName));
    if (!container._resizeObs) {
      const ro = new ResizeObserver(() => { try { chart.resize(); } catch (e) {} });
      ro.observe(chartDiv);
      container._resizeObs = ro;
    }
  }

  global.DeckRender = { renderBloco, montarOptionEcharts, fmtValor, fmtCompacto };
})(window);
