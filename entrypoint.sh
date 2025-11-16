#!/bin/bash

# 1. Inicia o snmpd em background, como root, e silencioso
echo "[ENTRYPOINT] Iniciando snmpd como root..."
/usr/sbin/snmpd -f -Lf /dev/null -C -c /etc/snmp/snmpd.conf &

# 2. Espera 2s para o snmpd iniciar
sleep 2
echo "[ENTRYPOINT] snmpd iniciado. Abrindo shell."
echo "----------------------------------------------"
echo "Você está no container 'vitima'. O snmpd está rodando."
echo "Para a Demo 1 (DDoS), rode: python3 guardiao_ddos.py"
echo "Para a Demo 2 (Failover), rode: python3 gerenciador_failover.py"
echo "----------------------------------------------"

# 3. Executa o comando padrão (CMD), que será /bin/bash
exec "$@"