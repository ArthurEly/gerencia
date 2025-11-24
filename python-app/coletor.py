import time
import docker
from pysnmp.hlapi import *
from rdflib import Graph, Literal, Namespace, RDF, URIRef
import requests
import os
import networkx as nx  # <--- Nova dependência para análise de grafos

# --- CONFIGURAÇÕES ---
SNMP_TARGET = "device-node"
SNMP_PORT = 161
COMMUNITY = "public"
FUSEKI_UPDATE_URL = "http://jena-fuseki:3030/rede/update"
REDE = Namespace("http://rede#")

# HA Gateways
GATEWAY_ALPHA = "172.25.0.101"
GATEWAY_BETA =  "172.25.0.102"
ALLOWED_GATEWAYS = [GATEWAY_ALPHA, GATEWAY_BETA]

try:
    client = docker.from_env()
    router_container = client.containers.get('device-node')
except:
    print("AVISO: Docker não conectado.")
    router_container = None

# --- OIDS ---
OID_IF_DESCR = "1.3.6.1.2.1.2.2.1.2"
OID_IF_OPER  = "1.3.6.1.2.1.2.2.1.8"
OID_ROUTE_DEST = "1.3.6.1.2.1.4.21.1.1"
OID_ROUTE_NEXT_HOP = "1.3.6.1.2.1.4.21.1.7"
OID_ROUTE_IF_INDEX = "1.3.6.1.2.1.4.21.1.2"

# --- FUNÇÕES AUXILIARES ---

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
    """Descobre Gateway baseado no nome (vethX) para Auto-Reparo"""
    try:
        idx = int(if_name.replace("veth", ""))
        if idx % 2 == 0: return GATEWAY_ALPHA
        else: return GATEWAY_BETA
    except: return None

def get_subnet_by_name(if_name):
    try:
        idx = int(if_name.replace("veth", ""))
        return f"50.0.{idx}.0"
    except: return None

def perform_failover(dead_gw, backup_gw, affected_routes, if_names_map):
    if not router_container: return
    print(f"!!! ALERTA: Gateway {dead_gw} CAIU! Movendo rotas...")
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
    """Recria a rota no Linux se a interface voltou mas a rota não"""
    if not router_container: return
    subnet = get_subnet_by_name(if_name)
    if subnet:
        print(f"🔧 AUTO-REPARO: Interface {if_name} voltou. Reconectando a {ideal_gw}...")
        cmd = f"ip route replace {subnet}/24 via {ideal_gw} dev {if_name} onlink"
        try: 
            router_container.exec_run(cmd)
            router_container.exec_run("service snmpd restart")
        except: pass

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

# --- NOVA FUNÇÃO: ANÁLISE TOPOLÓGICA ---
def analisar_inteligencia_topologica(g_rdf, active_gateways):
    G = nx.Graph()
    for s, p, o in g_rdf:
        s_name = str(s).split('#')[-1]
        o_name = str(o).split('#')[-1]
        if "InterfaceReal" in str(o) and str(p) == str(RDF.type):
             G.add_node(s_name, type="interface")
        if "dependeDe" in str(p):
            G.add_edge(s_name, o_name)
            G.add_node(o_name, type="gateway")

    # Diagnóstico 1: Componentes Conexos
    num_componentes = nx.number_connected_components(G)
    num_gateways = len(active_gateways)
    orphan_nodes = []
    if num_componentes > max(1, num_gateways): 
        for component in nx.connected_components(G):
            has_gateway = any("Gateway" in node for node in component)
            if not has_gateway:
                orphan_nodes.extend(list(component))

    # Diagnóstico 2: Balanceamento
    load_distribution = {}
    for gw_ip in active_gateways:
        gw_node_name = f"Gateway_{gw_ip.replace('.', '_')}"
        if G.has_node(gw_node_name):
            load_distribution[gw_node_name] = G.degree(gw_node_name)
        else:
            load_distribution[gw_node_name] = 0

    status = "OK"
    msg = []
    if orphan_nodes:
        status = "CRÍTICO"
        msg.append(f"ISOLAMENTO: {len(orphan_nodes)} interfaces desconectadas")
    
    if len(load_distribution) >= 2:
        loads = list(load_distribution.values())
        if (max(loads) - min(loads)) > 2:
             if status != "CRÍTICO": status = "ALERTA"
             msg.append(f"DESBALANCEADO: {load_distribution}")

    return {"status": status, "mensagens": msg, "cargas": load_distribution}

# --- LOOP PRINCIPAL ---

