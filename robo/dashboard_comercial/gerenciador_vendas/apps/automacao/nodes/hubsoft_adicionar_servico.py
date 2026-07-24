"""Nó `hubsoft_adicionar_servico` — adiciona um novo serviço a um cliente que já
existe no HubSoft, via API interna do painel (POST /api/v1/cliente/servico).

O serviço novo nasce "Aguardando Instalação" (status do perfil, padrao 6), igual ao
que o operador faz no painel: a OS de instalacao habilita depois. O payload sai do
`montar_payload_adicionar_servico` (mesmo builder do upgrade), com os IDs do perfil.

Precisa de um `lead` (com pk) ja convertido: o id_cliente do HubSoft vem do espelho
ClienteHubsoft. Idempotencia: no-op se o cliente ja tem esse plano ativo.
"""
from .base import NodeResult, registrar
from .hubsoft_painel_base import (
    HubsoftPainelNode, integ_id_de, perfil_do_tenant, flag, cliente_hubsoft_do_lead,
    resolver_endereco_cadastral, resolver_forma_cobranca,
)


@registrar
class HubsoftAdicionarServicoNode(HubsoftPainelNode):
    tipo = "hubsoft_adicionar_servico"
    label = "HubSoft: adicionar serviço"
    icone = "bi-plus-square"

    def _campos_extra(self) -> list:
        return [
            {'nome': 'id_servico', 'label': 'Plano (id do serviço)', 'tipo': 'texto',
             'ajuda': 'Id do plano no HubSoft. Vazio = usa o id_plano_rp do lead.'},
            {'nome': 'dia_vencimento', 'label': 'Dia de vencimento (opcional)', 'tipo': 'numero',
             'ajuda': 'O perfil traduz no id_vencimento do ERP. Vazio = usa o do lead.'},
        ]

    def executar(self, config, entrada, contexto) -> NodeResult:
        lead = contexto.lead
        if lead is None or not getattr(lead, 'pk', None):
            return NodeResult(status='erro', branch='erro', erro='Sem lead (com pk) no contexto.')

        perfil = perfil_do_tenant(contexto.tenant, str(contexto.resolver(config.get('perfil', '')) or '').strip())
        if perfil is None:
            return NodeResult(status='erro', branch='erro',
                              erro='Perfil de conversao HubSoft nao encontrado/ativo pro tenant.')

        espelho = cliente_hubsoft_do_lead(lead)
        if espelho is None or not espelho.id_cliente:
            return NodeResult(status='erro', branch='erro',
                              erro='Lead sem cliente HubSoft (espelho). Converta o prospecto antes.')

        id_servico = str(contexto.resolver(config.get('id_servico', '')) or '').strip() \
            or str(getattr(lead, 'id_plano_rp', '') or '').strip()
        if not id_servico.isdigit():
            return NodeResult(status='erro', branch='erro', erro='id_servico invalido/ausente.')
        id_servico = int(id_servico)

        # Idempotencia: cliente ja tem esse plano ativo?
        if self._ja_tem_plano_ativo(espelho, id_servico):
            return NodeResult(branch='sucesso',
                              output={'ok': True, 'ja_existe': True, 'motivo': 'plano_ativo', 'id_servico': id_servico})

        from apps.integracoes.services.hubsoft_painel import hubsoft_painel_do_tenant
        svc = hubsoft_painel_do_tenant(
            contexto.tenant, integracao_id=integ_id_de(config, contexto), perfil=perfil)
        if svc is None:
            return NodeResult(status='erro', branch='erro', erro='Tenant sem integracao hubsoft_painel ativa.')

        dry = perfil.dry_run_efetivo(flag(config.get('dry_run'), True), getattr(lead, 'cpf_cnpj', '') or '')

        dia_cfg = str(contexto.resolver(config.get('dia_vencimento', '')) or '').strip()
        dia = int(dia_cfg) if dia_cfg.isdigit() else getattr(lead, 'id_dia_vencimento', None)
        id_vencimento = perfil.id_vencimento(dia)

        try:
            servico_obj = svc.buscar_plano_por_id(id_servico, lead=lead)
            if not servico_obj:
                return NodeResult(status='erro', branch='erro',
                                  erro=f'Plano {id_servico} nao encontrado no painel.')
            forma = resolver_forma_cobranca(svc, perfil)
            if not dry and not forma:
                return NodeResult(status='erro', branch='erro',
                                  erro='Forma de cobranca nao resolvida (perfil sem forma_cobranca_obj/id).')
            id_en, end_obj = resolver_endereco_cadastral(svc, espelho.id_cliente)
            endereco_item = {'id_endereco_numero': id_en, 'endereco_numero': end_obj}
            valor = float(getattr(lead, 'valor', None) or servico_obj.get('valor') or 0)
            payload = svc.montar_payload_adicionar_servico(
                id_cliente=espelho.id_cliente, endereco_item=endereco_item,
                servico_obj=servico_obj, forma_cobranca_obj=forma or {},
                valor=valor, id_vencimento=id_vencimento)
        except Exception as exc:  # noqa: BLE001
            return NodeResult(status='erro', branch='erro', erro=str(exc))

        resumo = {'id_cliente': espelho.id_cliente, 'id_servico': id_servico,
                  'valor': valor, 'id_vencimento': id_vencimento}

        if dry:
            return NodeResult(branch='dry_run',
                              output={'ok': True, 'dry_run': True, 'resumo': resumo, 'payload': payload})

        try:
            resp = svc.adicionar_servico(payload, lead=lead)
        except Exception as exc:  # noqa: BLE001
            return NodeResult(status='erro', branch='erro', erro=str(exc))
        cs = (resp or {}).get('cliente_servico') or {}
        resumo['id_cliente_servico'] = cs.get('id_cliente_servico')
        return NodeResult(branch='sucesso', output={'ok': True, 'dry_run': False, 'resumo': resumo})

    @staticmethod
    def _ja_tem_plano_ativo(espelho, id_servico) -> bool:
        return (espelho.servicos
                .filter(id_servico=id_servico)
                .exclude(status_prefixo='servico_cancelado').exists())
