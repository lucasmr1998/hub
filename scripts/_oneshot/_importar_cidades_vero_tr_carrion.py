"""Importa as cidades atendidas pela Vero pro tenant TR Carrion (id=11)
em viabilidade_cidadeviabilidade. Idempotente: skip se ja existe.

Fonte: PDF "Cidades VERO.pdf" enviado pelo Tiago/Lucas Carrion em
26/05/2026. Sem tier (campo nao existe ainda — fica pra depois).
"""
import sys
import psycopg2
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

env_path = Path(__file__).resolve().parents[1] / '.env.prod_readonly'
env = {}
for line in env_path.read_text(encoding='utf-8').splitlines():
    line = line.strip()
    if not line or line.startswith('#') or '=' not in line:
        continue
    k, v = line.split('=', 1)
    env[k.strip()] = v.strip()

TENANT_ID = 11

CIDADES = [
    # Pagina 1
    ('Abadia de Goiás', 'GO'), ('Acreúna', 'GO'), ('Águas Mornas', 'SC'),
    ('Agudos', 'SP'), ('Alfredo Marcondes', 'SP'), ('Alfredo Vasconcelos', 'MG'),
    ('Alto Horizonte', 'GO'), ('Alvorada', 'RS'), ('Amaralina', 'GO'),
    ('Americana', 'SP'), ('Anaurilândia', 'MS'), ('Anchieta', 'SC'),
    ('Andradina', 'SP'), ('Angelina', 'SC'), ('Antônio Carlos', 'MG'),
    ('Antônio Carlos', 'SC'), ('Aparecida', 'SP'), ('Aparecida de Goiânia', 'GO'),
    ('Araçatuba', 'SP'), ('Araçoiaba da Serra', 'SP'), ('Araras', 'SP'),
    ('Arroio do Sal', 'RS'), ('Arujá', 'SP'), ('Avanhandava', 'SP'),
    ('Balneário Pinhal', 'RS'), ('Bandeirante', 'SC'),
    # Pagina 2
    ('Barão de Cocais', 'MG'), ('Barbacena', 'MG'), ('Barra Bonita', 'SP'),
    ('Barracão', 'PR'), ('Barroso', 'MG'), ('Barueri', 'SP'),
    ('Bataguassu', 'MS'), ('Batayporã', 'MS'), ('Bauru', 'SP'),
    ('Bela Vista de Goiás', 'GO'), ('Belmonte', 'SC'), ('Belo Horizonte', 'MG'),
    ('Bento de Abreu', 'SP'), ('Bertioga', 'SP'), ('Betim', 'MG'),
    ('Bicas', 'MG'), ('Biguaçu', 'SC'), ('Birigui', 'SP'),
    ('Boa Esperança', 'MG'), ('Bom Despacho', 'MG'), ('Bom Princípio', 'RS'),
    ('Bom Sucesso', 'MG'), ('Botucatu', 'SP'), ('Brasília', 'DF'),
    ('Brochier', 'RS'), ('Brotas', 'SP'), ('Brumadinho', 'MG'),
    ('Buriti Alegre', 'GO'),
    # Pagina 3
    ('Caçapava', 'SP'), ('Cachoeira Alta', 'GO'), ('Cachoeira Paulista', 'SP'),
    ('Cachoeirinha', 'RS'), ('Caeté', 'MG'), ('Caieiras', 'SP'),
    ('Caiuá', 'SP'), ('Cajamar', 'SP'), ('Caldas Novas', 'GO'),
    ('Campestre de Goiás', 'GO'), ('Campinas', 'SP'), ('Campo Belo', 'MG'),
    ('Campo Erê', 'SC'), ('Campo Grande', 'MS'), ('Canas', 'SP'),
    ('Canelinha', 'SC'), ('Canoas', 'RS'), ('Capão da Canoa', 'RS'),
    ('Capela de Santana', 'RS'), ('Carandaí', 'MG'), ('Carapicuíba', 'SP'),
    ('Caratinga', 'MG'), ('Carmo da Mata', 'MG'), ('Carmópolis de Minas', 'MG'),
    ('Castilho', 'SP'), ('Catalão', 'GO'), ('Catanduva', 'SP'),
    ('Caxambu', 'MG'),
    # Pagina 4
    ('Cezarina', 'GO'), ('Charqueadas', 'RS'), ('Cidreira', 'RS'),
    ('Cláudio', 'MG'), ('Conceição da Barra de Minas', 'MG'), ('Congonhas', 'MG'),
    ('Conselheiro Lafaiete', 'MG'), ('Contagem', 'MG'), ('Cordeirópolis', 'SP'),
    ('Coroados', 'SP'), ('Coronel Fabriciano', 'MG'), ('Cotia', 'SP'),
    ('Cristiano Otoni', 'MG'), ('Cromínia', 'GO'), ('Cruz Alta', 'RS'),
    ('Cruzeiro', 'SP'), ('Curitiba', 'PR'), ('Descanso', 'SC'),
    ('Diadema', 'SP'), ('Dionísio Cerqueira', 'SC'), ('Divinópolis', 'MG'),
    ('Dois Córregos', 'SP'), ('Dois Irmãos', 'RS'), ('Dores de Campos', 'MG'),
    ('Dourados', 'MS'), ('Duque de Caxias', 'RJ'), ('Edealina', 'GO'),
    ('Edéia', 'GO'),
    # Pagina 5
    ('Embu das Artes', 'SP'), ('Emilianópolis', 'SP'), ('Entre Rios de Minas', 'MG'),
    ('Esmeraldas', 'MG'), ('Estância Velha', 'RS'), ('Esteio', 'RS'),
    ('Fátima do Sul', 'MS'), ('Feliz', 'RS'), ('Fernandópolis', 'SP'),
    ('Firminópolis', 'GO'), ('Flor da Serra do Sul', 'PR'), ('Florianópolis', 'SC'),
    ('Francisco Beltrão', 'PR'), ('Francisco Morato', 'SP'), ('Franco da Rocha', 'SP'),
    ('Frederico Westphalen', 'RS'), ('Galvão', 'SC'), ('Glorinha', 'RS'),
    ('Goiânia', 'GO'), ('Goianira', 'GO'), ('Goiatuba', 'GO'),
    ('Governador Celso Ramos', 'SC'), ('Governador Valadares', 'MG'),
    ('Gravataí', 'RS'), ('Guaiçara', 'SP'), ('Guapó', 'GO'),
    ('Guaraçaí', 'SP'), ('Guaraciaba', 'SC'),
    # Pagina 6
    ('Guarará', 'MG'), ('Guararapes', 'SP'), ('Guarujá', 'SP'),
    ('Guarujá do Sul', 'SC'), ('Guarulhos', 'SP'), ('Harmonia', 'RS'),
    ('Hidrolândia', 'GO'), ('Iacanga', 'SP'), ('Ibirité', 'MG'),
    ('Ibiúna', 'SP'), ('Igaraçu do Tietê', 'SP'), ('Igarapé', 'MG'),
    ('Ijaci', 'MG'), ('Ijuí', 'RS'), ('Ilha Solteira', 'SP'),
    ('Imbé', 'RS'), ('Indaiatuba', 'SP'), ('Indiara', 'GO'),
    ('Inhumas', 'GO'), ('Ipameri', 'GO'), ('Ipatinga', 'MG'),
    ('Iperó', 'SP'), ('Iracemápolis', 'SP'), ('Itabira', 'MG'),
    ('Itabirito', 'MG'), ('Itaguara', 'MG'), ('Itapecerica da Serra', 'SP'),
    ('Itapema', 'SC'),
    # Pagina 7
    ('Itapevi', 'SP'), ('Itapura', 'SP'), ('Itaquaquecetuba', 'SP'),
    ('Itaqui', 'RS'), ('Itatiaiuçu', 'MG'), ('Itauçu', 'GO'),
    ('Itaúna', 'MG'), ('Itu', 'SP'), ('Itupeva', 'SP'),
    ('Ivoti', 'RS'), ('Jales', 'SP'), ('Jandaia', 'GO'),
    ('Jandira', 'SP'), ('Jarinu', 'SP'), ('Jaú', 'SP'),
    ('Jeceaba', 'MG'), ('João Monlevade', 'MG'), ('Juiz de Fora', 'MG'),
    ('Jundiaí', 'SP'), ('Jupiá', 'SC'), ('Lagoa Santa', 'MG'),
    ('Lavínia', 'SP'), ('Lavras', 'MG'), ('Lavrinhas', 'SP'),
    ('Leme', 'SP'), ('Leopoldina', 'MG'), ('Lima Duarte', 'MG'),
    ('Limeira', 'SP'),
    # Pagina 8
    ('Lindolfo Collor', 'RS'), ('Linha Nova', 'RS'), ('Lins', 'SP'),
    ('Lorena', 'SP'), ('Louveira', 'SP'), ('Luziânia', 'GO'),
    ('Macatuba', 'SP'), ('Mairinque', 'SP'), ('Major Gercino', 'SC'),
    ('Manhuaçu', 'MG'), ('Maquiné', 'RS'), ('Mar de Espanha', 'MG'),
    ('Mara Rosa', 'GO'), ('Maratá', 'RS'), ('Mariana', 'MG'),
    ('Mariópolis', 'PR'), ('Marmeleiro', 'PR'), ('Martinho Campos', 'MG'),
    ('Martinópolis', 'SP'), ('Marzagão', 'GO'), ('Matias Barbosa', 'MG'),
    ('Matozinhos', 'MG'), ('Mauá', 'SP'), ('Mineiros do Tietê', 'SP'),
    ('Mirandópolis', 'SP'), ('Mirassol', 'SP'), ('Mogi das Cruzes', 'SP'),
    ('Monte Mor', 'SP'),
    # Pagina 9
    ('Montenegro', 'RS'), ('Morro Reuter', 'RS'), ('Murutinga do Sul', 'SP'),
    ('Nepomuceno', 'MG'), ('Nova Andradina', 'MS'), ('Nova Iguaçu de Goiás', 'GO'),
    ('Nova Independência', 'SP'), ('Nova Lima', 'MG'), ('Nova Odessa', 'SP'),
    ('Nova Santa Rita', 'RS'), ('Nova Serrana', 'MG'), ('Nova Trento', 'SC'),
    ('Novo Gama', 'GO'), ('Novo Hamburgo', 'RS'), ('Novo Horizonte', 'SC'),
    ('Oliveira', 'MG'), ('Osasco', 'SP'), ('Osório', 'RS'),
    ('Ouro Branco', 'MG'), ('Ouro Preto', 'MG'), ('Palhoça', 'SC'),
    ('Palma Sola', 'SC'), ('Palmeiras de Goiás', 'GO'), ('Panambi', 'RS'),
    ('Pará de Minas', 'MG'), ('Paraíso', 'SC'), ('Paraúna', 'GO'),
    ('Pareci Novo', 'RS'),
    # Pagina 10
    ('Pato Branco', 'PR'), ('Paulínia', 'SP'), ('Pederneiras', 'SP'),
    ('Pedro Leopoldo', 'MG'), ('Penápolis', 'SP'), ('Pequeri', 'MG'),
    ('Perdões', 'MG'), ('Pereira Barreto', 'SP'), ('Petrolina de Goiás', 'GO'),
    ('Picada Café', 'RS'), ('Piedade', 'SP'), ('Pindamonhangaba', 'SP'),
    ('Piquerobi', 'SP'), ('Piracanjuba', 'GO'), ('Piracicaba', 'SP'),
    ('Pirajuí', 'SP'), ('Pirapora do Bom Jesus', 'SP'), ('Pirassununga', 'SP'),
    ('Piratininga', 'SP'), ('Poá', 'SP'), ('Pontalina', 'GO'),
    ('Ponte Nova', 'MG'), ('Porangatu', 'GO'), ('Portão', 'RS'),
    ('Porto Alegre', 'RS'), ('Porto Belo', 'SC'), ('Porto Ferreira', 'SP'),
    ('Potim', 'SP'),
    # Pagina 11
    ('Prados', 'MG'), ('Presidente Bernardes', 'SP'), ('Presidente Epitácio', 'SP'),
    ('Presidente Lucena', 'RS'), ('Presidente Prudente', 'SP'), ('Presidente Venceslau', 'SP'),
    ('Princesa', 'SC'), ('Promissão', 'SP'), ('Rancho Queimado', 'SC'),
    ('Renascença', 'PR'), ('Ressaquinha', 'MG'), ('Ribeirão das Neves', 'MG'),
    ('Ribeirão dos Índios', 'SP'), ('Ribeirão Pires', 'SP'), ('Ribeirão Vermelho', 'MG'),
    ('Rio de Janeiro', 'RJ'), ('Rio Grande da Serra', 'SP'), ('Rio Quente', 'GO'),
    ('Rio Verde', 'GO'), ('Rubiácea', 'SP'), ('Rubinéia', 'SP'),
    ('Sabará', 'MG'), ('Salto', 'SP'), ('Salvador', 'BA'),
    ('Salvador do Sul', 'RS'), ('Santa Bárbara', 'MG'), ('Santa Bárbara d\'Oeste', 'SP'),
    ('Santa Cruz da Conceição', 'SP'),
    # Pagina 12
    ('Santa Cruz de Minas', 'MG'), ('Santa Fé do Sul', 'SP'), ('Santa Helena de Goiás', 'GO'),
    ('Santa Isabel', 'SP'), ('Santa Luzia', 'MG'), ('Santa Maria da Serra', 'SP'),
    ('Santa Maria do Herval', 'RS'), ('Santa Salete', 'SP'), ('Santa Tereza de Goiás', 'GO'),
    ('Santana da Ponte Pensa', 'SP'), ('Santana de Parnaíba', 'SP'), ('Santana do Paraíso', 'MG'),
    ('Santiago', 'RS'), ('Santo Amaro da Imperatriz', 'SC'), ('Santo Anastácio', 'SP'),
    ('Santo André', 'SP'), ('Santo Ângelo', 'RS'), ('Santo Antônio da Patrulha', 'RS'),
    ('Santo Antônio do Amparo', 'MG'), ('Santo Augusto', 'RS'), ('Santo Expedito', 'SP'),
    ('Santos', 'SP'), ('Santos Dumont', 'MG'), ('São Bernardo do Campo', 'SP'),
    ('São Borja', 'RS'), ('São Brás do Suaçuí', 'MG'), ('São Caetano do Sul', 'SP'),
    ('São Domingos', 'SC'),
    # Pagina 13
    ('São Francisco de Paula', 'MG'), ('São Jerônimo', 'RS'), ('São João Batista', 'SC'),
    ('São João da Boa Vista', 'SP'), ('São João da Paraúna', 'GO'), ('São João de Meriti', 'RJ'),
    ('São João Del Rei', 'MG'), ('São Joaquim de Bicas', 'MG'), ('São José', 'SC'),
    ('São José da Lapa', 'MG'), ('São José do Cedro', 'SC'), ('São José do Hortêncio', 'RS'),
    ('São José do Rio Preto', 'SP'), ('São José do Sul', 'RS'), ('São José dos Campos', 'SP'),
    ('São Leopoldo', 'RS'), ('São Lourenço', 'MG'), ('São Lourenço do Oeste', 'SC'),
    ('São Luís de Montes Belos', 'GO'), ('São Luiz Gonzaga', 'RS'), ('São Miguel do Oeste', 'SC'),
    ('São Paulo', 'SP'), ('São Pedro de Alcântara', 'SC'), ('São Roque', 'SP'),
    ('São Sebastião do Caí', 'RS'), ('São Vicente', 'SP'), ('Sapucaia do Sul', 'RS'),
    ('Senador Canedo', 'GO'),
    # Pagina 14
    ('Serra', 'ES'), ('Sete Lagoas', 'MG'), ('Sorocaba', 'SP'),
    ('Sumaré', 'SP'), ('Suzano', 'SP'), ('Taboão da Serra', 'SP'),
    ('Tanabi', 'SP'), ('Tatuí', 'SP'), ('Taubaté', 'SP'),
    ('Teófilo Otoni', 'MG'), ('Terra de Areia', 'RS'), ('Tijucas', 'SC'),
    ('Timóteo', 'MG'), ('Tiradentes', 'MG'), ('Torres', 'RS'),
    ('Torrinha', 'SP'), ('Tramandaí', 'RS'), ('Três Cachoeiras', 'RS'),
    ('Três Fronteiras', 'SP'), ('Três Lagoas', 'MS'), ('Trindade', 'GO'),
    ('Triunfo', 'RS'), ('Turvelândia', 'GO'), ('Ubá', 'MG'),
    ('Uberlândia', 'MG'), ('Urânia', 'SP'), ('Uruguaiana', 'RS'),
    ('Valparaíso', 'SP'),
    # Pagina 15
    ('Valparaíso de Goiás', 'GO'), ('Vargem Grande Paulista', 'SP'), ('Varjão', 'GO'),
    ('Várzea Paulista', 'SP'), ('Venâncio Aires', 'RS'), ('Vespasiano', 'MG'),
    ('Viamão', 'RS'), ('Vicentina', 'MS'), ('Viçosa', 'MG'),
    ('Vinhedo', 'SP'), ('Visconde do Rio Branco', 'MG'), ('Vitória', 'ES'),
    ('Vitorino', 'PR'), ('Votorantim', 'SP'), ('Votuporanga', 'SP'),
    ('Xangri-lá', 'RS'), ('Xanxerê', 'SC'),
]


