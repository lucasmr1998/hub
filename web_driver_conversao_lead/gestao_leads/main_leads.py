import requests
import json
import sys
import os
import time
import psycopg2
import datetime
# Adicionar o diretório pai ao path para importar o main_refatorado
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importar a função main do arquivo main_refatorado
from main_refatorado import main

token_primordial = []

# Configurações do banco de dados
DB_CONFIG = {
    'host': '187.62.153.52',
    'database': 'robo_venda_automatica',
    'user': 'admin',
    'password': 'qualidade@trunks.57',
    'port': 5432
}

# Banco de dados secundário (Django)
DB_CONFIG_DJANGO = {
    'host': '187.62.153.52',
    'database': 'venda_automatica_django',
    'user': 'admin',
    'password': 'qualidade@trunks.57',
    'port': 5432
}

def ajustar_finalizados_para_aguardando_validacao_segundo_banco():
    """No banco Django, altera status 'finalizado' para 'aguardando_validacao'."""
    try:
        conn = psycopg2.connect(**DB_CONFIG_DJANGO)
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE prospectos
            SET status = 'aguardando_validacao'
            WHERE status = 'finalizado'
            """
        )
        alterados = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        if alterados > 0:
            print(f"🔄 Banco Django: {alterados} registros atualizados de 'finalizado' para 'aguardando_validacao'")
        return alterados
    except Exception as e:
        print(f"⚠️ Falha ao ajustar status no banco Django: {e}")
        return 0

def verificar_tentativas_prospecto(id_prospecto):
    """Verifica quantas tentativas o prospecto já teve no banco de dados"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT tentativas_processamento, status FROM prospectos WHERE id_prospecto_hubsoft = %s",
            (str(id_prospecto),)
        )
        resultado = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if resultado:
            tentativas, status = resultado
            return tentativas, status
        else:
            return 0, None  # Prospecto novo
            
    except Exception as e:
        print(f"⚠️ Erro ao verificar tentativas do prospecto {id_prospecto}: {e}")
        return 0, None  # Em caso de erro, assumir que é novo

def marcar_prospecto_como_erro_final(id_prospecto, nome):
    """Marca prospecto como erro final quando atinge 3 tentativas"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE prospectos SET
                status = 'erro',
                erro_processamento = 'Máximo de 3 tentativas atingido',
                resultado_processamento = 'falha',
                data_atualizacao = %s
            WHERE id_prospecto_hubsoft = %s
        """, (
            datetime.datetime.now(),
            str(id_prospecto)
        ))
        
        linhas_afetadas = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        
        # Replicar para o banco Django (não impactar fluxo se falhar)
        try:
            conn2 = psycopg2.connect(**DB_CONFIG_DJANGO)
            cursor2 = conn2.cursor()
            cursor2.execute("""
                UPDATE prospectos SET
                    status = 'erro',
                    erro_processamento = 'Máximo de 3 tentativas atingido',
                    resultado_processamento = 'falha',
                    data_processamento = %s
                WHERE id_prospecto_hubsoft = %s
            """, (
                datetime.datetime.now(),
                str(id_prospecto)
            ))
            conn2.commit()
            cursor2.close()
            conn2.close()
        except Exception as e2:
            print(f"⚠️ Falha ao replicar erro final no banco Django: {e2}")

        if linhas_afetadas > 0:
            print(f"❌ Prospecto {nome} (ID: {id_prospecto}) marcado como erro final após 3 tentativas")
            return True
        else:
            print(f"⚠️ Nenhuma linha foi atualizada para o prospecto {id_prospecto}")
            return False
        
    except Exception as e:
        print(f"⚠️ Erro ao marcar prospecto como erro final: {e}")
        return False

def new_token():
    """Obtém novo token da API Megalink e armazena em token_primordial."""
    url = "https://api.megalinktelecom.hubsoft.com.br/oauth/token"
    data = {
        "client_id": "75",
        "client_secret": "JCqEuHLcam8zt0mYGvJVP8rZpNJFA2hf7aMrhGmM",
        "username": "api.hub.buzzlead@megalinkinternet.com.br",
        "password": "Api#5554",
        "grant_type": "password"
    }
    response = requests.post(url, json=data)
    if response.status_code == 200:
        token_primordial.clear()
        token_primordial.append(response.json()['access_token'])
        return token_primordial[0]
    else:
        raise Exception(f"Erro ao obter token: {response.text}")


