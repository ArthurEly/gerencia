# Salve como: guardiao_headless.py (Versão Headless para Docker)
import sys
import time
from rdflib import Graph, Literal, Namespace
from rdflib.namespace import RDF
from easysnmp import Session, EasySNMPError
from collections import deque 

# --- Configuração ---
# MUITO IMPORTANTE: No Docker, o 'snmpd' roda em localhost (127.0.0.1)
SNMP_TARGET_HOST = '127.0.0.1' 
SNMP_COMMUNITY = 'public'
SNMP_VERSION = 2
POLL_INTERVAL = 1 
MIBO = Namespace("http://purl.org/net/mibo#")
IF_OIDS_PARA_COLETAR = {
    "ifDescr": "1.3.6.1.2.1.2.2.1.2",
    "ifAdminStatus": "1.3.6.1.2.1.2.2.1.7", # Precisa do AdminStatus
    "ifOperStatus": "1.3.6.1.2.1.2.2.1.8",
    "ifHCInOctets": "1.3.6.1.2.1.31.1.1.1.6",
    "ifHCOutOctets": "1.3.6.1.2.1.31.1.1.1.10"
}
SYSINFO_OIDS_PARA_COLETAR = {
    "sysDescr": "1.3.6.1.2.1.1.1.0", "sysUpTime": "1.3.6.1.2.1.1.3.0",
    "sysContact": "1.3.6.1.2.1.1.4.0", "sysName": "1.3.6.1.2.1.1.5.0",
    "sysLocation": "1.3.6.1.2.1.1.6.0"
}
OID_IF_ADMIN_STATUS = "1.3.6.1.2.1.2.2.1.7"
OID_SYS_LOCATION = "1.3.6.1.2.1.1.6.0"
MAX_PONTOS_GRAFICO = 50 
SMA_WINDOW = 3 

# --- Configurações do Guardião de DDoS ---
# ATENÇÃO: Ajuste este limite para disparar o teste!
DDOS_LIMIT_MIBPS = 10.0 # <--- Ajuste para 10.0 MiB/s para o teste
QUARANTINE_SECONDS = 30 
# --- Fim Configuração ---

# --- Consulta SPARQL ---
QUERY_MONITORAMENTO = """
PREFIX mibo: <http://purl.org/net/mibo#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT ?idx ?descricao ?download ?upload ?status ?adminStatus
WHERE {
  ?instanciaDescr rdf:type mibo:ifDescr ;
                  mibo:hasValue ?descricao ;
                  mibo:hasIndex ?idx .
  ?instanciaInHC rdf:type mibo:ifHCInOctets ;
                   mibo:hasValue ?inOctets_raw ;
                   mibo:hasIndex ?idx .
  ?instanciaOutHC rdf:type mibo:ifHCOutOctets ;
                    mibo:hasValue ?outOctets_raw ;
                    mibo:hasIndex ?idx .
  ?instanciaStatus rdf:type mibo:ifOperStatus ;
                     mibo:hasValue ?status_val ;
                     mibo:hasIndex ?idx .
  ?instanciaAdmin rdf:type mibo:ifAdminStatus ;
                     mibo:hasValue ?admin_val ;
                     mibo:hasIndex ?idx .
  
  BIND(xsd:integer(?inOctets_raw) AS ?download)
  BIND(xsd:integer(?outOctets_raw) AS ?upload)
  BIND(IF(?status_val = "1", "UP", "DOWN") AS ?status)
  BIND(?admin_val AS ?adminStatus)
} ORDER BY (xsd:integer(?idx))
"""
# --- Fim Consultas SPARQL ---

def coletar_dados_eficiente(session):
    g_vivo = Graph()
    g_vivo.bind("mibo", MIBO)
    
    for col_name, oid_str in IF_OIDS_PARA_COLETAR.items():
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
                instance_uri = MIBO[f"{col_name}_{instance_index}"]
                g_vivo.add((instance_uri, RDF.type, col_uri))
                g_vivo.add((instance_uri, MIBO.hasIndex, Literal(instance_index)))
                g_vivo.add((instance_uri, MIBO.hasValue, Literal(item.value)))
        except EasySNMPError:
            pass
            
    temp_sysinfo = {}
    for name, oid in SYSINFO_OIDS_PARA_COLETAR.items():
        try:
            item = session.get(oid)
            if item.value is not None and item.value != 'NOSUCHOBJECT':
                temp_sysinfo[name] = item.value
        except EasySNMPError:
            temp_sysinfo[name] = "Erro"
            
    return g_vivo, temp_sysinfo

