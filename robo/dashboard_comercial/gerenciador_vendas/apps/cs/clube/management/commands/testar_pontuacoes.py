import os

import psycopg2
from django.core.management.base import BaseCommand, CommandError
from apps.cs.clube.services.hubsoft_service import HubsoftService
from apps.cs.clube.models import MembroClube, RegraPontuacao

class Command(BaseCommand):
    help = 'Testa as pontuações simulando CPFs direto do banco da Hubsoft'

    def add_arguments(self, parser):
        parser.add_argument('--qtd', type=int, default=10, help='Quantidade de CPFs para testar')
        parser.add_argument('--cpf', type=str, help='Testar um CPF específico')
        parser.add_argument('--buscar-adiantado', action='store_true', help='Busca especificamente um CPF que pagou fatura adiantada este mês')

    def handle(self, *args, **options):
        qtd = options['qtd']
        cpf_especifico = options.get('cpf')
        buscar_adiantado = options.get('buscar_adiantado')

        self.stdout.write(self.style.WARNING("=== INICIANDO TESTE DE PONTUAÇÕES NA HUBSOFT ==="))
        
        required_vars = ['HUBSOFT_DB_USER', 'HUBSOFT_DB_PASSWORD', 'HUBSOFT_DB_HOST', 'HUBSOFT_DB_PORT', 'HUBSOFT_DB_NAME']
        missing = [v for v in required_vars if not os.environ.get(v)]
        if missing:
            raise CommandError(f"Variáveis de ambiente faltando: {', '.join(missing)}")

        try:
            connection = psycopg2.connect(
                user=os.environ['HUBSOFT_DB_USER'],
                password=os.environ['HUBSOFT_DB_PASSWORD'],
                host=os.environ['HUBSOFT_DB_HOST'],
                port=os.environ['HUBSOFT_DB_PORT'],
                database=os.environ['HUBSOFT_DB_NAME'],
            )
            
            cpfs_para_testar = []
            
            with connection:
                with connection.cursor() as cursor:
                    if cpf_especifico:
                        cpf_clean = cpf_especifico.replace('.', '').replace('-', '').replace('/', '')
                        cursor.execute("SELECT cpf_cnpj, nome_razaosocial FROM cliente WHERE REPLACE(REPLACE(REPLACE(cpf_cnpj, '.', ''), '-', ''), '/', '') = %s", [cpf_clean])
                        rows = cursor.fetchall()
                        if rows:
                            cpfs_para_testar.append(rows[0])
                        else:
                            self.stdout.write(self.style.ERROR(f"CPF {cpf_especifico} não encontrado na Hubsoft."))
                            return
                    elif buscar_adiantado:
                        self.stdout.write(f"Buscando 1 CPF de pessoa que pagou Fatura Adiantada este mês...")
                        sql_query = """
                            SELECT cli.cpf_cnpj, cli.nome_razaosocial
                            FROM cliente_servico cs
                            JOIN cliente cli ON cs.id_cliente = cli.id_cliente
                            JOIN cobranca cob ON cob.id_cliente_servico = cs.id_cliente_servico
                            WHERE cob.data_pagamento <= cob.data_vencimento
                            AND date_trunc('month', cob.data_vencimento) = date_trunc('month', current_date)
                            AND LENGTH(cli.cpf_cnpj) <= 14
                            ORDER BY RANDOM()
                            LIMIT 1;
                        """
                        cursor.execute(sql_query)
                        cpfs_para_testar = cursor.fetchall()
                    else:
                        self.stdout.write(f"Buscando {qtd} CPFs aleatórios valendo para Varejo (Instalação)...")
                        sql_query = """
                            SELECT cli.cpf_cnpj, cli.nome_razaosocial
                            FROM cliente_servico cs
                            JOIN cliente cli ON cs.id_cliente = cli.id_cliente
                            JOIN cliente_servico_endereco cse ON cs.id_cliente_servico = cse.id_cliente_servico
                            JOIN cliente_servico_grupo csg ON csg.id_cliente_servico = cs.id_cliente_servico
                            JOIN grupo_cliente_servico gcs ON gcs.id = csg.id_grupo_cliente_servico
                            WHERE cse.tipo = 'instalacao'
                            AND cs.id_servico_status IN (11)
                            AND gcs.descricao = 'Varejo'
                            AND LENGTH(cli.cpf_cnpj) <= 14
                            ORDER BY RANDOM()
                            LIMIT %s;
                        """
                        cursor.execute(sql_query, [qtd])
                        cpfs_para_testar = cursor.fetchall()
                        
            if not cpfs_para_testar:
                self.stdout.write(self.style.ERROR("Nenhum CPF encontrado para teste."))
                return
                
            resultados_gerais = {
                'total_testados': len(cpfs_para_testar),
                'recorrencia': 0,
                'adiantado': 0,
                'app': 0,
            }

            for row in cpfs_para_testar:
                cpf_raw, nome = row
                self.stdout.write(self.style.SUCCESS(f"\n[{cpf_raw}] {nome}"))
                self.stdout.write("Buscando pontos extras...")
                
                pontos = HubsoftService.checar_pontos_extras_cpf(cpf_raw)
                
                if pontos:
                    self.stdout.write(f"  > Pagamento Recorrente: {'✅ SIM' if pontos['hubsoft_recorrencia'] else '❌ NÃO'}")
                    
                    data_str = ""
                    if pontos['hubsoft_adiantado'] and pontos.get('data_pagamento_adiantado'):
                        data_pgto = pontos['data_pagamento_adiantado']
                        if hasattr(data_pgto, 'strftime'):
                            data_str = f" (Paga em: {data_pgto.strftime('%d/%m/%Y')})"
                        else:
                            data_str = f" (Paga em: {data_pgto})"
                            
                    self.stdout.write(f"  > Fatura Adiantada:     {'✅ SIM' + data_str if pontos['hubsoft_adiantado'] else '❌ NÃO'}")
                    self.stdout.write(f"  > App Central:          {'✅ SIM' if pontos['hubsoft_app'] else '❌ NÃO'}")
                    
                    if pontos['hubsoft_recorrencia']: resultados_gerais['recorrencia'] += 1
                    if pontos['hubsoft_adiantado']: resultados_gerais['adiantado'] += 1
                    if pontos['hubsoft_app']: resultados_gerais['app'] += 1
                else:
                    self.stdout.write(self.style.ERROR("  > Erro ou nenhum dado retornado pelas queries do HubsoftService."))

            self.stdout.write(self.style.WARNING("\n=== RESUMO DO TESTE ==="))
            self.stdout.write(f"Total Testados: {resultados_gerais['total_testados']}")
            self.stdout.write(f"Com Recorrência ativa: {resultados_gerais['recorrencia']}")
            self.stdout.write(f"Faturas Pagas Adiantadas: {resultados_gerais['adiantado']}")
            self.stdout.write(f"Baixaram App Central: {resultados_gerais['app']}")
            self.stdout.write(self.style.SUCCESS("Teste concluído com sucesso.\n"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erro inesperado: {str(e)}"))