def buscar_prospectos():
    """Busca prospectos convertidos dos vendedores ID 1613 e 1618 e retorna apenas ID e nome."""
    # Verifica se há token disponível, senão obtém um novo
    if not token_primordial:
        new_token()
    
    url = "https://api.megalinktelecom.hubsoft.com.br/api/v1/integracao/prospecto/all?convertido=nao"
    payload = {}
    headers = {
        'Authorization': f'Bearer {token_primordial[0]}'
    }
    
    try:
        response = requests.request("GET", url, headers=headers, data=payload)
        
        if response.status_code == 200:
            dados = response.json()
            
            # Verifica se dados é um dicionário com uma chave que contém a lista
            if isinstance(dados, dict):
                # Procura por chaves comuns que podem conter a lista de prospectos
                if 'data' in dados:
                    dados = dados['data']
                elif 'prospectos' in dados:
                    dados = dados['prospectos']
                elif 'results' in dados:
                    dados = dados['results']
                elif len(dados.keys()) == 1:
                    # Se há apenas uma chave, pode ser ela
                    chave = list(dados.keys())[0]
                    dados = dados[chave]
            
            # Verifica se dados é uma lista
            if not isinstance(dados, list):
                return []
            
            # Filtra prospectos onde id_vendedor = 1613 ou 1618
            prospectos_filtrados = []
            for prospecto in dados:
                if isinstance(prospecto, dict) and prospecto.get('id_vendedor') in [1613, 1618]:
                    prospectos_filtrados.append({
                        'id_prospecto': prospecto.get('id_prospecto'),
                        'nome_razaosocial': prospecto.get('nome_razaosocial')
                    })
                
            return prospectos_filtrados
            
        elif response.status_code == 401:
            # Token expirado, tenta obter novo token
            new_token()
            headers['Authorization'] = f'Bearer {token_primordial[0]}'
            response = requests.request("GET", url, headers=headers, data=payload)
            
            if response.status_code == 200:
                dados = response.json()
                
                # Verifica se dados é um dicionário com uma chave que contém a lista
                if isinstance(dados, dict):
                    # Procura por chaves comuns que podem conter a lista de prospectos
                    if 'data' in dados:
                        dados = dados['data']
                    elif 'prospectos' in dados:
                        dados = dados['prospectos']
                    elif 'results' in dados:
                        dados = dados['results']
                    elif len(dados.keys()) == 1:
                        # Se há apenas uma chave, pode ser ela
                        chave = list(dados.keys())[0]
                        dados = dados[chave]
                
                # Verifica se dados é uma lista
                if not isinstance(dados, list):
                    return []
                
                # Filtra prospectos onde id_vendedor = 1613 ou 1618
                prospectos_filtrados = []
                for prospecto in dados:
                    if isinstance(prospecto, dict) and prospecto.get('id_vendedor') in [1613, 1618]:
                        prospectos_filtrados.append({
                            'id_prospecto': prospecto.get('id_prospecto'),
                            'nome_razaosocial': prospecto.get('nome_razaosocial')
                        })
                
                return prospectos_filtrados
            else:
                raise Exception(f"Erro ao buscar prospectos após renovar token: {response.text}")
        else:
            raise Exception(f"Erro ao buscar prospectos: {response.status_code} - {response.text}")
            
    except Exception as e:
        raise Exception(f"Erro na requisição: {str(e)}")

