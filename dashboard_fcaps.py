# Salve como: dashboard_fcaps.py (Versão 7.9 - Tabela de Status Completa)
import sys
import time
import multiprocessing as mp
from queue import Empty 
from rdflib import Graph, Literal, Namespace
from rdflib.namespace import RDF
from easysnmp import Session, EasySNMPError
import dearpygui.dearpygui as dpg
from collections import deque 

# --- Configuração (Não muda) ---
SNMP_TARGET_HOST = 'localhost'
SNMP_COMMUNITY = 'public'
SNMP_VERSION = 2
POLL_INTERVAL = 1 
MIBO = Namespace("http://purl.org/net/mibo#")
IF_OIDS_PARA_COLETAR = {
    "ifDescr": "1.3.6.1.2.1.2.2.1.2",
    "ifOperStatus": "1.3.6.1.2.1.2.2.1.8",
    "ifHCInOctets": "1.3.6.1.2.1.31.1.1.1.6",
    "ifHCOutOctets": "1.3.6.1.2.1.31.1.1.1.10"
}
SYSINFO_OIDS_PARA_COLETAR = {
    "sysDescr": "1.3.6.1.2.1.1.1.0",
    "sysUpTime": "1.3.6.1.2.1.1.3.0",
    "sysContact": "1.3.6.1.2.1.1.4.0",
    "sysName": "1.3.6.1.2.1.1.5.0",
    "sysLocation": "1.3.6.1.2.1.1.6.0"
}
OID_IF_ADMIN_STATUS = "1.3.6.1.2.1.2.2.1.7"
OID_SYS_LOCATION = "1.3.6.1.2.1.1.6.0"
INTERFACE_PADRAO = "2" 
MAX_PONTOS_GRAFICO = 50 
SMA_WINDOW = 3 
# --- Fim Configuração ---

# --- Buffers de Dados Globais (Preenchidos pela Fila) ---
dados_para_falhas = []      
stats_interfaces = {}       
historico_grafico = {}      
sysinfo_buffer = {}         
interface_lista_formatada = [] 
combo_foi_populado = False
interface_selecionada_idx = INTERFACE_PADRAO 
global_status_message = "Pronto."
# --- Fim Buffers ---

# --- Consulta SPARQL (Não muda) ---
QUERY_MONITORAMENTO = """
PREFIX mibo: <http://purl.org/net/mibo#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT ?idx ?descricao ?download ?upload ?status
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
  BIND(xsd:integer(?inOctets_raw) AS ?download)
  BIND(xsd:integer(?outOctets_raw) AS ?upload)
  BIND(IF(?status_val = "1", "UP", "DOWN") AS ?status)
}
ORDER BY (xsd:integer(?idx))
"""

# --- Lógica de Coleta (Roda em um PROCESSO separado) ---

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

