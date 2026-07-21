/**
 * Board do pipeline de recrutamento.
 *
 * A tela tem duas vistas:
 *
 *   LISTA (padrao) — chips por etapa e por saida no topo, e a lista da selecao.
 *   Aqui o volume manda: dezenas de candidatos numa etapa cabem numa lista e
 *   nao cabem numa coluna. Tem selecao em lote.
 *
 *   KANBAN (toggle) — colunas arrastaveis. Melhor com poucos candidatos, porque
 *   mover e arrastar.
 *
 * Duas regras que valem nas duas vistas:
 *   Mover ENTRE etapas e livre (etapa e configuracao, nao maquina de estados).
 *   SAIR do pipeline exige motivo e passa por regra, entao e modal, nao arrasto.
 */
(function () {
  'use strict';

  const csrf = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
  const modal = document.getElementById('modal-saida');

  // Alvo do modal de saida: um card (kanban), uma linha, ou uma lista de ids
  // (lote). Guardar os dois evita dois modais que fazem a mesma coisa.
  let cardDaSaida = null;
  let idsDoLote = [];

  function post(url, corpo) {
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
      body: JSON.stringify(corpo),
    }).then(r => r.json().then(j => ({ status: r.status, corpo: j })));
  }

  function abrirModalSaida() {
    if (!modal) return;
    modal.querySelector('[data-motivo]').value = '';
    modal.querySelector('[data-saida-valor]').value = '';
    modal.querySelectorAll('[data-saida-opcao]').forEach(o => o.classList.remove('is-selected'));
    abrirModal('modal-saida');
  }

  // ── Filtros ─────────────────────────────────────────────────────────────
  document.querySelectorAll('#filtro-pipeline select').forEach(function (s) {
    s.addEventListener('change', function () { s.form.submit(); });
  });

  // ── Selecao em lote (vista de lista) ────────────────────────────────────
  const barra = document.getElementById('lote-barra');
  if (barra) {
    const itens = () => Array.from(document.querySelectorAll('.lote-item'));
    const marcados = () => itens().filter(i => i.checked);

    function atualizarBarra() {
      const n = marcados().length;
      document.getElementById('lote-total').textContent = n;
      barra.hidden = n === 0;
    }

    document.getElementById('lote-todos')?.addEventListener('change', function () {
      itens().forEach(i => { i.checked = this.checked; });
      atualizarBarra();
    });
    itens().forEach(i => i.addEventListener('change', atualizarBarra));

    function aplicarLote(corpo) {
      post('/people/candidatos/lote/', corpo).then(function (resp) {
        if (resp.status === 200) {
          // Recusa parcial nao pode passar batida: o RH precisa saber que
          // alguns nao foram, e por que.
          if (resp.corpo.recusados && resp.corpo.recusados.length) {
            toast('Movidos com ressalva',
                  resp.corpo.movidos + ' movidos. ' + resp.corpo.recusados[0], 'warning');
            setTimeout(() => window.location.reload(), 2500);
          } else {
            window.location.reload();
          }
          return;
        }
        toast('Nao foi possivel', resp.corpo.erro || 'Erro inesperado.', 'danger');
      }).catch(() => toast('Nao foi possivel', 'Falha de conexao.', 'danger'));
    }

    document.getElementById('lote-mover')?.addEventListener('click', function () {
      const etapa = document.getElementById('lote-etapa').value;
      if (!etapa) { toast('Escolha a etapa', 'Diga pra onde mover.', 'warning'); return; }
      aplicarLote({ acao: 'etapa', etapa_id: Number(etapa),
                    ids: marcados().map(i => Number(i.value)) });
    });

    document.getElementById('lote-sair')?.addEventListener('click', function () {
      cardDaSaida = null;
      idsDoLote = marcados().map(i => Number(i.value));
      abrirModalSaida();
    });

    // Guarda o aplicador pro modal alcancar no modo lote.
    barra._aplicar = aplicarLote;
  }

  // ── Modal de saida: serve lista, lote e kanban ──────────────────────────
  if (modal) {
    modal.querySelectorAll('[data-saida-opcao]').forEach(function (opcao) {
      opcao.addEventListener('click', function () {
        modal.querySelectorAll('[data-saida-opcao]').forEach(o => o.classList.remove('is-selected'));
        opcao.classList.add('is-selected');
        modal.querySelector('[data-saida-valor]').value = opcao.dataset.saidaOpcao;
      });
    });

    modal.querySelector('[data-confirmar-saida]')?.addEventListener('click', function () {
      const saida = modal.querySelector('[data-saida-valor]').value;
      const motivo = modal.querySelector('[data-motivo]').value.trim();

      if (!saida) { toast('Escolha uma saida', 'Diga pra onde o candidato vai.', 'warning'); return; }
      if (!motivo) { toast('Registre o motivo', 'Toda saida precisa de um motivo.', 'warning'); return; }

      // Modo lote
      if (!cardDaSaida && idsDoLote.length) {
        barra._aplicar({ acao: 'saida', saida: saida, motivo: motivo, ids: idsDoLote });
        fecharModal('modal-saida');
        return;
      }

      // Modo card unico (kanban)
      const tabuleiro = document.querySelector('.kanban-board');
      if (!cardDaSaida || !tabuleiro) return;
      const id = cardDaSaida.dataset.candidatoId;
      post(tabuleiro.dataset.urlSaida.replace('0', id),
           { saida: saida, motivo: motivo }).then(function (resp) {
        if (resp.status === 200) {
          const origem = cardDaSaida.closest('.kanban-col');
          cardDaSaida.remove();
          atualizarContador(origem);
          marcarVazio(origem);
          fecharModal('modal-saida');
          toast('Candidato movido', 'Saiu do processo: ' + (resp.corpo.rotulo || ''), 'success');
          if (resp.corpo.aviso) toast('Atenção', resp.corpo.aviso, 'warning');
          return;
        }
        toast('Nao foi possivel', resp.corpo.erro || 'Erro inesperado.', 'danger');
      }).catch(() => toast('Nao foi possivel', 'Falha de conexao.', 'danger'));
    });
  }

  // ── Abrir a ficha: vale pra QUALQUER um que enxerga o board ─────────────
  //
  // Fica fora da guarda de `podeMover` de proposito. Abrir a ficha e leitura,
  // nao movimentacao: quem so tem people.ver precisa conseguir clicar no card.
  let arrastouAgora = false;

  document.querySelectorAll('.kanban-card').forEach(function (card) {
    card.addEventListener('click', function (e) {
      if (arrastouAgora) return;
      if (e.target.closest('a, button, form, input')) return;
      const destino = card.dataset.detalhe;
      if (destino) window.location.href = destino;
    });
  });

  document.querySelectorAll('[data-abrir-saida]').forEach(function (botao) {
    botao.addEventListener('click', function () {
      cardDaSaida = botao.closest('.kanban-card');
      idsDoLote = [];
      abrirModalSaida();
    });
  });

  // ── Daqui pra baixo: kanban, so pra quem pode mover ─────────────────────
  const board = document.querySelector('.kanban-board');
  if (!board) return;

  const podeMover = board.dataset.podeMover === '1';
  const urlMover = board.dataset.urlMover;
  if (!podeMover) return;

  let arrastando = null;
  let colunaOrigem = null;

  document.querySelectorAll('.kanban-card').forEach(function (card) {
    card.draggable = true;

    card.addEventListener('dragstart', function (e) {
      arrastando = card;
      colunaOrigem = card.closest('.kanban-col');
      arrastouAgora = true;
      card.classList.add('is-dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', card.dataset.candidatoId || '');
    });

    card.addEventListener('dragend', function () {
      card.classList.remove('is-dragging');
      document.querySelectorAll('.kanban-col').forEach(function (col) {
        col.classList.remove('is-drop-target');
      });
      // Solta a trava no proximo tick: o clique sintetico, quando vem, chega
      // logo apos o dragend. Sem isso, soltar o card abriria a ficha.
      setTimeout(function () { arrastouAgora = false; }, 0);
    });
  });

  // Toda etapa aceita o drop: mover entre etapas e livre.
  document.querySelectorAll('.kanban-col[data-etapa-id]').forEach(function (coluna) {
    coluna.addEventListener('dragover', function (e) {
      if (!arrastando) return;
      e.preventDefault();
      coluna.classList.add('is-drop-target');
    });
    coluna.addEventListener('dragleave', function () {
      coluna.classList.remove('is-drop-target');
    });
    coluna.addEventListener('drop', function (e) {
      e.preventDefault();
      coluna.classList.remove('is-drop-target');
      if (!arrastando || colunaOrigem === coluna) return;

      const card = arrastando;
      const origem = colunaOrigem;
      post(urlMover.replace('0', card.dataset.candidatoId),
           { etapa_id: Number(coluna.dataset.etapaId) }).then(function (resp) {
        if (resp.status === 200) {
          coluna.querySelector('.kanban-col-body').appendChild(card);
          atualizarContador(origem);
          atualizarContador(coluna);
          limparVazio(coluna);
          marcarVazio(origem);
          return;
        }
        toast('Nao foi possivel mover', resp.corpo.erro || 'Erro inesperado.', 'danger');
      }).catch(() => toast('Nao foi possivel mover', 'Falha de conexao.', 'danger'));
    });
  });

  // ── Contadores e estado vazio ──────────────────────────────────────────
  function atualizarContador(coluna) {
    if (!coluna) return;
    const alvo = coluna.querySelector('.kanban-col-count');
    if (alvo) alvo.textContent = coluna.querySelectorAll('.kanban-card').length;
  }

  function limparVazio(coluna) {
    coluna.querySelector('.kanban-empty')?.remove();
  }

  function marcarVazio(coluna) {
    if (!coluna) return;
    const body = coluna.querySelector('.kanban-col-body');
    if (body.querySelectorAll('.kanban-card').length === 0 && !body.querySelector('.kanban-empty')) {
      const vazio = document.createElement('p');
      vazio.className = 'kanban-empty';
      vazio.textContent = 'Vazio';
      body.appendChild(vazio);
    }
  }
})();
