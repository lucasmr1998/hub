/**
 * Hub de Configuracoes do recrutamento: Etapas, Mensagens, Campos, Captacao.
 *
 * Abas CLIENT-SIDE: trocar de aba mostra/esconde painel, sem recarregar. Criar
 * e editar etapa/campo acontecem em modal, reusando um form so pra criar e
 * editar (dois forms identicos e a origem classica de um divergir do outro).
 *
 * Tudo por delegacao no documento: e o mesmo motivo do pipeline.js, e de quebra
 * deixa o codigo indiferente a qual painel esta visivel no momento do clique.
 */
(function () {
  'use strict';

  // Chamadas via window NA HORA do clique, e nao capturadas agora: o
  // layout_app.html define abrirModal/fecharModal num <script> que roda DEPOIS
  // deste, entao capturar a referencia aqui pegaria undefined e o modal nunca
  // abriria.
  const abrir = function (id) { (window.abrirModal || function () {})(id); };

  // ── Abas ────────────────────────────────────────────────────────────────

  function trocarAba(aba) {
    document.querySelectorAll('.tabs-item').forEach(function (botao) {
      const ativo = botao.dataset.tab === aba;
      botao.classList.toggle('is-active', ativo);
      botao.setAttribute('aria-selected', ativo ? 'true' : 'false');
    });
    document.querySelectorAll('.config-painel').forEach(function (painel) {
      painel.hidden = painel.id !== aba;
    });

    // Seletor de unidade so vale pras abas que ele declara em data-abas. Some
    // nas outras pra nao sugerir que filtrar unidade muda Campos ou Captacao.
    const filtro = document.getElementById('filtro-unidade');
    if (filtro) {
      const valeAqui = (filtro.dataset.abas || '').split(' ').indexOf(aba) !== -1;
      filtro.style.display = valeAqui ? '' : 'none';
      // O reload de unidade precisa cair na aba atual, e nao na padrao.
      const campoTab = filtro.querySelector('input[name=tab]');
      if (campoTab) campoTab.value = aba;
    }

    // ?tab= na URL, pra refresh e link manterem a aba. replaceState, e nao push:
    // trocar de aba nao e navegar, e encher o historico atrapalharia o voltar.
    const url = new URL(window.location.href);
    url.searchParams.set('tab', aba);
    window.history.replaceState({}, '', url);
  }

  // ── Modal de etapa ──────────────────────────────────────────────────────

  function sincronizarBlocos() {
    // Os textareas de roteiro e checklist so aparecem quando o bloco
    // correspondente esta marcado. O fluxo antigo CHAMAVA esta funcao mas nunca
    // a definia, entao os campos ficavam escondidos pra sempre: o RH marcava
    // "Roteiro" e nao tinha onde escrever as perguntas.
    const marcado = function (valor) {
      const caixa = document.querySelector('#form-etapa [name=blocos][value="' + valor + '"]');
      return caixa && caixa.checked;
    };
    const roteiro = document.getElementById('bloco-roteiro');
    const checklist = document.getElementById('bloco-checklist');
    if (roteiro) roteiro.hidden = !marcado('roteiro');
    if (checklist) checklist.hidden = !marcado('checklist');
  }

  function abrirEtapaNova() {
    const form = document.getElementById('form-etapa');
    if (!form) return;
    form.reset();
    document.getElementById('etapa-pk').value = '';
    document.getElementById('titulo-modal-etapa').textContent = 'Nova etapa';
    sincronizarBlocos();
    abrir('modal-etapa');
  }

  function abrirEtapaEdicao(idJson) {
    const no = document.getElementById(idJson);
    if (!no) return;
    // O dado vem de um <script type="application/json">, e nao de um data-*:
    // roteiro e checklist tem quebra de linha, que num atributo geraria JSON
    // invalido. O json_script escapa certo.
    const dados = JSON.parse(no.textContent);
    const form = document.getElementById('form-etapa');
    document.getElementById('etapa-pk').value = dados.pk;
    form.querySelector('[name=nome]').value = dados.nome || '';
    document.getElementById('etapa-cor').value = dados.cor || '';
    form.querySelector('[name=sla_dias]').value = dados.sla || '';
    form.querySelectorAll('[name=blocos]').forEach(function (caixa) {
      caixa.checked = (dados.blocos || []).indexOf(caixa.value) !== -1;
    });
    form.querySelector('[name=roteiro]').value = dados.roteiro || '';
    form.querySelector('[name=checklist]').value = dados.checklist || '';
    sincronizarBlocos();
    document.getElementById('titulo-modal-etapa').textContent = 'Editar: ' + dados.nome;
    abrir('modal-etapa');
  }

  // ── Modal de campo ──────────────────────────────────────────────────────

  function sincronizarOpcoes() {
    // Opcoes so fazem sentido no tipo lista. Mostrar sempre convidaria a
    // preencher opcao num campo de texto, que o salvar descartaria calado.
    const tipo = document.getElementById('campo-tipo');
    const bloco = document.getElementById('bloco-opcoes');
    if (tipo && bloco) bloco.hidden = tipo.value !== 'select';
  }

  function abrirCampoNovo() {
    const form = document.getElementById('form-campo');
    if (!form) return;
    form.reset();
    document.getElementById('campo-pk').value = '';
    document.getElementById('titulo-modal-campo').textContent = 'Novo campo';
    sincronizarOpcoes();
    abrir('modal-campo');
  }

  // ── Modal de quadro ─────────────────────────────────────────────────────

  function abrirQuadroNovo() {
    // So cria: redefinir e re-salvar o mesmo cargo+unidade (o form recusa
    // duplicata e manda editar o existente), entao nao ha edicao a popular.
    const form = document.getElementById('form-quadro');
    if (!form) return;
    form.reset();
    abrir('modal-quadro');
  }

  function abrirLinkNovo() {
    // Link nao tem edicao: se errou, desativa e cria outro. So cria.
    const form = document.getElementById('form-link');
    if (!form) return;
    form.reset();
    abrir('modal-link');
  }

  function abrirCampoEdicao(dados) {
    const form = document.getElementById('form-campo');
    document.getElementById('campo-pk').value = dados.pk;
    form.querySelector('[name=nome]').value = dados.nome || '';
    form.querySelector('[name=ajuda]').value = dados.ajuda || '';
    form.querySelector('[name=opcoes]').value = dados.opcoes || '';
    document.getElementById('campo-tipo').value = dados.tipo;
    document.getElementById('campo-secao').value = dados.secao;
    sincronizarOpcoes();
    document.getElementById('titulo-modal-campo').textContent = 'Editar: ' + dados.nome;
    abrir('modal-campo');
  }

  // ── Delegacao ───────────────────────────────────────────────────────────

  document.addEventListener('click', function (evento) {
    const aba = evento.target.closest('.tabs-item');
    if (aba) { trocarAba(aba.dataset.tab); return; }

    if (evento.target.closest('[data-nova-etapa]')) { abrirEtapaNova(); return; }
    if (evento.target.closest('[data-novo-campo]')) { abrirCampoNovo(); return; }
    if (evento.target.closest('[data-novo-quadro]')) { abrirQuadroNovo(); return; }
    if (evento.target.closest('[data-novo-link]')) { abrirLinkNovo(); return; }

    const editarEtapa = evento.target.closest('[data-editar-etapa]');
    if (editarEtapa) { abrirEtapaEdicao(editarEtapa.dataset.editarEtapa); return; }

    const editarCampo = evento.target.closest('[data-editar-campo]');
    if (editarCampo) { abrirCampoEdicao(JSON.parse(editarCampo.dataset.editarCampo)); return; }

    const copiar = evento.target.closest('[data-copiar]');
    if (copiar) {
      const campo = document.getElementById(copiar.dataset.copiar);
      if (campo) navigator.clipboard.writeText(campo.value).then(function () {
        if (window.toast) toast('Copiado', 'Link na área de transferência.', 'success');
      });
    }
  });

  document.addEventListener('change', function (evento) {
    if (evento.target.matches('#form-etapa [name=blocos]')) sincronizarBlocos();
    if (evento.target.id === 'campo-tipo') sincronizarOpcoes();
    // Trocar a unidade aplica na hora: recarrega com a unidade nova, levando o
    // ?tab pra manter a aba (o reload e inevitavel, sao outras etapas).
    if (evento.target.closest('#filtro-unidade')) evento.target.form.submit();
  });
})();
