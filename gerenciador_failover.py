# Salve como: gerenciador_failover.py (V10.4 - Usando ip route)
import sys
import time
import os
import subprocess
from rdflib import Graph, Literal, Namespace
from rdflib.namespace import RDF
from easysnmp import Session, EasySNMPError

# --- Configuração ---
SNMP_TARGET_HOST = '127.0.0.1' 
SNMP_COMMUNITY = 'public'
SNMP_VERSION = 2
POLL_INTERVAL = 3 # Checa o link a cada 3 segundos
MIBO = Namespace("http://purl.org/net/mibo#")

OIDS_PARA_COLETAR = {
    "ipCidrRouteDest": "1.3.6.1.2.1.4.24.4.1.1",
    "ipCidrRouteMask": "1.3.6.1.2.1.4.24.4.1.2",
    "ipCidrRouteNextHop": "1.3.6.1.2.1.4.24.4.1.4",
    "ipCidrRouteIfIndex": "1.3.6.1.2.1.4.24.4.1.5",
    "ipCidrRouteType": "1.3.6.1.2.1.4.24.4.1.6",
    "ipCidrRouteStatus": "1.3.6.1.2.1.4.24.4.1.16"
}
# --- Fim Configuração ---

# --- Configurações do Failover ---
GATEWAY_A_IP = "172.19.0.2"
GATEWAY_B_IP = "172.19.0.3"
# --- Fim Configuração ---

# --- Consulta SPARQL ---
QUERY_DEFAULT_ROUTE = """
PREFIX mibo: <http://purl.org/net/mibo#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT ?idx ?gateway ?ifIndex ?tipo
WHERE {
  ?instanciaDest rdf:type mibo:ipCidrRouteDest ;
                 mibo:hasValue "0.0.0.0" ;
                 mibo:hasIndex ?idx .
  
  ?instanciaHop rdf:type mibo:ipCidrRouteNextHop ;
                mibo:hasValue ?gateway ;
                mibo:hasIndex ?idx .
  
  ?instanciaIf rdf:type mibo:ipCidrRouteIfIndex ;
                 mibo:hasValue ?ifIndex ;
                 mibo:hasIndex ?idx .
  ?instanciaType rdf:type mibo:ipCidrRouteType ;
                 mibo:hasValue ?tipo ;
                 mibo:hasIndex ?idx .
} LIMIT 1
"""
# --- Fim Consultas SPARQL ---

def coletar_dados_eficiente(session):
    g_vivo = Graph()
    g_vivo.bind("mibo", MIBO)
    for col_name, oid_str in OIDS_PARA_COLETAR.items():
        try:
            items_list = session.walk(oid_str)
            col_uri = MIBO[col_name]
            for item in items_list:
                full_oid = item.oid.lstrip('.')
                oid_str_norm = oid_str.lstrip('.')
                instance_index = ""
                if full_oid.startswith(oid_str_norm + '.'):
                    instance_index = full_oid[len(oid_str_norm):].lstrip('.')
                if not instance_index:
                    instance_index = item.oid_index
                if not instance_index:
                    continue
                
                idx_limpo = instance_index.replace('.', '_')
                
                instance_uri = MIBO[f"{col_name}_{idx_limpo}"]
                g_vivo.add((instance_uri, RDF.type, col_uri))
                g_vivo.add((instance_uri, MIBO.hasIndex, Literal(idx_limpo)))
                g_vivo.add((instance_uri, MIBO.hasValue, Literal(item.value)))
        except Exception:
            pass
    return g_vivo

def ping_gateway(ip_alvo):
    """ Tenta pingar o gateway. Retorna True se sucesso, False se falha. """
    cmd = ["ping", "-c", "1", "-W", "2", ip_alvo]
    try:
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False

