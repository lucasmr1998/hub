/**
 * Kanban drag-and-drop nativo (HTML5 Drag and Drop API).
 *
 * Sem libs externas. Funciona com cards <a class="kanban-card"> dentro de
 * colunas <div class="kanban-col" data-status="...">.
 *
 * Ao soltar, faz POST em window.WORKSPACE_API_KANBAN_MOVER com:
 *   { tarefa_id, novo_status, ordem }
 *
 * Em caso de erro, reverte a card pra coluna original e mostra toast.
 */
(function () {
  'use strict';

  const board = document.querySelector('.kanban-board');
  if (!board) return;

  const apiUrl = window.WORKSPACE_API_KANBAN_MOVER;
  const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value
    || getCookie('csrftoken');
  const podeEditar = board.dataset.podeEditar === '1';

  if (!podeEditar) {
    return; // Sem permissao, nao registra handlers
  }

  // ── Estado ────────────────────────────────────────────────────────────────
  let cardArrastando = null;
  let colunaOrigem = null;

  // ── Cards: drag start/end ─────────────────────────────────────────────────
  document.querySelectorAll('.kanban-card').forEach(function (card) {
    card.draggable = true;

    card.addEventListener('dragstart', function (e) {
      cardArrastando = card;
      colunaOrigem = card.closest('.kanban-col');
      card.classList.add('is-dragging');
      e.dataTransfer.effectAllowed = 'move';
      // Truque pra permitir drag sem o ghost feio do Chrome
      e.dataTransfer.setData('text/plain', card.dataset.tarefaId || '');
    });

    card.addEventListener('dragend', function () {
      card.classList.remove('is-dragging');
      document.querySelectorAll('.kanban-col').forEach(function (col) {
        col.classList.remove('is-drop-target');
      });
      cardArrastando = null;
      colunaOrigem = null;
    });
  });

  // ── Colunas: dragover / drop ──────────────────────────────────────────────
  document.querySelectorAll('.kanban-col').forEach(function (col) {
    const body = col.querySelector('.kanban-col-body');

    col.addEventListener('dragover', function (e) {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      col.classList.add('is-drop-target');
    });

    col.addEventListener('dragleave', function (e) {
      // Soh remove se saiu pra fora da coluna mesmo
      if (!col.contains(e.relatedTarget)) {
        col.classList.remove('is-drop-target');
      }
    });

    col.addEventListener('drop', async function (e) {
      e.preventDefault();
      col.classList.remove('is-drop-target');
      if (!cardArrastando) return;

      const novoStatus = col.dataset.status;
      const tarefaId = cardArrastando.dataset.tarefaId;
      const empty = col.querySelector('.kanban-col-empty');

      // Move card no DOM imediatamente (UI otimista)
      if (empty) empty.remove();
      body.appendChild(cardArrastando);
      atualizarContadores();

      // Empty placeholder na coluna que ficou vazia
      if (colunaOrigem && colunaOrigem !== col) {
        const origemBody = colunaOrigem.querySelector('.kanban-col-body');
        if (origemBody && !origemBody.querySelector('.kanban-card')) {
          const placeholder = document.createElement('p');
          placeholder.className = 'kanban-col-empty';
          placeholder.textContent = 'Nenhuma tarefa.';
          origemBody.appendChild(placeholder);
        }
      }

      // Calcula nova ordem (posicao do card dentro da coluna)
      const cardsNaColuna = body.querySelectorAll('.kanban-card');
      let novaOrdem = 0;
      cardsNaColuna.forEach(function (c, idx) {
        if (c === cardArrastando) novaOrdem = idx;
      });

      // POST API
      try {
        const res = await fetch(apiUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest',
          },
          body: JSON.stringify({
            tarefa_id: tarefaId,
            novo_status: novoStatus,
            ordem: novaOrdem,
          }),
        });

        if (!res.ok) {
          const erro = await res.json().catch(() => ({ erro: 'Erro de rede' }));
          throw new Error(erro.erro || `HTTP ${res.status}`);
        }
        const data = await res.json();
        if (!data.ok) throw new Error(data.erro || 'Erro desconhecido');

        // Sucesso — toast leve
        if (typeof window.toast === 'function') {
          window.toast('Tarefa movida', `Status: ${labelStatus(novoStatus)}`, 'success');
        }
      } catch (err) {
        // Reverte: move card de volta pra origem
        if (colunaOrigem) {
          const origemBody = colunaOrigem.querySelector('.kanban-col-body');
          const placeholder = origemBody.querySelector('.kanban-col-empty');
          if (placeholder) placeholder.remove();
          origemBody.appendChild(cardArrastando);
          atualizarContadores();
        }
        if (typeof window.toast === 'function') {
          window.toast('Falha ao mover', err.message || 'Tente novamente.', 'danger');
        } else {
          alert('Falha ao mover: ' + (err.message || ''));
        }
      }
    });
  });

  // ── Helpers ───────────────────────────────────────────────────────────────
  function atualizarContadores() {
    document.querySelectorAll('.kanban-col').forEach(function (col) {
      const count = col.querySelectorAll('.kanban-card').length;
      const badge = col.querySelector('.kanban-count');
      if (badge) badge.textContent = count;
    });
  }

  function labelStatus(s) {
    return ({
      rascunho: 'Rascunho',
      pendente: 'Pendente',
      em_andamento: 'Em andamento',
      concluida: 'Concluida',
      bloqueada: 'Bloqueada',
    })[s] || s;
  }

  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return '';
  }
})();
