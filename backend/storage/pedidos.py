# storage/pedidos.py

import re
import sqlite3
from .connection import get_db_connection
from storage.configuracoes import obter_todas_categorias_db


def migrar_status_confirmado(usuario_id=None):
    try:
        with get_db_connection() as conn:
            if usuario_id:
                conn.execute(
                    "UPDATE pedidos SET status = 'EM_PREPARO' WHERE status = 'CONFIRMADO' AND usuario_id = ?",
                    (usuario_id,)
                )
            else:
                conn.execute(
                    "UPDATE pedidos SET status = 'EM_PREPARO' WHERE status = 'CONFIRMADO'"
                )
            conn.commit()
    except Exception as e:
        print(f"Erro na migração de status: {e}")


def obter_id_pedido_aberto(telefone, usuario_id=1):
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT id FROM pedidos WHERE cliente_telefone = ? AND status = 'ABERTO' AND usuario_id = ?",
            (telefone, usuario_id),
        ).fetchone()
        return row["id"] if row else None


def abandonar_pedido_aberto(telefone, usuario_id=1):
    pedido_id = obter_id_pedido_aberto(telefone, usuario_id)
    if pedido_id:
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE pedidos SET status = 'ABANDONADO' WHERE id = ? AND usuario_id = ?", 
                (pedido_id, usuario_id)
            )
            conn.commit()
        return True
    return False


def sincronizar_itens_pedido_db(pedido_id, itens, usuario_id=1):
    if not pedido_id:
        return
    with get_db_connection() as conn:
        conn.execute(
            "DELETE FROM pedido_outros_itens WHERE pedido_id = ?", (pedido_id,)
        )
        for item in itens:
            conn.execute(
                """
                INSERT INTO pedido_outros_itens 
                (pedido_id, tipo, produto_id, quantidade, preco_vendido, observacao, adicionais, usuario_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    pedido_id,
                    item.get("tipo", "produto"),
                    item.get("produto_id") or item.get("id"),
                    item.get("quantidade", 1),
                    item.get("preco_vendido") or item.get("preco", 0.0),
                    item.get("observacao", ""),
                    item.get("adicionais", ""),
                    usuario_id
                ),
            )
        conn.commit()


def salvar_pedido_completo_db(telefone, fluxo):
    usuario_id = fluxo.get("usuario_id", 1) # Identifica a loja do bot
    carrinho = fluxo.get("carrinho_atual", [])
    if not carrinho:
        return

    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT id FROM pedidos WHERE cliente_telefone = ? AND status = 'ABERTO' AND usuario_id = ?",
            (telefone, usuario_id),
        ).fetchone()

        tipo_entrega = fluxo.get("pedido_info", {}).get("tipo_entrega")

        if row:
            pedido_id = row["id"]
            if tipo_entrega:
                conn.execute(
                    "UPDATE pedidos SET tipo_entrega = ?, data_hora = datetime('now', 'localtime') WHERE id = ?",
                    (tipo_entrega, pedido_id),
                )
            else:
                conn.execute(
                    "UPDATE pedidos SET data_hora = datetime('now', 'localtime') WHERE id = ?",
                    (pedido_id,),
                )
        else:
            # INSERE O usuario_id NO NOVO PEDIDO
            cursor = conn.execute(
                "INSERT INTO pedidos (cliente_telefone, status, tipo_entrega, data_hora, usuario_id) VALUES (?, 'ABERTO', ?, datetime('now', 'localtime'), ?)",
                (telefone, tipo_entrega, usuario_id),
            )
            pedido_id = cursor.lastrowid

        conn.execute(
            "DELETE FROM pedido_outros_itens WHERE pedido_id = ?", (pedido_id,)
        )

        for item in carrinho:
            produto_id = item.get("id")
            if not produto_id:
                from storage.configuracoes import get_nome_tabela

                tabela = get_nome_tabela(item.get("tipo", "produto"))
                try:
                    p_row = conn.execute(
                        f"SELECT id FROM {tabela} WHERE nome = ?", (item["nome"],)
                    ).fetchone()
                    if p_row:
                        produto_id = p_row["id"]
                except Exception:
                    pass

            obs_save = item.get("observacao", "")
            nome_real = item.get("nome", "")

            if nome_real and f"[NM:{nome_real}]" not in obs_save:
                obs_save = f"[NM:{nome_real}] {obs_save}".strip()

            adicionais_save = item.get("adicionais", "")
            if item.get("tipo") == "pizza" and item.get("borda"):
                if not adicionais_save:
                    adicionais_save = item.get("borda")
                elif item.get("borda") not in adicionais_save:
                    adicionais_save = f"{item.get('borda')}, {adicionais_save}"

            # INSERE O usuario_id NOS ITENS DO PEDIDO
            conn.execute(
                """
                INSERT INTO pedido_outros_itens 
                (pedido_id, tipo, produto_id, quantidade, preco_vendido, observacao, adicionais, usuario_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    pedido_id,
                    item.get("tipo", "extra"),
                    produto_id,
                    item.get("quantidade", 1),
                    item.get("preco", 0.0),
                    obs_save,
                    adicionais_save,
                    usuario_id
                ),
            )
        conn.commit()


