"""Nó `hubsoft_converter_prospecto` — converte o prospecto do lead em cliente no
HubSoft, via API interna do painel (o wizard "Converter em Cliente" do operador).

Faz o MESMO POST /api/v1/cliente que o painel faz no salvar, com `id_prospecto`
linkando o prospecto ao novo cliente. O payload sai do template do perfil
(`montar_payload_conversao`, ja golden testado), com os IDs do HubSoft do tenant.

Segurança em 3 camadas:
1. Idempotencia tripla — status_api do lead == 'convertido_cliente', espelho
   ClienteHubsoft ja existe, e (no modo real) cpf_ja_cadastrado no painel. Qualquer
   uma verdadeira = no-op na saida `sucesso` (nao duplica cliente).
2. Guard de dry run do perfil — enquanto `dry_run_forcado` estiver ligado, so os
   CPFs da allowlist escrevem; o resto sai por `dry_run` com o payload que SERIA
   enviado. O campo "Forcar simulacao" do nó reforça isso (padrao ligado).
3. `retry_seguro=False` (na base) — a engine nunca reexecuta o POST sozinha.

Precisa de um `lead` real (com pk e id_hubsoft/prospecto) no contexto.
"""
from .base import NodeResult, registrar
from .hubsoft_painel_base import (
    HubsoftPainelNode, integ_id_de, perfil_do_tenant, flag, mascara_cpf,
)


@registrar
class HubsoftConverterProspectoNode(HubsoftPainelNode):
    tipo = "hubsoft_converter_prospecto"
    label = "HubSoft: converter prospecto em cliente"
    icone = "bi-person-check"

    def _campos_extra(self) -> list:
        return [
            {'nome': 'dia_vencimento', 'label': 'Dia de vencimento (opcional)', 'tipo': 'numero',
             'ajuda': 'Sobrepoe o dia do lead. O perfil traduz no id_vencimento do ERP.'},
        ]

    # ------------------------------------------------------------------
    # Idempotencia local (sem rede)
    # ------------------------------------------------------------------
    @staticmethod
    def _ja_convertido_local(lead):
        """Retorna o motivo (str) se o lead ja consta como convertido, senao None."""
        if (getattr(lead, 'status_api', '') or '') == 'convertido_cliente':
            return 'status_api'
        from apps.integracoes.models import ClienteHubsoft
        if ClienteHubsoft.all_tenants.filter(tenant=lead.tenant, lead=lead).exists():
            return 'espelho_cliente_hubsoft'
        return None

    def executar(self, config, entrada, contexto) -> NodeResult:
        lead = contexto.lead
        if lead is None or not getattr(lead, 'pk', None):
            return NodeResult(status='erro', branch='erro', erro='Sem lead (com pk) no contexto.')
        if not str(getattr(lead, 'id_hubsoft', '') or '').strip():
            return NodeResult(status='erro', branch='erro',
                              erro='Lead sem id_hubsoft (prospecto). Sincronize o prospecto antes.')

        perfil = perfil_do_tenant(contexto.tenant, str(contexto.resolver(config.get('perfil', '')) or '').strip())
        if perfil is None:
            return NodeResult(status='erro', branch='erro',
                              erro='Perfil de conversao HubSoft nao encontrado/ativo pro tenant.')

        # (1) idempotencia local — no-op se ja convertido
        motivo = self._ja_convertido_local(lead)
        if motivo:
            return NodeResult(branch='sucesso',
                              output={'ok': True, 'ja_convertido': True, 'motivo': motivo})

        from apps.integracoes.services.hubsoft_painel import hubsoft_painel_do_tenant
        svc = hubsoft_painel_do_tenant(
            contexto.tenant, integracao_id=integ_id_de(config, contexto), perfil=perfil)
        if svc is None:
            return NodeResult(status='erro', branch='erro',
                              erro='Tenant sem integracao hubsoft_painel ativa.')

        cpf = getattr(lead, 'cpf_cnpj', '') or ''
        dry = perfil.dry_run_efetivo(flag(config.get('dry_run'), True), cpf)

        dia_cfg = str(contexto.resolver(config.get('dia_vencimento', '')) or '').strip()
        dia = int(dia_cfg) if dia_cfg.isdigit() else getattr(lead, 'id_dia_vencimento', None)

        # Monta o payload (endereco resolvido no painel; funcao pura pro resto).
        try:
            endereco, cidade_obj = self._resolver_endereco(svc, lead)
            if not dry and not cidade_obj:
                return NodeResult(status='erro', branch='erro',
                                  erro=f'CEP {getattr(lead, "cep", None)!r} sem cidade no painel.')
            payload = svc.montar_payload_conversao(lead, endereco, dia_vencimento=dia)
        except Exception as exc:  # noqa: BLE001
            return NodeResult(status='erro', branch='erro', erro=str(exc))

        resumo = {'id_prospecto': payload.get('id_prospecto'), 'cpf': mascara_cpf(cpf),
                  'nome': getattr(lead, 'nome_razaosocial', '')}

        # (2) guard de dry run — para aqui com o payload que SERIA enviado
        if dry:
            return NodeResult(branch='dry_run',
                              output={'ok': True, 'dry_run': True, 'resumo': resumo, 'payload': payload})

        # Real: pre-check anti duplicata no painel (3ª camada) + POST
        try:
            if svc.cpf_ja_cadastrado(cpf, lead=lead):
                return NodeResult(branch='sucesso',
                                  output={'ok': True, 'ja_convertido': True, 'motivo': 'cpf_ja_cadastrado'})
            resp = svc.criar_cliente(payload, lead=lead)
        except Exception as exc:  # noqa: BLE001
            return NodeResult(status='erro', branch='erro', erro=str(exc))

        cli_obj = (resp or {}).get('cliente') or {}
        resumo['id_cliente_novo'] = cli_obj.get('id_cliente') or cli_obj.get('codigo_cliente')
        return NodeResult(branch='sucesso',
                          output={'ok': True, 'dry_run': False, 'resumo': resumo})

    # ------------------------------------------------------------------
    # Endereco resolvido (leitura no painel; formato que o payload espera)
    # ------------------------------------------------------------------
    @staticmethod
    def _resolver_endereco(svc, lead):
        """Monta o endereco_resolvido pro payload. Enriquece a cidade via buscar_cep
        (leitura). Devolve (endereco, cidade_obj) — cidade_obj None = CEP sem cidade."""
        cep_d = ''.join(c for c in str(getattr(lead, 'cep', '') or '') if c.isdigit())
        cidade_obj = None
        pais_obj = {}
        try:
            corpo = svc.buscar_cep(cep_d) or {}
            cep_data = corpo.get('cep', corpo) if isinstance(corpo, dict) else {}
            cidade_obj = cep_data.get('cidade_completo') or cep_data.get('cidade')
            pais_obj = cep_data.get('pais', {}) or {}
        except Exception:
            cidade_obj = None
        endereco = {
            'id_endereco_numero': None,
            'cep': cep_d,
            'endereco': getattr(lead, 'rua', '') or getattr(lead, 'endereco', '') or '',
            'numero': str(getattr(lead, 'numero_residencia', '') or 'S/N'),
            'bairro': getattr(lead, 'bairro', '') or '',
            'complemento': getattr(lead, 'complemento', '') or None,
            'referencia': getattr(lead, 'ponto_referencia', '') or None,
            'cidade': cidade_obj or {},
            'estado': (cidade_obj or {}).get('estado', {}) if isinstance(cidade_obj, dict) else {},
            'pais': pais_obj,
            'condominio': None,
            'atualizar_coords_auto': True,
        }
        return endereco, cidade_obj