def processo_coleta_de_dados(output_queue, input_queue):
    """
    Função que roda em loop no PROCESSO FILHO.
    Envia dados para a GUI via 'output_queue'.
    Recebe comandos da GUI via 'input_queue'.
    """
    print("[COLETOR-PROCESS] Processo de coleta iniciado (modo 'spawn').")
    try:
        session = Session(
            hostname=SNMP_TARGET_HOST, 
            community=SNMP_COMMUNITY, 
            version=SNMP_VERSION,
            timeout=1,
            retries=1,
            use_numeric=True
        )
        print("[COLETOR-PROCESS] Sessão SNMP criada com sucesso.")
    except Exception as e:
        print(f"!! ERRO NO PROCESSO: Não foi possível conectar ao SNMP: {e}", file=sys.stderr)
        return

    dados_anteriores = {}
    sma_buffers = {}
    temp_historico_grafico = {}
    tempo_anterior = time.time()
    
    _combo_foi_populado = False # Flag local DO COLETOR
    _status_message = "Pronto." 

    while True:
        # 1. FAZ O TRABALHO DE COLETA (leitura)
        tempo_atual = time.time()
        intervalo_real = tempo_atual - tempo_anterior
        g_vivo, temp_sysinfo = coletar_dados_eficiente(session)
        results = g_vivo.query(QUERY_MONITORAMENTO)
        novos_dados_falha = []; novos_stats_interfaces = {}; novos_lista_dropdown = []

        for row in results:
            idx = str(row.idx); desc = str(row.descricao); status = str(row.status)
            dl_bytes_atuais = int(row.download); ul_bytes_atuais = int(row.upload)
            
            if idx not in dados_anteriores:
                dados_anteriores[idx] = (dl_bytes_atuais, ul_bytes_atuais)
                sma_buffers[idx] = (deque([0.0]*SMA_WINDOW, maxlen=SMA_WINDOW), deque([0.0]*SMA_WINDOW, maxlen=SMA_WINDOW))
                temp_historico_grafico[idx] = (deque([0.0]*MAX_PONTOS_GRAFICO, maxlen=MAX_PONTOS_GRAFICO), 
                                               deque([0.0]*MAX_PONTOS_GRAFICO, maxlen=MAX_PONTOS_GRAFICO))
            
            dl_rate_mibps_inst = 0.0; ul_rate_mibps_inst = 0.0
            if intervalo_real > 0:
                dl_bytes_ant, ul_bytes_ant = dados_anteriores[idx]
                delta_dl = max(0, dl_bytes_atuais - dl_bytes_ant); delta_ul = max(0, ul_bytes_atuais - ul_bytes_ant)
                dl_rate_mibps_inst = (delta_dl / intervalo_real) / (1024 * 1024)
                ul_rate_mibps_inst = (delta_ul / intervalo_real) / (1024 * 1024)

            sma_buffers[idx][0].append(dl_rate_mibps_inst); sma_buffers[idx][1].append(ul_rate_mibps_inst)
            dl_rate_avg = sum(sma_buffers[idx][0]) / SMA_WINDOW; ul_rate_avg = sum(sma_buffers[idx][1]) / SMA_WINDOW
            
            dados_anteriores[idx] = (dl_bytes_atuais, ul_bytes_atuais)
            temp_historico_grafico[idx][0].append(dl_rate_avg); temp_historico_grafico[idx][1].append(ul_rate_avg)

            # ---
            # MUDANÇA 1: Adiciona TODAS as interfaces na lista (não só as DOWN)
            # ---
            novos_dados_falha.append([idx, desc, status])
            # --- FIM DA MUDANÇA ---
            
            novos_stats_interfaces[idx] = {
                "desc": desc, "status": status, 
                "dl_rate": dl_rate_avg, "ul_rate": ul_rate_avg, 
                "dl_total_bytes": dl_bytes_atuais, "ul_total_bytes": ul_bytes_atuais
            }
            if not _combo_foi_populado:
                novos_lista_dropdown.append(f"{idx}: {desc}")
        
        tempo_anterior = tempo_atual
        
        lista_para_envio = None
        if not _combo_foi_populado and novos_lista_dropdown:
            lista_para_envio = novos_lista_dropdown
            _combo_foi_populado = True
        
        # 2. FAZ O TRABALHO DE CONFIGURAÇÃO (escrita)
        try:
            request_to_run = input_queue.get_nowait()
            
            if request_to_run:
                print("\n[COLETOR-PROCESS] Recebeu um pedido da GUI!")
            
            if request_to_run:
                oid, valor, tipo, msg_sucesso = request_to_run
                print(f"[COLETOR-PROCESS] Executando: session.set(oid={oid}, valor={valor}, tipo={tipo})")
                try:
                    if tipo: session.set(oid, valor, tipo)
                    else: session.set(oid, valor)
                    _status_message = msg_sucesso 
                    print(f"[COLETOR-PROCESS] SET executado com SUCESSO.")
                except Exception as e:
                    _status_message = f"Falha no SET: {e}" 
                    print(f"[COLETOR-PROCESS] !! ERRO no SET: {e}")
        except Empty:
            pass 

        # 3. EMPACOTA TUDO e envia para a GUI
        pacote_de_dados = {
            "falhas": novos_dados_falha,
            "stats": novos_stats_interfaces,
            "sysinfo": temp_sysinfo,
            "historico": {idx: (list(dqs[0]), list(dqs[1])) for idx, dqs in temp_historico_grafico.items()},
            "dropdown_list": lista_para_envio,
            "status_msg": _status_message
        }
        output_queue.put(pacote_de_dados)
        
        time.sleep(POLL_INTERVAL)

# --- Lógica da GUI (Processo Principal) ---

