# routes/route_clientes.py

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from storage import get_db_connection, templates
import sqlite3

router = APIRouter()

def obter_loja_logada(request: Request) -> int:
    """Busca o ID da Loja/Tenant correspondente ao usuário logado."""
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
    """Retorna o perfil do usuário logado para controle de permissões no template e API."""
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

def garantir_estrutura_tabelas(conn):
    try:
        cursor = conn.execute("PRAGMA table_info(cliente)")
        colunas_cliente = [row[1] for row in cursor.fetchall()]
        if "loja_id" not in colunas_cliente:
            conn.execute("ALTER TABLE cliente ADD COLUMN loja_id INTEGER DEFAULT 1")
            conn.commit()
    except Exception as e:
        print(f"⚠️ Erro ao checar estrutura: {e}")


@router.get("/clientes", response_class=HTMLResponse)
def ver_clientes(request: Request):
    loja_id = obter_loja_logada(request)
    perfil_usuario = obter_perfil_logado(request) # Captura para o template ocultar os botões

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    garantir_estrutura_tabelas(conn)
    
    try:
        clientes_db = conn.execute(
            "SELECT * FROM cliente WHERE loja_id = ? ORDER BY nome COLLATE NOCASE ASC", 
            (loja_id,)
        ).fetchall()
        clientes = [dict(c) for c in clientes_db]
    except Exception as e:
        print(f"❌ Erro ao buscar clientes: {e}")
        clientes = []

    try:
        bairros_db = conn.execute("SELECT nome FROM bairros_entrega WHERE loja_id = ? ORDER BY nome ASC", (loja_id,)).fetchall()
        lista_bairros = [b["nome"] for b in bairros_db]
    except Exception:
        lista_bairros = []

    colunas_fixas = ['nome', 'cpf', 'rua', 'numero_casa', 'bairro', 'ponto_referencia']
    colunas_extras = []
    try:
        campos_cadastro = conn.execute("SELECT coluna, label FROM config_cadastro WHERE loja_id = ? ORDER BY ordem ASC", (loja_id,)).fetchall()
        for c in campos_cadastro:
            if c["coluna"] not in colunas_fixas:
                colunas_extras.append({"coluna": c["coluna"], "label": c["label"]})
    except Exception:
        pass
    finally:
        conn.close()

    return templates.TemplateResponse(
        "clientes.html",
        {
            "request": request,
            "perfil": perfil_usuario, # -> PASSANDO VARIÁVEL PARA O BASE.HTML AQUI!
            "clientes": clientes,
            "bairros_disponiveis": lista_bairros,
            "colunas_extras": colunas_extras,
            "page_title": "Gerenciar Clientes",
            "active_page": "clientes",
        },
    )

@router.post("/api/clientes")
def criar_cliente(request: Request, data: dict):
    loja_id = obter_loja_logada(request)

    conn = get_db_connection()
    garantir_estrutura_tabelas(conn)
    
    try:
        chat_ativo = int(data.get("chat_ativo", 1))
        telefone = data.get("telefone")
        
        existe = conn.execute(
            "SELECT telefone FROM cliente WHERE telefone = ? AND loja_id = ?", 
            (telefone, loja_id)
        ).fetchone()
        
        if existe:
            raise HTTPException(400, "Telefone já cadastrado nesta loja.")

        valid_cols = [row[1] for row in conn.execute("PRAGMA table_info(cliente)").fetchall()]
        
        insert_cols = []
        insert_vals = []
        
        for k, v in data.items():
            if k in valid_cols and k not in ['chat_ativo', 'loja_id', 'usuario_id']:
                insert_cols.append(k)
                insert_vals.append(v)
        
        if "chat_ativo" in valid_cols:
            insert_cols.append("chat_ativo")
            insert_vals.append(chat_ativo)
            
        if "loja_id" in valid_cols:
            insert_cols.append("loja_id")
            insert_vals.append(loja_id)
            
        cols_str = ", ".join(insert_cols)
        placeholders = ", ".join(["?"] * len(insert_cols))
        
        conn.execute(f"INSERT INTO cliente ({cols_str}) VALUES ({placeholders})", tuple(insert_vals))
        conn.commit()
        return {"ok": True}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        conn.close()

