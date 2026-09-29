# connection.py

import sqlite3
import logging
import os
from .config import DB_PATH


def get_db_connection():
    """
    Cria uma conexão padrão e limpa com o SQLite.
    Usa WAL mode para melhor performance de leitura/escrita simultânea.
    """
    # Garante que a pasta do banco existe
    try:
        db_dir = os.path.dirname(DB_PATH)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
    except Exception as e:
        logging.error(f"Erro ao verificar diretório do banco: {e}")

    # Conecta ao banco
    # check_same_thread=False é necessário para FastAPI/Threads
    # timeout=10.0 faz o SQLite esperar nativamente até 10s se houver lock simples
    conn = sqlite3.connect(DB_PATH, timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    # Configurações Essenciais
    conn.execute("PRAGMA foreign_keys=ON;")  # Garante integridade relacional
    conn.execute(
        "PRAGMA journal_mode=WAL;"
    )  # Write-Ahead Logging (Melhor para concorrência)
    conn.execute(
        "PRAGMA busy_timeout=5000;"
    )  # Espera até 5s em caso de 'database locked'

    return conn


def get_db():
    """Wrapper para injeção de dependência no FastAPI."""
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()


def execute_with_retry(cursor, sql, params=()):
    """
    Mantido para compatibilidade com códigos existentes (ex: clientes.py).
    Como o problema de I/O era externo, agora executamos diretamente.
    O 'timeout' na conexão já resolve locks normais.
    """
    cursor.execute(sql, params)
    return cursor
