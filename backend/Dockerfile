# Alterado para 3.12 para aceitar f-strings com barra invertida (\)
FROM python:3.12-slim

# Define a pasta de trabalho
WORKDIR /app

# Instala dependências do sistema
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# Copia e instala dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código
COPY . .

# Inicia o painel
CMD ["python", "painel.py"]