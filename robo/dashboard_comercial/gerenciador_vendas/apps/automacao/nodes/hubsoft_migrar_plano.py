"""Nó `hubsoft_migrar_plano` — upgrade/migração de plano de um serviço existente no
HubSoft, via API interna do painel.

A migração é o MESMO POST /api/v1/cliente/servico do novo serviço, só que com os
campos de migração (id_cliente_servico_antigo + executar_migracao_imediata + flags)
e o serviço já nasce Habilitado (status do perfil, padrao 11). Reaproveita o
`montar_payload_adicionar_servico` com `migracao=...`.

Precisa de um `lead` ja convertido (espelho ClienteHubsoft) e do serviço antigo:
o id_cliente_servico vem do config ou, se houver so um serviço ativo, do espelho.
Idempotencia: no-op se o cliente ja esta no plano de destino.
"""
from .base import NodeResult, registrar
from .hubsoft_painel_base import (
    HubsoftPainelNode, integ_id_de, perfil_do_tenant, flag, cliente_hubsoft_do_lead,
    resolver_endereco_cadastral, resolver_forma_cobranca,
)


@registrar
class HubsoftMigrarPlanoNode(HubsoftPainelNode):
    tipo = "hubsoft_migrar_plano"
    label = "HubSoft: migrar/upgrade de plano"
    icone = "bi-arrow-up-square"

    def _campos_extra(self) -> list:
        return [
            {'nome': 'id_servico_novo', 'label': 'Plano de destino (id)', 'tipo': 'texto',
             'obrigatorio': True, 'ajuda': 'Id do plano novo no HubSoft.'},
            {'nome': 'id_cliente_servico_antigo', 'label': 'Serviço atual (id_cliente_servico)',
             'tipo': 'texto', 'ajuda': 'Vazio = usa o único serviço ativo do cliente (erro se houver mais de um).'},
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

        id_novo = str(contexto.resolver(config.get('id_servico_novo', '')) or '').strip()
        if not id_novo.isdigit():
            return NodeResult(status='erro', branch='erro', erro='id_servico_novo invalido/ausente.')
        id_novo = int(id_novo)

        # Idempotencia: ja esta no plano de destino?
        if espelho.servicos.filter(id_servico=id_novo).exclude(status_prefixo='servico_cancelado').exists():
            return NodeResult(branch='sucesso',
                              output={'ok': True, 'ja_migrado': True, 'motivo': 'plano_destino_ativo', 'id_servico_novo': id_novo})

        # Serviço antigo: do config ou o único ativo do espelho
        antigo_cfg = str(contexto.resolver(config.get('id_cliente_servico_antigo', '')) or '').strip()
        if antigo_cfg.isdigit():
            id_cs_antigo = int(antigo_cfg)
        else:
            ativos = list(espelho.servicos.exclude(status_prefixo='servico_cancelado')
                          .values_list('id_cliente_servico', flat=True))
            if len(ativos) != 1:
                return NodeResult(status='erro', branch='erro',
                                  erro=f'Nao deu pra inferir o serviço antigo ({len(ativos)} ativos). Informe id_cliente_servico_antigo.')
            id_cs_antigo = ativos[0]

        from apps.integracoes.services.hubsoft_painel import hubsoft_painel_do_tenant
        svc = hubsoft_painel_do_tenant(
            contexto.tenant, integracao_id=integ_id_de(config, contexto), perfil=perfil)
        if svc is None:
            return NodeResult(status='erro', branch='erro', erro='Tenant sem integracao hubsoft_painel ativa.')

        dry = perfil.dry_run_efetivo(flag(config.get('dry_run'), True), getattr(lead, 'cpf_cnpj', '') or '')

        try:
            antigo = svc.obter_servico_edit(id_cs_antigo, lead=lead) or {}
            id_vencimento = antigo.get('id_vencimento') or perfil.id_vencimento(getattr(lead, 'id_dia_vencimento', None))
            servico_obj = svc.buscar_plano_por_id(id_novo, lead=lead)
            if not servico_obj:
                return NodeResult(status='erro', branch='erro', erro=f'Plano {id_novo} nao encontrado no painel.')
            forma = resolver_forma_cobranca(svc, perfil)
            if not dry and not forma:
                return NodeResult(status='erro', branch='erro',
                                  erro='Forma de cobranca nao resolvida (perfil sem forma_cobranca_obj/id).')
            id_en, end_obj = resolver_endereco_cadastral(svc, espelho.id_cliente)
            endereco_item = {'id_endereco_numero': id_en, 'endereco_numero': end_obj}
            valor = float(servico_obj.get('valor') or 0)
            payload = svc.montar_payload_adicionar_servico(
                id_cliente=espelho.id_cliente, endereco_item=endereco_item,
                servico_obj=servico_obj, forma_cobranca_obj=forma or {},
                valor=valor, id_vencimento=id_vencimento,
                migracao={'id_cliente_servico_antigo': id_cs_antigo})
        except Exception as exc:  # noqa: BLE001
            return NodeResult(status='erro', branch='erro', erro=str(exc))

        resumo = {'id_cliente': espelho.id_cliente, 'id_cliente_servico_antigo': id_cs_antigo,
                  'id_servico_novo': id_novo, 'valor': valor, 'id_vencimento': id_vencimento}

        if dry:
            return NodeResult(branch='dry_run',
                              output={'ok': True, 'dry_run': True, 'resumo': resumo, 'payload': payload})

        try:
            resp = svc.adicionar_servico(payload, lead=lead)
        except Exception as exc:  # noqa: BLE001
            return NodeResult(status='erro', branch='erro', erro=str(exc))
        cs = (resp or {}).get('cliente_servico') or {}
        resumo['id_cliente_servico_novo'] = cs.get('id_cliente_servico')
        return NodeResult(branch='sucesso', output={'ok': True, 'dry_run': False, 'resumo': resumo})
