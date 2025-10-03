import rdflib
import networkx as nx
from pyvis.network import Network

def visualizar_interativo():
    """
    Carrega o grafo RDF, converte para NetworkX e gera uma
    visualização interativa com Pyvis.
    """
    # 1. Carrega o grafo RDF a partir do arquivo
    g = rdflib.Graph()
    try:
        g.parse("knowledge_graph.ttl", format="turtle")
        print("-> Grafo 'knowledge_graph.ttl' carregado com sucesso.")
    except FileNotFoundError:
        print("Erro: Arquivo 'knowledge_graph.ttl' não encontrado.")
        print("Por favor, execute 'tradutor_mib_para_rdf.py' primeiro.")
        return

    # 2. Converte para um grafo NetworkX
    nx_graph = nx.DiGraph()

    for subj, pred, obj in g:
        # Simplifica os nomes para usar como labels no grafo
        subj_node = str(subj.split('#')[-1]) if '#' in subj else str(subj)
        obj_node = str(obj.split('#')[-1]) if '#' in obj else str(obj)
        pred_label = str(pred.split('#')[-1]) if '#' in pred else str(pred.split('/')[-1])

        # Adiciona os nós e a aresta ao grafo NetworkX
        # O 'title' é o que aparece ao passar o mouse por cima
        nx_graph.add_node(subj_node, title=str(subj))
        nx_graph.add_node(obj_node, title=str(obj))
        nx_graph.add_edge(subj_node, obj_node, label=pred_label)

    print("-> Grafo convertido para o formato NetworkX.")

    # 3. Cria a visualização interativa com Pyvis
    # Aumentamos a altura e largura para dar mais espaço
    net = Network(height="800px", width="100%", notebook=False, directed=True, bgcolor="#222222", font_color="white")

    # Adiciona opções para manipular a física da visualização
    net.set_options("""
    var options = {
      "physics": {
        "barnesHut": {
          "gravitationalConstant": -30000,
          "centralGravity": 0.1,
          "springLength": 150
        },
        "minVelocity": 0.75
      }
    }
    """)
    
    # Carrega o grafo NetworkX no objeto Pyvis
    net.from_nx(nx_graph)
    
    # Gera o arquivo HTML
    output_filename = "grafo_interativo.html"
    try:
        net.save_graph(output_filename)
        print(f"-> Visualização interativa salva com sucesso em '{output_filename}'!")
    except Exception as e:
        print(f"Erro ao salvar o grafo interativo: {e}")

if __name__ == "__main__":
    visualizar_interativo()