def normalize(s):
    """Normaliza pra comparar dedup: lower + sem espacos extra."""
    return (s or '').strip().lower()


def main():
    print(f'Total cidades na lista: {len(CIDADES)}')

    conn = psycopg2.connect(
        host=env['PROD_DB_HOST'], port=env['PROD_DB_PORT'],
        dbname=env['PROD_DB_NAME'], user=env['PROD_DB_USER'],
        password=env['PROD_DB_PASSWORD'], connect_timeout=10,
    )
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # 1. Carrega existentes
        cur.execute("""
            SELECT cidade, estado FROM viabilidade_cidadeviabilidade
            WHERE tenant_id = %s;
        """, (TENANT_ID,))
        existentes = {(normalize(c), normalize(e)) for c, e in cur.fetchall()}
        print(f'Cidades ja cadastradas no tenant: {len(existentes)}')

        # 2. Filtra duplicatas (consigo a partir do PDF)
        a_inserir = []
        ja_existe = []
        for cidade, estado in CIDADES:
            key = (normalize(cidade), normalize(estado))
            if key in existentes:
                ja_existe.append((cidade, estado))
            else:
                a_inserir.append((cidade, estado))

        print(f'\nJa existem (skip): {len(ja_existe)}')
        for c, e in ja_existe:
            print(f'  - {c}/{e}')

        print(f'\nVai inserir: {len(a_inserir)}')

        # 3. INSERT em batch
        for cidade, estado in a_inserir:
            cur.execute("""
                INSERT INTO viabilidade_cidadeviabilidade
                  (tenant_id, cidade, estado, cep, bairro, observacao, ativo,
                   data_criacao, data_atualizacao)
                VALUES (%s, %s, %s, '', '', '', true, NOW(), NOW());
            """, (TENANT_ID, cidade, estado))

        # 4. Verifica
        cur.execute("SELECT COUNT(*) FROM viabilidade_cidadeviabilidade WHERE tenant_id = %s;", (TENANT_ID,))
        total_final = cur.fetchone()[0]
        print(f'\nTotal cidades no tenant apos insert: {total_final}')

        conn.commit()
        print('\nCOMMIT.')
    except Exception as e:
        conn.rollback()
        print(f'\nERRO: {e}')
        print('ROLLBACK.')
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    main()
