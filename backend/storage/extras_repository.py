# storage/extras_repository.py

import sqlite3
import logging
from storage import get_db_connection

def buscar_variacoes_por_categoria(categoria):
    """Busca variações de tamanho/tipo para uma categoria."""
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM produto_variacoes WHERE categoria = ? ORDER BY preco",
                (categoria,),
            ).fetchall()
        ]

def buscar_grupos_adicionais_db(chaves, prod_id=None, var_id=None):
    """Busca grupos de adicionais vinculados ao produto/categoria e suas opções."""
    with get_db_connection() as conn:
        ph = ",".join(["?"] * len(chaves))
        query = f"""
            SELECT * FROM grupos_adicionais 
            WHERE categoria_alvo IN ({ph}) 
            AND (
                (produto_alvo_id IS NULL AND variacao_alvo_id IS NULL)
                OR (produto_alvo_id = ?)
                OR (variacao_alvo_id = ?)
            )
            ORDER BY ordem
        """
        params = list(chaves) + [prod_id, var_id]
        rows = conn.execute(query, tuple(params)).fetchall()
        
        grupos = []
        for r in rows:
            g = dict(r)
            ops = conn.execute(
                "SELECT * FROM produto_adicionais WHERE grupo = ? ORDER BY nome",
                (str(g["id"]),),
            ).fetchall()
            g["opcoes"] = [dict(o) for o in ops]
            grupos.append(g)
        return grupos

def buscar_apelidos_adicionais_por_grupo(ids_grupo):
    """Busca apelidos específicos para um grupo de opções de adicionais."""
    if not ids_grupo:
        return []
    
    try:
        with get_db_connection() as conn:
            ph = ",".join(["?"] * len(ids_grupo))
            query = f"SELECT apelido, sabor_produto_id FROM sabor_apelido WHERE categoria='adicional' AND sabor_produto_id IN ({ph})"
            return conn.execute(query, tuple(ids_grupo)).fetchall()
    except Exception as e:
        logging.error(f"Erro ao carregar apelidos do grupo: {e}")
        return []