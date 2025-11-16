## Relatório - Etapa 2: Gerenciamento Autônomo com SPARQL

**Integrantes:**

  * Arthur Ferreira Ely (00338434)
  * Laura Becker Ramos (00326890)
  * Ian dos Reis Nodari (00341889)

### 1\. Evolução da Arquitetura (Etapa 1 vs. Etapa 2)

Na Etapa 1, o projeto focou em *traduzir* MIBs para um Grafo de Conhecimento estático (arquivo `.ttl`) e executar consultas de *leitura* (`SPARQL SELECT`).

Para a Etapa 2, que exige **operações de gerenciamento** (escrita/ação), a arquitetura evoluiu para um sistema de gerenciamento autônomo. O `Makefile` e os scripts `preencher_grafos.py` e `gerador_de_grafos.py` ainda são usados para o *setup* inicial de compilação das MIBs e geração dos schemas `.ttl`.

A principal mudança é a introdução de **agentes autônomos** (`guardiao_ddos.py` e `gerenciador_failover.py`). Estes scripts:

1.  **Coletam dados vivos** do agente `snmpd` via `easysnmp`.
2.  **Constroem o Grafo de Conhecimento em memória** a cada ciclo, usando `rdflib`.
3.  **Analisam o grafo** usando consultas `SPARQL` (o "cérebro").
4.  **Tomam decisões** baseadas nas respostas das consultas.
5.  **Executam ações** (as "mãos") para alterar o dispositivo real, cumprindo o requisito de uma operação de gerenciamento baseada no grafo.

Para simular um ambiente de rede realista e resolver problemas de permissão (`genError`), toda a demonstração da Etapa 2 roda em um **laboratório virtual com Docker**.

### 2\. Estrutura de Arquivos (Etapa 2)

Os arquivos centrais para a demonstração da Etapa 2 são:

  * **`Dockerfile.vitima`**: Constrói o container principal que roda o `snmpd` (como `root`) e os scripts de gerenciamento.
  * **`Dockerfile.atacante`**: Constrói um container com `hping3` para a simulação de DDoS.
  * **`Dockerfile.gateway`**: Constrói um container "dummy" (`sleep`) para simular os roteadores A e B.
  * **`entrypoint.sh`**: Script de inicialização do container `vitima` que inicia o `snmpd` corretamente e abre o terminal.
  * **`guardiao_ddos.py`**: **(Demo 1)** Script de gerenciamento autônomo (P/C/F-FCAPS) que detecta picos de tráfego (via SPARQL) e desliga a interface (via `easysnmp.set()`).
  * **`gerenciador_failover.py`**: **(Demo 2)** Script de gerenciamento autônomo (F/C-FCAPS) que detecta falha de link (ping), consulta o grafo (SPARQL) e muda o gateway (via `ip route`).
  * **`requirements.txt`**: Dependências Python para o Docker (`rdflib`, `easysnmp`, `pysnmp`).

-----

## 🚀 Roteiro de Execução (Demonstração da Etapa 2)

Este roteiro documentado permite a execução e avaliação das duas operações de gerenciamento autônomo.

### Pré-requisitos

  * Docker e Docker Compose instalados.

### Passo 1: Limpeza e Build (Terminal 0 - No seu PC)

(Use este terminal para controlar o laboratório)

```bash
# 1. Pare qualquer container antigo
docker stop vitima atacante gateway-a gateway-b

# 2. Limpe imagens e redes antigas
docker rmi vitima atacante gateway
docker network rm lab-rede-snmp lab-rede-failover

# 3. Crie as duas redes virtuais
docker network create lab-rede-snmp
docker network create --subnet=172.19.0.0/24 lab-rede-failover

# 4. Construa as 3 imagens
docker build -t vitima -f Dockerfile.vitima .
docker build -t atacante -f Dockerfile.atacante .
docker build -t gateway -f Dockerfile.gateway .
```

-----

### Demonstração 1: Guardião de DDoS (P/C/F-FCAPS)

Esta demo prova que o "Cérebro" (baseado no Grafo/SPARQL) pode detectar uma **anomalia de Performance** (Pico de DDoS) e executar uma **ação de Configuração** (`easysnmp.set`) para mitigar a **Falha**.

**Passo 1.1: Iniciar Vítima (Terminal 1)**

```bash
docker run --rm -it \
    --name=vitima \
    --hostname=vitima \
    --network=lab-rede-snmp \
    --cap-add=NET_ADMIN \
    --cap-add=NET_RAW \
    vitima
```

  * Dentro do container `root@vitima:/app#`, inicie o guardião (use o python do venv):
    ```bash
    /app/venv/bin/python3 guardiao_ddos.py
    ```
  * **Observe:** O log do Guardião (`Limite: 10.0 MiB/s`) começará a rodar.

