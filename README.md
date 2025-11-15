
# 🌐 Gerador de Grafo de Conhecimento para MIBs SNMP

Por:
Arthur Ferreira Ely 00338434
Laura Becker Ramos 00326890
Ian dos Reis Nodari 00341889

Este projeto implementa um pipeline completo em Python para traduzir módulos **MIB (Management Information Base) do protocolo SNMP** em um **Grafo de Conhecimento RDF (Resource Description Framework)**. A solução utiliza um pré-processador para extração robusta de metadados e um gerador principal que automatiza a criação de grafos de dados e visualizações interativas para cada MIB processada.

A execução do projeto é totalmente automatizada através de um `Makefile`.

Este trabalho foi desenvolvido para a disciplina INF01015 - Gerência e Aplicações em Redes.

## ✨ Funcionalidades Principais

* **Pipeline Automatizado**: Processa múltiplos MIBs em sequência, gerando artefatos de dados e visualizações individuais para cada um.
* **Pré-processamento Robusto**: Utiliza um script dedicado para extrair descrições diretamente dos arquivos-fonte `.my`, garantindo a captura completa dos metadados textuais.
* **Tradução Rica para RDF**: Converte a estrutura hierárquica das MIBs para o formato de grafo RDF/Turtle, capturando OIDs, tipos de dados, status, permissões de acesso e as relações de pertencimento a grupos (`OBJECT-GROUP`).
* **Visualização Interativa Dedicada**: Para cada MIB, gera uma página HTML autônoma com um grafo interativo, onde é possível explorar os nós e suas relações com zoom, arrastar e obter informações detalhadas ao passar o mouse.
* **Tooltips Informativos**: Cada nó na visualização possui um tooltip completo, exibindo o nome do objeto, seu tipo, todos os seus atributos (OID, `MAX-ACCESS`, `STATUS`, etc.) e a descrição completa extraída.
* **Mapeamento Semântico Visual**: Os nós no grafo são coloridos de acordo com o `OBJECT-GROUP` ao qual pertencem, tornando a identificação de módulos e funcionalidades visualmente intuitiva.

## 🏗️ Estrutura do Projeto Final

A arquitetura foi consolidada em um fluxo de dois scripts principais, orquestrados por um `Makefile`.

```

gerencia/
│
├── mibs\_compilados/              \# MIBs compilados em .py (gerado automaticamente)
├── mibs\_originais/               \# MIBs originais em formato .my (entrada para o pré-processador)
│   ├── SNMPv2-MIB.my
│   └── IF-MIB.my
│
├── pre\_processador\_descricoes.py \# Script que lê os .my e gera o JSON de descrições
├── gerador\_de\_grafos.py          \# Script principal que gera os .ttl e os .html
│
├── descricoes\_consolidadas.json  \# Arquivo JSON com as descrições (gerado automaticamente)
│
├── grafo\_SNMPv2-MIB.ttl          \# Saída RDF para o SNMPv2-MIB (gerado automaticamente)
├── visualizacao\_SNMPv2-MIB.html  \# Saída interativa para o SNMPv2-MIB (gerado automaticamente)
│
├── grafo\_IF-MIB.ttl              \# Saída RDF para o IF-MIB (gerado automaticamente)
├── visualizacao\_IF-MIB.html      \# Saída interativa para o IF-MIB (gerado automaticamente)
│
├── Makefile                      \# Arquivo de automação com os comandos do projeto
├── requirements.txt              \# Dependências Python do projeto
└── README.md                     \# Este arquivo

```

---

## 🚀 Como Executar com `Makefile`

O `Makefile` automatiza todo o processo de instalação e execução.

### Pré-requisitos

* Python 3.10+
* Gerenciador de pacotes `pip`
* Ferramenta `make` (padrão em Linux e macOS; pode ser instalada no Windows via WSL ou Chocolatey)

### Fluxo de Execução

**Passo 1: Preparar os Arquivos MIB Originais**

1. Se ainda não o fez, crie uma pasta chamada `mibs_originais` no diretório raiz do projeto.
2. Baixe os arquivos de texto MIB que deseja processar (ex: `SNMPv2-MIB.my` e `IF-MIB.my`) e coloque-os dentro desta pasta.

**Passo 2: Instalar o Ambiente e as Dependências**

Este comando único prepara todo o ambiente do projeto. **Execute-o apenas na primeira vez** ou após um `make uninstall`.

```bash
make install
```

*Isto irá criar um ambiente virtual `venv` e instalar todas as bibliotecas do `requirements.txt`.*

Talvez seja necessário instalar o venv do Python antes.

```
apt install python3.10-venv
```

**Passo 3: Executar o Pipeline Completo**

Este é o comando principal que você usará para gerar todos os artefatos do projeto.

```bash
make run
```

*Isto irá, em sequência: compilar as MIBs, executar o pré-processador para criar o JSON de descrições e, finalmente, executar o gerador principal para criar os arquivos `.ttl` e `.html`.*

**Passo 4: Analisar os Resultados**

Após a execução, sua pasta conterá os arquivos `visualizacao_SNMPv2-MIB.html` e `visualizacao_IF-MIB.html`. Abra-os em qualquer navegador web para explorar os grafos interativos.

