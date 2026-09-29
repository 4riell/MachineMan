# storage/mesas.py

import sqlite3
from storage import get_db_connection

def garantir_coluna_loja(conn, tabela: str):
    """Função utilitária global para garantir a coluna loja_id."""
    try:
        cur = conn.execute(f"PRAGMA table_info({tabela})")
        colunas = [c[1] for c in cur.fetchall()]
        if "loja_id" not in colunas:
            conn.execute(f"ALTER TABLE {tabela} ADD COLUMN loja_id INTEGER DEFAULT 1")
            conn.commit()
    except Exception as e:
        print(f"Erro ao garantir coluna em {tabela}: {e}")

def listar_mesas_status(loja_id):
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            garantir_coluna_loja(conn, "mesas")
            
            mesas = conn.execute("SELECT * FROM mesas WHERE loja_id = ? ORDER BY numero", (loja_id,)).fetchall()

            resultado = []
            for m in mesas:
                mesa = dict(m)
                pedido = conn.execute(
                    "SELECT id, cliente_nome, valor_total FROM pedidos WHERE mesa_id = ? AND status = 'ABERTO' AND loja_id = ?",
                    (mesa["id"], loja_id),
                ).fetchone()

                if pedido:
                    mesa["status"] = "OCUPADA"
                    total = conn.execute(
                        "SELECT SUM(preco_vendido * quantidade) FROM pedido_outros_itens WHERE pedido_id = ? AND loja_id = ?",
                        (pedido["id"], loja_id),
                    ).fetchone()[0]
                    mesa["total"] = total or 0.0
                else:
                    mesa["status"] = "LIVRE"
                    mesa["total"] = 0.0
                resultado.append(mesa)
            return resultado
    except Exception as e:
        print(f"🔥 ERRO FATAL NO SQL: {e}")
        raise e 

def obter_detalhes_mesa(mesa_id, loja_id):
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        pedido = conn.execute(
            "SELECT * FROM pedidos WHERE mesa_id = ? AND status = 'ABERTO' AND loja_id = ?", 
            (mesa_id, loja_id)
        ).fetchone()

        if not pedido:
            return [], None, ""

        pedido_id = pedido["id"]
        nome_cliente = pedido["cliente_nome"] or ""

        itens = conn.execute(
            "SELECT * FROM pedido_outros_itens WHERE pedido_id = ? AND loja_id = ?", 
            (pedido_id, loja_id)
        ).fetchall()
        return [dict(i) for i in itens], pedido_id, nome_cliente


def atualizar_nome_cliente(mesa_id, nome, loja_id):
    with get_db_connection() as conn:
        pedido = conn.execute(
            "SELECT id FROM pedidos WHERE mesa_id = ? AND status = 'ABERTO' AND loja_id = ?", 
            (mesa_id, loja_id)
        ).fetchone()

        if not pedido:
            if nome and nome.strip():
                conn.execute(
                    """
                    INSERT INTO pedidos (cliente_telefone, status, mesa_id, tipo_entrega, cliente_nome, loja_id) 
                    VALUES ('MESA', 'ABERTO', ?, 'Mesa', ?, ?)
                """,
                    (mesa_id, nome, loja_id),
                )
        else:
            conn.execute(
                "UPDATE pedidos SET cliente_nome = ? WHERE id = ? AND loja_id = ?", 
                (nome, pedido[0], loja_id)
            )

        conn.commit()
    return True


def adicionar_item_mesa_estruturado(mesa_id, item_data, loja_id):
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        pedido = conn.execute(
            "SELECT id FROM pedidos WHERE mesa_id = ? AND status = 'ABERTO' AND loja_id = ?", 
            (mesa_id, loja_id)
        ).fetchone()

        if not pedido:
            cur = conn.execute(
                "INSERT INTO pedidos (cliente_telefone, status, mesa_id, tipo_entrega, cliente_nome, loja_id) VALUES ('MESA', 'ABERTO', ?, 'Mesa', '', ?)",
                (mesa_id, loja_id),
            )
            pedido_id = cur.lastrowid
        else:
            pedido_id = pedido["id"]

        lista_adds = item_data.get("lista_adicionais", [])
        str_adds = ", ".join([a["nome"] for a in lista_adds])

        obs_final = item_data.get("observacao", "")
        var_nome = item_data.get("variacao_nome", "")
        if var_nome and "Tamanho:" not in obs_final:
            obs_final = f"Tamanho: {var_nome}. {obs_final}"

        nome_item = item_data.get("nome", "Item")
        categoria = item_data.get("categoria")

        if categoria not in ["extra", "desconto"]:
            if f"[NM:{nome_item}]" not in obs_final:
                obs_final = f"[NM:{nome_item}] {obs_final}".strip()

        conn.execute(
            """
            INSERT INTO pedido_outros_itens 
            (pedido_id, tipo, produto_id, quantidade, preco_vendido, observacao, adicionais, nome_cache, loja_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                pedido_id,
                categoria,
                item_data.get("produto_id", 0),
                item_data.get("quantidade", 1),
                item_data.get("total_unitario", 0),
                obs_final,
                str_adds,
                nome_item,
                loja_id
            ),
        )
        conn.commit()
    return True


def cancelar_mesa(mesa_id, loja_id):
    with get_db_connection() as conn:
        conn.execute(
            """
            UPDATE pedidos SET status = 'CANCELADO' 
            WHERE mesa_id = ? AND status = 'ABERTO' AND loja_id = ?
        """,
            (mesa_id, loja_id),
        )
        conn.execute(
            "UPDATE mesas SET status = 'LIVRE' WHERE id = ? AND loja_id = ?", 
            (mesa_id, loja_id)
        )
        conn.commit()
    return True


def definir_quantidade_mesas(nova_qtd, loja_id):
    with get_db_connection() as conn:
        atual = conn.execute("SELECT COUNT(*) FROM mesas WHERE loja_id = ?", (loja_id,)).fetchone()[0]
        if nova_qtd > atual:
            for i in range(atual + 1, nova_qtd + 1):
                conn.execute(
                    "INSERT INTO mesas (numero, nome, loja_id) VALUES (?, ?, ?)",
                    (i, f"Mesa {i:02d}", loja_id),
                )
        elif nova_qtd < atual:
            conn.execute("DELETE FROM mesas WHERE numero > ? AND loja_id = ?", (nova_qtd, loja_id))
        conn.commit()
    return True


def remover_item_mesa(item_id, loja_id):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM pedido_outros_itens WHERE id = ? AND loja_id = ?", (item_id, loja_id))
        conn.commit()
    return True


def fechar_mesa(mesa_id, forma_pagamento, valor_total, loja_id):
    with get_db_connection() as conn:
        conn.execute(
            """
            UPDATE pedidos SET status = 'CONCLUIDO', forma_pagamento = ?, valor_total = ?, data_hora = DATETIME('now', 'localtime')
            WHERE mesa_id = ? AND status = 'ABERTO' AND loja_id = ?
        """,
            (forma_pagamento, valor_total, mesa_id, loja_id),
        )
        conn.commit()
    return True


def renomear_mesa(mesa_id, novo_nome, loja_id):
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE mesas SET nome = ? WHERE id = ? AND loja_id = ?", 
            (novo_nome, mesa_id, loja_id)
        )
        conn.commit()
    return True