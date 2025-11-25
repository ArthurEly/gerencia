# 🧠 Knowledge-Based SDN Manager

> **Trabalho de Gerência e Aplicação de Redes - Etapa 2**
> *Instituto de Informática - UFRGS*

Este projeto implementa um sistema de **Gerência de Redes Autonômica** baseado em **Grafos de Conhecimento** (*Knowledge Graphs*).

Diferente de sistemas tradicionais que monitoram apenas tabelas estáticas (MIBs), este controlador SDN constrói uma representação semântica da topologia da rede em tempo real. Isso permite diagnósticos complexos, como a detecção de **Desbalanceamento de Carga** e a **Mitigação de Ataques DDoS** com base em comportamento, fechando o ciclo de controle autonômico (MAPE-K).

---

## 🏗️ Arquitetura do Sistema

O sistema utiliza uma arquitetura de microsserviços orquestrada via Docker:

* **`device-node` (Data Plane):** Roteador Linux emulado com `net-snmp` e interfaces virtuais (`veth`).
* **`python-app` (Control Plane):**
    * **Coletor:** Loop de monitoramento (0.5s) que coleta SNMP, calcula derivadas de tráfego e popula o grafo.
    * **Gerente Web:** Servidor Flask que serve a API e o Frontend.
    * **Intelligence:** Módulo `NetworkX` que calcula componentes conexos e centralidade de grau.
* **`jena-fuseki` (Knowledge Base):** Banco de dados RDF Triple Store que armazena o estado da rede.
* **`attacker`:** Container isolado com `iperf3` para injeção de tráfego malicioso.

---

## 🚀 Como Executar

### Pré-requisitos
* Docker e Docker Compose instalados.

### Passo a Passo

1.  **Subir o ambiente:**
    ```bash
    docker-compose up --build
    ```

2.  **Acessar o Dashboard:**
    Abra o navegador em: **`http://localhost:5000`**

---

## 🧪 Cenários de Teste (Proof of Concept)

Utilize os comandos abaixo para reproduzir os resultados apresentados no relatório (FCAPS, Segurança e Desempenho).

### 🟢 Cenário 1: Failover de Gateway (Alta Disponibilidade)
**Objetivo:** Demonstrar que se um Gateway cai, o sistema detecta a falha via SNMP e migra as rotas no Grafo de Conhecimento.

```bash
# 1. Derrube o Gateway Alpha
echo "🔴 Simulando falha no Gateway Alpha..."
docker stop gateway-alpha

# 2. (Observe no Dashboard: As interfaces devem migrar visualmente para o Gateway Beta)

# 3. Verifique a tabela de rotas no roteador (Tudo deve estar via .102)
docker exec device-node ip route show | grep "via"

# 4. Recupere o Gateway
echo "🟢 Recuperando Gateway Alpha..."
docker start gateway-alpha
````

-----

### 🔵 Cenário 2: Balanceamento de Carga (Load Balancing)

**Objetivo:** Demonstrar a capacidade do sistema de identificar assimetria de carga (Centralidade de Grau) e corrigir automaticamente via Engenharia de Tráfego.

1.  **Situação Inicial:** No Dashboard, observe o Gráfico de Pizza. Pode haver desbalanceamento (ex: 70% Alpha, 30% Beta).
2.  **Ação:**
      * No painel lateral, verifique se o status indica **"DESBALANCEADO"** ou **"ALERTA"**.
      * Clique no botão azul **"⚖️ Balancear Cargas"**.
3.  **Resultado Esperado:**
      * O botão mudará para "Processando...".
      * No grafo, você verá as linhas de conexão mudando em tempo real.
      * O gráfico de pizza ficará dividido 50/50.
      * O status mudará para **"OPERACIONAL"**.

-----

### ✂️ Cenário 3: Falha Física de Interface

**Objetivo:** Demonstrar isolamento topológico quando um cabo é desconectado.

```bash
# 1. Corte o cabo da interface veth7
echo "✂️ Cortando cabo da veth7..."
docker exec device-node ip link set veth7 down

# 2. (Observe no Dashboard: Nó veth7 deve virar um Diamante Vermelho Isolado)
#    O painel lateral mostrará "ALERTA: 1 interface isolada"

# 3. Reconecte o cabo (O sistema deve detectar e reconectar no grafo)
echo "🔌 Reconectando cabo da veth7..."
docker exec device-node ip link set veth7 up
```

-----

### 🔴 Cenário 4: Segurança - Ataque DDoS (UDP Flood)

**Objetivo:** Validar o IDS (Intrusion Detection System) que detecta tráfego volumétrico e isola o ofensor visualmente sem perder a conectividade física (apenas marcação semântica).

1.  **Inicie o ataque:** Execute o script de ataque incluído no container `attacker`. Ele cria um namespace isolado para injetar 50Mbps reais.

    ```bash
    echo "🚀 Iniciando ataque DDoS..."
    cat attack.sh | docker exec -i traffic-attacker sh
    ```

2.  **Resultado Imediato (Dashboard):**

      * **Detecção:** O terminal do Python exibirá `👮 POLÍCIA: veth0 estourou banda!`.
      * **Visualização:** O nó `veth0` mudará para um **Diamante Roxo** e perderá a linha de conexão (Isolamento Visual).
      * **Alerta:** Aparecerá uma caixa **"⚠️ Alertas de Segurança"** listando a interface suspeita.

3.  **Recuperação:**

      * Após o ataque parar, clique no botão vermelho **"🛡️ Resetar Alertas"** que aparecerá no painel.
      * O sistema limpará o status de suspeita e a interface voltará a ficar verde e conectada.

-----

### ⚫ Cenário 5: Desastre Total (Blackout)

**Objetivo:** Validar a detecção de partição total da rede.

```bash
# 1. Derrube todos os Gateways
echo "⚫ Simulando Blackout Total..."
docker stop gateway-alpha gateway-beta

# 2. (Observe no Dashboard: Todos os nós interfaces ficam Vermelhos/Diamantes)
#    Status: CRÍTICO

# 3. Restaure a ordem
echo "⚪ Restaurando energia..."
docker start gateway-alpha gateway-beta
```

-----

## 🛠️ Tecnologias Utilizadas

  * **Backend:** Python 3.9, PySNMP, RDFLib, SPARQLWrapper, NetworkX, Flask.
  * **Frontend:** HTML5, Vis.js (Grafos), Chart.js (Métricas).
  * **Infraestrutura:** Docker, Linux Networking (`iproute2`), `iperf3`.

## 📚 Autores

  * Arthur Ferreira Ely
  * Ian dos Reis Nodari
  * Laura Becker Ramos

<!-- end list -->

```