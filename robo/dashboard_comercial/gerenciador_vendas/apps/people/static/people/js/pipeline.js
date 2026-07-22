/**
 * Board do pipeline de recrutamento.
 *
 * A tela tem duas vistas:
 *
 *   LISTA (padrao) — chips por etapa e por saida no topo, e a grade de cards da
 *   selecao. Aqui o volume manda: dezenas de candidatos numa etapa cabem numa
 *   grade e nao cabem numa coluna. Tem selecao em lote.
 *
 *   KANBAN (toggle) — colunas arrastaveis. Melhor com poucos candidatos, porque
 *   mover e arrastar.
 *
 * Duas regras que valem nas duas vistas:
 *   Mover ENTRE etapas e livre (etapa e configuracao, nao maquina de estados).
 *   SAIR do pipeline exige motivo e passa por regra, entao e modal, nao arrasto.
 *
 * TUDO POR DELEGACAO NO DOCUMENTO, e nao listener por card. E o que permite
 * trocar o conteudo por busca parcial (filtro e chip nao recarregam a pagina)
 * sem religar nada: os nos novos ja nascem funcionando, porque quem escuta e o
 * documento. Antes, um innerHTML novo deixava todos os cards mortos.
 */
(function () {
  'use strict';

  const ALVO = 'pipeline-conteudo';   // id da regiao que a busca parcial troca

  let cardDaSaida = null;   // card unico esperando o modal de saida
  let idsDoLote = [];       // ou a lista de ids, no modo lote
  let arrastando = null;
  let colunaOrigem = null;
  let arrastouAgora = false;

  const csrf = () => document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
  const dados = () => document.getElementById('pipeline-dados');
  const modal = () => document.getElementById('modal-saida');
  const conteudo = () => document.getElementById(ALVO);

  function post(url, corpo) {
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
      body: JSON.stringify(corpo),
    }).then(r => r.json().then(j => ({ status: r.status, corpo: j })));
  }

  // ── Busca parcial ───────────────────────────────────────────────────────
  //
  // Filtrar e trocar de chip nao recarregam a pagina: buscam so a regiao do
  // conteudo e trocam. A URL e atualizada com pushState, entao voltar, recarregar
  // e compartilhar continuam funcionando, que e o que se perde quando alguem
  // resolve isso guardando estado so em memoria.
  let buscando = false;

  function trocarConteudo(url, empurrarHistorico) {
    if (buscando) return;
    buscando = true;

    const alvo = conteudo();
    if (alvo) alvo.style.opacity = '0.5';

    const separador = url.indexOf('?') === -1 ? '?' : '&';
    fetch(url + separador + 'parcial=1', {
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
      .then(r => r.text())
      .then(function (html) {
        const atual = conteudo();
        if (atual) {
          atual.innerHTML = html;
          atual.style.opacity = '';
        }
        if (empurrarHistorico) window.history.pushState({}, '', url);
      })
      .catch(function () {
        // Falhou a busca parcial: cai pra navegacao normal, que sempre
        // funciona. Melhor recarregar a pagina do que deixar o filtro mudo.
        window.location.href = url;
      })
      .finally(function () {
        buscando = false;
        const atual = conteudo();
        if (atual) atual.style.opacity = '';
      });
  }

  function urlDoFiltro() {
    const form = document.getElementById('filtro-pipeline');
    if (!form) return null;
    // A fase escolhida vem junto porque o template a coloca como input
    // escondido no proprio form. Resolver isso aqui no JS funcionaria igual, e
    // deixaria o form quebrado pra quem submete sem JS.
    const params = new URLSearchParams(new FormData(form));

    // Tira vazio, pra a URL nao encher de `&canal=&periodo=`
    for (const [chave, valor] of Array.from(params.entries())) {
      if (!valor) params.delete(chave);
    }
    const query = params.toString();
    return window.location.pathname + (query ? '?' + query : '');
  }

  // Voltar no navegador refaz a busca da URL anterior.
  window.addEventListener('popstate', function () {
    trocarConteudo(window.location.href, false);
  });

  // ── Delegacao: um listener pra tudo ─────────────────────────────────────

  document.addEventListener('submit', function (evento) {
    if (evento.target.id !== 'filtro-pipeline') return;
    evento.preventDefault();
    const url = urlDoFiltro();
    if (url) trocarConteudo(url, true);
  });

  document.addEventListener('change', function (evento) {
    const alvo = evento.target;

    // Filtro: trocar o select ja aplica, sem precisar do botao.
    if (alvo.closest('#filtro-pipeline')) {
      const url = urlDoFiltro();
      if (url) trocarConteudo(url, true);
      return;
    }

    if (alvo.classList.contains('lote-item') || alvo.id === 'lote-todos') {
      if (alvo.id === 'lote-todos') {
        document.querySelectorAll('.lote-item').forEach(i => { i.checked = alvo.checked; });
      }
      atualizarBarraDeLote();
    }
  });

  document.addEventListener('click', function (evento) {
    const alvo = evento.target;

    // Chip: busca parcial no lugar de navegar. O alternador de lista/kanban
    // fica de fora e navega mesmo: ele vive no cabecalho, e o proprio rotulo
    // dele ("Ver em kanban") muda junto, entao trocar so o miolo deixaria o
    // botao mentindo sobre o que faz.
    const link = alvo.closest('.pipe-chip');
    if (link && link.href) {
      evento.preventDefault();
      trocarConteudo(link.href, true);
      return;
    }

    if (alvo.closest('[data-avancar]')) {
      evento.stopPropagation();
      return avancar(alvo.closest('[data-avancar]'));
    }
    if (alvo.closest('[data-reabrir]')) {
      evento.stopPropagation();
      return reabrir(alvo.closest('[data-reabrir]'));
    }
    if (alvo.closest('[data-abrir-saida]')) {
      evento.stopPropagation();
      cardDaSaida = alvo.closest('.kanban-card');
      idsDoLote = [];
      return abrirModalSaida();
    }
    if (alvo.closest('#lote-mover')) return moverLote();
    if (alvo.closest('#lote-sair')) {
      cardDaSaida = null;
      idsDoLote = marcados().map(i => Number(i.value));
      return abrirModalSaida();
    }

    const opcao = alvo.closest('[data-saida-opcao]');
    if (opcao) {
      const m = modal();
      m.querySelectorAll('[data-saida-opcao]').forEach(o => o.classList.remove('is-selected'));
      opcao.classList.add('is-selected');
      m.querySelector('[data-saida-valor]').value = opcao.dataset.saidaOpcao;
      return;
    }
    if (alvo.closest('[data-confirmar-saida]')) return confirmarSaida();

    // Abrir a ficha. Fica FORA da guarda de permissao de proposito: abrir a
    // ficha e leitura, e quem so tem people.ver precisa conseguir clicar.
    const card = alvo.closest('.kanban-card');
    if (card && !arrastouAgora && !alvo.closest('a, button, form, input, label')) {
      if (card.dataset.detalhe) window.location.href = card.dataset.detalhe;
    }
  });

  // ── Selecao em lote ─────────────────────────────────────────────────────

  const marcados = () => Array.from(document.querySelectorAll('.lote-item:checked'));

  function atualizarBarraDeLote() {
    const barra = document.getElementById('lote-barra');
    if (!barra) return;
    const n = marcados().length;
    const total = document.getElementById('lote-total');
    if (total) total.textContent = n;
    barra.hidden = n === 0;
  }

  function aplicarLote(corpo) {
    post('/people/candidatos/lote/', corpo).then(function (resp) {
      if (resp.status === 200) {
        // Recusa parcial nao pode passar batida: o RH precisa saber que alguns
        // nao foram, e por que.
        if (resp.corpo.recusados && resp.corpo.recusados.length) {
          toast('Movidos com ressalva',
                resp.corpo.movidos + ' movidos. ' + resp.corpo.recusados[0], 'warning');
          setTimeout(() => trocarConteudo(window.location.href, false), 2000);
        } else {
          trocarConteudo(window.location.href, false);
        }
        return;
      }
      toast('Nao foi possivel', resp.corpo.erro || 'Erro inesperado.', 'danger');
    }).catch(() => toast('Nao foi possivel', 'Falha de conexao.', 'danger'));
  }

  function moverLote() {
    const etapa = document.getElementById('lote-etapa')?.value;
    if (!etapa) { toast('Escolha a etapa', 'Diga pra onde mover.', 'warning'); return; }
    aplicarLote({ acao: 'etapa', etapa_id: Number(etapa),
                  ids: marcados().map(i => Number(i.value)) });
  }

  // ── Acoes rapidas do card ───────────────────────────────────────────────
  //
  // Existem porque com 82 candidatos numa etapa, abrir a ficha e voltar 82
  // vezes e o que faz o RH desistir da tela.

  function moverCandidato(botao, etapaId, aviso) {
    const card = botao.closest('.kanban-card');
    const d = dados();
    if (!card || !d) return;
    botao.disabled = true;
    post(d.dataset.urlMover.replace('0', card.dataset.candidatoId),
         { etapa_id: Number(etapaId) }).then(function (resp) {
      if (resp.status === 200) { trocarConteudo(window.location.href, false); return; }
      botao.disabled = false;
      toast(aviso, resp.corpo.erro || 'Tente de novo.', 'danger');
    }).catch(function () {
      botao.disabled = false;
      toast(aviso, 'Falha de conexao.', 'danger');
    });
  }

  function avancar(botao) {
    moverCandidato(botao, botao.dataset.avancar, 'Nao consegui mover');
  }

  function reabrir(botao) {
    const primeira = dados()?.dataset.primeiraEtapa;
    if (!primeira) {
      toast('Sem etapa', 'O fluxo nao tem etapa pra onde reativar.', 'warning');
      return;
    }
    moverCandidato(botao, primeira, 'Nao consegui reativar');
  }

  // ── Modal de saida: serve lista, lote e kanban ──────────────────────────

  function abrirModalSaida() {
    const m = modal();
    if (!m) return;
    m.querySelector('[data-motivo]').value = '';
    m.querySelector('[data-motivo-codigo]').value = '';
    m.querySelector('[data-saida-valor]').value = '';
    m.querySelectorAll('[data-saida-opcao]').forEach(o => o.classList.remove('is-selected'));
    abrirModal('modal-saida');
  }

  function confirmarSaida() {
    const m = modal();
    const saida = m.querySelector('[data-saida-valor]').value;
    const motivoCodigo = m.querySelector('[data-motivo-codigo]').value;
    const motivo = m.querySelector('[data-motivo]').value.trim();

    if (!saida) { toast('Escolha uma saida', 'Diga pra onde o candidato vai.', 'warning'); return; }
    if (!motivoCodigo) { toast('Registre o motivo', 'Toda saida precisa de um motivo.', 'warning'); return; }
    // "Outro" sozinho nao diz nada, e e justamente o motivo que mais some na
    // analise depois. Ai o detalhe vira obrigatorio.
    if (motivoCodigo === 'outro' && !motivo) {
      toast('Descreva o motivo', 'Com "Outro", o detalhe e obrigatorio.', 'warning');
      return;
    }

    if (!cardDaSaida && idsDoLote.length) {
      aplicarLote({ acao: 'saida', saida: saida, motivo: motivo,
                    motivo_codigo: motivoCodigo, ids: idsDoLote });
      fecharModal('modal-saida');
      return;
    }

    const d = dados();
    if (!cardDaSaida || !d) return;
    post(d.dataset.urlSaida.replace('0', cardDaSaida.dataset.candidatoId),
         { saida: saida, motivo: motivo, motivo_codigo: motivoCodigo })
      .then(function (resp) {
        if (resp.status === 200) {
          fecharModal('modal-saida');
          toast('Candidato movido', 'Saiu do processo: ' + (resp.corpo.rotulo || ''), 'success');
          if (resp.corpo.aviso) toast('Atenção', resp.corpo.aviso, 'warning');
          trocarConteudo(window.location.href, false);
          return;
        }
        toast('Nao foi possivel', resp.corpo.erro || 'Erro inesperado.', 'danger');
      }).catch(() => toast('Nao foi possivel', 'Falha de conexao.', 'danger'));
  }

  // ── Arrastar no kanban ──────────────────────────────────────────────────
  //
  // Tambem por delegacao: dragstart e drop borbulham, entao um listener no
  // documento cobre os cards que a busca parcial trouxer depois.

  document.addEventListener('dragstart', function (evento) {
    const card = evento.target.closest?.('.kanban-card');
    if (!card || dados()?.dataset.podeMover !== '1') return;
    arrastando = card;
    colunaOrigem = card.closest('.kanban-col');
    arrastouAgora = true;
    card.classList.add('is-dragging');
    evento.dataTransfer.effectAllowed = 'move';
    evento.dataTransfer.setData('text/plain', card.dataset.candidatoId || '');
  });

  document.addEventListener('dragend', function (evento) {
    evento.target.closest?.('.kanban-card')?.classList.remove('is-dragging');
    document.querySelectorAll('.kanban-col').forEach(c => c.classList.remove('is-drop-target'));
    // Solta a trava no proximo tick: o clique sintetico, quando vem, chega
    // logo apos o dragend. Sem isso, soltar o card abriria a ficha.
    setTimeout(function () { arrastouAgora = false; }, 0);
  });

  document.addEventListener('dragover', function (evento) {
    // So etapa aceita: saida exige motivo, e o arrasto nao tem onde perguntar.
    const coluna = evento.target.closest?.('.kanban-col[data-etapa-id]');
    if (!coluna || !arrastando) return;
    evento.preventDefault();
    coluna.classList.add('is-drop-target');
  });

  document.addEventListener('dragleave', function (evento) {
    evento.target.closest?.('.kanban-col')?.classList.remove('is-drop-target');
  });

  document.addEventListener('drop', function (evento) {
    const coluna = evento.target.closest?.('.kanban-col[data-etapa-id]');
    if (!coluna) return;
    evento.preventDefault();
    coluna.classList.remove('is-drop-target');
    if (!arrastando || colunaOrigem === coluna) return;

    const card = arrastando;
    post(dados().dataset.urlMover.replace('0', card.dataset.candidatoId),
         { etapa_id: Number(coluna.dataset.etapaId) }).then(function (resp) {
      if (resp.status === 200) { trocarConteudo(window.location.href, false); return; }
      toast('Nao foi possivel mover', resp.corpo.erro || 'Erro inesperado.', 'danger');
    }).catch(() => toast('Nao foi possivel mover', 'Falha de conexao.', 'danger'));
  });

  // Cards so ficam arrastaveis pra quem pode mover, e o atributo precisa valer
  // tambem no conteudo que a busca parcial trouxer.
  function marcarArrastaveis() {
    if (dados()?.dataset.podeMover !== '1') return;
    document.querySelectorAll('.kanban-card').forEach(c => { c.draggable = true; });
  }

  marcarArrastaveis();
  new MutationObserver(marcarArrastaveis).observe(
    document.body, { childList: true, subtree: true });
})();
