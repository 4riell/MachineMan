# storage/clientes.py
from .connection import get_db_connection, execute_with_retry
import logging

def buscar_cliente_completo(telefone):
    with get_db_connection() as conn:
        try:
            row = conn.execute("SELECT * FROM cliente WHERE telefone = ?", (telefone,)).fetchone()
            return dict(row) if row else None
        except Exception as e:
            logging.error(f"Erro ao buscar cliente: {e}")
            return None

def buscar_cliente_por_telefone(telefone):
    c = buscar_cliente_completo(telefone)
    return c["nome"] if c else None

def salvar_cliente_no_banco(telefone, cadastro):
    """Agora suporta QUALQUER coluna adicionada no painel de configurações"""
    with get_db_connection() as conn:
        try:
            # Identifica quais colunas físicas existem na tabela de clientes
            valid_cols = [row[1] for row in conn.execute("PRAGMA table_info(cliente)").fetchall()]
            
            cols_to_insert = ["telefone", "chat_ativo"]
            vals_to_insert = [telefone, 1]
            
            # Adiciona apenas dados que correspondem a colunas válidas no banco
            for k, v in cadastro.items():
                if k in valid_cols and k not in ["telefone", "chat_ativo"]:
                    cols_to_insert.append(k)
                    vals_to_insert.append(v)
                    
            placeholders = ", ".join(["?"] * len(cols_to_insert))
            cols_str = ", ".join(cols_to_insert)
            
            sql = f"INSERT OR REPLACE INTO cliente ({cols_str}) VALUES ({placeholders})"
            
            execute_with_retry(conn.cursor(), sql, tuple(vals_to_insert))
            conn.commit()
        except Exception as e:
            logging.error(f"Erro ao salvar cliente dinâmico: {e}")

def get_endereco_formatado(telefone):
    c = buscar_cliente_completo(telefone)
    if not c or not c.get("rua"):
        return None
    end = f"{c['rua']}"
    if c.get("numero_casa"):
        end += f", {c['numero_casa']}"
    if c.get("bairro"):
        end += f" - {c['bairro']}"
    return end