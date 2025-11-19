from pyvis.network import Network
from SPARQLWrapper import SPARQLWrapper, JSON, BASIC
import time
import os

# --- Configurações ---
FUSEKI_URL = "http://localhost:3030/rede/query"
OUTPUT_FILE = "monitoramento.html"
REFRESH_RATE = 2

# --- IPs e URIs Fixos ---
GW_A_IP = "172.25.0.101"
GW_B_IP = "172.25.0.102"
GW_A_URI = f"Gateway_{GW_A_IP.replace('.', '_')}"
GW_B_URI = f"Gateway_{GW_B_IP.replace('.', '_')}"

# --- Layout (Pixels) ---
X_GW_LEFT = -700   
X_GW_RIGHT = 700   
X_CENTER = 0       
Y_SPACING = 160    

def fetch_data():
    sparql = SPARQLWrapper(FUSEKI_URL)
    sparql.setHTTPAuth(BASIC)
    sparql.setCredentials("admin", "admin")
    sparql.setReturnFormat(JSON)
    
    sparql.setQuery("""
        PREFIX : <http://rede#>
        SELECT ?interface ?nome ?status ?gateway ?metricType ?metricVal ?metricUnit
        WHERE {
            GRAPH ?g {
                ?interface :tipo :InterfaceReal ;
                           :nome ?nome ;
                           :status ?status ;
                           :dependeDe ?gateway .
                OPTIONAL { 
                    ?interface :temMetrica ?m .
                    ?m :tipo ?metricType ; :valor ?metricVal ; :unidade ?metricUnit .
                }
            }
        }
    """)
    try: return sparql.query().convert()["results"]["bindings"]
    except: return []

def get_name(uri): return uri.split('#')[-1]

def format_metric(val, unit):
    try:
        val = int(val)
        if unit == 'bps':
            power = 1000
            labels = {0 : '', 1: 'k', 2: 'M', 3: 'G'}
        else: 
            power = 1024
            labels = {0 : '', 1: 'K', 2: 'M', 3: 'G'}
            
        n = 0
        while val > power:
            val /= power
            n += 1
        return f"{val:.1f} {labels[n]}{unit}"
    except: return f"0 {unit}"

def add_gateway_safe(net, uri, label, x_pos):
    """Adiciona gateway se não existir, ou atualiza se já existir"""
    # Verifica se já existe na lista de nós do Pyvis (acesso interno)
    existing_ids = [n['id'] for n in net.nodes]
    if uri not in existing_ids:
        net.add_node(uri, label=label, color='#ffae00', 
                     size=60, shape='dot', x=x_pos, y=0, 
                     font={'size': 32, 'color': 'white', 'face': 'arial', 'bold': True})

print(f"--- Dashboard Blindado ---")

