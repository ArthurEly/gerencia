# Salve como: debug_oids.py
import sys
from rdflib import Graph, Namespace
from easysnmp import Session, EasySNMPError

# --- Configuração ---
GRAPH_FILE = "grafo_IF-MIB.ttl" # O arquivo que queremos depurar
SNMP_TARGET_HOST = 'localhost'
SNMP_COMMUNITY = 'public'
SNMP_VERSION = 2
MIBO = Namespace("http://purl.org/net/mibo#")
# --- Fim da Configuração ---

print(f"--- Iniciando Depuração de OIDs para: {GRAPH_FILE} ---")

# 1. Conecta ao SNMP
try:
    session = Session(
        hostname=SNMP_TARGET_HOST, 
        community=SNMP_COMMUNITY, 
        version=SNMP_VERSION,
        timeout=1,
        retries=1
    )
except EasySNMPError as e:
    print(f"!! ERRO FATAL: Não foi possível conectar ao {SNMP_TARGET_HOST}: {e}")
    sys.exit(1)

# 2. Carrega o Grafo
try:
    g = Graph()
    g.parse(GRAPH_FILE, format="turtle")
except FileNotFoundError:
    print(f"!! ERRO: Arquivo {GRAPH_FILE} não encontrado. Rode 'make run' primeiro.")
    sys.exit(1)

# 3. Testa os Escalares (Onde o bug está)
print(f"\n--- Testando Escalares (definidos no .ttl) ---")
query_scalars = """
SELECT ?subject ?oid
WHERE { ?subject a mibo:Scalar ; mibo:hasOID ?oid . }
"""
rows_scalars = list(g.query(query_scalars))
print(f"-> O {GRAPH_FILE} definiu {len(rows_scalars)} Escalares. Testando um por um...")

sucesso_scalar = 0
falha_scalar = 0
for row in rows_scalars:
    subject_uri, oid_literal = row
    oid_str = str(oid_literal)
    obj_name = str(subject_uri).split('#')[-1]
    
    try:
        # Tenta buscar como escalar (com .0)
        item = session.get(f"{oid_str}.0")
        if item.value is not None and item.value != 'NOSUCHOBJECT' and item.value != 'NOSUCHINSTANCE':
            print(f"[ SUCESSO ] Escalar: {obj_name:<25} (OID: {oid_str}.0) -> Valor: {item.value}")
            sucesso_scalar += 1
        else:
            print(f"[ FALHA-S ] Escalar: {obj_name:<25} (OID: {oid_str}.0) -> Agente retornou: {item.value}")
            falha_scalar += 1
    except EasySNMPError as e:
        # Erro (provavelmente noSuchName)
        print(f"[ FALHA-E ] Escalar: {obj_name:<25} (OID: {oid_str}.0) -> Erro: {e}")
        falha_scalar += 1

# 4. Testa as Colunas de Tabela
print(f"\n--- Testando Colunas de Tabela (definidas no .ttl) ---")
query_tables = """
SELECT ?subject ?oid
WHERE { ?subject a mibo:TableColumn ; mibo:hasOID ?oid . }
"""
rows_tables = list(g.query(query_tables))
print(f"-> O {GRAPH_FILE} definiu {len(rows_tables)} Colunas. Testando um por um...")

sucesso_col = 0
falha_col = 0
for row in rows_tables:
    subject_uri, oid_literal = row
    oid_str = str(oid_literal)
    obj_name = str(subject_uri).split('#')[-1]
    
    try:
        # Tenta buscar como tabela (com walk)
        items_list = session.walk(oid_str)
        if items_list:
            print(f"[ SUCESSO ] Coluna: {obj_name:<25} (OID: {oid_str}) -> Encontrados {len(items_list)} valores.")
            sucesso_col += 1
        else:
            print(f"[ FALHA-S ] Coluna: {obj_name:<25} (OID: {oid_str}) -> Walk retornou 0 valores.")
            falha_col += 1
    except EasySNMPError as e:
        print(f"[ FALHA-E ] Coluna: {obj_name:<25} (OID: {oid_str}) -> Erro: {e}")
        falha_col += 1

print("\n--- Resumo da Depuração ---")
print(f"Escalares: {sucesso_scalar} SUCESSO, {falha_scalar} FALHA")
print(f"Colunas:   {sucesso_col} SUCESSO, {falha_col} FALHA")
print("Se 'Escalares' tem muitas FALHAS e 'Colunas' tem 0 SUCESSO, o 'gerador_de_grafos.py' está classificando errado.")