def confirmar_pedido_db(telefone, fluxo):
    usuario_id = fluxo.get("usuario_id", 1)
    pedido_id = obter_id_pedido_aberto(telefone, usuario_id)
    if not pedido_id:
        return None

    info = fluxo.get("pedido_info", {})
    taxa = info.get("taxa_entrega", 0.0)

    total = 0.0
    for item in fluxo.get("carrinho_atual", []):
        total += item.get("preco", 0.0) * item.get("quantidade", 1)
    total += taxa

    with get_db_connection() as conn:
        conn.execute(
            """
            UPDATE pedidos 
            SET status = 'EM_PREPARO', 
                valor_total = ?, 
                forma_pagamento = ?, 
                detalhe_pagamento = ?,
                data_hora = datetime('now', 'localtime')
            WHERE id = ?
        """,
            (
                total,
                info.get("forma_pagamento"),
                info.get("detalhe_pagamento"),
                pedido_id,
            ),
        )
        conn.commit()
    return pedido_id


def cancelar_pedido_ativo_e_notificar(telefone, motivo, usuario_id=1):
    pedido_id = obter_id_pedido_aberto(telefone, usuario_id)
    if pedido_id:
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE pedidos SET status = 'CANCELADO' WHERE id = ?", (pedido_id,)
            )
            conn.execute(
                "INSERT INTO notificacoes (tipo, mensagem, cliente_telefone, usuario_id) VALUES ('CANCELAMENTO', ?, ?, ?)",
                (
                    f"Pedido #{pedido_id} cancelado pelo cliente. Motivo: {motivo}",
                    telefone,
                    usuario_id
                ),
            )
            conn.commit()
        return True
    return False


def resumo_carrinho(fluxo):
    carrinho = fluxo.get("carrinho_atual", [])
    if not carrinho:
        return "Seu carrinho está vazio."

    try:
        categorias_db = obter_todas_categorias_db()
        mapa_emojis = {
            c["id"]: (c["emoji"] if c["emoji"] else "📦") for c in categorias_db
        }
    except Exception:
        mapa_emojis = {}

    linhas = []
    total = 0.0

    taxa_entrega = fluxo.get("pedido_info", {}).get("taxa_entrega", 0.0)

    for item in carrinho:
        nome = item.get("nome", "Item")
        qtd = item.get("quantidade", 1)
        preco = item.get("preco", 0.0)
        item_total = preco * qtd
        total += item_total

        tipo_item = item.get("tipo", "produto")
        emoji = mapa_emojis.get(tipo_item, "📦")

        detalhes = []
        adicionais = item.get("adicionais") or item.get("borda")
        if adicionais:
            detalhes.append(f"+ {adicionais}")
        if item.get("observacao"):
            detalhes.append(f"📝 Obs: {item['observacao']}")

        linha = f"{emoji} {qtd}x *{nome}* - R$ {item_total:.2f}"
        if detalhes:
            linha += "\n   " + "\n   ".join(detalhes)
        linhas.append(linha)

    if taxa_entrega > 0:
        linhas.append(f"\n🛵 Taxa de Entrega: R$ {taxa_entrega:.2f}")
        total += taxa_entrega

    linhas.append(f"\n💰 *TOTAL: R$ {total:.2f}*")
    return "\n".join(linhas)


# storage/pedidos.py

def contar_pedidos_na_frente(telefone, usuario_id=1):
    with get_db_connection() as conn:
        row = conn.execute("""
            SELECT COUNT(*) FROM pedidos 
            WHERE status = 'EM_PREPARO' 
              AND tipo_entrega IN ('Entrega', 'Retirada')
              AND date(data_hora) = date('now', 'localtime')
              AND usuario_id = ?
        """, (usuario_id,)).fetchone()
        return row[0] if row else 0


