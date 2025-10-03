import rdflib
import networkx as nx
from collections import Counter

def analisar_grafo():
    """
    Carrega o grafo RDF, converte para NetworkX e calcula métricas básicas.
    """
    # 1. Carrega o grafo RDF a partir do arquivo
    g = rdflib.Graph()
    try:
        g.parse("knowledge_graph.ttl", format="turtle")
    except FileNotFoundError:
        print("Erro: Arquivo 'knowledge_graph.ttl' não encontrado.")
        print("Por favor, execute 'tradutor_mib_para_rdf.py' primeiro.")
        return

    # 2. Converte para um grafo NetworkX para facilitar a análise
    # Vamos criar um grafo não-direcionado para métricas como componentes
    G = nx.Graph()
    for subj, pred, obj in g:
        G.add_edge(str(subj), str(obj), label=str(pred))

    print("--- Métricas do Grafo de Conhecimento ---\n")

    # --- Métrica 1: Número de Nós e Arestas ---
    num_nos = G.number_of_nodes()
    num_arestas = G.number_of_edges()
    print("1. Tamanho do Grafo:")
    print(f"   - Nós (Entidades): {num_nos}")
    print("     (Representa o total de 'coisas' únicas: objetos MIB, tipos de dados, etc.)")
    print(f"   - Arestas (Relações): {num_arestas}")
    print("     (Representa o total de 'fatos' ou 'conexões' entre as entidades.)\n")

    # --- Métrica 2: Componentes Conectados ---
    # Para esta métrica, usamos a versão não-direcionada do grafo
    componentes = nx.number_connected_components(G)
    print("2. Componentes Conectados:")
    print(f"   - Número de 'ilhas' de dados: {componentes}")
    print("     (Se for 1, todo o seu conhecimento está interligado em um único grande grafo.)")
    print("     (Se for >1, existem grupos de conhecimento que não têm nenhuma conexão entre si.)\n")

    # --- Métrica 3: Nós Mais Conectados (Centralidade de Grau) ---
    # A Centralidade de Grau é simplesmente o número de conexões que um nó possui.
    graus = G.degree()
    # Usamos Counter para contar e encontrar os mais comuns de forma eficiente
    contador_graus = Counter(dict(graus))
    
    print("3. Nós Mais Conectados (Principais 'Hubs' de Informação):")
    print("   (Mostra quais conceitos são mais centrais, conectando-se a muitos outros.)\n")
    
    for i, (no, grau) in enumerate(contador_graus.most_common(10)):
        # Tenta simplificar o nome do nó para melhor leitura
        nome_simplificado = no.split('#')[-1]
        print(f"   {i+1}. '{nome_simplificado}'")
        print(f"      Conectado a {grau} outros nós.")
        
    print("\n--- Análise Concluída ---")

if __name__ == "__main__":
    analisar_grafo()