def main():
    print("[GUARDIÃO-HEADLESS] Processo iniciado.")
    try:
        session = Session(
            hostname=SNMP_TARGET_HOST, # 127.0.0.1
            community=SNMP_COMMUNITY, 
            version=SNMP_VERSION,
            timeout=1,
            retries=1,
            use_numeric=True
        )
        print("[GUARDIÃO-HEADLESS] Sessão SNMP (127.0.0.1) criada.")
    except Exception as e:
        print(f"!! ERRO FATAL: {e}", file=sys.stderr)
        sys.exit(1)

    dados_anteriores = {}
    sma_buffers = {}
    interface_states = {}
    tempo_anterior = time.time()
    
    print(f"--- Guardião de DDoS iniciado ---")
    print(f"  Limite: {DDOS_LIMIT_MIBPS} MiB/s")
    print(f"  Quarentena: {QUARANTINE_SECONDS}s")
    print("----------------------------------")

    while True:
        try:
            # 1. FAZ O TRABALHO DE COLETA (leitura)
            tempo_atual = time.time()
            intervalo_real = tempo_atual - tempo_anterior
            g_vivo, temp_sysinfo = coletar_dados_eficiente(session)
            results = g_vivo.query(QUERY_MONITORAMENTO) # Usa a nova query

            print(f"\n--- Ciclo {time.strftime('%H:%M:%S')} ---")
            
            for row in results:
                idx = str(row.idx); desc = str(row.descricao); status = str(row.status)
                dl_bytes_atuais = int(row.download); ul_bytes_atuais = int(row.upload)
                admin_status = str(row.adminStatus) # '1' (up) ou '2' (down)
                
                if idx not in dados_anteriores:
                    dados_anteriores[idx] = (dl_bytes_atuais, ul_bytes_atuais)
                    sma_buffers[idx] = (deque([0.0]*SMA_WINDOW, maxlen=SMA_WINDOW), deque([0.0]*SMA_WINDOW, maxlen=SMA_WINDOW))
                    interface_states[idx] = {'state': 'MONITORING', 'shutdown_at': 0}
                
                dl_rate_mibps_inst = 0.0; ul_rate_mibps_inst = 0.0
                if intervalo_real > 0:
                    dl_bytes_ant, ul_bytes_ant = dados_anteriores[idx]
                    delta_dl = max(0, dl_bytes_atuais - dl_bytes_ant); delta_ul = max(0, ul_bytes_atuais - ul_bytes_ant)
                    dl_rate_mibps_inst = (delta_dl / intervalo_real) / (1024 * 1024)
                    ul_rate_mibps_inst = (delta_ul / intervalo_real) / (1024 * 1024)

                sma_buffers[idx][0].append(dl_rate_mibps_inst); sma_buffers[idx][1].append(ul_rate_mibps_inst)
                dl_rate_avg = sum(sma_buffers[idx][0]) / SMA_WINDOW; ul_rate_avg = sum(sma_buffers[idx][1]) / SMA_WINDOW
                
                dados_anteriores[idx] = (dl_bytes_atuais, ul_bytes_atuais)
                
                print(f"  IF {idx} ({desc:<15}): {dl_rate_avg:6.2f} MiB/s (Admin: {admin_status}, Oper: {status})")

                # --- O "CÉREBRO" DO GUARDIÃO (Lógica de Gerenciamento Autônomo) ---
                current_state = interface_states[idx]['state']
                
                if current_state == 'MONITORING':
                    # REGRA 1: Se a taxa ultrapassar o limite E a porta estiver ligada...
                    if (dl_rate_mibps_inst > DDOS_LIMIT_MIBPS) and (admin_status == '1'):
                        msg = f"  [DDOS] Pico de {dl_rate_mibps_inst:.1f} MiB/s em {desc}!"
                        print(msg)
                        msg2 = f"  [AÇÃO] Desligando {desc} (Idx {idx}) por {QUARANTINE_SECONDS}s."
                        print(msg2)
                        
                        try:
                            oid_completo = f"{OID_IF_ADMIN_STATUS}.{idx}"
                            session.set(oid_completo, '2', 'i') # SET 2 (down)
                            print("  [AÇÃO] SET(2) executado com SUCESSO.")
                            interface_states[idx]['state'] = 'SHUTDOWN'
                            interface_states[idx]['shutdown_at'] = time.time()
                        except Exception as e:
                            print(f"  [AÇÃO] !! ERRO no SET: {e}")
                        
                elif current_state == 'SHUTDOWN':
                    # REGRA 2: Se a porta está em quarentena e o tempo acabou...
                    shutdown_time = interface_states[idx]['shutdown_at']
                    if (time.time() - shutdown_time) > QUARANTINE_SECONDS:
                        msg = f"  [INFO] Fim da quarentena de {desc} (Idx {idx}). Reativando..."
                        print(msg)
                        
                        try:
                            oid_completo = f"{OID_IF_ADMIN_STATUS}.{idx}"
                            session.set(oid_completo, '1', 'i') # SET 1 (up)
                            print("  [AÇÃO] SET(1) executado com SUCESSO.")
                            interface_states[idx]['state'] = 'MONITORING'
                        except Exception as e:
                            print(f"  [AÇÃO] !! ERRO no SET: {e}")
            
            tempo_anterior = tempo_atual
            time.sleep(POLL_INTERVAL)
            
        except KeyboardInterrupt:
            print("\n[GUARDIÃO-HEADLESS] Encerrando...")
            sys.exit(0)
        except Exception as e:
            print(f"!! ERRO INESPERADO no loop: {e}")
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()