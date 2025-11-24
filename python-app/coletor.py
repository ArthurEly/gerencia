import time
import docker
from pysnmp.hlapi import *
from rdflib import Graph, Literal, Namespace, RDF, URIRef
import requests
import os
import networkx as nx

# --- CONFIGURAÇÕES ---
SNMP_TARGET = "device-node"
SNMP_PORT = 161
COMMUNITY = "public"
FUSEKI_UPDATE_URL = "http://jena-fuseki:3030/rede/update"
REDE = Namespace("http://rede#")

# Limites
LIMIT_MB_PER_SEC = 5.0   

# HA Gateways
GATEWAY_ALPHA = "172.25.0.101"
GATEWAY_BETA =  "172.25.0.102"
ALLOWED_GATEWAYS = [GATEWAY_ALPHA, GATEWAY_BETA]

# --- ESTADO GLOBAL ---
traffic_history_in = {}  
traffic_history_out = {}
suspicious_interfaces = set() 

try:
    client = docker.from_env()
    router_container = client.containers.get('device-node')
except:
    print("AVISO: Docker não conectado.")
    router_container = None

# --- OIDS ---
OID_IF_DESCR = "1.3.6.1.2.1.2.2.1.2"
OID_IF_OPER  = "1.3.6.1.2.1.2.2.1.8"
OID_IN_OCTETS = "1.3.6.1.2.1.2.2.1.10"
OID_OUT_OCTETS = "1.3.6.1.2.1.2.2.1.16"
OID_ROUTE_DEST = "1.3.6.1.2.1.4.21.1.1"
OID_ROUTE_NEXT_HOP = "1.3.6.1.2.1.4.21.1.7"
OID_ROUTE_IF_INDEX = "1.3.6.1.2.1.4.21.1.2"

# --- HELPERS ---

def check_ping(host):
    response = os.system(f"ping -c 1 -W 1 {host} > /dev/null 2>&1")
    return response == 0

def get_ideal_gateway_by_route(route_dest):
    try:
        octet = int(route_dest.split('.')[2])
        if octet % 2 == 0: return GATEWAY_ALPHA
        else: return GATEWAY_BETA
    except: return None

def get_ideal_gateway_by_name(if_name):
    try:
        idx = int(if_name.replace("veth", ""))
        if idx % 2 == 0: return GATEWAY_ALPHA
        else: return GATEWAY_BETA
    except: return None

def snmp_walk(oid_base):
    data = {}
    for (errorIndication, errorStatus, errorIndex, varBinds) in nextCmd(
        SnmpEngine(), CommunityData(COMMUNITY), UdpTransportTarget((SNMP_TARGET, SNMP_PORT)),
        ContextData(), ObjectType(ObjectIdentity(oid_base)), lexicographicMode=False
    ):
        if errorIndication or errorStatus: continue
        for varBind in varBinds:
            oid_str = str(varBind[0])
            val = varBind[1]
            if oid_str.startswith(oid_base):
                index = oid_str[len(oid_base)+1:]
                try: data[index] = val.prettyPrint()
                except: data[index] = str(val)
    return data

# --- LÓGICA IDS ---

def calculate_speed(idx, current_octets, history_dict):
    now = time.time()
    current_val = int(current_octets)
    if idx not in history_dict:
        history_dict[idx] = {'val': current_val, 'time': now}
        return 0.0
    prev = history_dict[idx]
    time_diff = now - prev['time']
    val_diff = current_val - prev['val']
    history_dict[idx] = {'val': current_val, 'time': now}
    if time_diff <= 0 or val_diff < 0: return 0.0
    return val_diff / time_diff

def mark_suspicious(if_name, speed_mb):
    if if_name not in suspicious_interfaces:
        print(f"⚠️  IDS ALERTA: {if_name} marcada como anômala ({speed_mb:.2f} MB/s)!")
        suspicious_interfaces.add(if_name)