def main():
    print("[GUARDIÃO-FAILOVER] Processo iniciado.")
    
    try:
        session = Session(
            hostname=SNMP_TARGET_HOST, # 127.0.0.1
            community=SNMP_COMMUNITY, 
            version=SNMP_VERSION,
            timeout=1,
            retries=1,
            use_numeric=True
        )
        print("[GUARDIÃO-FAILOVER] Sessão SNMP (127.0.0.1) criada.")
    except Exception as e:
        print(f"!! ERRO FATAL: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"--- Guardião de Failover iniciado ---")
    print(f"  Monitorando Link Principal: {GATEWAY_A_IP}")
    print(f"  Link de Backup: {GATEWAY_B_IP}")
    print("----------------------------------")
    
    falhas_consecutivas = 0
    link_ativo_atual = GATEWAY_A_IP # O estado começa em A

    while True:
        try:
            # 1. MONITOR (M)
            ip_alvo_teste = ""
            if link_ativo_atual == GATEWAY_A_IP:
                ip_alvo_teste = GATEWAY_A_IP # Pinga o A
            else:
                ip_alvo_teste = GATEWAY_B_IP # Pinga o B

            print(f"\n--- Ciclo {time.strftime('%H:%M:%S')} ---")
            print(f"  [MONITOR] Pingando link ativo ({ip_alvo_teste})...")
            
            if ping_gateway(ip_alvo_teste):
                print(f"  [MONITOR] Sucesso! Link {ip_alvo_teste} está UP.")
                falhas_consecutivas = 0
                
                # Se o link A voltou E estamos no backup...
                if link_ativo_atual == GATEWAY_B_IP and ping_gateway(GATEWAY_A_IP):
                    print("  [PLANO] Link principal (A) voltou! Iniciando failback...")
                    
                    # --- EXECUÇÃO DE FAILBACK ---
                    try:
                        print(f"  [AÇÃO] 1/2: Destruindo rota de backup (via {GATEWAY_B_IP})...")
                        os.system(f"ip route del default via {GATEWAY_B_IP}")
                        
                        print(f"  [AÇÃO] 2/2: Adicionando rota principal (via {GATEWAY_A_IP})...")
                        os.system(f"ip route add default via {GATEWAY_A_IP}")
                        
                        print("  [AÇÃO] FAILBACK CONCLUÍDO! O tráfego está usando o Gateway A.")
                        link_ativo_atual = GATEWAY_A_IP
                    except Exception as e:
                        print(f"  [AÇÃO] !! ERRO no FAILBACK: {e}")
                    # --- FIM EXECUÇÃO ---

            else:
                # O ping falhou
                falhas_consecutivas += 1
                print(f"  [MONITOR] Falha no ping! ({falhas_consecutivas} falha(s) consecutiva(s)).")
                
                # 2. ANALYZE (A)
                if falhas_consecutivas >= 3 and link_ativo_atual == GATEWAY_A_IP:
                    print("  [ALERTA] Link principal (A) está DOWN! (3 falhas seguidas).")
                    print("  [CÉREBRO] Consultando o Grafo de Conhecimento (SPARQL) para achar a rota...")
                    
                    g_vivo = coletar_dados_eficiente(session)
                    results = g_vivo.query(QUERY_DEFAULT_ROUTE)
                    
                    if not results:
                        print("  [ERRO] Não achei a rota padrão (0.0.0.0) no grafo!")
                        time.sleep(POLL_INTERVAL)
                        continue
                        
                    rota_encontrada = list(results)[0]
                    gateway_atual = str(rota_encontrada.gateway)
                    if_index_atual = str(rota_encontrada.ifIndex)

                    print(f"  [CÉREBRO] Grafo reporta: Rota padrão ATUAL usa Gateway {gateway_atual}")

                    # 3. PLAN (P)
                    if gateway_atual == GATEWAY_A_IP:
                        print("  [PLANO] Decisão: Mudar o gateway para o backup (GATEWAY_B).")
                        
                        #
                        # --- 4. EXECUTE (E) - USANDO 'ip route' ---
                        #
                        try:
                            # Passo A: Destruir a rota antiga
                            print(f"  [AÇÃO] 1/2: Destruindo rota antiga (via {GATEWAY_A_IP})...")
                            os.system(f"ip route del default via {GATEWAY_A_IP}")
                            
                            # Passo B: Criar a nova rota
                            print(f"  [AÇÃO] 2/2: Adicionando rota de backup (via {GATEWAY_B_IP})...")
                            os.system(f"ip route add default via {GATEWAY_B_IP}")
                            
                            print("  [AÇÃO] FAILOVER CONCLUÍDO! O tráfego está usando o Gateway B.")
                            link_ativo_atual = GATEWAY_B_IP
                            falhas_consecutivas = 0
                            
                        except Exception as e:
                            print(f"  [AÇÃO] !! ERRO no SET de failover: {e}")
                        # --- FIM DA CORREÇÃO ---
                            
                    else:
                        print(f"  [PLANO] O link principal ({GATEWAY_A_IP}) caiu, mas o gateway atual já é {gateway_atual}. Nada a fazer.")
            
            time.sleep(POLL_INTERVAL)
            
        except KeyboardInterrupt:
            print("\n[GUARDIÃO-FAILOVER] Encerrando...")
            sys.exit(0)
        except Exception as e:
            print(f"!! ERRO INESPERADO no loop: {e}")
            time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()