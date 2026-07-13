/*
 * Motor de grafico compartilhado (dashboards + decks).
 *
 * Define, no escopo global, as funcoes puras usadas pelos dois modulos:
 *   PALETTE, PALETTE_RGB, fmtCompacto, fmtNum, fmtValor, esc, montarOptionEcharts
 *
 * A PALETA vem da MARCA do tenant: a pagina injeta `window.CHART_PALETTE`
 * (montada por apps/relatorios/branding.paleta_tenant) ANTES de carregar este
 * arquivo. Sem isso, cai numa categorica saturada padrao.
 *
 * Antes essas funcoes viviam inline no dashboard_detalhe.html e estavam
 * duplicadas no deck_render.js — agora ficam so aqui.
 */

// Categorica saturada de fallback (espelha branding.CATEGORICA_PADRAO)
const PALETTE_FALLBACK = ['#2563eb', '#10b981', '#f59e0b', '#ef4444', '#6366f1', '#14b8a6', '#f97316', '#8b5cf6'];

const PALETTE = (Array.isArray(window.CHART_PALETTE) && window.CHART_PALETTE.length)
  ? window.CHART_PALETTE
  : PALETTE_FALLBACK;

function _hexToRgb(hex) {
  const h = String(hex || '').replace('#', '');
  const n = parseInt(h.length === 3 ? h.split('').map(c => c + c).join('') : h, 16);
  if (Number.isNaN(n)) return '37,99,235';
  return `${(n >> 16) & 255},${(n >> 8) & 255},${n & 255}`;
}
const PALETTE_RGB = PALETTE.map(_hexToRgb);

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

// Formata o valor de um KPI conforme config_extra.formato do widget:
// 'moeda' (R$), 'percentual' (%), ou numero (default, abrevia acima de 1k).
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
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(15,23,42,0.92)',
      borderWidth: 0,
      textStyle: { color: '#fff', fontSize: 12 },
      padding: [8, 12],
    },
    grid: { left: 50, right: 20, top: 20, bottom: 50, containLabel: true },
    animation: true,
    animationDuration: 600,
    animationEasing: 'cubicOut',
  };

  if (viz === 'pizza') {
    const total = valores.reduce((a, b) => a + Number(b || 0), 0);
    return {
      ...base,
      tooltip: { ...base.tooltip, trigger: 'item',
        formatter: (p) => `${p.marker} <b>${p.name}</b><br/>${fmtCompacto(p.value)} (${p.percent}%)` },
      legend: { top: 0, left: 'center', type: 'scroll', textStyle: { fontSize: 11, color: '#475569' }, icon: 'circle', itemWidth: 8, itemHeight: 8, itemGap: 14 },
      graphic: total > 0 ? [{
        type: 'text', left: 'center', top: '50%',
        style: { text: fmtCompacto(total), fontSize: 18, fontWeight: 'bold', fill: '#0f172a', textAlign: 'center' },
      }, {
        type: 'text', left: 'center', top: '58%',
        style: { text: 'Total', fontSize: 11, fill: '#94a3b8', textAlign: 'center' },
      }] : [],
      series: [{
        type: 'pie',
        radius: ['48%', '72%'],
        center: ['50%', '58%'],
        avoidLabelOverlap: true,
        itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
        label: { show: true, position: 'outside', fontSize: 11, color: '#475569',
          formatter: (p) => `${p.percent}%\n${fmtCompacto(p.value)}` },
        labelLine: { show: true, length: 10, length2: 16, smooth: true, lineStyle: { color: '#cbd5e1', width: 1 } },
        emphasis: { scale: true, scaleSize: 6, label: { fontSize: 12, fontWeight: 'bold', color: '#0f172a' } },
        data: labels.map((l, i) => ({ name: String(l), value: Number(valores[i] || 0) })),
      }],
    };
  }

  if (viz === 'funil') {
    return {
      ...base,
      grid: undefined,
      tooltip: { ...base.tooltip, formatter: (p) => `${p.marker} <b>${p.name}</b><br/>${fmtCompacto(p.value)}` },
      series: [{
        type: 'funnel',
        // Funil ocupa a metade esquerda; rotulos ficam FORA, a direita, com linha
        // guia (por dentro ficava ilegivel em segmento estreito).
        left: '4%', right: '48%', top: 12, bottom: 12,
        minSize: '22%', maxSize: '100%',
        sort: 'none',
        gap: 4,
        itemStyle: { borderColor: '#ffffff', borderWidth: 1, borderRadius: 4 },
        label: {
          show: true, position: 'right', color: '#334155', fontSize: 12, fontWeight: 600,
          // Se o label ja embute numero/percentual, mostra como esta.
          formatter: (p) => /[|(:]/.test(String(p.name))
            ? String(p.name)
            : `${p.name}: ${fmtCompacto(p.value)}`,
        },
        labelLine: { show: true, length: 14, lineStyle: { color: '#cbd5e1', width: 1 } },
        data: labels.map((l, i) => ({ name: String(l), value: Number(valores[i] || 0) })),
      }],
    };
  }

  if (viz === 'linha') {
    return {
      ...base,
      tooltip: { ...base.tooltip, trigger: 'axis',
        formatter: (arr) => arr.map(p => `${p.marker} <b>${p.axisValueLabel}</b><br/>${p.seriesName}: ${fmtCompacto(p.value)}`).join('') },
      xAxis: { type: 'category', data: labels.map(String), axisTick: { show: false }, axisLine: { lineStyle: { color: '#e2e8f0' } }, axisLabel: { color: '#64748b', fontSize: 11 } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: '#f1f5f9' } }, axisLabel: { color: '#64748b', fontSize: 11, formatter: (v) => fmtCompacto(v) } },
      series: [{
        type: 'line',
        name: seriesName,
        data: valores.map(v => Number(v || 0)),
        smooth: true, symbol: 'circle', symbolSize: 8,
        lineStyle: { width: 3, color: PALETTE[0] },
        itemStyle: { color: PALETTE[0], borderColor: '#fff', borderWidth: 2 },
        label: { show: true, position: 'top', fontSize: 11, fontWeight: 'bold', color: '#0f172a',
          formatter: (p) => fmtCompacto(p.value) },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: `rgba(${PALETTE_RGB[0]},0.30)` },
              { offset: 1, color: `rgba(${PALETTE_RGB[0]},0)` },
            ],
          },
        },
      }],
    };
  }

  // BARRA (default) — horizontal quando ha muitas categorias OU rotulos longos.
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
    tooltip: { ...base.tooltip, trigger: 'axis', axisPointer: { type: 'shadow' },
      formatter: (arr) => arr.map(p => `${p.marker} <b>${p.axisValueLabel}</b><br/>${p.seriesName}: ${fmtCompacto(p.value)}`).join('') },
    xAxis, yAxis,
    series: [{
      type: 'bar',
      name: seriesName,
      // Cada barra sai numa cor da paleta (a 1a e a cor da MARCA do tenant).
      // O eixo aqui e categorico (canal, cidade, motivo, etapa do funil), entao
      // cor por categoria ajuda a escanear — era o que deixava o relatorio
      // legado mais vivo que o nosso, que pintava tudo da mesma cor.
      data: valores.map((v, i) => ({
        value: Number(v || 0),
        itemStyle: { color: PALETTE[i % PALETTE.length] },
      })),
      itemStyle: { borderRadius: horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0] },
      barMaxWidth: 40,
      label: { show: true, position: horizontal ? 'right' : 'top', fontSize: 11, fontWeight: 'bold', color: '#0f172a',
        formatter: (p) => fmtCompacto(p.value) },
    }],
  };
}