def reset_all_alerts():
    """
    AÇÃO DE ADMINISTRAÇÃO:
    1. Levanta fisicamente as interfaces afetadas (veth e peer).
    2. Limpa a lista de suspeitos.
    3. Limpa histórico de tráfego.
    """
    if not suspicious_interfaces: return

    print("✅ ADMIN: Resetando alertas e reparando links físicos...")
    
    if router_container:
        for if_name in suspicious_interfaces:
            try:
                # 1. Levanta a Interface (vethX)
                print(f"   🔧 Ligando {if_name}...")
                router_container.exec_run(f"ip link set {if_name} up")
                
                # 2. Levanta o Par (peerX) - O Segredo do Sucesso!
                if "veth" in if_name:
                    peer_name = if_name.replace("veth", "peer")
                    print(f"   🔧 Ligando {peer_name} (o par)...")
                    router_container.exec_run(f"ip link set {peer_name} up")
            except Exception as e:
                print(f"   [ERRO AO REPARAR] {if_name}: {e}")
        
        # Força o SNMP a ver que tudo subiu
        try: router_container.exec_run("service snmpd restart")
        except: pass

    suspicious_interfaces.clear()
    traffic_history_in.clear()
    traffic_history_out.clear()

# --- MANUTENÇÃO ---

def perform_failover(dead_gw, backup_gw, affected_routes, if_names_map):
    if not router_container: return
    print(f"!!! ALERTA: Gateway {dead_gw} CAIU! Failover iniciado...")
    for route_dest, if_idx in affected_routes:
        if_name = if_names_map.get(if_idx, "")
        dev_cmd = f"dev {if_name}" if if_name else ""
        cmd = f"ip route replace {route_dest}/24 via {backup_gw} {dev_cmd} onlink"
        try: router_container.exec_run(cmd)
        except: pass

def perform_failback(target_gw, routes_to_restore, if_names_map):
    if not router_container: return
    print(f"--- BALANCEAMENTO: Restaurando rotas para {target_gw} ---")
    for route_dest, if_idx in routes_to_restore:
        if_name = if_names_map.get(if_idx, "")
        dev_cmd = f"dev {if_name}" if if_name else ""
        cmd = f"ip route replace {route_dest}/24 via {target_gw} {dev_cmd} onlink"
        try: router_container.exec_run(cmd)
        except: pass

def repair_missing_route(if_name, ideal_gw):
    if not router_container: return
    try:
        idx = int(if_name.replace("veth", ""))
        subnet = f"50.0.{idx}.0"
        cmd = f"ip route replace {subnet}/24 via {ideal_gw} dev {if_name} onlink"
        router_container.exec_run(cmd)
    except: pass

def forcar_rebalanceamento_total(descricoes, oper_status):
    if not router_container: return
    print("--- ⚖️ BALANCEAMENTO DINÂMICO ---")
    interfaces_up = []
    for idx, nome_obj in descricoes.items():
        nome = str(nome_obj)
        if "veth" not in nome: continue
        if oper_status.get(idx, '2') == '1': 
            num = int(nome.replace("veth", ""))
            interfaces_up.append((num, nome))
    interfaces_up.sort()
    gws = [GATEWAY_ALPHA, GATEWAY_BETA]
    cmds = []
    for i, (num, nome) in enumerate(interfaces_up):
        target = gws[i % 2]
        cmds.append(f"ip route replace 50.0.{num}.0/24 via {target} dev {nome} onlink")
    for c in cmds:
        try: router_container.exec_run(c)
        except: pass
    try: router_container.exec_run("service snmpd restart")
    except: pass
    print(f"--- REBALANCEADO: {len(cmds)} rotas ---")