def callback_mudou_interface(sender, app_data):
    global interface_selecionada_idx
    idx_selecionado = app_data.split(':')[0]
    interface_selecionada_idx = idx_selecionado

def callback_set_location(sender, app_data, user_data):
    """ Adiciona pedido na fila e ATUALIZA A GUI IMEDIATAMENTE """
    print("\n[GUI-PROCESS] 'callback_set_location' foi clicado!")
    input_queue = user_data 
    nova_location = dpg.get_value("input_location")
    print(f"[GUI-PROCESS] Novo local a ser enviado: {nova_location}")
    msg_sucesso = f"Localização atualizada para: {nova_location}"
    request = (OID_SYS_LOCATION, nova_location, 's', msg_sucesso) 
    input_queue.put(request)
    print("[GUI-PROCESS] Pedido de SET colocado na fila de entrada.")
    dpg.set_value("config_status_text", "Comando SET (sysLocation) na fila...")
    print("[GUI-PROCESS] Status da GUI atualizado para '...na fila...'.\n")

def callback_set_admin_status(sender, app_data, user_data):
    """ Adiciona pedido na fila e ATUALIZA A GUI IMEDIATAMENTE """
    print("\n[GUI-PROCESS] 'callback_set_admin_status' foi clicado!")
    input_queue, valor_set = user_data # (fila, '1' ou '2')
    idx_alvo = interface_selecionada_idx
    oid_completo = f"{OID_IF_ADMIN_STATUS}.{idx_alvo}"
    acao = "Ativando" if valor_set == '1' else "Desativando"
    print(f"[GUI-PROCESS] Enviando pedido para {acao} If {idx_alvo}")
    msg_sucesso = f"Interface Idx {idx_alvo} ({acao}) com sucesso."
    request = (oid_completo, valor_set, 'i', msg_sucesso) # 'i' de inteiro
    input_queue.put(request)
    print("[GUI-PROCESS] Pedido de SET colocado na fila de entrada.")
    dpg.set_value("config_status_text", f"Comando SET ({acao} If {idx_alvo}) na fila...")
    print("[GUI-PROCESS] Status da GUI atualizado para '...na fila...'.\n")
# --- Fim dos Callbacks ---

