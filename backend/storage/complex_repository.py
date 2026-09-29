# storage/complex_repository.py

import sqlite3
import logging
from storage import get_db_connection

def obter_cliente_bairro_taxa(telefone):
    try:
        from storage import get_db_connection
        with get_db_connection() as conn:
            # Busca o bairro do cliente
            cliente = conn.execute("SELECT bairro FROM cliente WHERE telefone = ?", (telefone,)).fetchone()
            if not cliente or not cliente[0]: return None
            
            # Busca a taxa na tabela correta (bairros_entrega)
            bairro_str = cliente[0].strip()
            taxa = conn.execute("SELECT taxa FROM bairros_entrega WHERE nome LIKE ?", (bairro_str,)).fetchone()
            
            if taxa and taxa[0] is not None:
                return float(taxa[0])
    except Exception as e:
        import logging
        logging.error(f"Erro ao buscar taxa do bairro: {e}")
    return None

def obter_menor_preco_variacao_db(categoria):
    """Busca o menor preço entre as variações de uma categoria."""
    try:
        with get_db_connection() as conn:
            rows = conn.execute("SELECT preco FROM produto_variacoes WHERE categoria = ?", (categoria,)).fetchall()
            if rows: return min(r[0] for r in rows)
    except Exception: pass
    return 0.0

def obter_mapa_pizzas_e_apelidos():
    """Retorna todas as pizzas e todos os apelidos de uma só vez para cache em memória."""
    pizzas = []
    apelidos = []
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        pizzas = [dict(r) for r in conn.execute("SELECT id, nome, disponivel FROM pizza").fetchall()]
        apelidos = [dict(r) for r in conn.execute("SELECT apelido, sabor_produto_id FROM sabor_apelido").fetchall()]
    return pizzas, apelidos

def resolver_apelido_geral_db(nome_clean):
    """Busca na tabela sabor_apelido por um termo genérico."""
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            res = conn.execute("SELECT sabor_produto_id, categoria FROM sabor_apelido WHERE apelido = ?", (nome_clean,)).fetchone()
            if res: return res["sabor_produto_id"], res["categoria"]
    except Exception: pass
    return None, None

def obter_produtos_por_tabela(tabela, produto_id=None):
    """Verifica se a tabela existe e retorna todos os produtos (ou 1 específico)."""
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            check_tab = conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{tabela}'").fetchone()
            if not check_tab: return None

            if produto_id:
                res = conn.execute(f'SELECT * FROM "{tabela}" WHERE id = ?', (produto_id,)).fetchone()
                return dict(res) if res else None
            
            rows = conn.execute(f'SELECT * FROM "{tabela}"').fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        logging.error(f"Erro ao buscar na tabela {tabela}: {e}")
        return None