def corrigir_prospectos_status_incorreto():
    """Corrige prospectos que estão com status incorreto no banco"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        # Conexão secundária (se falhar, seguimos apenas com primário)
        try:
            conn2 = psycopg2.connect(**DB_CONFIG_DJANGO)
            cursor2 = conn2.cursor()
        except Exception as e2:
            conn2 = None
            cursor2 = None
            print(f"⚠️ Não foi possível conectar ao banco Django para correção: {e2}")
        
        # Buscar prospectos que estão com status 'finalizado' mas têm 3 tentativas
        # (indicando que não foram realmente finalizados com sucesso)
        cursor.execute("""
            SELECT id, nome_prospecto, id_prospecto_hubsoft, tentativas_processamento, status, resultado_processamento
            FROM prospectos 
            WHERE tentativas_processamento >= 3 
            AND (status = 'finalizado' AND resultado_processamento != 'sucesso')
            OR (status = 'processando' AND tentativas_processamento >= 3)
        """)
        
        prospectos_incorretos = cursor.fetchall()
        
        if prospectos_incorretos:
            print(f"🔧 Encontrados {len(prospectos_incorretos)} prospectos com status incorreto para corrigir:")
            
            for prospecto in prospectos_incorretos:
                id_db, nome, id_hubsoft, tentativas, status_atual, resultado = prospecto
                
                print(f"   📝 Corrigindo: {nome} (ID: {id_hubsoft}) - Status: {status_atual} → erro")
                
                cursor.execute("""
                    UPDATE prospectos SET
                        status = 'erro',
                        erro_processamento = 'Máximo de 3 tentativas atingido - status corrigido automaticamente',
                        resultado_processamento = 'falha',
                        data_atualizacao = %s
                    WHERE id = %s
                """, (
                    datetime.datetime.now(),
                    id_db
                ))

                # Replicar no banco Django pelo id_prospecto_hubsoft
                if cursor2:
                    try:
                        cursor2.execute("""
                            UPDATE prospectos SET
                                status = 'erro',
                                erro_processamento = 'Máximo de 3 tentativas atingido - status corrigido automaticamente',
                                resultado_processamento = 'falha',
                                data_processamento = %s
                            WHERE id_prospecto_hubsoft = %s
                        """, (
                            datetime.datetime.now(),
                            str(id_hubsoft)
                        ))
                    except Exception as e_upd:
                        print(f"⚠️ Falha ao replicar correção no banco Django (ID Hubsoft {id_hubsoft}): {e_upd}")
            
            conn.commit()
            if conn2 and cursor2:
                try:
                    conn2.commit()
                except:
                    pass
            print(f"✅ {len(prospectos_incorretos)} prospectos corrigidos com sucesso")
        else:
            print("✅ Nenhum prospecto com status incorreto encontrado")
            
        cursor.close()
        conn.close()
        if cursor2:
            cursor2.close()
        if conn2:
            conn2.close()
        return len(prospectos_incorretos)
        
    except Exception as e:
        print(f"⚠️ Erro ao corrigir status de prospectos: {e}")
        return 0

def processar_todos_prospectos():
    """Busca todos os prospectos e executa a conversão para cada um."""
    try:
        # Ajuste prévio no banco secundário
        ajustar_finalizados_para_aguardando_validacao_segundo_banco()

        # PRIMEIRO: Corrigir prospectos com status incorreto
        print("🔧 Verificando e corrigindo prospectos com status incorreto...", flush=True)
        corrigidos = corrigir_prospectos_status_incorreto()
        if corrigidos > 0:
            print()
        
        # Buscar lista de prospectos
        print("🔍 Buscando prospectos não convertidos dos vendedores ID 1613 e 1618...")
        prospectos = buscar_prospectos()
        
        if not prospectos:
            print("❌ Nenhum prospecto encontrado para processar.")
            return
        
        print(f"📋 Encontrados {len(prospectos)} prospectos para processar:")
        for i, prospecto in enumerate(prospectos, 1):
            print(f"  {i}. ID: {prospecto['id_prospecto']} - Nome: {prospecto['nome_razaosocial']}")
        
        print("\n" + "="*80)
        print("🚀 INICIANDO PROCESSAMENTO DOS PROSPECTOS")
        print("="*80)
        
        # Processar cada prospecto
        sucessos = 0
        falhas = 0
        pulados_erro_final = 0
        pulados_max_tentativas = 0
        
        for i, prospecto in enumerate(prospectos, 1):
            nome = prospecto['nome_razaosocial']
            id_prospecto = str(prospecto['id_prospecto'])
            
            print(f"\n📊 PROCESSANDO {i}/{len(prospectos)}")
            print(f"👤 Nome: {nome}")
            print(f"🆔 ID: {id_prospecto}")
            print("-" * 60)
            
            try:
                # Verificar tentativas do prospecto
                tentativas, status = verificar_tentativas_prospecto(id_prospecto)
                
                print(f"📋 Status atual no banco: {status if status else 'Novo prospecto'}")
                print(f"🔄 Tentativas anteriores: {tentativas}")
                
                if status == 'erro':
                    print(f"❌ Prospecto {nome} (ID: {id_prospecto}) já marcado como erro final")
                    print(f"⏭️ Pulando para o próximo prospecto...")
                    pulados_erro_final += 1
                    continue
                
                if tentativas >= 3:
                    print(f"❌ Prospecto {nome} (ID: {id_prospecto}) já atingiu o máximo de 3 tentativas")
                    print(f"⏭️ Pulando para o próximo prospecto...")
                    
                    # Marcar como erro se ainda não estiver marcado
                    if status != 'erro':
                        print(f"🔧 Marcando prospecto como erro por atingir máximo de tentativas...")
                        if marcar_prospecto_como_erro_final(id_prospecto, nome):
                            print(f"✅ Status atualizado para erro")
                        else:
                            print(f"⚠️ Falha ao atualizar status")
                    
                    pulados_max_tentativas += 1
                    continue
                
                print(f"🚀 Iniciando tentativa {tentativas + 1} para o prospecto...")
                
                # Chamar a função main para processar o prospecto
                # Passa os textos das opções que devem ser selecionadas nos dropdowns
                main(
                    nome_filtro=nome,
                    id_prospecto=id_prospecto,
                    texto_boleto_digital="Boleto Digital",
                    texto_varejo="Varejo",
                    texto_banco_itau="BANCO ITAU"
                )
                sucessos += 1
                print(f"✅ Prospecto {id_prospecto} processado com sucesso!")
                
            except Exception as e:
                falhas += 1
                print(f"❌ ERRO ao processar prospecto {id_prospecto}:")
                print(f"   📝 Detalhes: {str(e)}")
                
                # Verificar se foi a terceira tentativa falhada
                tentativas_apos_erro, _ = verificar_tentativas_prospecto(id_prospecto)
                if tentativas_apos_erro >= 3:
                    print(f"🚫 Prospecto {nome} atingiu o máximo de tentativas e será marcado como erro final")
                
            print("-" * 60)
        
        # Relatório final
        print("\n" + "="*80)
        print("📊 RELATÓRIO FINAL DETALHADO")
        print("="*80)
        print(f"✅ Sucessos: {sucessos}")
        print(f"❌ Falhas: {falhas}")
        print(f"⏭️ Pulados (erro final): {pulados_erro_final}")
        print(f"⏭️ Pulados (max tentativas): {pulados_max_tentativas}")
        print(f"📋 Total encontrados: {len(prospectos)}")
        print(f"🔄 Total processados: {sucessos + falhas}")
        
        if len(prospectos) > 0:
            taxa_processamento = ((sucessos + falhas) / len(prospectos)) * 100
            print(f"📈 Taxa de processamento: {taxa_processamento:.1f}%")
            
        if (sucessos + falhas) > 0:
            taxa_sucesso = (sucessos / (sucessos + falhas)) * 100
            print(f"🎯 Taxa de sucesso: {taxa_sucesso:.1f}%")
        
        print("="*80)
        
    except Exception as e:
        print(f"❌ Erro geral ao processar prospectos: {str(e)}")


if __name__ == "__main__":
    # Garantir que a saída apareça imediatamente (evita buffer quando não há TTY)
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
    print("🚀 main_leads.py iniciado.", flush=True)
    # Executar processamento de todos os prospectos
    while True:
        processar_todos_prospectos()
        time.sleep(20)