def main():
    output_queue = mp.Queue() # Coletor -> GUI
    input_queue = mp.Queue()  # GUI -> Coletor
    
    dpg.create_context()
    
    print("[GUI-PROCESS] Iniciando processo filho...")
    p = mp.Process(target=processo_coleta_de_dados, args=(output_queue, input_queue), daemon=True)
    p.start()
    
    dpg.create_viewport(title='Dashboard de Gerenciamento de Rede (INF01015)', width=815, height=980)
    
    # --- Janela 0: Informações do Sistema ---
    with dpg.window(label="Informações do Sistema (SNMPv2-MIB)", width=800, height=140, pos=(0, 0)):
        with dpg.group(horizontal=True):
            dpg.add_text("Descrição:", tag="sysdescr_label"); dpg.add_text("Carregando...", tag="sysdescr_val", wrap=700)
        with dpg.group(horizontal=True):
            dpg.add_text("Tempo Ligado:", tag="sysuptime_label"); dpg.add_text("Carregando...", tag="sysuptime_val")
        with dpg.group(horizontal=True):
            dpg.add_text("Nome:", tag="sysname_label"); dpg.add_text("Carregando...", tag="sysname_val")
        with dpg.group(horizontal=True):
            dpg.add_text("Contato:", tag="syscontact_label"); dpg.add_text("Carregando...", tag="syscontact_val")
        with dpg.group(horizontal=True):
            dpg.add_text("Localização:", tag="syslocation_label"); dpg.add_text("Carregando...", tag="syslocation_val")

    # --- Janela 1: Performance (Monitor + Gráfico) ---
    eixo_x_inicial = list(range(MAX_PONTOS_GRAFICO)); eixo_y_inicial = [0.0] * MAX_PONTOS_GRAFICO
    with dpg.window(label="Operação 1: Monitoramento de Performance (P-FCAPS)", width=800, height=440, pos=(0, 150), tag="window_performance"):
        dpg.add_combo(items=[], tag="combo_interfaces", label="Selecionar Interface", 
                      callback=callback_mudou_interface, width=200)
        dpg.add_separator()
        with dpg.group(horizontal=True):
            with dpg.group():
                dpg.add_text("Taxa Atual (Média Móvel 3s)")
                dpg.add_text("  Recebendo (DL):", tag="label_dl_rate"); dpg.add_text("  Enviando (UL):", tag="label_ul_rate")
            with dpg.group():
                dpg.add_text(" ", tag="header_spacer_rate") 
                dpg.add_text("0.0000 MiB/s", tag="eth0_dl_rate"); dpg.add_text("0.0000 MiB/s", tag="eth0_ul_rate")
            dpg.add_spacer(width=50)
            with dpg.group():
                dpg.add_text("Volume Total (GiB)")
                dpg.add_text("  Total Recebido:", tag="label_dl_total"); dpg.add_text("  Total Enviado:", tag="label_ul_total")
            with dpg.group():
                dpg.add_text(" ", tag="header_spacer_total")
                dpg.add_text("0.00 GiB", tag="eth0_dl_total"); dpg.add_text("0.00 GiB", tag="eth0_ul_total")
        dpg.add_separator()
        with dpg.plot(label="Taxa de Transferência (Média Móvel 3s)", height=-1, width=-1): 
            dpg.add_plot_legend()
            dpg.add_plot_axis(dpg.mvXAxis, label="Últimos 50 segundos")
            y_axis_tag = dpg.add_plot_axis(dpg.mvYAxis, label="MiB/s", tag="eixo_y_grafico")
            dpg.add_line_series(eixo_x_inicial, eixo_y_inicial, label="Download (MiB/s)", tag="grafico_dl", parent=y_axis_tag) 
            dpg.add_line_series(eixo_x_inicial, eixo_y_inicial, label="Upload (MiB/s)", tag="grafico_ul", parent=y_axis_tag)

    # ---
    # MUDANÇA 2: Atualiza a Janela 2 (Títulos e Coluna)
    # ---
    with dpg.window(label="Operação 2: Status Operacional (F-FCAPS)", width=800, height=160, pos=(0, 600), tag="window_falhas"):
        dpg.add_text("Status Operacional de Todas as Interfaces")
        with dpg.table(header_row=True, borders_innerH=True, borders_outerH=True, 
                       borders_innerV=True, borders_outerV=True,
                       tag="tabela_falhas"):
            dpg.add_table_column(label="Idx"); dpg.add_table_column(label="Interface")
            dpg.add_table_column(label="Status Operacional") # <-- Label MUDOU
    # --- FIM DA MUDANÇA ---
            
    # --- Janela 3: Gerenciamento de Configuração ---
    with dpg.window(label="Operação 3: Gerenciamento de Configuração (C-FCAPS)", width=800, height=180, pos=(0, 770)):
        dpg.add_text("Status:", tag="config_status_label")
        dpg.add_text("Pronto.", tag="config_status_text")
        dpg.add_separator()
        dpg.add_text("Mudar sysLocation (Operação Segura)")
        with dpg.group(horizontal=True):
            dpg.add_input_text(tag="input_location", width=300)
            dpg.add_button(label="Aplicar SET", callback=callback_set_location, user_data=input_queue)
        dpg.add_separator()
        dpg.add_text("Mudar ifAdminStatus (Operação Perigosa!)")
        dpg.add_text("A interface selecionada no 'Monitor' (Operação 1) será afetada.")
        with dpg.group(horizontal=True):
            dpg.add_button(label="Ativar Interface (SET 1)", callback=callback_set_admin_status, user_data=(input_queue, '1'))
            dpg.add_button(label="Desativar Interface (SET 2)", callback=callback_set_admin_status, user_data=(input_queue, '2'))
            
    dpg.setup_dearpygui()
    dpg.show_viewport()

    # --- Loop Principal da GUI (Renderização) ---
    global combo_foi_populado, global_status_message, dados_para_falhas, stats_interfaces, historico_grafico, sysinfo_buffer, interface_lista_formatada
    eixo_x_dados = list(range(MAX_PONTOS_GRAFICO))
    
    while dpg.is_dearpygui_running():
        
        try:
            pacote_de_dados = output_queue.get_nowait()
            
            dados_para_falhas = pacote_de_dados["falhas"]
            stats_interfaces = pacote_de_dados["stats"]
            historico_grafico = pacote_de_dados["historico"]
            sysinfo_buffer = pacote_de_dados["sysinfo"]
            global_status_message = pacote_de_dados["status_msg"] 
            
            lista_dropdown_recebida = pacote_de_dados.get("dropdown_list")
            if lista_dropdown_recebida and not combo_foi_populado:
                interface_lista_formatada = lista_dropdown_recebida
                stats_padrao = stats_interfaces.get(INTERFACE_PADRAO, {})
                desc_padrao = stats_padrao.get('desc', 'eth0')
                default_value = f"{INTERFACE_PADRAO}: {desc_padrao}"
                dpg.configure_item("combo_interfaces", items=interface_lista_formatada, default_value=default_value)
                combo_foi_populado = True
        except Empty:
            pass 

        idx_ativo = interface_selecionada_idx
        stats_atuais = stats_interfaces.get(idx_ativo, {})
        hist_dl, hist_ul = historico_grafico.get(idx_ativo, (eixo_y_inicial, eixo_y_inicial))

        # --- Atualiza Janela 0: SysInfo ---
        dpg.set_value("sysdescr_val", sysinfo_buffer.get('sysDescr', '...'))
        dpg.set_value("sysuptime_val", sysinfo_buffer.get('sysUpTime', '...'))
        dpg.set_value("syscontact_val", sysinfo_buffer.get('sysContact', '...'))
        dpg.set_value("sysname_val", sysinfo_buffer.get('sysName', '...'))
        dpg.set_value("syslocation_val", sysinfo_buffer.get('sysLocation', '...'))
        
        # --- Atualiza Janela 1 (Performance) ---
        desc_ativa = stats_atuais.get("desc", "..."); total_dl_gib = stats_atuais.get("dl_total_bytes", 0) / (1024*1024*1024)
        total_ul_gib = stats_atuais.get("ul_total_bytes", 0) / (1024*1024*1024); dl_rate = stats_atuais.get("dl_rate", 0.0)
        ul_rate = stats_atuais.get("ul_rate", 0.0)
        
        dpg.set_value("eth0_dl_rate", f"{dl_rate:.4f} MiB/s"); dpg.set_value("eth0_ul_rate", f"{ul_rate:.4f} MiB/s")
        dpg.set_value("eth0_dl_total", f"{total_dl_gib:.3f} GiB"); dpg.set_value("eth0_ul_total", f"{total_ul_gib:.3f} GiB")
        dpg.configure_item("window_performance", label=f"Operação 1: Monitoramento ({desc_ativa} - Idx {idx_ativo})")

        dpg.set_value("grafico_dl", [eixo_x_dados, hist_dl]); dpg.set_value("grafico_ul", [eixo_x_dados, hist_ul])
        pico_dl = max(hist_dl) if hist_dl else 0.0; pico_ul = max(hist_ul) if hist_ul else 0.0
        pico_geral = max(pico_dl, pico_ul); padding = max(1.0, pico_geral * 0.15) 
        novo_y_max = pico_geral + padding
        dpg.set_axis_limits("eixo_y_grafico", 0.0, novo_y_max)

        # ---
        # MUDANÇA 3: Atualiza a Janela 2 (Tabela de Status)
        # ---
        children = dpg.get_item_children("tabela_falhas", 1)
        for child in children:
            dpg.delete_item(child)
        
        for row in dados_para_falhas: # O buffer agora tem todas as interfaces
            idx, desc, status = row
            # Define a cor baseada no status
            color = (0, 255, 0, 255) if status == "UP" else (255, 0, 0, 255)
            
            with dpg.table_row(parent="tabela_falhas"):
                dpg.add_text(idx, color=color)
                dpg.add_text(desc, color=color)
                dpg.add_text(status, color=color) # Mostra "UP" ou "DOWN"
        # --- FIM DA MUDANÇA ---
        
        # --- Atualiza Janela 3: Config Status ---
        dpg.set_value("config_status_text", global_status_message)

        dpg.render_dearpygui_frame()
    
    print("[GUI-PROCESS] Encerrando... Matando processo filho.")
    p.terminate()
    dpg.destroy_context()

if __name__ == "__main__":
    mp.set_start_method('spawn')
    mp.freeze_support() # Para compatibilidade com Windows
    main()