/**
 * Board do ciclo de vida do colaborador.
 *
 * Drag and drop nativo (HTML5), sem lib externa, no mesmo espirito do kanban de
 * projetos do workspace. A diferenca que justifica codigo proprio: aqui a
 * transicao pode ser RECUSADA por falta de campo obrigatorio, e a resposta
 * certa nao e reverter o card, e sim perguntar o que falta e repetir.
 *
 * Sem isso o gestor arrasta, o card volta sozinho e ele nao sabe por que. Com
 * isso ele arrasta, o sistema pede a data de admissao, ele preenche e pronto.
 *
 * Contrato do endpoint (POST):
 *   entra: { situacao, dados: {campo: valor} }
 *   sai 200: { ok: true, situacao, rotulo }
 *   sai 400: { erro, campos_faltando: [{nome, label, tipo}] }
 */
(function () {
  'use strict';

  // Filtro de unidade recarrega ao trocar. O <noscript> do template cobre quem
  // nao tem JS, entao o board nao depende disto pra funcionar.
  const filtro = document.querySelector('#filtro-board select');
  if (filtro) {
    filtro.addEventListener('change', function () { filtro.form.submit(); });
  }

  const board = document.querySelector('.kanban-board');
  if (!board) return;

  const podeMover = board.dataset.podeMover === '1';
  const urlMover = board.dataset.urlMover;
  const csrf = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

  if (!podeMover) return;

  let arrastando = null;
  let colunaOrigem = null;

  // ── Cards ──────────────────────────────────────────────────────────────
  function ligarCard(card) {
    card.draggable = true;

    card.addEventListener('dragstart', function (e) {
      arrastando = card;
      colunaOrigem = card.closest('.kanban-col');
      card.classList.add('is-dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', card.dataset.colaboradorId || '');
    });

    card.addEventListener('dragend', function () {
      card.classList.remove('is-dragging');
      document.querySelectorAll('.kanban-col').forEach(function (col) {
        col.classList.remove('is-drop-target', 'is-drop-blocked');
      });
    });
  }

  document.querySelectorAll('.kanban-card').forEach(ligarCard);

  // ── Colunas ────────────────────────────────────────────────────────────
  document.querySelectorAll('.kanban-col').forEach(function (coluna) {
    coluna.addEventListener('dragover', function (e) {
      if (!arrastando) return;
      const destino = coluna.dataset.situacao;
      const permitidos = (arrastando.dataset.destinos || '').split(',');

      // A maquina de estados ja disse o que da e o que nao da. Sinalizar antes
      // do drop evita a frustacao de soltar e ver o card voltar.
      if (permitidos.indexOf(destino) === -1) {
        coluna.classList.add('is-drop-blocked');
        return;
      }
      e.preventDefault();
      coluna.classList.add('is-drop-target');
    });

    coluna.addEventListener('dragleave', function () {
      coluna.classList.remove('is-drop-target', 'is-drop-blocked');
    });

    coluna.addEventListener('drop', function (e) {
      e.preventDefault();
      coluna.classList.remove('is-drop-target', 'is-drop-blocked');
      if (!arrastando) return;

      const card = arrastando;
      const destino = coluna.dataset.situacao;
      const origem = colunaOrigem;
      if (origem === coluna) return;

      mover(card, destino, {}, origem, coluna);
    });
  });

  // ── Mover ──────────────────────────────────────────────────────────────
  function mover(card, situacao, dados, origem, destinoCol) {
    const id = card.dataset.colaboradorId;

    fetch(urlMover.replace('0', id), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
      body: JSON.stringify({ situacao: situacao, dados: dados }),
    })
      .then(function (r) { return r.json().then(function (j) { return { status: r.status, corpo: j }; }); })
      .then(function (resposta) {
        if (resposta.status === 200) {
          aplicarMovimento(card, destinoCol, origem, resposta.corpo);
          return;
        }
        if (resposta.status === 400 && resposta.corpo.campos_faltando) {
          pedirCampos(card, situacao, resposta.corpo, origem, destinoCol);
          return;
        }
        toast('Nao foi possivel mover', resposta.corpo.erro || 'Erro inesperado.', 'danger');
      })
      .catch(function () {
        toast('Nao foi possivel mover', 'Falha de conexao.', 'danger');
      });
  }

  function aplicarMovimento(card, destinoCol, origem, corpo) {
    destinoCol.querySelector('.kanban-col-body').appendChild(card);
    card.dataset.destinos = (corpo.destinos || []).join(',');
    atualizarContador(origem);
    atualizarContador(destinoCol);
    limparVazio(destinoCol);
    marcarVazio(origem);
    toast('Colaborador movido', corpo.rotulo || '', 'success');
  }

  // ── Pedir o que a transicao exige ──────────────────────────────────────
  function pedirCampos(card, situacao, corpo, origem, destinoCol) {
    const modal = document.getElementById('modal-campos-transicao');
    const corpoModal = modal.querySelector('[data-campos]');
    const titulo = modal.querySelector('[data-titulo]');

    titulo.textContent = corpo.erro || 'Faltam dados pra concluir';
    corpoModal.innerHTML = '';

    corpo.campos_faltando.forEach(function (campo) {
      const wrap = document.createElement('div');
      wrap.className = 'field';
      wrap.innerHTML =
        '<label class="field-label" for="tr-' + campo.nome + '">' + campo.label +
        ' <span class="field-required">*</span></label>' +
        '<div class="field-input-wrap">' +
        '<input class="field-input" id="tr-' + campo.nome + '" name="' + campo.nome +
        '" type="' + (campo.tipo || 'text') + '" required>' +
        '</div>';
      corpoModal.appendChild(wrap);
    });

    const confirmar = modal.querySelector('[data-confirmar]');
    const novo = confirmar.cloneNode(true);  // limpa handlers de aberturas anteriores
    confirmar.parentNode.replaceChild(novo, confirmar);

    novo.addEventListener('click', function () {
      const dados = {};
      let faltou = false;
      corpo.campos_faltando.forEach(function (campo) {
        const input = document.getElementById('tr-' + campo.nome);
        if (!input.value) { faltou = true; input.closest('.field').classList.add('has-error'); return; }
        dados[campo.nome] = input.value;
      });
      if (faltou) return;
      fecharModal('modal-campos-transicao');
      mover(card, situacao, dados, origem, destinoCol);
    });

    abrirModal('modal-campos-transicao');
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
