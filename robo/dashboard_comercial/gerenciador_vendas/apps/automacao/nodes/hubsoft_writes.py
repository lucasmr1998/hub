"""Nós HubSoft de WRITE moderado: contratos, renegociação (efetivar), OS.

⚠️ Outbound REAL no ERP — criam/alteram registros. NÃO afetam o serviço ativo do
cliente (suspender/desconectar/reset/ativar/habilitar ficaram de fora por risco).
"""
from .base import registrar
from .hubsoft_base import HubsoftNode, _txt, _int, _faltando


def _ids(s):
    return [int(x.strip()) for x in (s or '').replace(';', ',').split(',') if x.strip().isdigit()]


@registrar
class HubsoftCriarContrato(HubsoftNode):
    tipo = "hubsoft_criar_contrato"
    label = "HubSoft: criar contrato"
    icone = "bi-file-earmark-plus"
    saida_chave = "contrato"

    def _campos_extra(self) -> list:
        return [
            {'nome': 'id_cliente_servico', 'label': 'ID cliente-serviço', 'tipo': 'numero', 'obrigatorio': True},
            {'nome': 'id_contrato_modelo', 'label': 'ID modelo de contrato', 'tipo': 'numero', 'obrigatorio': True},
            {'nome': 'id_empresa', 'label': 'ID empresa (HubSoft)', 'tipo': 'numero', 'obrigatorio': True},
            {'nome': 'autorizacao_nome', 'label': 'Nome do titular', 'tipo': 'texto', 'obrigatorio': True,
             'placeholder': '{{lead.nome}}'},
            {'nome': 'autorizacao_cpf', 'label': 'CPF do titular', 'tipo': 'texto', 'obrigatorio': True,
             'placeholder': '{{lead.cpf_cnpj}}'},
            {'nome': 'informacao_adicional', 'label': 'Informação adicional', 'tipo': 'textarea'},
        ]

    def validar_config(self, config) -> list:
        return _faltando(config, ('id_cliente_servico', 'id_contrato_modelo', 'id_empresa',
                                  'autorizacao_nome', 'autorizacao_cpf'))

    def _chamar(self, svc, config, contexto):
        return svc.criar_contrato(
            id_cliente_servico=_int(contexto.resolver(config.get('id_cliente_servico', '')), 0),
            id_contrato_modelo=_int(contexto.resolver(config.get('id_contrato_modelo', '')), 0),
            id_empresa=_int(contexto.resolver(config.get('id_empresa', '')), 0),
            autorizacao_nome=_txt(contexto, config, 'autorizacao_nome'),
            autorizacao_cpf=_txt(contexto, config, 'autorizacao_cpf'),
            informacao_adicional=_txt(contexto, config, 'informacao_adicional'),
        )


@registrar
class HubsoftAceitarContrato(HubsoftNode):
    tipo = "hubsoft_aceitar_contrato"
    label = "HubSoft: aceitar contrato"
    icone = "bi-file-earmark-check"
    saida_chave = "resultado"

    def _campos_extra(self) -> list:
        return [
            {'nome': 'id_contrato', 'label': 'ID do contrato', 'tipo': 'numero', 'obrigatorio': True},
            {'nome': 'observacao', 'label': 'Observação', 'tipo': 'texto'},
        ]

    def validar_config(self, config) -> list:
        return _faltando(config, ('id_contrato',))

    def _chamar(self, svc, config, contexto):
        return svc.aceitar_contrato(
            _int(contexto.resolver(config.get('id_contrato', '')), 0),
            observacao=_txt(contexto, config, 'observacao'))


@registrar
class HubsoftEfetivarRenegociacao(HubsoftNode):
    tipo = "hubsoft_efetivar_renegociacao"
    label = "HubSoft: efetivar renegociação"
    icone = "bi-cash-stack"
    saida_chave = "renegociacao"

    def _campos_extra(self) -> list:
        return [
            {'nome': 'ids_faturas', 'label': 'IDs das faturas (vírgula)', 'tipo': 'texto',
             'obrigatorio': True, 'placeholder': '123,124'},
            {'nome': 'quantidade_parcelas', 'label': 'Qtd parcelas', 'tipo': 'numero', 'obrigatorio': True},
            {'nome': 'vencimento', 'label': '1º vencimento (YYYY-MM-DD)', 'tipo': 'texto', 'obrigatorio': True},
            {'nome': 'cpf_cnpj', 'label': 'CPF/CNPJ', 'tipo': 'texto', 'placeholder': '{{lead.cpf_cnpj}}'},
            {'nome': 'id_cliente', 'label': 'ID cliente (HubSoft)', 'tipo': 'numero'},
        ]

    def validar_config(self, config) -> list:
        erros = _faltando(config, ('ids_faturas', 'quantidade_parcelas', 'vencimento'))
        if not (str(config.get('cpf_cnpj', '')).strip() or str(config.get('id_cliente', '')).strip()):
            erros.append('informe `cpf_cnpj` ou `id_cliente`.')
        return erros

    def _chamar(self, svc, config, contexto):
        kw = {
            'ids_faturas': _ids(_txt(contexto, config, 'ids_faturas')),
            'quantidade_parcelas': _int(contexto.resolver(config.get('quantidade_parcelas', '')), 1),
            'vencimento': _txt(contexto, config, 'vencimento'),
        }
        cpf = _txt(contexto, config, 'cpf_cnpj')
        if cpf:
            kw['cpf_cnpj'] = cpf
        idc = _int(contexto.resolver(config.get('id_cliente', '')), None)
        if idc:
            kw['id_cliente'] = idc
        return svc.efetivar_renegociacao(**kw)


