import rdflib

def executar_consulta_sparql(grafo, nome_consulta, consulta):
    """
    Executa uma consulta SPARQL em um grafo e imprime os resultados.
    """
    print(f"--- Executando Consulta: {nome_consulta} ---\n")
    
    try:
        resultados = grafo.query(consulta)
        
        if len(resultados) == 0:
            print("Nenhum resultado encontrado.\n")
            return

        # Imprime o cabeçalho das colunas (variáveis da consulta)
        variaveis = [str(var) for var in resultados.vars]
        print(f"{' | '.join(variaveis):<80}")
        print("-" * 80)

        # Imprime cada linha de resultado
        for linha in resultados:
            valores = [str(linha[var]) for var in variaveis]
            print(f"{' | '.join(valores):<80}")
            
        print(f"\nTotal de resultados: {len(resultados)}\n")

    except Exception as e:
        print(f"Erro ao executar a consulta: {e}\n")


if __name__ == "__main__":
    # 1. Carrega o grafo RDF a partir do arquivo
    g = rdflib.Graph()
    try:
        g.parse("knowledge_graph.ttl", format="turtle")
        print(f"Grafo 'knowledge_graph.ttl' carregado com {len(g)} triplas.\n")
    except FileNotFoundError:
        print("Erro: Arquivo 'knowledge_graph.ttl' não encontrado.")
        print("Por favor, execute 'tradutor_mib_para_rdf.py' primeiro.")
        exit()

    # --- PERGUNTA 1: Encontrar o OID de um objeto MIB específico ('ifSpeed') ---
    consulta_1 = """
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX mibo: <http://purl.org/net/mibo#>

        SELECT ?objeto ?oid
        WHERE {
          ?objeto rdfs:label ?label ;
                  mibo:hasOID ?oid .
          FILTER(str(?label) = "ifSpeed")
        }
    """
    executar_consulta_sparql(g, "Encontrar OID do 'ifSpeed'", consulta_1)

    # --- PERGUNTA 2: Listar todos os objetos MIB cujo nome contém 'Status' ---
    consulta_2 = """
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX mibo: <http://purl.org/net/mibo#>

        SELECT ?objeto ?label
        WHERE {
          ?objeto a mibo:MibObject ;
                  rdfs:label ?label .
          FILTER(regex(str(?label), "Status", "i"))
        }
    """
    executar_consulta_sparql(g, "Listar objetos com 'Status' no nome", consulta_2)
    
    # --- PERGUNTA 3 (CORRIGIDA): Encontrar todos os objetos que são do tipo "Counter32" ---
    # CORREÇÃO: Trocamos contains() por regex() para uma busca flexível e case-insensitive.
    consulta_3 = """
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX mibo: <http://purl.org/net/mibo#>

        SELECT ?label ?syntax
        WHERE {
          ?objeto rdfs:label ?label ;
                  mibo:hasSyntax ?syntax .
          FILTER(regex(str(?syntax), "Counter32", "i"))
        }
    """
    executar_consulta_sparql(g, "Encontrar todos os 'Counter32' (versão corrigida)", consulta_3)