def coletar_e_atualizar():
    print("--- Iniciando Ciclo de Gerência ---")
    g = Graph()
    g.bind("rede", REDE)

    descricoes = snmp_walk(OID_IF_DESCR) 
    oper_status = snmp_walk(OID_IF_OPER)
    rotas_next_hop = snmp_walk(OID_ROUTE_NEXT_HOP)
    rotas_if_index = snmp_walk(OID_ROUTE_IF_INDEX)

    alpha_alive = check_ping(GATEWAY_ALPHA)
    beta_alive = check_ping(GATEWAY_BETA)
    blackout_total = (not alpha_alive) and (not beta_alive)

    routes_by_gw = {GATEWAY_ALPHA: [], GATEWAY_BETA: []}
    interface_gateway_map = {}

    for route_dest, next_hop in rotas_next_hop.items():
        next_hop = next_hop.replace("'", "").strip()
        if next_hop != "0.0.0.0":
            if_idx = rotas_if_index.get(route_dest)
            if if_idx:
                interface_gateway_map[str(if_idx)] = next_hop
                if next_hop in routes_by_gw:
                    routes_by_gw[next_hop].append((route_dest, if_idx))

    # HA Logic
    if not blackout_total:
        if not alpha_alive:
            if len(routes_by_gw[GATEWAY_ALPHA]) > 0:
                perform_failover(GATEWAY_ALPHA, GATEWAY_BETA, routes_by_gw[GATEWAY_ALPHA], descricoes)
                if router_container: router_container.exec_run("service snmpd restart")
        else:
            routes_to_recover = [r for r in routes_by_gw[GATEWAY_BETA] if get_ideal_gateway_by_route(r[0]) == GATEWAY_ALPHA]
            if routes_to_recover:
                perform_failback(GATEWAY_ALPHA, routes_to_recover, descricoes)
                if router_container: router_container.exec_run("service snmpd restart")

        if not beta_alive:
            if len(routes_by_gw[GATEWAY_BETA]) > 0:
                perform_failover(GATEWAY_BETA, GATEWAY_ALPHA, routes_by_gw[GATEWAY_BETA], descricoes)
                if router_container: router_container.exec_run("service snmpd restart")
        else:
            routes_to_recover = [r for r in routes_by_gw[GATEWAY_ALPHA] if get_ideal_gateway_by_route(r[0]) == GATEWAY_BETA]
            if routes_to_recover:
                perform_failback(GATEWAY_BETA, routes_to_recover, descricoes)
                if router_container: router_container.exec_run("service snmpd restart")

    # Montagem do Grafo
    count_interfaces = 0
    stats_up = 0
    stats_down = 0

    for idx, nome_obj in descricoes.items():
        nome = str(nome_obj)
        if "lo" in nome or "peer" in nome: continue
        if nome == "eth0": continue 
        
        count_interfaces += 1
        uri_interface = URIRef(f"http://rede#Interface_{nome}")
        g.add((uri_interface, RDF.type, REDE.InterfaceReal))
        g.add((uri_interface, REDE.nome, Literal(nome)))
        
        if blackout_total: status_final = "DOWN"
        else: status_final = "UP" if oper_status.get(idx) == '1' else "DOWN"
        
        if status_final == "UP": stats_up += 1
        else: stats_down += 1
            
        g.add((uri_interface, REDE.status, Literal(status_final)))

        # Auto-Reparo + Criação de Arestas
        gw_ip = None
        if status_final == "UP":
            if idx in interface_gateway_map:
                gw_ip = interface_gateway_map[idx]
            else:
                # Interface Verde sem Rota: Auto-Reparo
                ideal_gw = get_ideal_gateway_by_name(nome)
                if ideal_gw:
                    repair_missing_route(nome, ideal_gw)
                    gw_ip = ideal_gw

            if gw_ip and gw_ip in ALLOWED_GATEWAYS:
                uri_gw = URIRef(f"http://rede#Gateway_{gw_ip.replace('.', '_')}")
                g.add((uri_interface, REDE.dependeDe, uri_gw))
                g.add((uri_gw, RDF.type, REDE.Gateway))
                g.add((uri_gw, REDE.ip, Literal(gw_ip)))

    # --- INSERÇÃO DA INTELIGÊNCIA TOPOLÓGICA ---
    active_gws = []
    if alpha_alive: active_gws.append(GATEWAY_ALPHA)
    if beta_alive: active_gws.append(GATEWAY_BETA)
    
    # Roda a análise matemática no grafo gerado
    diagnostico = analisar_inteligencia_topologica(g, active_gws)

    print(f"--- DIAGNÓSTICO ---")
    print(f"Status: {diagnostico['status']}")
    if diagnostico['mensagens']:
        for m in diagnostico['mensagens']: print(f"  -> {m}")
    print(f"Cargas: {diagnostico['cargas']}")

    # Estatísticas Node
    uri_stats = URIRef("http://rede#System_Stats")
    g.add((uri_stats, RDF.type, REDE.InterfaceReal))
    g.add((uri_stats, REDE.nome, Literal("RESUMO_REDE")))
    g.add((uri_stats, REDE.status, Literal("UP"))) 
    
    # Métrica UP (InOctets) - Sem mudanças
    g.add((uri_stats, REDE.temMetrica, URIRef("http://rede#Stat_UP")))
    g.add((URIRef("http://rede#Stat_UP"), REDE.tipo, Literal("InOctets")))
    g.add((URIRef("http://rede#Stat_UP"), REDE.valor, Literal(int(stats_up))))
    g.add((URIRef("http://rede#Stat_UP"), REDE.unidade, Literal("UP")))

    # --- A CORREÇÃO É AQUI ---
    # Prepara o texto da unidade DOWN
    texto_down = "DOWN"
    
    # Se tiver diagnóstico ruim, a gente GRUDA a mensagem aqui dentro
    if diagnostico['status'] != "OK":
        # Limpa caracteres estranhos da lista para ficar bonito
        msg_limpa = str(diagnostico['mensagens']).replace("'", "").replace('"', "")
        texto_down += f" [{diagnostico['status']}: {msg_limpa}]"

    # Métrica DOWN (OutOctets) - Carregando a mensagem de "Cavalo de Troia"
    g.add((uri_stats, REDE.temMetrica, URIRef("http://rede#Stat_DOWN")))
    g.add((URIRef("http://rede#Stat_DOWN"), REDE.tipo, Literal("OutOctets"))) # TEM QUE SER OutOctets
    g.add((URIRef("http://rede#Stat_DOWN"), REDE.valor, Literal(int(stats_down))))
    g.add((URIRef("http://rede#Stat_DOWN"), REDE.unidade, Literal(texto_down))) # <--- MENSAGEM VAI AQUI

    # REMOVA A PARTE DO Stat_Info, POIS O GERENTE.PY NÃO LÊ ELA!
    
    if count_interfaces > 0:
        delete_query = """PREFIX : <http://rede#> DELETE { ?s ?p ?o } WHERE { ?s ?p ?o . { ?s a :InterfaceReal } UNION { ?s a :Metrica } }"""
        try: requests.post(FUSEKI_UPDATE_URL, data={'update': delete_query})
        except: pass
        try: requests.post(FUSEKI_UPDATE_URL, data={'update': f"INSERT DATA {{ {g.serialize(format='nt')} }}"})
        except: pass