def copiar_ultimo_pedido(telefone, usuario_id=1):
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            last_order = conn.execute(
                "SELECT id FROM pedidos WHERE cliente_telefone = ? AND status IN ('CONFIRMADO', 'EM_PREPARO', 'CONCLUIDO') AND usuario_id = ? ORDER BY id DESC LIMIT 1",
                (telefone, usuario_id),
            ).fetchone()
            if not last_order:
                return None

            itens = conn.execute(
                "SELECT * FROM pedido_outros_itens WHERE pedido_id = ?",
                (last_order["id"],),
            ).fetchall()
            novo_carrinho = []

            from storage.configuracoes import get_nome_tabela

            for it in itens:
                nome_item = "Item copiado"
                obs = it["observacao"] or ""
                match_nome = re.search(r"\[NM:(.*?)\]", obs)

                if match_nome:
                    nome_item = match_nome.group(1)
                    obs = obs.replace(match_nome.group(0), "").strip()
                elif it["produto_id"]:
                    tbl = get_nome_tabela(it["tipo"])
                    try:
                        n_row = conn.execute(
                            f"SELECT nome FROM {tbl} WHERE id=?", (it["produto_id"],)
                        ).fetchone()
                        if n_row:
                            nome_item = n_row["nome"]
                    except Exception:
                        pass

                item_obj = {
                    "tipo": it["tipo"],
                    "nome": nome_item,
                    "preco": it["preco_vendido"],
                    "quantidade": it["quantidade"],
                    "observacao": obs,
                    "adicionais": it["adicionais"],
                    "id": it["produto_id"],
                }
                if "pizza" in str(it["tipo"]).lower():
                    item_obj["borda"] = it["adicionais"]

                novo_carrinho.append(item_obj)
            return novo_carrinho
    except Exception:
        return None


def buscar_itens_do_pedido(pedido_id):
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM pedido_outros_itens WHERE pedido_id = ?", (pedido_id,)
        ).fetchall()

        pizzas = []
        extras = []

        from storage.configuracoes import get_nome_tabela

        for r in rows:
            item = dict(r)
            obs = item["observacao"] or ""

            match_nome = re.search(r"\[NM:(.*?)\]", obs)
            nome_real = "Item Indefinido"

            if match_nome:
                nome_real = match_nome.group(1)
                obs = obs.replace(match_nome.group(0), "").strip()
            elif item["produto_id"]:
                try:
                    tabela = get_nome_tabela(item["tipo"])
                    if tabela:
                        prod = conn.execute(
                            f"SELECT nome, preco FROM {tabela} WHERE id = ?",
                            (item["produto_id"],),
                        ).fetchone()
                        if prod:
                            if prod["nome"]:
                                nome_real = prod["nome"]
                except Exception:
                    pass

            try:
                preco_unit = (
                    float(item["preco_vendido"]) if item["preco_vendido"] else 0.0
                )
            except Exception:
                preco_unit = 0.0

            tamanho_txt = ""
            if "pizza" in str(item["tipo"]).lower():
                match_tam = re.search(r"Tamanho:\s*([^.|,]+)[.|,]?", obs)
                if match_tam:
                    tamanho_encontrado = match_tam.group(1).strip()
                    tamanho_txt = f"Pizza ({tamanho_encontrado})"

                    obs = obs.replace(match_tam.group(0), "").strip()
                    obs = obs.strip("., ")

                pizzas.append(
                    {
                        "tamanho": tamanho_txt,
                        "sabores": nome_real,
                        "borda": item["adicionais"]
                        if item["adicionais"] and "Borda" in str(item["adicionais"])
                        else "",
                        "observacao": obs,
                        "preco": preco_unit,
                        "quantidade": item["quantidade"],
                    }
                )
            else:
                extras.append(
                    {
                        "quantidade": item["quantidade"],
                        "nome_item": nome_real,
                        "opcoes": "",
                        "adicionais": item["adicionais"],
                        "observacao": obs,
                        "preco": preco_unit,
                    }
                )

        return pizzas, extras


# --- NOVA FUNÇÃO ADICIONADA ---
def listar_pedidos_ativos_cliente(telefone, usuario_id=1):
    """
    Retorna uma lista de pedidos ativos (não concluídos/cancelados) para um telefone específico.
    """
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT id, status, valor_total, data_hora 
                FROM pedidos 
                WHERE cliente_telefone = ? 
                AND status NOT IN ('CONCLUIDO', 'CANCELADO', 'ABANDONADO')
                AND usuario_id = ?
                ORDER BY id DESC
            """,
                (telefone, usuario_id),
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        print(f"Erro ao listar pedidos ativos: {e}")
        return []