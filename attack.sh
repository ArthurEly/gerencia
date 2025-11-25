#!/bin/bash

# --- CONFIGURAÇÕES ---
INTERFACE_ALVO="veth0"
INTERFACE_ATACANTE="peer0"
IP_ALVO="10.99.0.1"
IP_ATACANTE="10.99.0.2"
NAMESPACE="ns_attack"
BANDWIDTH="50M" # Aumente se precisar (ex: 100M)
DURATION="10"   # Segundos de ataque

# --- FUNÇÃO DE LIMPEZA (Rodar ao sair ou erro) ---
cleanup() {
    echo ""
    echo "--- 🧹 Limpeza Automática ---"
    pkill iperf3 2>/dev/null
    
    # Tenta devolver a interface para o namespace principal (PID 1 do container)
    ip netns exec $NAMESPACE ip link set $INTERFACE_ATACANTE netns 1 2>/dev/null
    
    # Remove a sala isolada
    ip netns del $NAMESPACE 2>/dev/null
    
    echo "--- ✅ Ambiente Restaurado ---"
}

# Ativa a limpeza se der Ctrl+C ou o script terminar
trap cleanup EXIT INT TERM

echo "--- 🛠️  Verificando Ferramentas... ---"
if ! command -v iperf3 &> /dev/null; then
    echo "Instalando iperf3 e iproute2..."
    apk add --no-cache iperf3 iproute2 >/dev/null 2>&1
fi

# Garante estado limpo antes de começar
pkill iperf3 2>/dev/null
ip netns del $NAMESPACE 2>/dev/null
ip link set $INTERFACE_ATACANTE netns 1 2>/dev/null 

echo "--- 🛡️  Criando Sala Isolada (Namespace: $NAMESPACE) ---"
ip netns add $NAMESPACE

echo "--- 🔌 Movendo $INTERFACE_ATACANTE para o Isolamento ---"
ip link set $INTERFACE_ATACANTE netns $NAMESPACE

# Configura o 'PC Atacante' (Lado B do cabo)
ip netns exec $NAMESPACE ip link set $INTERFACE_ATACANTE up
ip netns exec $NAMESPACE ip addr add $IP_ATACANTE/24 dev $INTERFACE_ATACANTE

echo "--- 🎯 Preparando o Alvo ($INTERFACE_ALVO) ---"
# Garante que o Router (Lado A do cabo) esteja pronto
ip addr add $IP_ALVO/24 dev $INTERFACE_ALVO 2>/dev/null
ip link set $INTERFACE_ALVO up
ip route add 10.99.0.0/24 dev $INTERFACE_ALVO 2>/dev/null

echo "--- 📡 Iniciando Servidor no Roteador ---"
# Inicia servidor em background
iperf3 -s -B $IP_ALVO --one-off > /dev/null 2>&1 &
PID_SERVER=$!
sleep 2

echo "--- 🚀 DISPARANDO CANHÃO DE TRÁFEGO (UDP $BANDWIDTH) ---"
# O Cliente dispara DE DENTRO do namespace para fora
ip netns exec $NAMESPACE iperf3 -c $IP_ALVO -u -b $BANDWIDTH -t $DURATION

# O script termina aqui e chama a função 'cleanup' automaticamente