def forcar_rebalanceamento_total(descricoes, oper_status):
    """
    Balanceamento Dinâmico (Round-Robin):
    Pega apenas as interfaces UP e distribui alternadamente entre Alpha e Beta.
    Garante 50/50 de carga independente de quais interfaces caíram.
    """
    if not router_container: return
    print("--- ⚖️ BALANCEAMENTO DINÂMICO INICIADO ---")
    
    # 1. Filtra apenas interfaces UP e ordena para ser determinístico
    interfaces_up = []
    for idx, nome_obj in descricoes.items():
        nome = str(nome_obj)
        if "veth" not in nome: continue
        
        estado = oper_status.get(idx, '2')
        if estado == '1': # 1 = UP
            # Guardamos (numero_int, nome) para ordenar corretamente: veth2 antes de veth10
            num = int(nome.replace("veth", ""))
            interfaces_up.append((num, nome))
    
    # Ordena pela numeração (0, 1, 2, 3...)
    interfaces_up.sort()
    
    acoes_agendadas = []
    gateways = [GATEWAY_ALPHA, GATEWAY_BETA]
    
    # 2. Distribuição Round-Robin
    # i=0 -> Alpha, i=1 -> Beta, i=2 -> Alpha...
    for i, (num, nome) in enumerate(interfaces_up):
        
        # A Mágica: O gateway depende da ORDEM na lista, não do ID da interface
        target_gw = gateways[i % 2]
        subnet = f"50.0.{num}.0"
        
        cmd = f"ip route replace {subnet}/24 via {target_gw} dev {nome} onlink"
        
        acoes_agendadas.append({
            'cmd': cmd,
            'iface': nome,
            'gw': target_gw,
            'sub': subnet
        })

    if not acoes_agendadas:
        print("--- Nenhuma interface UP para balancear. ---")
        return

    print(f"--- Redistribuindo {len(acoes_agendadas)} interfaces ativas... ---")
    
    for acao in acoes_agendadas:
        try:
            router_container.exec_run(acao['cmd'])
            
            icone = "A" if acao['gw'] == GATEWAY_ALPHA else "B"
            gw_nome = "Alpha" if acao['gw'] == GATEWAY_ALPHA else "Beta "
            
            print(f"   {icone} [MOVE] {acao['iface']} ({acao['sub']}) -> {gw_nome}")
            
        except Exception as e:
            print(f"   [ERRO] {acao['iface']}: {e}")
        
    try: router_container.exec_run("service snmpd restart")
    except: pass
    
    print(f"--- ⚖️ REBALANCEAMENTO CONCLUÍDO ---")

if __name__ == "__main__":
    print("Aguardando inicialização...")
    time.sleep(10)
    while True:
        try: 
            # 1. Verifica se alguém apertou o botão (Arquivo existe?)
            if os.path.exists("/app/balancear.trigger"):
                print("Botão acionado! Coletando estado atual...")
                
                # Coletamos descrições E status agora
                descricoes_atuais = snmp_walk(OID_IF_DESCR)
                status_atuais = snmp_walk(OID_IF_OPER)
                
                # Passamos os dois para a função
                forcar_rebalanceamento_total(descricoes_atuais, status_atuais)
                
                # Apaga o gatilho
                os.remove("/app/balancear.trigger")
                
            # 2. Roda o ciclo normal
            coletar_e_atualizar()
            
        except Exception as e: 
            print(f"Erro: {e}")
        time.sleep(0.5)