#!/bin/bash

echo "--- Criando Interfaces e Rotas Reais ---"

# IPs dos Containers de Gateway (na rede Docker)
GW_ALPHA="172.25.0.101"
GW_BETA="172.25.0.102"

for i in {0..9}
do
    # 1. Cria par veth
    ip link add veth$i type veth peer name peer$i
    ip link set veth$i up
    ip link set peer$i up
    
    # 2. Dá IP interno
    ip addr add 10.99.$i.1/24 dev veth$i
    
    # 3. CRIA ROTA (Com a correção 'onlink')
    if (( $i % 2 == 0 )); then
        # Força a rota via Gateway Alpha na interface veth
        ip route add 50.0.$i.0/24 via $GW_ALPHA dev veth$i onlink
    else
        # Força a rota via Gateway Beta na interface veth
        ip route add 50.0.$i.0/24 via $GW_BETA dev veth$i onlink
    fi

    # 4. Gera tráfego
    ping -f -i 0.1 10.99.$i.1 -I peer$i > /dev/null 2>&1 &
done

echo "--- SNMPD Iniciando ---"
/usr/sbin/snmpd -f -C -c /etc/snmp/snmpd.conf