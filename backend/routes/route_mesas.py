# routes/route_mesas.py

import sqlite3
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from storage import templates, get_db_connection
from storage.configuracoes import get_nome_tabela  

from routes.route_pedidos import deduzir_estoque_pedido 

from storage.mesas import (
    listar_mesas_status,
    obter_detalhes_mesa,
    adicionar_item_mesa_estruturado,
    fechar_mesa,
    remover_item_mesa,
    cancelar_mesa,
    definir_quantidade_mesas,
    atualizar_nome_cliente,
    renomear_mesa,
)

router = APIRouter()

# --- Funções Auxiliares de Segurança (SaaS) ---
def obter_loja_logada(request: Request) -> int:
    usuario_id = request.cookies.get("session_user_id")
    if not usuario_id:
        usuario_id = getattr(request.state, "usuario_id", None)
    if not usuario_id:
        raise HTTPException(status_code=401, detail="Não autorizado. Faça login novamente.")
        
    with get_db_connection() as conn:
        row = conn.execute("SELECT loja_id FROM usuarios WHERE id = ?", (int(usuario_id),)).fetchone()
        if row and row["loja_id"]:
            return int(row["loja_id"])
        else:
            raise HTTPException(status_code=403, detail="Este usuário não está vinculado a nenhuma loja.")

def obter_perfil_logado(request: Request) -> str:
    """Busca o perfil do usuário logado para controlar o menu e botões do Front-End"""
    usuario_id = request.cookies.get("session_user_id")
    if not usuario_id:
        usuario_id = getattr(request.state, "usuario_id", None)
    if not usuario_id: return "funcionario"
    with get_db_connection() as conn:
        try:
            row = conn.execute("SELECT perfil FROM usuarios WHERE id = ?", (int(usuario_id),)).fetchone()
            return row["perfil"] if row and "perfil" in row.keys() else "dono"
        except Exception:
            return "dono"

def garantir_coluna_loja(conn, tabela: str):
    try:
        cur = conn.execute(f"PRAGMA table_info({tabela})")
        colunas = [c[1] for c in cur.fetchall()]
        if "loja_id" not in colunas:
            conn.execute(f"ALTER TABLE {tabela} ADD COLUMN loja_id INTEGER DEFAULT 1")
            conn.commit()
    except Exception: pass

# --- Rotas ---

@router.get("/mesas", response_class=HTMLResponse)
def page_mesas(request: Request):
    loja_id = obter_loja_logada(request)
    perfil_usuario = obter_perfil_logado(request) # Captura o perfil para a tela
    
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    try:
        garantir_coluna_loja(conn, "categorias_cardapio")
        garantir_coluna_loja(conn, "formas_pagamento")
        
        categorias = conn.execute(
            "SELECT * FROM categorias_cardapio WHERE ativa = 1 AND loja_id = ? ORDER BY ordem ASC", 
            (loja_id,)
        ).fetchall()
        
        try:
            formas_pagamento = [dict(r) for r in conn.execute(
                "SELECT * FROM formas_pagamento WHERE loja_id = ? ORDER BY nome ASC", 
                (loja_id,)
            ).fetchall()]
        except Exception:
            formas_pagamento = [
                {"nome": "Dinheiro", "pede_detalhe": 1, "pergunta_detalhe": "Troco para?"}, 
                {"nome": "Pix", "pede_detalhe": 0, "pergunta_detalhe": ""}, 
                {"nome": "Cartão de Crédito", "pede_detalhe": 0, "pergunta_detalhe": ""}, 
                {"nome": "Cartão de Débito", "pede_detalhe": 0, "pergunta_detalhe": ""}
            ]
            
        return templates.TemplateResponse(
            "mesas.html",
            {
                "request": request, 
                "perfil": perfil_usuario, # <- ENVIANDO PARA O TEMPLATE BASE.HTML
                "categorias": [dict(c) for c in categorias],
                "formas_pagamento": formas_pagamento
            },
        )
    finally:
        conn.close()

@router.get("/api/mesas/promocoes")
def api_obter_promocoes_mesas(request: Request):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    try: 
        garantir_coluna_loja(conn, "promocoes")
        return [dict(r) for r in conn.execute("SELECT * FROM promocoes WHERE loja_id = ?", (loja_id,)).fetchall()]
    except Exception: return []
    finally: conn.close()

@router.get("/api/mesas/buscar_produtos")
def api_buscar_produtos(request: Request, q: str):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    resultados = []
    try:
        tabelas_existentes = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        categorias = conn.execute("SELECT id, nome, emoji FROM categorias_cardapio WHERE ativa = 1 AND loja_id = ?", (loja_id,)).fetchall()
        
        for cat in categorias:
            cat_id = cat["id"]
            tabela = get_nome_tabela(cat_id)
            if tabela in tabelas_existentes:
                itens = conn.execute(
                    f"SELECT id, nome, preco FROM {tabela} WHERE nome LIKE ? AND disponivel = 1 AND loja_id = ? LIMIT 5", 
                    (f'%{q}%', loja_id)
                ).fetchall()
                for item in itens:
                    resultados.append({
                        "categoria_id": cat_id, "categoria_nome": cat["nome"], "emoji": cat["emoji"],
                        "produto_id": item["id"], "nome": item["nome"], "preco": item["preco"] or 0.0
                    })
    finally: conn.close()
    return resultados

