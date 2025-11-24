from flask import Flask, jsonify, send_from_directory
import json
import time
import os
from SPARQLWrapper import SPARQLWrapper, JSON, BASIC

app = Flask(__name__)

# --- CONFIGURAÇÕES ---
FUSEKI_URL = "http://jena-fuseki:3030/rede/query"
PUBLIC_HTML = "/app/public_html"

def fetch_data_from_fuseki():
    """Busca dados do Fuseki e converte para formato Vis.js"""
    sparql = SPARQLWrapper(FUSEKI_URL)
    sparql.setHTTPAuth(BASIC)
    sparql.setCredentials("admin", "admin")
    sparql.setReturnFormat(JSON)
    
    sparql.setQuery("""
        PREFIX : <http://rede#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        SELECT ?s ?nome ?status ?gwIp ?metricType ?metricVal ?metricUnit
        WHERE {
            ?s a :InterfaceReal ; :nome ?nome ; :status ?status .
            OPTIONAL { ?s :dependeDe ?gw . ?gw :ip ?gwIp . }
            OPTIONAL { ?s :temMetrica ?m . ?m :tipo ?metricType ; :valor ?metricVal ; :unidade ?metricUnit . }
        }
    """)
    
    try:
        results = sparql.query().convert()["results"]["bindings"]
    except:
        return {"nodes": [], "edges": []}

    nodes_dict = {}
    edges = []
    
    # Processa resultados do SPARQL
    for row in results:
        uri = row['s']['value']
        nome = row['nome']['value']
        status = row['status']['value']
        gw = row.get('gwIp', {}).get('value')
        
        if uri not in nodes_dict:
            # Define cor e grupo
            color = '#55ff55' if status == 'UP' else '#ff5555'
            group = 'interface'
            if "RESUMO_REDE" in nome: group = 'resumo'
            
            label = nome
            # Monta label inicial
            nodes_dict[uri] = {
                'id': uri, 'label': label, 'group': group, 
                'color': color, 'status': status, 'metrics': {}
            }

        # Adiciona Métricas ao Label
        if 'metricType' in row:
            m_type = row['metricType']['value'] # Ex: InOctets (UP), OutOctets (DOWN)
            m_val = row.get('metricVal', {}).get('value', '0')
            m_unit = row.get('metricUnit', {}).get('value', '')
            
            # Monta string: "UP: 10" ou "DOWN: 0 [MSG]"
            nodes_dict[uri]['metrics'][m_type] = f"{m_val} {m_unit}"

        # Cria Aresta se tiver Gateway
        if gw:
            gw_id = f"http://rede#Gateway_{gw.replace('.', '_')}"
            if gw_id not in nodes_dict:
                nodes_dict[gw_id] = {
                    'id': gw_id, 'label': f"Gateway\n{gw}", 
                    'group': 'gateway', 'level': 0, 'metrics' : {}
                }
            # Evita duplicar arestas
            edge_id = f"{uri}_{gw_id}"
            if not any(e['id'] == edge_id for e in edges):
                edges.append({'id': edge_id, 'from': uri, 'to': gw_id})

    # Finaliza Labels com Métricas
    final_nodes = []
    for n in nodes_dict.values():
        if n['metrics']:
            # Ex: "UP: 5\nDOWN: 2"
            metrics_str = "\n".join([f"{k}: {v}" for k, v in n['metrics'].items()])
            n['label'] += f"\n{metrics_str}"
        final_nodes.append(n)

    return {"nodes": final_nodes, "edges": edges}

# --- ROTAS DO SERVIDOR ---

@app.route('/')
def index():
    return send_from_directory(PUBLIC_HTML, 'index.html')

@app.route('/dados.json')
def dados():
    # Agora geramos o JSON em tempo real ao pedir, sem delay de escrita em disco!
    return jsonify(fetch_data_from_fuseki())

@app.route('/balancear', methods=['POST'])
def balancear():
    # Cria o arquivo que o coletor.py está vigiando
    with open("/app/balancear.trigger", "w") as f:
        f.write("GO")
    return jsonify({"status": "Comando enviado! Rebalanceando..."})

if __name__ == '__main__':
    print("--- Servidor Web SDN Iniciado na porta 5000 ---")
    # Host 0.0.0.0 permite acesso de fora do container
    app.run(host='0.0.0.0', port=5000, debug=False)