while True:
    data = fetch_data()
    
    if data:
        net = Network(height='1200px', width='100%', bgcolor='#222222', font_color='white')
        net.toggle_physics(False) 

        # 1. Desenha Gateways Fixos (Garante que eles existem ANTES de tudo)
        label_a = f"Gateway Alpha\n{GW_A_IP}"
        label_b = f"Gateway Beta\n{GW_B_IP}"
        
        add_gateway_safe(net, GW_A_URI, label_a, X_GW_LEFT)
        add_gateway_safe(net, GW_B_URI, label_b, X_GW_RIGHT)

        # 2. Agrupa dados
        interfaces = {}
        for item in data:
            uri = get_name(item['interface']['value'])
            if uri not in interfaces:
                interfaces[uri] = {
                    'nome': item['nome']['value'],
                    'status': item['status']['value'],
                    'gw': get_name(item['gateway']['value']),
                    'metrics': {}
                }
            
            if 'metricType' in item:
                m_type = get_name(item['metricType']['value'])
                m_val = item.get('metricVal', {}).get('value', '0')
                m_unit = item.get('metricUnit', {}).get('value', '')
                interfaces[uri]['metrics'][m_type] = format_metric(m_val, m_unit)

        # Converte e Ordena
        node_list = []
        for uri, info in interfaces.items():
            name = info['nome']
            sort_key = int(name.replace('veth', '')) if 'veth' in name else 99
            
            mets = info['metrics']
            rx = mets.get('InOctets', '-')
            tx = mets.get('OutOctets', '-')
            
            label_final = f"{name}\nRX: {rx}\nTX: {tx}"

            node_list.append({
                'id': uri,
                'label': label_final,
                'status': info['status'],
                'gw_uri': info['gw'],
                'sort_key': sort_key
            })

        node_list.sort(key=lambda x: x['sort_key'])

        # 3. Desenha Interfaces
        total_h = len(node_list) * Y_SPACING
        current_y = -(total_h / 2)

        for item in node_list:
            color = '#55ff55' 
            if item['status'] in ['UNREACHABLE', 'DOWN']: color = '#ff5555' 

            # Adiciona o nó da interface
            net.add_node(item['id'], 
                         label=item['label'], 
                         title=item['status'], 
                         color=color, 
                         size=50,
                         shape='square',
                         x=X_CENTER, 
                         y=current_y, 
                         font={'face': 'monospace', 'align': 'center', 'size': 32, 'color': 'black', 'bold': True})
            
            # --- CORREÇÃO DO CRASH AQUI ---
            # Verifica se o Gateway alvo existe. Se não, cria ele na hora.
            # Isso acontece se o SNMP reportar um IP estranho ou durante transição.
            gw_target = item['gw_uri']
            
            # Verifica se é um dos nossos conhecidos para posicionar certo
            if gw_target == GW_A_URI:
                x_gw = X_GW_LEFT
                lbl_gw = label_a
            elif gw_target == GW_B_URI:
                x_gw = X_GW_RIGHT
                lbl_gw = label_b
            else:
                # Gateway desconhecido/fantasma? Joga pro lado esquerdo por segurança
                x_gw = X_GW_LEFT
                lbl_gw = gw_target
            
            add_gateway_safe(net, gw_target, lbl_gw, x_gw)
            
            # Agora é seguro adicionar a aresta
            net.add_edge(gw_target, item['id'], color='#aaaaaa', width=3)
            
            current_y += Y_SPACING

        # 4. Salva
        net.save_graph(OUTPUT_FILE)
        
        with open(OUTPUT_FILE, "r") as f: html = f.read()
        script = f"<script>setTimeout(()=>window.location.reload(1), {REFRESH_RATE*1000});</script>"
        
        legend = """
        <div style='position:absolute;top:10px;left:10px;background:rgba(255,255,255,0.95);padding:15px;color:black;border-radius:8px;font-family:sans-serif;border:2px solid #444;box-shadow: 0 0 15px rgba(0,0,0,0.8)'>
            <h2 style='margin:0 0 10px 0;border-bottom:2px solid #000;padding-bottom:5px'>Legenda</h2>
            <div style='margin:10px 0;display:flex;align-items:center'>
                <div style='width:30px;height:30px;background:#ffae00;margin-right:15px;border-radius:50%'></div>
                <span style='font-size:20px;font-weight:bold'>Gateway</span>
            </div>
            <div style='margin:10px 0;display:flex;align-items:center'>
                <div style='width:30px;height:30px;background:#00ff00;margin-right:15px;'></div>
                <span style='font-size:20px;font-weight:bold'>Interface OK</span>
            </div>
            <div style='margin:10px 0;display:flex;align-items:center'>
                <div style='width:30px;height:30px;background:#ff0000;margin-right:15px;'></div>
                <span style='font-size:20px;font-weight:bold'>Falha (RCA)</span>
            </div>
        </div>
        """
        html = html.replace("</body>", f"{legend}{script}</body>")
        with open(OUTPUT_FILE, "w") as f: f.write(html)

        print(f"Atualizado: {len(node_list)} interfaces.")
    
    time.sleep(REFRESH_RATE)