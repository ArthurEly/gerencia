FROM python:3.9-slim

WORKDIR /app

# --- CORREÇÃO: Instala o ping ---
RUN apt-get update && \
    apt-get install -y iputils-ping && \
    rm -rf /var/lib/apt/lists/*

# Copia e instala dependências Python
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copia o script
COPY gerente.py .

CMD ["python", "gerente.py"]