@router.put("/api/clientes/{telefone}")
def atualizar_cliente(request: Request, telefone: str, data: dict):
    loja_id = obter_loja_logada(request)

    conn = get_db_connection()
    garantir_estrutura_tabelas(conn)
    
    try:
        valid_cols = [row[1] for row in conn.execute("PRAGMA table_info(cliente)").fetchall()]
        set_clauses = []
        values = []
        
        for k, v in data.items():
            if k in valid_cols and k not in ['telefone', 'chat_ativo', 'loja_id', 'usuario_id']:
                set_clauses.append(f"{k}=?")
                values.append(v)
        
        if "chat_ativo" in valid_cols:
            set_clauses.append("chat_ativo=?")
            values.append(int(data.get("chat_ativo", 1)))
            
        if not set_clauses:
            return {"ok": True}
            
        values.extend([telefone, loja_id])
        set_str = ", ".join(set_clauses)
        
        conn.execute(f"UPDATE cliente SET {set_str} WHERE telefone = ? AND loja_id = ?", tuple(values))
        conn.commit()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        conn.close()

# ==========================================
# ROTA: ATUALIZAÇÃO RÁPIDA (TOGGLE INDIVIDUAL)
# ==========================================
@router.post("/api/clientes/{telefone}/chat_status")
async def atualizar_status_chat(request: Request, telefone: str, data: dict):
    loja_id = obter_loja_logada(request)
    novo_status = data.get("chat_ativo", 0)
    
    conn = get_db_connection()
    try:
        conn.execute(
            "UPDATE cliente SET chat_ativo = ? WHERE telefone = ? AND loja_id = ?", 
            (novo_status, telefone, loja_id)
        )
        conn.commit()
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"erro": str(e)}, status_code=500)
    finally:
        conn.close()

# ==========================================
# ROTA: ATUALIZAÇÃO EM MASSA (BOTÕES "TODOS")
# ==========================================
@router.post("/api/clientes/bulk_update_status")
async def bulk_update_status(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    novo_status = data.get("novo_status", 0)
    
    conn = get_db_connection()
    try:
        conn.execute(
            "UPDATE cliente SET chat_ativo = ? WHERE loja_id = ?", 
            (novo_status, loja_id)
        )
        conn.commit()
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"erro": str(e)}, status_code=500)
    finally:
        conn.close()

@router.delete("/api/clientes/{telefone}")
def excluir_cliente(request: Request, telefone: str):
    loja_id = obter_loja_logada(request)
    perfil = obter_perfil_logado(request)
    
    # BLOQUEIO DE BACKEND: Segurança Máxima
    if perfil not in ["dono", "admin"]:
        return {"ok": False, "erro": "Acesso negado. Apenas administradores podem excluir clientes do banco de dados."}

    conn = get_db_connection()
    garantir_estrutura_tabelas(conn)
    try:
        cursor = conn.execute("SELECT id FROM pedidos WHERE cliente_telefone=? AND loja_id=?", (telefone, loja_id))
        pedidos = cursor.fetchall()
        for p in pedidos:
            pid = p["id"]
            try: conn.execute("DELETE FROM pedido_outros_itens WHERE pedido_id=? AND loja_id=?", (pid, loja_id))
            except: pass
            
        conn.execute("DELETE FROM pedidos WHERE cliente_telefone=? AND loja_id=?", (telefone, loja_id))
        conn.execute("DELETE FROM cliente WHERE telefone = ? AND loja_id = ?", (telefone, loja_id))
        conn.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "erro": str(e)}
    finally:
        conn.close()