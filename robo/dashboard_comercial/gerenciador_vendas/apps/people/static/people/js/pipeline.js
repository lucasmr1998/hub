/**
 * Board do pipeline de recrutamento.
 *
 * Drag and drop nativo, no mesmo espirito do board do DP, com duas diferencas
 * que vem do dominio:
 *
 *   Mover ENTRE etapas e livre. Etapa e configuracao, nao maquina de estados,
 *   entao toda coluna aceita o drop. Nao ha o sinal "bloqueado" do board do DP.
 *
 *   SAIR do pipeline nao e arrasto, e acao. A saida exige motivo e passa por
 *   regra (admitido vinculado nao volta), entao vive num menu por card que abre
 *   um modal, e nao numa coluna pra onde se arrasta.
 *
 * Contratos (POST):
 *   mover:  entra { etapa_id } -> 200 { ok, etapa_id }
 *   saida:  entra { saida, motivo } -> 200 { ok, saida, rotulo }
 *                                   -> 400 { erro, precisa_motivo }
 */
(function () {
  'use strict';

  document.querySelectorAll('#filtro-pipeline select').forEach(function (s) {
    s.addEventListener('change', function () { s.form.submit(); });
  });

  const board = document.querySelector('.kanban-board');
  if (!board) return;

  const podeMover = board.dataset.podeMover === '1';
  const urlMover = board.dataset.urlMover;
  const urlSaida = board.dataset.urlSaida;
  const csrf = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

  if (!podeMover) return;

  let arrastando = null;
  let colunaOrigem = null;
  // Marca que houve arrasto, pra o clique que vem logo depois nao navegar. O
  // navegador ja costuma suprimir esse clique, mas nao da pra confiar: soltar o
  // card e cair na ficha e o tipo de surpresa que faz o usuario parar de
  // arrastar.
  let arrastouAgora = false;

  // ── Cards ──────────────────────────────────────────────────────────────
  function ligarCard(card) {
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
      // logo apos o dragend.
      setTimeout(function () { arrastouAgora = false; }, 0);
    });

    // Card inteiro abre a ficha. Clique em acao (link do curriculo, botao de
    // saida) NAO navega: quem clicou no botao quer o botao.
    card.addEventListener('click', function (e) {
      if (arrastouAgora) return;
      if (e.target.closest('a, button, form')) return;
      const destino = card.dataset.detalhe;
      if (destino) window.location.href = destino;
    });
  }

  document.querySelectorAll('.kanban-card').forEach(ligarCard);

  // ── Colunas: toda etapa aceita o drop ──────────────────────────────────
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
      mover(arrastando, coluna, colunaOrigem);
    });
  });

  // ── Mover de etapa ─────────────────────────────────────────────────────
  function mover(card, destinoCol, origem) {
    const id = card.dataset.candidatoId;
    const etapaId = destinoCol.dataset.etapaId;

    fetch(urlMover.replace('0', id), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
      body: JSON.stringify({ etapa_id: Number(etapaId) }),
    })
      .then(function (r) { return r.json().then(function (j) { return { status: r.status, corpo: j }; }); })
      .then(function (resposta) {
        if (resposta.status === 200) {
          destinoCol.querySelector('.kanban-col-body').appendChild(card);
          atualizarContador(origem);
          atualizarContador(destinoCol);
          limparVazio(destinoCol);
          marcarVazio(origem);
          return;
        }
        toast('Nao foi possivel mover', resposta.corpo.erro || 'Erro inesperado.', 'danger');
      })
      .catch(function () { toast('Nao foi possivel mover', 'Falha de conexao.', 'danger'); });
  }

  // ── Saida: botao por card abre o modal ─────────────────────────────────
  let cardDaSaida = null;

  document.querySelectorAll('[data-abrir-saida]').forEach(function (botao) {
    botao.addEventListener('click', function () {
      cardDaSaida = botao.closest('.kanban-card');
      const modal = document.getElementById('modal-saida');
      modal.querySelector('[data-motivo]').value = '';
      modal.querySelector('[data-saida-valor]').value = '';
      modal.querySelectorAll('[data-saida-opcao]').forEach(function (o) {
        o.classList.remove('is-selected');
      });
      abrirModal('modal-saida');
    });
  });

  document.querySelectorAll('[data-saida-opcao]').forEach(function (opcao) {
    opcao.addEventListener('click', function () {
      document.querySelectorAll('[data-saida-opcao]').forEach(function (o) {
        o.classList.remove('is-selected');
      });
      opcao.classList.add('is-selected');
      document.querySelector('[data-saida-valor]').value = opcao.dataset.saidaOpcao;
    });
  });

  const confirmarSaida = document.querySelector('[data-confirmar-saida]');
  if (confirmarSaida) {
    confirmarSaida.addEventListener('click', function () {
      const saida = document.querySelector('[data-saida-valor]').value;
      const motivo = document.querySelector('[data-motivo]').value.trim();

      if (!saida) { toast('Escolha uma saida', 'Diga pra onde o candidato vai.', 'warning'); return; }
      if (!motivo) { toast('Registre o motivo', 'Toda saida precisa de um motivo.', 'warning'); return; }

      const id = cardDaSaida.dataset.candidatoId;
      fetch(urlSaida.replace('0', id), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        body: JSON.stringify({ saida: saida, motivo: motivo }),
      })
        .then(function (r) { return r.json().then(function (j) { return { status: r.status, corpo: j }; }); })
        .then(function (resposta) {
          if (resposta.status === 200) {
            const origem = cardDaSaida.closest('.kanban-col');
            cardDaSaida.remove();
            atualizarContador(origem);
            marcarVazio(origem);
            fecharModal('modal-saida');
            toast('Candidato movido', 'Saiu do processo: ' + (resposta.corpo.rotulo || ''), 'success');
            return;
          }
          toast('Nao foi possivel', resposta.corpo.erro || 'Erro inesperado.', 'danger');
        })
        .catch(function () { toast('Nao foi possivel', 'Falha de conexao.', 'danger'); });
    });
  }

  // ── Contadores e estado vazio ──────────────────────────────────────────
  function atualizarContador(coluna) {
    if (!coluna) return;
    const total = coluna.querySelectorAll('.kanban-card').length;
    const alvo = coluna.querySelector('.kanban-col-count');
    if (alvo) alvo.textContent = total;
  }

  function limparVazio(coluna) {
    const vazio = coluna.querySelector('.kanban-empty');
    if (vazio) vazio.remove();
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