@registrar
class HubsoftAbrirAtendimentoOs(HubsoftNode):
    tipo = "hubsoft_abrir_atendimento_os"
    label = "HubSoft: abrir atendimento/OS"
    icone = "bi-clipboard-plus"
    saida_chave = "atendimento"

    def _campos_extra(self) -> list:
        return [
            {'nome': 'id_cliente_servico', 'label': 'ID cliente-serviço', 'tipo': 'numero', 'obrigatorio': True},
            {'nome': 'descricao', 'label': 'Descrição', 'tipo': 'textarea', 'obrigatorio': True},
            {'nome': 'nome', 'label': 'Nome do contato', 'tipo': 'texto', 'obrigatorio': True,
             'placeholder': '{{lead.nome}}'},
            {'nome': 'telefone', 'label': 'Telefone', 'tipo': 'texto', 'obrigatorio': True,
             'placeholder': '{{lead.telefone}}'},
            {'nome': 'email', 'label': 'E-mail', 'tipo': 'texto'},
            {'nome': 'id_tipo_atendimento', 'label': 'ID tipo de atendimento', 'tipo': 'numero'},
            {'nome': 'abrir_os', 'label': 'Abrir OS junto', 'tipo': 'booleano'},
            {'nome': 'id_tipo_ordem_servico', 'label': 'ID tipo de OS', 'tipo': 'numero'},
            {'nome': 'ids_tecnicos', 'label': 'IDs técnicos (vírgula)', 'tipo': 'texto'},
        ]

    def validar_config(self, config) -> list:
        return _faltando(config, ('id_cliente_servico', 'descricao', 'nome', 'telefone'))

    def _chamar(self, svc, config, contexto):
        kw = dict(
            id_cliente_servico=_int(contexto.resolver(config.get('id_cliente_servico', '')), 0),
            descricao=_txt(contexto, config, 'descricao'),
            nome=_txt(contexto, config, 'nome'),
            telefone=_txt(contexto, config, 'telefone'),
            abrir_os=bool(config.get('abrir_os', True)),
        )
        email = _txt(contexto, config, 'email')
        if email:
            kw['email'] = email
        ita = _int(contexto.resolver(config.get('id_tipo_atendimento', '')), None)
        if ita:
            kw['id_tipo_atendimento'] = ita
        itos = _int(contexto.resolver(config.get('id_tipo_ordem_servico', '')), None)
        if itos:
            kw['id_tipo_ordem_servico'] = itos
        tec = _ids(_txt(contexto, config, 'ids_tecnicos'))
        if tec:
            kw['ids_tecnicos'] = tec
        return svc.abrir_atendimento_os(**kw)


@registrar
class HubsoftAgendarOs(HubsoftNode):
    tipo = "hubsoft_agendar_os"
    label = "HubSoft: agendar OS"
    icone = "bi-calendar-check"
    saida_chave = "resultado"

    def _campos_extra(self) -> list:
        return [{'nome': 'id_ordem_servico', 'label': 'ID da OS', 'tipo': 'numero', 'obrigatorio': True}]

    def validar_config(self, config) -> list:
        return _faltando(config, ('id_ordem_servico',))

    def _chamar(self, svc, config, contexto):
        return svc.agendar_os(_int(contexto.resolver(config.get('id_ordem_servico', '')), 0))


@registrar
class HubsoftAbrirOs(HubsoftNode):
    tipo = "hubsoft_abrir_os"
    label = "HubSoft: abrir OS (de atendimento)"
    icone = "bi-clipboard2-plus"
    saida_chave = "ordem_servico"

    def _campos_extra(self) -> list:
        return [
            {'nome': 'id_atendimento', 'label': 'ID do atendimento', 'tipo': 'numero', 'obrigatorio': True},
            {'nome': 'id_tipo_ordem_servico', 'label': 'ID tipo de OS', 'tipo': 'numero'},
            {'nome': 'id_agenda_ordem_servico', 'label': 'ID agenda de OS', 'tipo': 'numero'},
            {'nome': 'data_inicio_programado', 'label': 'Data início (YYYY-MM-DD)', 'tipo': 'texto'},
            {'nome': 'hora_inicio_programado', 'label': 'Hora início (HH:MM)', 'tipo': 'texto'},
            {'nome': 'status', 'label': 'Status', 'tipo': 'texto'},
            {'nome': 'descricao_servico', 'label': 'Descrição do serviço', 'tipo': 'textarea'},
            {'nome': 'tecnicos', 'label': 'IDs técnicos (vírgula)', 'tipo': 'texto'},
        ]

    def validar_config(self, config) -> list:
        return _faltando(config, ('id_atendimento',))

    def _chamar(self, svc, config, contexto):
        kw = {'id_atendimento': _int(contexto.resolver(config.get('id_atendimento', '')), 0)}
        for c in ('data_inicio_programado', 'hora_inicio_programado', 'status', 'descricao_servico'):
            v = _txt(contexto, config, c)
            if v:
                kw[c] = v
        for c in ('id_tipo_ordem_servico', 'id_agenda_ordem_servico'):
            v = _int(contexto.resolver(config.get(c, '')), None)
            if v:
                kw[c] = v
        tec = _ids(_txt(contexto, config, 'tecnicos'))
        if tec:
            kw['tecnicos'] = tec
        return svc.abrir_os(**kw)