def analisar_inteligencia_topologica(g_rdf, active_gateways):
    G = nx.Graph()
    for s, p, o in g_rdf:
        s_name = str(s).split('#')[-1]
        o_name = str(o).split('#')[-1]
        if "InterfaceReal" in str(o) and str(p) == str(RDF.type): G.add_node(s_name, type="interface")
        if "dependeDe" in str(p):
            G.add_edge(s_name, o_name)
            G.add_node(o_name, type="gateway")

    num_comp = nx.number_connected_components(G)
    orphans = []
    if num_comp > max(1, len(active_gateways)): 
        for comp in nx.connected_components(G):
            if not any("Gateway" in n for n in comp): orphans.extend(list(comp))

    load = {}
    for gw in active_gateways:
        n = f"Gateway_{gw.replace('.', '_')}"
        load[n] = G.degree(n) if G.has_node(n) else 0

    status = "OK"
    msg = []
    if orphans:
        status = "CRÍTICO"
        msg.append(f"ISOLAMENTO: {len(orphans)} interfaces.")
    if len(load) >= 2:
        vals = list(load.values())
        if (max(vals) - min(vals)) > 1:
             if status != "CRÍTICO": status = "ALERTA"
             msg.append(f"DESBALANCEADO: {load}")
    return {"status": status, "mensagens": msg, "cargas": load}

# --- LOOP PRINCIPAL ---

