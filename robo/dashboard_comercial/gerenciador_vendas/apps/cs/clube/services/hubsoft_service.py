import logging
import os
import requests


class HubsoftService:

    @staticmethod
    def _get_hubsoft_connection(connect_timeout=10):
        """Cria conexão com o banco Hubsoft usando variáveis de ambiente."""
        import psycopg2
        return psycopg2.connect(
            user=os.getenv('HUBSOFT_DB_USER', ''),
            password=os.getenv('HUBSOFT_DB_PASSWORD', ''),
            host=os.getenv('HUBSOFT_DB_HOST', ''),
            port=os.getenv('HUBSOFT_DB_PORT', '9432'),
            database=os.getenv('HUBSOFT_DB_NAME', 'hubsoft'),
            connect_timeout=connect_timeout,
        )
    @staticmethod
    def consultar_cliente(cpf: str):
        """
        Consulta os dados do cliente no webhook do Hubsoft via n8n.
        Retorna o dicionário com dados do cliente ou None.
        """
        webhook_url = "https://automation-n8n.v4riem.easypanel.host/webhook/roletaconsultarcliente"
        try:
            response = requests.post(webhook_url, json={'cpf': cpf}, timeout=10)
            if response.status_code == 200:
                data = response.json()
                
                # Pega o primeiro item se for lista
                top_data = data[0] if isinstance(data, list) and len(data) > 0 else data
                
                if isinstance(top_data, dict) and top_data.get('status') == 'success':
                    clientes_list = top_data.get('clientes', [])
                    if isinstance(clientes_list, list) and len(clientes_list) > 0:
                        cliente_data = clientes_list[0]
                        
                        # Processa e oculta informações de numero
                        tel = cliente_data.get('telefone_primario', '')
                        masked_tel = ""
                        if tel and len(tel) > 2:
                            masked_tel = f"(**) ****-{tel[-4:]}"
                            
                        # Anexa ao retorno
                        cliente_data['masked_tel'] = masked_tel
                        return cliente_data
            return None
        except Exception as e:
            logging.getLogger(__name__).warning(f"Erro ao comunicar com HubsoftService: {e}")
            return None

    @staticmethod
    def checar_pontos_extras_cpf(cpf: str):
        import datetime
        from django.utils import timezone

        try:
            connection = HubsoftService._get_hubsoft_connection()
            # Formatação de CPF para busca no banco
            cpf_clean = cpf.replace('.', '').replace('-', '').replace('/', '')

            sql_query = """
                SELECT DISTINCT ON (cli.codigo_cliente)
                    (CASE WHEN (
                        SELECT MIN(cc.id_cliente)
                        FROM cliente_cartao cc
                        WHERE cli.id_cliente = cc.id_cliente
                        AND cc.deleted_at IS NULL
                        AND cc.padrao
                    ) IS NOT NULL THEN 1 ELSE 0 END) AS pontos_recorrencia,

                    (CASE WHEN (
                        SELECT MIN(cob.id_cobranca)
                        FROM cobranca cob
                        WHERE cob.id_cliente_servico = cs.id_cliente_servico
                        AND cob.data_pagamento <= cob.data_vencimento
                        AND date_trunc('month', cob.data_vencimento) = date_trunc('month', current_date)
                    ) IS NOT NULL THEN 1 ELSE 0 END) AS pontos_adiantado,

                    (CASE WHEN (
                        SELECT MIN(cac.id_cliente_acesso_central)
                        FROM cliente_acesso_central cac
                        WHERE cac.id_cliente = cli.id_cliente
                        AND cac.status = 'success'
                        AND cac.origem = 'app_cliente'
                    ) IS NOT NULL THEN 1 ELSE 0 END) AS pontos_app,

                    (
                        SELECT MIN(cob.data_pagamento)
                        FROM cobranca cob
                        WHERE cob.id_cliente_servico = cs.id_cliente_servico
                        AND cob.data_pagamento <= cob.data_vencimento
                        AND date_trunc('month', cob.data_vencimento) = date_trunc('month', current_date)
                    ) AS data_pagamento_adiantado,

                    (
                        SELECT MIN(cob.data_vencimento)
                        FROM cobranca cob
                        WHERE cob.id_cliente_servico = cs.id_cliente_servico
                        AND cob.data_pagamento <= cob.data_vencimento
                        AND date_trunc('month', cob.data_vencimento) = date_trunc('month', current_date)
                    ) AS data_vencimento_adiantado
                FROM cliente_servico cs
                JOIN cliente cli ON cs.id_cliente = cli.id_cliente
                JOIN cliente_servico_endereco cse ON cs.id_cliente_servico = cse.id_cliente_servico
                JOIN cliente_servico_grupo csg ON csg.id_cliente_servico = cs.id_cliente_servico
                JOIN grupo_cliente_servico gcs ON gcs.id = csg.id_grupo_cliente_servico
                WHERE cse.tipo = 'instalacao'
                AND cs.id_servico_status IN (11)
                AND gcs.descricao = 'Varejo'
                AND REPLACE(REPLACE(REPLACE(cli.cpf_cnpj, '.', ''), '-', ''), '/', '') = %s
                LIMIT 1;
            """

            # BUG-14: usar context manager garante fechamento mesmo em excecao
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql_query, [cpf_clean])
                    row = cursor.fetchone()

            if row:
                return {
                    'hubsoft_recorrencia': row[0] == 1,
                    'hubsoft_adiantado': row[1] == 1,
                    'hubsoft_app': row[2] == 1,
                    'data_pagamento_adiantado': row[3],
                    'data_vencimento_adiantado': row[4]
                }
            return None
        except Exception as e:
            logging.getLogger(__name__).warning(f"Erro ao consultar_pontos_extras_cpf: {e}")
            return None

    @staticmethod
    def consultar_cidade_cliente_cpf(cpf: str):
        try:
            connection = HubsoftService._get_hubsoft_connection()
            cpf_clean = cpf.replace('.', '').replace('-', '').replace('/', '')

            sql_query = """
                SELECT
                    ci.nome as cidade
                FROM
                    cliente cli
                JOIN
                    cliente_servico cs on cli.id_cliente = cs.id_cliente
                JOIN
                    cliente_servico_endereco cse on cs.id_cliente_servico = cse.id_cliente_servico
                JOIN
                    endereco_numero en on cse.id_endereco_numero = en.id_endereco_numero
                JOIN
                    cidade ci on en.id_cidade = ci.id_cidade
                WHERE
                    cse.tipo = 'instalacao'
                    AND REPLACE(REPLACE(REPLACE(cli.cpf_cnpj, '.', ''), '-', ''), '/', '') = %s
                LIMIT 1;
            """

            # BUG-14: context manager garante fechamento mesmo em excecao
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql_query, [cpf_clean])
                    row = cursor.fetchone()

            if row and row[0]:
                return row[0].strip()
            return None
        except Exception as e:
            logging.getLogger(__name__).warning(f"Erro ao consultar_cidade_cliente_cpf: {e}")
            return None

    @staticmethod
    def consultar_clientes_por_cidade():
        """
        Retorna um dict {cidade: quantidade_clientes} com todos os clientes ativos do Hubsoft.
        Cache de 1 hora via Django cache framework (funciona multi-worker).
        """
        import logging
        from django.core.cache import cache

        CACHE_KEY = 'hubsoft_clientes_por_cidade'
        cached = cache.get(CACHE_KEY)
        if cached is not None:
            return cached

        try:
            connection = HubsoftService._get_hubsoft_connection()

            sql_query = """
                SELECT
                    ci.nome AS cidade,
                    COUNT(DISTINCT cli.id_cliente) AS total
                FROM
                    cliente cli
                JOIN
                    cliente_servico cs ON cli.id_cliente = cs.id_cliente
                JOIN
                    cliente_servico_endereco cse ON cs.id_cliente_servico = cse.id_cliente_servico
                JOIN
                    endereco_numero en ON cse.id_endereco_numero = en.id_endereco_numero
                JOIN
                    cidade ci ON en.id_cidade = ci.id_cidade
                GROUP BY
                    ci.nome
                ORDER BY
                    COUNT(DISTINCT cli.id_cliente) DESC;
            """

            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql_query)
                    rows = cursor.fetchall()

            resultado = {row[0].strip(): row[1] for row in rows if row[0]}

            # Cache por 1 hora (3600 segundos)
            cache.set(CACHE_KEY, resultado, 3600)

            return resultado
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning(f"Erro ao consultar_clientes_por_cidade: {e}")
            return {}
