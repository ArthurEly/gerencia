from flask import Flask, jsonify, send_from_directory
import json
import time
import os
import threading
from SPARQLWrapper import SPARQLWrapper, JSON, BASIC

app = Flask(__name__)

# --- CONFIGURAÇÕES ---
FUSEKI_URL = "http://jena-fuseki:3030/rede/query"
PUBLIC_HTML = "/app/public_html" 
JSON_FILE = os.path.join(PUBLIC_HTML, "dados.json")

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
    except Exception as e:
        return {"nodes": [], "edges": []}

    nodes_dict = {}
    edges = []
    
    for row in results:
        uri = row['s']['value']
        nome = row['nome']['value']
        status = row['status']['value']
        gw = row.get('gwIp', {}).get('value')
        
        if uri not in nodes_dict:
            color = '#55ff55' if status == 'UP' else '#ff5555'
            group = 'interface'
            if "RESUMO_REDE" in nome: group = 'resumo'
            
            nodes_dict[uri] = {
                'id': uri, 'label': nome, 'group': group, 
                'color': color, 'status': status, 'metrics': {}
            }

        if 'metricType' in row:
            m_type = row['metricType']['value'] 
            m_val = row.get('metricVal', {}).get('value', '0')
            m_unit = row.get('metricUnit', {}).get('value', '')
            nodes_dict[uri]['metrics'][m_type] = f"{m_val} {m_unit}"

        if gw:
            gw_id = f"http://rede#Gateway_{gw.replace('.', '_')}"
            if gw_id not in nodes_dict:
                nodes_dict[gw_id] = {
                    'id': gw_id, 'label': f"Gateway\n{gw}", 
                    'group': 'gateway', 'level': 0, 'metrics': {}
                }
            
            edge_id = f"{uri}_{gw_id}"
            if not any(e['id'] == edge_id for e in edges):
                edges.append({'id': edge_id, 'from': uri, 'to': gw_id})

    final_nodes = []
    for n in nodes_dict.values():
        if n.get('metrics'):
            metrics_str = "\n".join([f"{k}: {v}" for k, v in n['metrics'].items()])
            n['label'] += f"\n{metrics_str}"
        final_nodes.append(n)

    return {"nodes": final_nodes, "edges": edges}

def loop_escreve_arquivo():
    print(f"--- Iniciando Escritor de Arquivo em {JSON_FILE} ---")
    while True:
        try:
            dados = fetch_data_from_fuseki()
            with open(JSON_FILE, 'w') as f:
                json.dump(dados, f)
        except Exception as e:
            print(f"Erro ao escrever JSON: {e}")
        time.sleep(0.5)

# --- ROTAS FLASK ---
@app.route('/')
def index():
    return send_from_directory(PUBLIC_HTML, 'index.html')

@app.route('/dados.json')
def dados_endpoint():
    try: return send_from_directory(PUBLIC_HTML, 'dados.json')
    except: return jsonify(fetch_data_from_fuseki())

@app.route('/balancear', methods=['POST'])
def balancear():
    with open("/app/balancear.trigger", "w") as f: f.write("GO")
    return jsonify({"status": "Rebalanceamento Solicitado"})

# --- ROTA DE RESET ---
@app.route('/reset', methods=['POST'])
def reset_ids():
    with open("/app/reset_alertas.trigger", "w") as f: f.write("RESET")
    return jsonify({"status": "Alertas Resetados"})

if __name__ == '__main__':
    t = threading.Thread(target=loop_escreve_arquivo)
    t.daemon = True
    t.start()
    print("--- Servidor Web SDN + Escritor JSON Rodando ---")
    app.run(host='0.0.0.0', port=5000, debug=False)