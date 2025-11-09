import os
import json
from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS
from pysnmp.smi import builder, error
import networkx as nx
from pyvis.network import Network

# --- PARTE 1: TRADUTOR (sem alterações) ---
def mib_para_rdf(mib_builder, mib_name):
    g = Graph()
    MIBO = Namespace("http://purl.org/net/mibo#")
    g.bind("mibo", MIBO)
    g.bind("rdfs", RDFS)
    MibScalar, MibTableColumn = mib_builder.import_symbols('SNMPv2-SMI', 'MibScalar', 'MibTableColumn')
    ObjectGroup, = mib_builder.import_symbols('SNMPv2-CONF', 'ObjectGroup')
    symbols = {name: obj for name, obj in mib_builder.mibSymbols.get(mib_name, {}).items()}
    for symbol_name, symbol_obj in symbols.items():
        subject = MIBO[symbol_name]
        if isinstance(symbol_obj, (MibScalar, MibTableColumn)):
            #g.add((subject, RDF.type, MIBO.MibObject))
            if hasattr(symbol_obj, 'name'):
                g.add((subject, MIBO.hasOID, Literal('.'.join(map(str, symbol_obj.name)))))
            if hasattr(symbol_obj, 'syntax') and symbol_obj.syntax is not None:
                g.add((subject, MIBO.hasSyntax, Literal(symbol_obj.syntax.__class__.__name__)))
#            if hasattr(symbol_obj, 'maxAccess'):
#                g.add((subject, MIBO.hasMaxAccess, Literal(str(symbol_obj.maxAccess))))
            if hasattr(symbol_obj, 'status') and symbol_obj.status != 'current':
                g.add((subject, MIBO.hasStatus, Literal(str(symbol_obj.status))))
        elif isinstance(symbol_obj, ObjectGroup):
            g.add((subject, RDF.type, MIBO.MibGroup))
            if hasattr(symbol_obj, 'objects'):
                for member_tuple in symbol_obj.objects:
                    member_name = member_tuple[1]
                    if member_name in symbols:
                        g.add((MIBO[member_name], MIBO.isMemberOf, subject))
    return g

# --- PARTE 2: VISUALIZADOR (COM A NOVA LÓGICA DE TOOLTIP) ---
def visualizar_interativo(rdf_graph, descricoes, output_filename):
    nx_graph = nx.DiGraph()
    node_groups = {str(s): str(o) for s, p, o in rdf_graph.triples((None, Namespace("http://purl.org/net/mibo#")["isMemberOf"], None))}
    group_colors = {}
    palette = ["#FF6347", "#4682B4", "#32CD32", "#FFD700", "#6A5ACD", "#BA55D3", "#00FA9A", "#FF4500"]
    default_color = "#CCCCCC"
    all_uris = set(s for s in rdf_graph.subjects() if isinstance(s, URIRef)) | set(o for o in rdf_graph.objects() if isinstance(o, URIRef))
    
    for uri in all_uris:
        node_label = uri.split('#')[-1]
        
        # --- LÓGICA DE CONSTRUÇÃO DO TOOLTIP APRIMORADA ---
        # 1. Pega as informações básicas
        description = descricoes.get(node_label, "Nenhuma descrição disponível.")
        node_type_uri = rdf_graph.value(subject=uri, predicate=RDF.type)
        type_text = node_type_uri.split('#')[-1] if node_type_uri else "Tipo não definido"

        # 2. Busca todos os outros atributos do nó no grafo RDF
        attributes = []
        for p, o in rdf_graph.predicate_objects(subject=uri):
            # Ignora atributos que já tratamos ou não queremos mostrar diretamente
            if p not in [RDF.type, RDFS.comment, Namespace("http://purl.org/net/mibo#")["isMemberOf"]]:
                prop_name = p.split('#')[-1] if '#' in p else p.split('/')[-1]
                obj_value = str(o)
                attributes.append(f"  - {prop_name}: {obj_value}")
        
        attributes_text = "\n\nAtributos:\n" + "\n".join(sorted(attributes)) if attributes else ""

        # 3. Monta o tooltip final e completo
        title = f"Objeto: {node_label}\nTipo: {type_text}\n{attributes_text}\n\nDescrição:\n{description}"
        # --- FIM DA LÓGICA DO TOOLTIP ---

        group_uri = node_groups.get(str(uri))
        color = default_color
        if group_uri:
            if group_uri not in group_colors:
                group_colors[group_uri] = palette[len(group_colors) % len(palette)]
            color = group_colors[group_uri]
        nx_graph.add_node(node_label, title=title, color=color, label=node_label)
        
    for s, p, o in rdf_graph:
        if isinstance(s, URIRef):
            subj_node = s.split('#')[-1]
            obj_node = o.split('#')[-1] if isinstance(o, URIRef) else str(o)
            pred_label = p.split('#')[-1] if '#' in p else p.split('/')[-1]
            if obj_node not in nx_graph:
                nx_graph.add_node(obj_node, title=str(o), color=default_color)
            nx_graph.add_edge(subj_node, obj_node, label=pred_label, font={"size": 10, "align": "top"})

    net = Network(height="800px", width="100%", notebook=False, directed=True, bgcolor="#222222", font_color="white")
    net.set_options("""
    var options = {
      "configure": { "enabled": true, "filter": "physics" },
      "physics": {
        "stabilization": { "iterations": 1000 },
        "forceAtlas2Based": {
          "gravitationalConstant": -15000,
          "centralGravity": 0.1,
          "springLength": 200,
          "damping": 0.3
        }
      }
    }
    """)
    net.from_nx(nx_graph)
    net.save_graph(output_filename)
    print(f"-> Visualização interativa salva em '{output_filename}'!")

# --- PARTE 3: ORQUESTRADOR PRINCIPAL (sem alterações) ---
if __name__ == "__main__":
    mib_directory = "mibs_compilados"
    mibs_para_processar = ['SNMPv2-MIB', 'IF-MIB']
    json_descricoes_file = 'descricoes_consolidadas.json'
    print(f"Carregando descrições do arquivo '{json_descricoes_file}'...")
    try:
        with open(json_descricoes_file, 'r', encoding='utf-8') as f:
            descricoes = json.load(f)
        print(f"-> {len(descricoes)} descrições carregadas.")
    except FileNotFoundError:
        print(f"!! ERRO: Arquivo '{json_descricoes_file}' não encontrado. Execute 'pre_processador_descricoes.py' primeiro.")
        exit()
    print("\nInicializando o MIB Builder...")
    mib_builder = builder.MibBuilder()
    mib_builder.add_mib_sources(builder.DirMibSource(mib_directory))
    for mib_name in mibs_para_processar:
        print(f"\n--- Processando MIB: {mib_name} ---")
        try:
            mib_builder.load_modules(mib_name)
            print(f"-> Módulo '{mib_name}' carregado com sucesso.")
            rdf_graph = mib_para_rdf(mib_builder, mib_name)
            rdf_filename = f"grafo_{mib_name}.ttl"
            rdf_graph.serialize(destination=rdf_filename, format="turtle")
            print(f"-> Grafo RDF salvo em '{rdf_filename}'.")
            html_filename = f"visualizacao_{mib_name}.html"
            visualizar_interativo(rdf_graph, descricoes, html_filename)
        except error.SmiError as e:
            print(f"ERRO: Não foi possível processar o MIB '{mib_name}'. Detalhes: {e}")
    print("\n--- Processo concluído! ---")
