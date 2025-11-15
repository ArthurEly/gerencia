PYTHON=python3
VENV=. venv/bin/activate;

# Define as MIBs que serão processadas em todo o projeto
MIBS_TO_COMPILE = IF-MIB SNMPv2-MIB

# --- Alvos Principais e de Conveniência ---

# O alvo 'all' é o padrão (executado ao rodar 'make') e prepara o ambiente.
all: install
	@echo "--------------------------------------------------"
	@echo "Ambiente pronto. Para executar o projeto, use:"
	@echo "make run"
	@echo "--------------------------------------------------"

# Alvo para executar o pipeline completo.
run: venv compile-mib
	@echo ">>> Executando o pipeline principal..."
	@echo "--- ETAPA 1: Pré-processando descrições (.json) ---"
	$(VENV) $(PYTHON) pre_processador_descricoes.py
	@echo "--- ETAPA 1: Gerando grafos de schema (.ttl) e visualizações (.html) ---"
	$(VENV) $(PYTHON) gerador_de_grafos.py
	@echo "--- ETAPA 2: Preenchendo grafos com dados SNMP vivos (_vivo.ttl) ---"
	$(VENV) $(PYTHON) preencher_grafos.py
	@echo ">>> Pipeline concluído com sucesso!"

# --- Alvos de Configuração e Limpeza ---

# Instala as dependências do projeto no ambiente virtual.
install: venv
	@echo ">>> Instalando dependências (com feedback detalhado)..."
	$(VENV) $(PYTHON) -m pip install --verbose -r requirements.txt

# Executa a compilação das MIBs usando o caminho correto do módulo.
compile-mib: venv
	@echo ">>> Compilando MIBs para o formato PySNMP..."
	@mkdir -p mibs_compilados
	$(VENV) ./venv/bin/mibdump \
		--destination-format pysnmp \
		--destination-directory mibs_compilados \
		$(MIBS_TO_COMPILE)

# ATUALIZADO: Limpa APENAS os arquivos de saída gerados pelos scripts.
clean:
	@echo ">>> Removendo arquivos de saída (.html, .ttl, .json)..."
	# Este padrão (com .ttl) já remove os _vivo.ttl também
	rm -f *.html *.ttl *.json
	@echo ">>> Limpeza de saídas concluída."

# NOVO: Desinstala o ambiente, removendo o venv, caches e MIBs compiladas.
uninstall:
	@echo ">>> Removendo ambiente virtual, caches e MIBs compiladas..."
	rm -rf venv
	rm -rf mibs_compilados
	rm -rf __pycache__
	@echo ">>> Desinstalação concluída."

# --- Alvo Auxiliar ---

# Cria o ambiente virtual se ele não existir e garante que o pip exista.
venv:
	if [ ! -f venv ]; then python3 -m venv venv ; fi;

# Declara alvos que não representam arquivos para evitar conflitos.
.PHONY: all run install compile-mib clean uninstall venv

# --- Alvo para SPARQL ---
# Este alvo ainda aponta para o script antigo,
# vamos mantê-lo por enquanto.
query: compile-mib
	$(VENV) $(PYTHON) query_mibs.py