### Outros Comandos Úteis do `Makefile`

* **Limpar apenas os arquivos de saída:**

  ```bash
  make clean
  ```

  *Este comando apaga apenas os arquivos `.html`, `.ttl` e `.json` gerados, mas mantém seu ambiente virtual e MIBs compiladas. Ideal para uma nova execução sem reinstalar tudo.*
* **Desinstalar o projeto (limpeza total):**

  ```bash
  make uninstall
  ```

  *Este comando apaga tudo que foi gerado, incluindo o ambiente virtual `venv`, caches e MIBs compiladas. Use-o para retornar o projeto ao seu estado original.*

---

## 🛠️ Tecnologias Utilizadas

* **Linguagem:** Python
* **Automação:** GNU Make
* **Processamento SNMP:** PySNMP, PySMI
* **Grafos de Conhecimento:** RDFlib
* **Análise e Estrutura de Grafos:** NetworkX
* **Visualização Interativa:** Pyvis
* **Extração de Texto:** Módulo `re` (Expressões Regulares)
* **Formato de Dados:** RDF/Turtle, JSON

---

### Justificativa da Escolha das MIBs (SNMPv2-MIB e IF-MIB)

A escolha dos módulos `SNMPv2-MIB` e `IF-MIB` foi estratégica para atender aos requisitos do trabalho e demonstrar a robustez da ferramenta de tradução automatizada. Juntos, eles representam um par ideal que cobre desde os conceitos mais fundamentais até as estruturas de dados mais práticas e complexas do gerenciamento de redes.

#### 1\. SNMPv2-MIB: A Base Fundamental e Universal

Esta MIB foi escolhida por ser a **pedra angular de todo o gerenciamento via SNMP**. Ela serve como uma "meta-MIB", descrevendo o próprio agente SNMP em um dispositivo.

* **Atendimento ao Requisito 1 (Padrão da Internet):** A `SNMPv2-MIB` é definida na **RFC 3418**, um padrão fundamental da IETF. Sua escolha garante a aderência a um padrão de internet universalmente reconhecido.
* **Universalidade:** Praticamente todo dispositivo que suporta SNMP implementa esta MIB. Isso a torna um exemplo perfeito de uma estrutura de dados de gerenciamento onipresente.
* **Informação de "Identidade":** Ela fornece dados essenciais sobre o dispositivo gerenciado, como descrição do sistema (`sysDescr`), tempo de atividade (`sysUpTime`) e contato (`sysContact`). Isso demonstra a capacidade da ferramenta de extrair informações de identidade e estado.
* **Variedade de Dados:** A MIB contém uma gama diversificada de tipos de dados (strings, contadores, identificadores de objeto), o que permitiu testar e validar a capacidade da ferramenta de traduzir diferentes primitivas para o RDF.

#### 2\. IF-MIB: O Exemplo Prático e Estruturalmente Complexo

Se a `SNMPv2-MIB` é a base, a `IF-MIB` é o exemplo **mais comum e prático** de gerenciamento de redes. Ela é usada para monitorar e gerenciar interfaces de rede (portas de switch, interfaces de roteador, etc.).

* **Atendimento ao Requisito 1 (Padrão da Internet):** A `IF-MIB` também é um padrão consolidado da IETF, definido na **RFC 2863**.
* **Representação de Dados Tabulares:** Sua principal característica é a `ifTable`, uma tabela complexa que lista todas as interfaces e suas dezenas de atributos (velocidade, status, erros, octetos de entrada/saída). A tradução de uma estrutura tabular para um grafo é um desafio significativo e demonstra a capacidade da ferramenta em lidar com estruturas de dados complexas, um ponto central do **Requisito 2**.
* **Relevância Operacional:** A `IF-MIB` é utilizada diariamente por administradores de rede para monitoramento de performance e diagnóstico de falhas. Escolhê-la confere ao projeto uma aplicação prática e de alto impacto no mundo real.
* **Demonstração da Semântica Visual:** A `IF-MIB` possui grupos bem definidos. A capacidade da nossa ferramenta de colorir os nós do grafo de acordo com o grupo ao qual pertencem (`ifGeneralInformationGroup`, `ifCounterGroup`, etc.) é perfeitamente demonstrada com esta MIB, tornando a visualização rica e funcional.

Em conjunto, a `SNMPv2-MIB` e a `IF-MIB` formam uma dupla que não só cumpre os requisitos formais do trabalho, mas também permite demonstrar a capacidade da solução em traduzir desde os dados mais básicos e universais até as estruturas tabulares mais complexas e relevantes para o gerenciamento de redes moderno.

```


colocar dps
# Relatório - Etapa 2: Gerenciamento com SPARQL

**Integrantes:**
* Arthur Ferreira Ely (00338434)
* Laura Becker Ramos (00326890)
* Ian dos Reis Nodari (00341889)

## 1. Dependências de Execução

Para que o pipeline `make run` seja executado com sucesso, são necessárias duas dependências de sistema:

### 1.1. Agente SNMP (`snmpd`)

O agente é responsável por *fornecer* os dados.
```bash
sudo apt install snmpd