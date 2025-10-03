import rdflib
import networkx as nx
import matplotlib.pyplot as plt
from rdflib.namespace import RDF, RDFS

# 1. Carrega o grafo RDF
g = rdflib.Graph()
g.parse("knowledge_graph.ttl", format="turtle")

# 2. Converte para NetworkX
G = nx.DiGraph()

for subj, pred, obj in g:
    subj_str = str(subj)
    pred_str = str(pred)
    obj_str = str(obj)
    
    # adiciona o nó sujeito
    if not G.has_node(subj_str):
        G.add_node(subj_str)
    
    # adiciona o objeto como nó ou atributo
    if (pred == RDF.type or pred == RDFS.label or pred == RDFS.comment):
        # para tipos e labels, podemos colocar como atributo do nó
        if 'label' not in G.nodes[subj_str]:
            G.nodes[subj_str]['label'] = obj_str
    else:
        # cria uma aresta do sujeito para o objeto
        G.add_node(obj_str)
        G.add_edge(subj_str, obj_str, label=pred_str)

# 3. Desenha o grafo
plt.figure(figsize=(20, 20))
pos = nx.spring_layout(G, k=0.5)  # força layout para melhor visualização

# desenha nós
nx.draw_networkx_nodes(G, pos, node_size=500, node_color="skyblue")

# desenha labels
labels = {n: G.nodes[n].get('label', n.split('#')[-1]) for n in G.nodes()}
nx.draw_networkx_labels(G, pos, labels, font_size=8)

# desenha arestas
nx.draw_networkx_edges(G, pos, arrows=True)
edge_labels = {(u, v): d['label'].split('#')[-1] for u, v, d in G.edges(data=True)}
nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=6)

plt.title("Visualização do Grafo RDF do IF-MIB")
plt.axis('off')
plt.savefig("grafo_ifmib.png", dpi=300)
print("Grafo salvo em 'grafo_ifmib.png'")