@router.get("/api/mesas")
def api_listar_mesas(request: Request):
    loja_id = obter_loja_logada(request)
    return listar_mesas_status(loja_id)

@router.get("/api/mesas/{mesa_id}/itens")
def api_itens_mesa(request: Request, mesa_id: int):
    loja_id = obter_loja_logada(request)
    itens, _, nome_cliente = obter_detalhes_mesa(mesa_id, loja_id)
    total = sum(i["preco_vendido"] * i["quantidade"] for i in itens)
    return {"itens": itens, "total": total, "cliente_nome": nome_cliente}

@router.post("/api/mesas/{mesa_id}/adicionar")
def api_add_mesa(request: Request, mesa_id: int, item: dict):
    loja_id = obter_loja_logada(request)
    sucesso = adicionar_item_mesa_estruturado(mesa_id, item, loja_id)
    return {"success": sucesso}

@router.delete("/api/mesas/{mesa_id}/item/{item_id}")
def api_remove_item_mesa(request: Request, mesa_id: int, item_id: int):
    loja_id = obter_loja_logada(request)
    _, pedido_id, _ = obter_detalhes_mesa(mesa_id, loja_id)
    remover_item_mesa(item_id, loja_id)
    
    itens_restantes, _, nome_cliente = obter_detalhes_mesa(mesa_id, loja_id)
    if not itens_restantes and not nome_cliente:
        cancelar_mesa(mesa_id, loja_id)
        if pedido_id:
            conn = get_db_connection()
            try:
                conn.execute(
                    "UPDATE pedidos SET data_hora=datetime('now', 'localtime') WHERE id=? AND loja_id=?", 
                    (pedido_id, loja_id)
                )
                conn.commit()
            except: pass
            finally: conn.close()
            
    return {"success": True}

@router.post("/api/mesas/{mesa_id}/fechar")
def api_close_mesa(request: Request, mesa_id: int, data: dict):
    loja_id = obter_loja_logada(request)
    _, pedido_id, _ = obter_detalhes_mesa(mesa_id, loja_id)
    forma_pagamento = data.get("forma_pagamento", data.get("pagamento", "Dinheiro"))
    detalhe_pagamento = data.get("detalhe_pagamento", "")
    
    fechar_mesa(mesa_id, forma_pagamento, float(data.get("total", 0)), loja_id)
    
    if pedido_id:
        conn = get_db_connection()
        try:
            conn.execute(
                "UPDATE pedidos SET forma_pagamento=?, detalhe_pagamento=?, data_hora=datetime('now', 'localtime') WHERE id=? AND loja_id=?",
                (forma_pagamento, detalhe_pagamento, pedido_id, loja_id)
            )
            conn.commit()
        except Exception as e:
            print("Erro ao atualizar detalhes:", e)
        finally:
            conn.close()
            
        deduzir_estoque_pedido(pedido_id, loja_id)
            
    return {"success": True}

@router.post("/api/mesas/{mesa_id}/cancelar")
def api_cancel_mesa(request: Request, mesa_id: int):
    loja_id = obter_loja_logada(request)
    perfil = obter_perfil_logado(request)
    
    # Restrição de Cancelamento de Mesa
    if perfil not in ["dono", "admin"]:
        raise HTTPException(status_code=403, detail="Apenas administradores podem cancelar mesas.")

    _, pedido_id, _ = obter_detalhes_mesa(mesa_id, loja_id)
    cancelar_mesa(mesa_id, loja_id)
    
    if pedido_id:
        conn = get_db_connection()
        try:
            conn.execute(
                "UPDATE pedidos SET data_hora=datetime('now', 'localtime') WHERE id=? AND loja_id=?", 
                (pedido_id, loja_id)
            )
            conn.commit()
        except: pass
        finally: conn.close()
        
    return {"success": True}

@router.post("/api/mesas/configurar_qtd")
def api_config_qtd(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    definir_quantidade_mesas(int(data.get("qtd", 10)), loja_id)
    return {"success": True}

@router.post("/api/mesas/{mesa_id}/nome_cliente")
def api_update_nome(request: Request, mesa_id: int, data: dict):
    loja_id = obter_loja_logada(request)
    atualizar_nome_cliente(mesa_id, data.get("nome", ""), loja_id)
    return {"success": True}

@router.post("/api/mesas/renomear")
def api_rename_mesa(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    renomear_mesa(data.get("id"), data.get("nome"), loja_id)
    return {"success": True}