**Passo 1.2: Iniciar Atacante (Terminal 2)**

```bash
docker run --rm -it \
    --name=atacante \
    --network=lab-rede-snmp \
    atacante
```

  * Dentro do container `root@atacante:/#`, inicie o ataque (rápido, com pacotes grandes e com logs de resposta):
    ```bash
    hping3 --interval u100 --syn -p 80 -d 1200 vitima
    ```

**Passo 1.3: Observar o Resultado**

1.  **Terminal 2 (Atacante):** Você verá um fluxo de respostas (`RST/ACK`) da `vitima`.
2.  **Terminal 1 (Vítima):** O log detectará o pico (ex: `Pico de 11.4 MiB/s`):
    ```
    [DDOS] Pico de XX.X MiB/s em eth0!
    [AÇÃO] Desligando eth0 (Idx ...) por 30s.
    [AÇÃO] SET(2) executado com SUCESSO.
    ```
3.  **Terminal 2 (Atacante):** No exato momento do `SET`, as respostas **vão parar**. O ataque foi mitigado.
4.  **Terminal 1 (Vítima):** O log mostrará a porta em `(Admin: 2, Oper: DOWN)`.
5.  **(Opcional) Espere 30 segundos:** O log no Terminal 1 mostrará:
    ```
    [INFO] Fim da quarentena de eth0... Reativando...
    [AÇÃO] SET(1) executado com SUCESSO.
    ```
6.  **Terminal 2 (Atacante):** As respostas do `hping3` voltarão.

(Pare os containers com `Ctrl+C` antes de ir para a próxima demo).

-----

### Demonstração 2: Gerenciador de Failover (F/C-FCAPS)

Esta demo prova que o "Cérebro" (SPARQL) pode detectar uma **Falha** (Link A caído) e executar uma **ação de Configuração** (`ip route`) para mudar o gateway, baseando-se no conhecimento lido do grafo.

**Passo 2.1: Iniciar os Gateways (Terminais 2 e 3)**

  * **Terminal 2 (Gateway A - Principal):**
    ```bash
    docker run --rm -it \
        --name=gateway-a \
        --network=lab-rede-failover \
        --ip=172.19.0.2 \
        gateway
    ```
  * **Terminal 3 (Gateway B - Backup):**
    ```bash
    docker run --rm -it \
        --name=gateway-b \
        --network=lab-rede-failover \
        --ip=172.19.0.3 \
        gateway
    ```

**Passo 2.2: Iniciar Vítima (Terminal 1)**

```bash
docker run --rm -it \
    --name=vitima \
    --hostname=vitima \
    --network=lab-rede-failover \
    --ip=172.19.0.100 \
    --cap-add=NET_ADMIN --cap-add=NET_RAW --privileged \
    vitima
```

  * **Dentro do Terminal 1**, configure a rota inicial manualmente (o `entrypoint.sh` nos deu o terminal, mas não configurou a rota):
    ```bash
    # 1. Remove a rota padrão do Docker (via ...0.1)
    root@vitima:/app# ip route del default
    # 2. Adiciona a rota via Gateway A
    root@vitima:/app# ip route add default via 172.19.0.2
    ```
  * **Ainda no Terminal 1**, inicie o guardião:
    ```bash
    root@vitima:/app# /app/venv/bin/python3 gerenciador_failover.py
    ```
  * **Observe:** O log mostrará `[MONITOR] Pingando link ativo (172.19.0.2)...` e `Sucesso! Link principal está UP.`

**Passo 2.3: Simular a Falha (Terminal 4)**

  * Abra um **quarto** terminal (no seu PC) e "mate" o Gateway A:
    ```bash
    docker stop gateway-a
    ```

**Passo 2.4: Observar o Resultado (Terminal 1)**

1.  O log da Vítima mostrará 3 falhas de ping.
2.  **O "Cérebro" é acionado:**
    ```
    [ALERTA] Link principal (A) está DOWN! (3 falhas seguidas).
    [CÉREBRO] Consultando o Grafo de Conhecimento (SPARQL)...
    [CÉREBRO] Grafo reporta: Rota padrão ATUAL usa Gateway 172.19.0.2
    ```
3.  **A "Mão" age:**
    ```
    [PLANO] Decisão: Mudar o gateway para o backup (GATEWAY_B).
    [AÇÃO] 1/2: Destruindo rota antiga (via 172.19.0.2)...
    [AÇÃO] 2/2: Adicionando rota de backup (via 172.19.0.3)...
    [AÇÃO] FAILOVER CONCLUÍDO!
    ```
4.  **A Verificação:** O ciclo seguinte mostrará:
    ```
    [MONITOR] Pingando link ativo (172.19.0.3)...
    [MONITOR] Sucesso! Link 172.19.0.3 está UP.
    ```