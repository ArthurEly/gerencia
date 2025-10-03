# 🌐 Gerador de Grafo de Conhecimento para MIBs SNMP

Este projeto implementa um pipeline completo para traduzir módulos **MIB (Management Information Base) do protocolo SNMP** em um **Grafo de Conhecimento RDF (Resource Description Framework)**. Além da tradução, o projeto fornece um conjunto de ferramentas em Python para analisar, consultar e visualizar o grafo gerado, transformando dados de gerenciamento de rede em uma base de conhecimento estruturada e semanticamente rica.

Este trabalho foi desenvolvido para a disciplina INF01015 - Gerência e Aplicações em Redes.

## ✨ Funcionalidades Principais

  * **Tradução Rica de MIBs**: Converte módulos MIB (IF-MIB, SNMPv2-MIB, etc.) para o formato RDF/Turtle.
  * **Extração Detalhada de Dados**: Captura não apenas OIDs e tipos, mas também metadados operacionais como permissões de acesso (`MAX-ACCESS`), status (`current`, `deprecated`) e mapeamentos de valores enumerados (`up(1)`, `down(2)`).
  * **Análise de Métricas**: Calcula e exibe métricas essenciais do grafo, como número de nós e arestas, componentes conectados e os "hubs" de informação mais importantes (centralidade de grau).
  * **Consultas Semânticas**: Permite fazer perguntas complexas ao grafo utilizando a linguagem SPARQL, como "Encontre todos os contadores" ou "Liste os objetos que posso escrever".
  * **Múltiplas Visualizações**:
      * Gera uma **imagem estática** de alta resolução do grafo completo para relatórios e visão geral.
      * Cria uma **visualização interativa em HTML**, onde é possível arrastar nós, dar zoom e explorar as conexões dinamicamente no navegador.

## 📊 Visualizações Geradas

O projeto é capaz de gerar representações visuais complexas do grafo de conhecimento, como a imagem estática abaixo, e um arquivo HTML totalmente interativo.

#### Visualização Estática (`grafo_ifmib.jpg`)

Uma visão geral de todas as entidades e suas interconexões.

#### Visualização Interativa (`grafo_interativo.html`)

Um arquivo HTML que permite explorar o grafo no navegador com zoom, arrastar e destacar nós e conexões, ideal para uma análise detalhada.

-----

## 🏗️ Estrutura do Projeto

```
gerencia/
│
├── mibs_compilados/              # Diretório para os arquivos MIB compilados em .py pela PySMI
│
├── analisar_grafo.py             # Script para calcular e exibir métricas do grafo
├── consultar_grafo.py            # Script com exemplos de consultas SPARQL
├── tradutor_mib_para_rdf.py      # Script principal que traduz MIB para RDF
├── visualizar_grafo_completo.py  # Script que gera a imagem ESTÁTICA do grafo (PNG)
├── visualizar_grafo_interativo.py# Script que gera a página INTERATIVA do grafo (HTML)
│
├── knowledge_graph.ttl           # Arquivo de saída do grafo em formato Turtle
├── grafo_ifmib.png               # Imagem de saída da visualização estática
├── grafo_interativo.html         # Página de saída da visualização interativa
│
├── requirements.txt              # Dependências Python do projeto
└── README.md                     # Este arquivo
```

-----

## 🚀 Como Executar

### Pré-requisitos

  * Python 3.10+
  * Gerenciador de pacotes `pip`

### Instalação

1.  **Clone este repositório** e entre na pasta do projeto.

2.  **Crie e ative um ambiente virtual** (altamente recomendado):

    ```bash
    python3 -m venv venv
    source venv/bin/activate
    # No Windows PowerShell, use: .\venv\Scripts\Activate.ps1
    ```

3.  **Instale as dependências** listadas no `requirements.txt`:

    ```bash
    python3 -m pip install -r requirements.txt
    ```

### Fluxo de Trabalho Completo

Siga os passos na ordem para executar o projeto do início ao fim.

**Passo 1: Compilar as MIBs-Fonte para Python**
Este passo usa a `PySMI` para baixar os módulos MIB e suas dependências, compilando-os para o formato `.py` que o `PySNMP` utiliza.

```bash
# Este comando garante que IF-MIB, SNMPv2-MIB e suas dependências principais sejam baixadas
python3 -m pysmi.apps.mibdump --destination-format pysnmp --destination-directory mibs_compilados IF-MIB SNMPv2-MIB SNMPv2-SMI SNMPv2-TC
```

**Passo 2: Gerar o Grafo de Conhecimento**
Execute o script tradutor para processar os arquivos `.py` e gerar o arquivo `knowledge_graph.ttl`.

```bash
python3 tradutor_mib_para_rdf.py
```

**Passo 3: Consultar o Grafo com SPARQL**
Execute o script de consulta para fazer perguntas ao grafo recém-criado.

```bash
python3 consultar_grafo.py
```

**Passo 4: Analisar as Métricas do Grafo**
Execute o script de análise para obter os "sinais vitais" do seu grafo.

```bash
python3 analisar_grafo.py
```

**Passo 5: Gerar as Visualizações**
Execute os dois scripts de visualização para criar os artefatos visuais.

```bash
# Gera a imagem estática 'grafo_ifmib.png'
python3 visualizar_grafo_completo.py

# Gera a página interativa 'grafo_interativo.html'
python3 visualizar_grafo_interativo.py
```

> Após a execução, abra o arquivo `grafo_interativo.html` em qualquer navegador web para explorar o grafo.

-----

## 🛠️ Tecnologias Utilizadas

  * **Linguagem:** Python
  * **Processamento SNMP:** PySNMP, PySMI
  * **Grafos de Conhecimento:** RDFlib
  * **Análise e Estrutura de Grafos:** NetworkX
  * **Visualização:** Matplotlib, Pyvis
  * **Linguagem de Consulta:** SPARQL
  * **Formato de Dados:** RDF/Turtle