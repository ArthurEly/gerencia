# Salve como: preencher_grafos.py
import sys
from rdflib import Graph, Literal, Namespace
from rdflib.namespace import RDF
from easysnmp import Session

# --- Configuração ---
SNMP_TARGET_HOST = 'localhost'
SNMP_COMMUNITY = 'public'
SNMP_VERSION = 2
MIBS_PARA_PREENCHER = ['SNMPv2-MIB', 'IF-MIB']
MIBO = Namespace("http://purl.org/net/mibo#")
RDF = RDF
# --- Fim da Configuração ---

def format_snmp_value(item):
    """
    Formata valores especiais do SNMP, como MAC addresses.
    Baseado no seu script de exemplo.
    """
    # Tenta formatar MAC (ifPhysAddress)
    # NOTA: O valor binário do easysnmp às vezes é bytes, às vezes str.
    if item.snmp_type == 'STRING' and isinstance(item.value, (bytes, str)):
         if len(item.value) == 6:
             try:
                 # Converte para bytes se for str
                 val_bytes = item.value if isinstance(item.value, bytes) else item.value.encode('latin1')
                 formatted_mac = ":".join(f"{b:02x}" for b in val_bytes)
                 # Ignora MACs zerados
                 if formatted_mac != "00:00:00:00:00:00":
                     return formatted_mac
             except Exception:
                 pass # Não era um MAC, apenas uma string normal
    
    # Formata Timeticks (sysUpTime)
    if item.snmp_type == 'TIMETICKS':
        try:
            total_seconds = int(item.value) / 100
            days = total_seconds // 86400
            hours = (total_seconds % 86400) // 3600
            minutes = (total_seconds % 3600) // 60
            return f"({item.value}) {int(days)}d {int(hours)}h {int(minutes)}m"
        except (ValueError, TypeError):
            pass # Deixa o valor bruto
            
    # Valor padrão
    return item.value

def main():
    print("\n--- Iniciando Etapa 2: Preenchimento de Grafos com Dados Vivos (usando easysnmp) ---")
    
    try:
        # 
        # --- ESTA É A CORREÇÃO ---
        # Adicionamos 'use_numeric=True' para forçar OIDs numéricos
        #
        session = Session(
            hostname=SNMP_TARGET_HOST, 
            community=SNMP_COMMUNITY, 
            version=SNMP_VERSION,
            timeout=2,
            retries=1,
            use_numeric=True  # <--- CORREÇÃO APLICADA AQUI
        )
        # --- FIM DA CORREÇÃO ---
        
    except Exception as e:
        print(f"!! ERRO FATAL: Não foi possível criar a sessão easysnmp.", file=sys.stderr)
        print(f"!! Detalhe: {e}", file=sys.stderr)
        print(f"!! Verifique se as bibliotecas C (libsnmp-dev) estão instaladas.", file=sys.stderr)
        sys.exit(1)

    for mib_name in MIBS_PARA_PREENCHER:
        input_file = f"grafo_{mib_name}.ttl"
        output_file = f"grafo_{mib_name}_vivo.ttl"
        
        print(f"\nProcessando '{input_file}'...")
        
        try:
            g = Graph()
            g.parse(input_file, format="turtle")
            g.bind("mibo", MIBO)
        except FileNotFoundError:
            print(f"!! ERRO: Arquivo schema '{input_file}' não encontrado.", file=sys.stderr)
            continue
            
        # --- 1. Processa os Escalares (com session.get) ---
        query_scalars = """
        SELECT ?subject ?oid
        WHERE { ?subject a mibo:Scalar ; mibo:hasOID ?oid . }
        """
        rows_scalars = g.query(query_scalars)
        print(f"  -> Buscando {len(list(g.query(query_scalars)))} Escalares...")
        
        triplos_adicionados = 0
        for row in rows_scalars:
            subject_uri, oid_literal = row
            oid_str = str(oid_literal)
            try:
                # Usa .0 para pegar escalar
                item = session.get(f"{oid_str}.0") 
                if item.value is not None and item.value != 'NOSUCHOBJECT' and item.value != 'NOSUCHINSTANCE':
                    g.add((subject_uri, MIBO.hasValue, Literal(format_snmp_value(item))))
                    triplos_adicionados += 1
            except Exception as e:
                # Ignora OIDs não encontrados
                pass 
                
        print(f"  -> {triplos_adicionados} valores de Escalares adicionados.")

        # --- 2. Processa as Colunas de Tabela (com session.walk) ---
        # (Este bloco agora está limpo, sem os prints de debug)
        query_tables = """
        SELECT ?subject ?oid
        WHERE { ?subject a mibo:TableColumn ; mibo:hasOID ?oid . }
        """
        rows_tables = g.query(query_tables)
        print(f"  -> Buscando {len(list(g.query(query_scalars)))} Colunas de Tabela (walk)...")
        
        triplos_tabela = 0
        for row in rows_tables:
            col_uri, oid_literal = row
            # oid_str é o OID da *coluna* (ex: .1.3.6.1.2.1.2.2.1.2)
            oid_str = str(oid_literal)
            col_name = str(col_uri).split('#')[-1]
            try:
                items_list = session.walk(oid_str) 
                
                for item in items_list:
                    # --- CORREÇÃO DO BUG DE ÍNDICE (v2) ---
                    # Agora 'item.oid' será numérico graças a 'use_numeric=True'
                    full_oid = item.oid
                    
                    # Normaliza os OIDs removendo o '.' inicial, se existir
                    full_oid_norm = full_oid.lstrip('.')
                    oid_str_norm = oid_str.lstrip('.')
                    
                    instance_index = "" # Reseta o índice

                    # Tenta calcular o índice manualmente
                    if full_oid_norm.startswith(oid_str_norm + '.'):
                        # Extrai o que vem depois (ex: ".1", ".2", ".10.1")
                        instance_index = full_oid_norm[len(oid_str_norm):]
                        # Remove o '.' inicial do índice (ex: ".1" -> "1")
                        instance_index = instance_index.lstrip('.')
                    
                    # Se o cálculo manual falhar, tenta o fallback
                    if not instance_index:
                         instance_index = item.oid_index
                    # --- FIM DA CORREÇÃO ---

                    if not instance_index:
                         print(f"  !! AVISO: Índice vazio para {col_name}, valor {item.value}. Pulando.", file=sys.stderr)
                         continue
                    
                    # Agora instance_index será "1", "2", "3", "4"
                    instance_uri = MIBO[f"{col_name}_{instance_index}"]
                    
                    # Adiciona os triplos da instância
                    g.add((instance_uri, RDF.type, col_uri)) # Ex: mibo:ifDescr_1 a mibo:ifDescr
                    g.add((instance_uri, MIBO.hasIndex, Literal(instance_index)))
                    g.add((instance_uri, MIBO.hasValue, Literal(format_snmp_value(item))))
                    triplos_tabela += 3
                    
            except Exception as e:
                print(f"  !! AVISO: Falha no walk do OID {oid_str} ({col_name}): {e}", file=sys.stderr)
        
        print(f"  -> {triplos_tabela} triplos de Tabela adicionados.")
        
        g.serialize(destination=output_file, format="turtle")
        print(f"  -> Grafo preenchido salvo em '{output_file}'.")

    print("\n--- Preenchimento de grafos concluído! ---")

if __name__ == "__main__":
    main()