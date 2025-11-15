# Salve como: monitor_interfaces.py (CORRIGIDO)
import sys
from rdflib import Graph

# O grafo "vivo" da IF-MIB que você acabou de gerar
GRAFO_VIVO = "grafo_IF-MIB_vivo.ttl"

# Esta é a sua "operação de gerenciamento"
# MUDANÇA: ?index foi renomeado para ?idx para evitar conflito
QUERY_MONITORAMENTO = """
PREFIX mibo: <http://purl.org/net/mibo#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?idx ?descricao ?download ?upload
WHERE {
  # 1. Encontra a instância da descrição e pega seu valor e índice
  ?instanciaDescr rdf:type mibo:ifDescr ;
                  mibo:hasValue ?descricao ;
                  mibo:hasIndex ?idx .

  # 2. Encontra a instância de HCInOctets (Download) COM O MESMO ÍNDICE
  ?instanciaInHC rdf:type mibo:ifHCInOctets ;
                   mibo:hasValue ?inOctets_raw ;
                   mibo:hasIndex ?idx .

  # 3. Encontra a instância de HCOutOctets (Upload) COM O MESMO ÍNDICE
  ?instanciaOutHC rdf:type mibo:ifHCOutOctets ;
                    mibo:hasValue ?outOctets_raw ;
                    mibo:hasIndex ?idx .
  
  # 4. Converte os valores para inteiro para facilitar a ordenação e cálculo
  BIND(xsd:integer(?inOctets_raw) AS ?download)
  BIND(xsd:integer(?outOctets_raw) AS ?upload)
}
# Ordena pelo número do índice
ORDER BY (xsd:integer(?idx))
"""

def main():
    print(f"--- Executando consulta de monitoramento em '{GRAFO_VIVO}' ---")
    
    g = Graph()
    try:
        g.parse(GRAFO_VIVO, format="turtle")
    except FileNotFoundError:
        print(f"!! ERRO: Arquivo '{GRAFO_VIVO}' não encontrado.", file=sys.stderr)
        print("!! Execute 'make run' primeiro para gerar o grafo.", file=sys.stderr)
        sys.exit(1)
        
    results = g.query(QUERY_MONITORAMENTO)
    
    if not results:
        print("!! Nenhum resultado encontrado. O grafo está vazio ou a consulta falhou.")
        return

    print("\n=== Monitoramento de Tráfego por Interface ===")
    print(f"{'Index':<6} | {'Interface':<18} | {'Download':<22} | {'Upload':<22}")
    print("-" * 72)
    
    for row in results:
        # Pega os valores da consulta
        dl_bytes = int(row.download)
        ul_bytes = int(row.upload)
        
        # Converte para Gigabytes (GB) para facilitar a leitura
        dl_gb = dl_bytes / (1024 * 1024 * 1024)
        ul_gb = ul_bytes / (1024 * 1024 * 1024)
        
        # MUDANÇA: 'row.index' virou 'row.idx'
        print(f"{str(row.idx):<6} | {str(row.descricao):<18} | {dl_bytes:<22} ({dl_gb:.2f} GB)")
        print(f"{'':<6} | {'':<18} | {'':<22} | {ul_bytes:<22} ({ul_gb:.2f} GB)")
        print("-" * 72)

if __name__ == "__main__":
    main()