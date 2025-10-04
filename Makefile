# Define o interpretador Python a ser usado a partir do ambiente virtual
PYTHON = venv/bin/python3

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
	@$(PYTHON) pre_processador_descricoes.py
	@$(PYTHON) gerador_de_grafos.py
	@echo ">>> Pipeline concluído com sucesso!"

# --- Alvos de Configuração e Limpeza ---

# Instala as dependências do projeto no ambiente virtual.
install: venv
	@echo ">>> Instalando dependências (com feedback detalhado)..."
	@$(PYTHON) -m pip install --verbose -r requirements.txt

# Executa a compilação das MIBs usando o caminho correto do módulo.
compile-mib: venv
	@echo ">>> Compilando MIBs para o formato PySNMP..."
	@mkdir -p mibs_compilados
	mibdump \
		--destination-format pysnmp \
		--destination-directory mibs_compilados \
		$(MIBS_TO_COMPILE)

# ATUALIZADO: Limpa APENAS os arquivos de saída gerados pelos scripts.
clean:
	@echo ">>> Removendo arquivos de saída (.html, .ttl, .json)..."
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

# Cria o ambiente virtual se ele não existir.
venv:
	test -d venv || python3 -m venv venv

# Declara alvos que não representam arquivos para evitar conflitos.
.PHONY: all run install compile-mib clean uninstall venv