def coletar_e_atualizar():
    print("\n--- Iniciando Ciclo ---")
    
    descricoes = snmp_walk(OID_IF_DESCR)
    oper_status = snmp_walk(OID_IF_OPER)
    in_octets = snmp_walk(OID_IN_OCTETS)
    out_octets = snmp_walk(OID_OUT_OCTETS)
    rotas_next_hop = snmp_walk(OID_ROUTE_NEXT_HOP)
    rotas_if_index = snmp_walk(OID_ROUTE_IF_INDEX)

    alpha_alive = check_ping(GATEWAY_ALPHA)
    beta_alive = check_ping(GATEWAY_BETA)
    blackout_total = (not alpha_alive) and (not beta_alive)

    g = Graph()
    g.bind("rede", REDE)

    # 1. Detecção IDS (Marcação Persistente)
    for idx, nome_obj in descricoes.items():
        nome = str(nome_obj)
        if "veth" not in nome: continue

        rx = calculate_speed(idx, in_octets.get(idx, 0), traffic_history_in) / 1048576.0
        tx = calculate_speed(idx, out_octets.get(idx, 0), traffic_history_out) / 1048576.0
        
        if rx > 0.01 or tx > 0.01: print(f"📊 {nome}: RX={rx:.2f} MB/s")

        if (rx > LIMIT_MB_PER_SEC or tx > LIMIT_MB_PER_SEC):
            mark_suspicious(nome, max(rx, tx))

    # 2. Mapeamento
    routes_by_gw = {GATEWAY_ALPHA: [], GATEWAY_BETA: []}
    interface_gateway_map = {}
    for r, nh in rotas_next_hop.items():
        nh = nh.replace("'", "").strip()
        if nh != "0.0.0.0":
            if_idx = rotas_if_index.get(r)
            if if_idx:
                interface_gateway_map[str(if_idx)] = nh
                if nh in routes_by_gw: routes_by_gw[nh].append((r, if_idx))

    # 3. Failover
    if not blackout_total:
        if not alpha_alive and len(routes_by_gw[GATEWAY_ALPHA]) > 0:
            perform_failover(GATEWAY_ALPHA, GATEWAY_BETA, routes_by_gw[GATEWAY_ALPHA], descricoes)
        elif alpha_alive:
            to_recover = [r for r in routes_by_gw[GATEWAY_BETA] if get_ideal_gateway_by_route(r[0]) == GATEWAY_ALPHA]
            if to_recover: perform_failback(GATEWAY_ALPHA, to_recover, descricoes)

        if not beta_alive and len(routes_by_gw[GATEWAY_BETA]) > 0:
            perform_failover(GATEWAY_BETA, GATEWAY_ALPHA, routes_by_gw[GATEWAY_BETA], descricoes)
        elif beta_alive:
            to_recover = [r for r in routes_by_gw[GATEWAY_ALPHA] if get_ideal_gateway_by_route(r[0]) == GATEWAY_BETA]
            if to_recover: perform_failback(GATEWAY_BETA, to_recover, descricoes)

    # 4. Grafo
    count = 0
    s_up = 0
    s_down = 0
    
    for idx, nome_obj in descricoes.items():
        nome = str(nome_obj)
        if "lo" in nome or "peer" in nome or nome == "eth0": continue
        count += 1
        
        uri = URIRef(f"http://rede#Interface_{nome}")
        g.add((uri, RDF.type, REDE.InterfaceReal))
        g.add((uri, REDE.nome, Literal(nome)))
        
        real_stat = oper_status.get(idx, '2')
        
        if blackout_total:
            rdf_status = "DOWN"
        elif nome in suspicious_interfaces:
            rdf_status = "SUSPECT"
        elif real_stat == '1':
            rdf_status = "UP"
        else:
            rdf_status = "DOWN"
        
        if rdf_status in ["UP", "SUSPECT"]: s_up += 1
        else: s_down += 1
        
        g.add((uri, REDE.status, Literal(rdf_status)))

        gw_ip = None
        if rdf_status == "UP": 
            if idx in interface_gateway_map: gw_ip = interface_gateway_map[idx]
            else:
                ideal = get_ideal_gateway_by_name(nome)
                if ideal:
                    repair_missing_route(nome, ideal)
                    gw_ip = ideal

            if gw_ip in ALLOWED_GATEWAYS:
                ugw = URIRef(f"http://rede#Gateway_{gw_ip.replace('.', '_')}")
                g.add((uri, REDE.dependeDe, ugw))
                g.add((ugw, RDF.type, REDE.Gateway))
                g.add((ugw, REDE.ip, Literal(gw_ip)))

    # 5. Stats
    active = []
    if alpha_alive: active.append(GATEWAY_ALPHA)
    if beta_alive: active.append(GATEWAY_BETA)
    diag = analisar_inteligencia_topologica(g, active)

    ustats = URIRef("http://rede#System_Stats")
    g.add((ustats, RDF.type, REDE.InterfaceReal))
    g.add((ustats, REDE.nome, Literal("RESUMO_REDE")))
    g.add((ustats, REDE.status, Literal("UP")))
    
    g.add((ustats, REDE.temMetrica, URIRef("http://rede#Stat_UP")))
    g.add((URIRef("http://rede#Stat_UP"), REDE.tipo, Literal("InOctets")))
    g.add((URIRef("http://rede#Stat_UP"), REDE.valor, Literal(int(s_up))))
    g.add((URIRef("http://rede#Stat_UP"), REDE.unidade, Literal("UP")))

    txt_down = "DOWN"
    if diag['status'] != "OK":
        msg = str(diag['mensagens']).replace("'", "").replace('"', "")
        txt_down += f" [{diag['status']}: {msg}]"
        
    g.add((ustats, REDE.temMetrica, URIRef("http://rede#Stat_DOWN")))
    g.add((URIRef("http://rede#Stat_DOWN"), REDE.tipo, Literal("OutOctets")))
    g.add((URIRef("http://rede#Stat_DOWN"), REDE.valor, Literal(int(s_down))))
    g.add((URIRef("http://rede#Stat_DOWN"), REDE.unidade, Literal(txt_down)))

    if count > 0:
        dq = """PREFIX : <http://rede#> DELETE { ?s ?p ?o } WHERE { ?s ?p ?o . { ?s a :InterfaceReal } UNION { ?s a :Metrica } }"""
        try: requests.post(FUSEKI_UPDATE_URL, data={'update': dq})
        except: pass
        try: requests.post(FUSEKI_UPDATE_URL, data={'update': f"INSERT DATA {{ {g.serialize(format='nt')} }}"})
        except: pass

if __name__ == "__main__":
    print("Aguardando inicialização...")
    time.sleep(10)
    while True:
        try: 
            if os.path.exists("/app/balancear.trigger"):
                print("Botão Balancear acionado!")
                d = snmp_walk(OID_IF_DESCR)
                s = snmp_walk(OID_IF_OPER)
                forcar_rebalanceamento_total(d, s)
                os.remove("/app/balancear.trigger")
            
            if os.path.exists("/app/reset_alertas.trigger"):
                reset_all_alerts()
                os.remove("/app/reset_alertas.trigger")

            coletar_e_atualizar()
        except Exception as e: print(f"Erro: {e}")
        time.sleep(0.5)