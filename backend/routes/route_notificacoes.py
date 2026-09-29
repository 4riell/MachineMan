# routes/route_notificacoes.py

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from storage import (
    templates,
    get_db_connection,
)
import sqlite3
import time

router = APIRouter()

# ==========================================
# FUNÇÃO MULTI-TENANT E PERFIL (SAAS)
# ==========================================
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
            if not row: return "dono"
            row_dict = dict(row)
            return row_dict.get("perfil", "dono")
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

# --- CACHE DE NOTIFICAÇÕES POR LOJA ---
CACHE_NOTIF_CHECK = {}

# 1. Rota Principal
@router.get("/notificacoes", response_class=HTMLResponse)
def ver_notificacoes(request: Request):
    loja_id = obter_loja_logada(request)
    perfil_usuario = obter_perfil_logado(request) # Captura o perfil para enviar para o HTML
    
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    try:
        garantir_coluna_loja(conn, "notificacoes")
        garantir_coluna_loja(conn, "configuracoes")
        
        lista = [dict(n) for n in conn.execute(
            "SELECT * FROM notificacoes WHERE loja_id = ? ORDER BY data_hora DESC", 
            (loja_id,)
        ).fetchall()]
        
        for n in lista:
            msg = n.get("mensagem", "") or ""
            n["is_inativo"] = "CLIENTE INATIVO" in msg.upper()
            n["is_bloqueado"] = False

        rows = conn.execute(
            "SELECT chave, valor FROM configuracoes WHERE chave IN ('notif_inativos', 'notif_restritos') AND loja_id = ?",
            (loja_id,)
        ).fetchall()
        prefs = {row["chave"]: row["valor"] for row in rows}

        return templates.TemplateResponse(
            "notificacoes.html",
            {
                "request": request,
                "perfil": perfil_usuario, # <- INJETADO NO CONTEXTO DO TEMPLATE BASE.HTML
                "notificacoes": lista,
                "page_title": "Central de Notificações",
                "active_page": "notificacoes",
                "pref_inativos": prefs.get("notif_inativos", "1") == "1",
                "pref_restritos": prefs.get("notif_restritos", "1") == "1",
            },
        )
    finally:
        conn.close()

# 2. Monitoramento Otimizado
@router.get("/api/notificacoes/check")
def check_novas_notificacoes(request: Request):
    loja_id = obter_loja_logada(request)
    headers_cache = {"Cache-Control": "public, max-age=5"}

    if loja_id in CACHE_NOTIF_CHECK:
        if time.time() - CACHE_NOTIF_CHECK[loja_id]["last_update"] < 5.0:
            return JSONResponse(CACHE_NOTIF_CHECK[loja_id]["payload"], headers=headers_cache)

    inc_restritos = request.query_params.get("inc_restritos") == "true"
    inc_inativos = request.query_params.get("inc_inativos") == "true"

    conn = get_db_connection()
    try:
        garantir_coluna_loja(conn, "notificacoes")
        
        cursor_total = conn.execute("SELECT COUNT(id) FROM notificacoes WHERE lida = 0 AND loja_id = ?", (loja_id,))
        total_badge = cursor_total.fetchone()[0]

        query_alarme = """
            SELECT COUNT(n.id) 
            FROM notificacoes n
            LEFT JOIN cliente c ON n.cliente_telefone = c.telefone AND n.loja_id = c.loja_id
            WHERE n.lida = 0 AND n.loja_id = ?
        """
        if not inc_restritos:
            query_alarme += " AND n.mensagem NOT LIKE '%[RESTRITO]%' AND (c.chat_ativo IS NULL OR c.chat_ativo != 0) "
        if not inc_inativos:
            query_alarme += " AND n.mensagem NOT LIKE '%CLIENTE INATIVO%' "

        unread_count = conn.execute(query_alarme, (loja_id,)).fetchone()[0]

        payload = {"total_badge": total_badge, "unread_count": unread_count}
        CACHE_NOTIF_CHECK[loja_id] = {"payload": payload, "last_update": time.time()}

        return JSONResponse(payload, headers=headers_cache)
    finally:
        conn.close()

# 3. Salvar Preferências
@router.post("/api/notificacoes/preferencias")
async def salvar_preferencias_notificacao(request: Request):
    loja_id = obter_loja_logada(request)
    data = await request.json()
    inativos = "1" if data.get("inativos") else "0"
    restritos = "1" if data.get("restritos") else "0"
    
    conn = get_db_connection()
    garantir_coluna_loja(conn, "configuracoes")
    conn.execute("INSERT OR REPLACE INTO configuracoes (chave, valor, loja_id) VALUES ('notif_inativos', ?, ?)", (inativos, loja_id))
    conn.execute("INSERT OR REPLACE INTO configuracoes (chave, valor, loja_id) VALUES ('notif_restritos', ?, ?)", (restritos, loja_id))
    conn.commit()
    conn.close()
    
    if loja_id in CACHE_NOTIF_CHECK: CACHE_NOTIF_CHECK[loja_id]["last_update"] = 0
    return {"ok": True}

# 4. Rotas de Ação
@router.delete("/api/notificacoes/limpar_tudo")
def api_limpar_todas_notificacoes(request: Request):
    loja_id = obter_loja_logada(request)
    perfil = obter_perfil_logado(request)
    
    # BLOQUEIO DE BACKEND: Só admin limpa o histórico
    if perfil not in ["dono", "admin"]:
        return {"ok": False, "erro": "Acesso negado. Apenas administradores podem excluir notificações."}
        
    conn = get_db_connection()
    conn.execute("DELETE FROM notificacoes WHERE loja_id = ?", (loja_id,))
    conn.commit()
    conn.close()
    if loja_id in CACHE_NOTIF_CHECK: CACHE_NOTIF_CHECK[loja_id]["last_update"] = 0
    return {"ok": True}

@router.post("/api/notificacoes/{id}/lida")
def api_marcar_lida(request: Request, id: int):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.execute("UPDATE notificacoes SET lida = 1 WHERE id = ? AND loja_id = ?", (id, loja_id))
    conn.commit()
    conn.close()
    if loja_id in CACHE_NOTIF_CHECK: CACHE_NOTIF_CHECK[loja_id]["last_update"] = 0
    return {"ok": True}

@router.delete("/api/notificacoes/{id}")
def api_excluir_notificacao(request: Request, id: int):
    loja_id = obter_loja_logada(request)
    perfil = obter_perfil_logado(request)
    
    # BLOQUEIO DE BACKEND: Só admin limpa
    if perfil not in ["dono", "admin"]:
        return {"ok": False, "erro": "Acesso negado. Apenas administradores podem excluir notificações."}
        
    conn = get_db_connection()
    conn.execute("DELETE FROM notificacoes WHERE id = ? AND loja_id = ?", (id, loja_id))
    conn.commit()
    conn.close()
    if loja_id in CACHE_NOTIF_CHECK: CACHE_NOTIF_CHECK[loja_id]["last_update"] = 0
    return {"ok": True}

@router.post("/api/notificacoes/marcar_todas_lidas")
def api_marcar_todas_lidas(request: Request):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.execute("UPDATE notificacoes SET lida = 1 WHERE lida = 0 AND loja_id = ?", (loja_id,))
    conn.commit()
    conn.close()
    if loja_id in CACHE_NOTIF_CHECK: CACHE_NOTIF_CHECK[loja_id]["last_update"] = 0
    return {"ok": True}