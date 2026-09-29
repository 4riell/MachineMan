# routes/route_cardapio.py

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from storage import get_db_connection, templates
from storage.configuracoes import (
    obter_todas_categorias_db,
    get_nome_tabela,
    init_tabela_variacoes_extras,
)
import sqlite3

router = APIRouter()

# ==========================================
# FUNÇÃO MULTI-TENANT E TRAVA DE SEGURANÇA (SAAS)
# ==========================================
def obter_loja_logada(request: Request) -> int:
    usuario_id = request.cookies.get("session_user_id")
    if not usuario_id:
        usuario_id = getattr(request.state, "usuario_id", None)
    if not usuario_id:
        raise HTTPException(status_code=401, detail="Não autorizado. Faça login novamente.")
        
    with get_db_connection() as conn:
        row = conn.execute("SELECT loja_id, perfil FROM usuarios WHERE id = ?", (int(usuario_id),)).fetchone()
        
        if not row:
            raise HTTPException(status_code=403, detail="Usuário não encontrado.")
            
        usuario_data = dict(row)
        perfil = usuario_data.get("perfil", "dono")
        
        # BLOQUEIO DE SEGURANÇA ABSOLUTO
        # Se for funcionário e tentar acessar/salvar cardápio pela URL ou API, é bloqueado.
        if perfil not in ["dono", "admin"]:
            raise HTTPException(status_code=403, detail="Acesso negado. Apenas administradores podem acessar ou alterar o cardápio.")
            
        return int(usuario_data["loja_id"])

def garantir_coluna_loja(conn, tabela: str):
    """Garante que a tabela (seja ela fixa ou dinâmica) tenha a coluna loja_id."""
    try:
        cur = conn.execute(f"PRAGMA table_info({tabela})")
        colunas = [c[1] for c in cur.fetchall()]
        if "loja_id" not in colunas:
            conn.execute(f"ALTER TABLE {tabela} ADD COLUMN loja_id INTEGER DEFAULT 1")
            conn.commit()
    except Exception:
        pass # Falha silenciosa se a tabela ainda não existir

# ==========================================
# ROTAS DO CARDÁPIO
# ==========================================
@router.get("/cardapio", response_class=HTMLResponse)
async def ver_cardapio(request: Request):
    # Ao chamar esta função, se for funcionário, o código para aqui e cospe o Erro 403.
    loja_id = obter_loja_logada(request)
    
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    dados = {}

    garantir_coluna_loja(conn, "categorias_cardapio")
    categorias_ativas = conn.execute(
        "SELECT * FROM categorias_cardapio WHERE ativa = 1 AND loja_id = ?", 
        (loja_id,)
    ).fetchall()

    todos_produtos = []
    for cat in categorias_ativas:
        cat_id = cat["id"]
        tabela = get_nome_tabela(cat_id)

        try:
            check = conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{tabela}'").fetchone()
            if not check:
                check_fallback = conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{cat_id}'").fetchone()
                if check_fallback:
                    tabela = cat_id
                    check = True

            if not check:
                dados[cat_id] = []
                continue
            
            garantir_coluna_loja(conn, tabela)

            cur = conn.execute(f"PRAGMA table_info({tabela})")
            colunas_db = [c["name"] for c in cur.fetchall()]

            campos_select = ["id", "nome"]
            if "preco" in colunas_db: campos_select.append("preco")
            if "descricao" in colunas_db: campos_select.append("descricao")
            if "ingredientes" in colunas_db: campos_select.append("ingredientes")
            if "disponivel" in colunas_db: campos_select.append("disponivel")
            if "tipo" in colunas_db: campos_select.append("tipo")

            cols_str = ", ".join(campos_select)
            
            rows = conn.execute(
                f"SELECT {cols_str}, '{cat_id}' as categoria_origem FROM {tabela} WHERE loja_id = ? ORDER BY nome",
                (loja_id,)
            ).fetchall()
            
            lista_cat = [dict(row) for row in rows]
            dados[cat_id] = lista_cat
            todos_produtos.extend(lista_cat)

        except Exception as e:
            print(f"Erro ao carregar categoria {cat_id}: {e}")
            dados[cat_id] = []

    try:
        init_tabela_variacoes_extras()
        garantir_coluna_loja(conn, "produto_variacoes")
        
        variacoes_raw = conn.execute(
            "SELECT * FROM produto_variacoes WHERE loja_id = ? ORDER BY categoria, nome",
            (loja_id,)
        ).fetchall()
        dados["variacoes"] = [dict(v) for v in variacoes_raw]
    except Exception:
        dados["variacoes"] = []

    try:
        garantir_coluna_loja(conn, "grupos_adicionais")
        colunas_grp = [c[1] for c in conn.execute("PRAGMA table_info(grupos_adicionais)").fetchall()]
        
        if "limite_gratis" not in colunas_grp: conn.execute("ALTER TABLE grupos_adicionais ADD COLUMN limite_gratis INTEGER DEFAULT 0")
        if "produto_alvo_id" not in colunas_grp: conn.execute("ALTER TABLE grupos_adicionais ADD COLUMN produto_alvo_id INTEGER")
        if "variacao_alvo_id" not in colunas_grp: conn.execute("ALTER TABLE grupos_adicionais ADD COLUMN variacao_alvo_id INTEGER")
        if "minimo_escolha" not in colunas_grp: conn.execute("ALTER TABLE grupos_adicionais ADD COLUMN minimo_escolha INTEGER DEFAULT 0")
        if "maximo_escolha" not in colunas_grp: conn.execute("ALTER TABLE grupos_adicionais ADD COLUMN maximo_escolha INTEGER DEFAULT 1")

        conn.execute("CREATE TABLE IF NOT EXISTS produto_adicionais (id INTEGER PRIMARY KEY AUTOINCREMENT, categoria_alvo TEXT, grupo TEXT, nome TEXT, preco_adicional REAL, limite_gratis INTEGER DEFAULT 0)")
        garantir_coluna_loja(conn, "produto_adicionais")

        grupos_raw = conn.execute(
            "SELECT * FROM grupos_adicionais WHERE loja_id = ? ORDER BY categoria_alvo, ordem",
            (loja_id,)
        ).fetchall()
        
        grupos = []
        for g in grupos_raw:
            grp = dict(g)
            grp["alvo_desc"] = "Toda a Categoria"
            if grp.get("produto_alvo_id"):
                p = next((p for p in todos_produtos if str(p["id"]) == str(grp["produto_alvo_id"]) and p["categoria_origem"] == grp["categoria_alvo"]), None)
                if p: grp["alvo_desc"] = f"Apenas: {p['nome']}"
            elif grp.get("variacao_alvo_id"):
                v = next((v for v in dados["variacoes"] if str(v["id"]) == str(grp["variacao_alvo_id"])), None)
                if v: grp["alvo_desc"] = f"Apenas Tamanho: {v['nome']}"

            itens_raw = conn.execute(
                "SELECT * FROM produto_adicionais WHERE grupo = ? AND loja_id = ? ORDER BY nome",
                (str(grp["id"]), loja_id)
            ).fetchall()
            grp["opcoes"] = [dict(i) for i in itens_raw]
            grupos.append(grp)
            
        dados["adicionais_config"] = grupos
    except Exception as e:
        print(f"Erro adicionais: {e}")
        dados["adicionais_config"] = []

    conn.close()

    # Como a view Base.html precisa saber o perfil para montar o menu, enviamos "dono" forçado
    # pois se chegou até aqui, é porque o bloqueio lá em cima deixou passar.
    return templates.TemplateResponse(
        "cardapio.html",
        {
            "request": request,
            "perfil": "dono", 
            "dados": dados,
            "categorias_db": categorias_ativas,
            "todos_produtos": todos_produtos,
            "todas_variacoes": dados["variacoes"],
            "page_title": "Gerenciar Cardápio",
        },
    )

@router.post("/api/cardapio")
async def adicionar_item_cardapio(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        cat = data.get("categoria")
        tabela = get_nome_tabela(cat)

        check = conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{tabela}'").fetchone()
        if not check:
            check_fallback = conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{cat}'").fetchone()
            if check_fallback: tabela = cat
            
        garantir_coluna_loja(conn, tabela)

        if cat == "pizza":
            conn.execute(
                f"INSERT INTO {tabela} (nome, ingredientes, tipo, preco, loja_id) VALUES (?, ?, ?, ?, ?)",
                (data["nome"], data.get("ingredientes", ""), data.get("tipo", "Salgada"), float(data.get("preco", 0)), loja_id),
            )
        else:
            conn.execute(
                f"INSERT INTO {tabela} (nome, preco, descricao, loja_id) VALUES (?, ?, ?, ?)",
                (data["nome"], float(data.get("preco", 0)), data.get("descricao", ""), loja_id),
            )
        conn.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "erro": str(e)}
    finally:
        conn.close()

@router.put("/api/cardapio/{categoria}/{item_id}")
async def atualizar_item_cardapio(request: Request, categoria: str, item_id: int, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        tabela = get_nome_tabela(categoria)
        check = conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{tabela}'").fetchone()
        if not check:
            check_fallback = conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{categoria}'").fetchone()
            if check_fallback: tabela = categoria
            
        garantir_coluna_loja(conn, tabela)

        if categoria == "pizza":
            conn.execute(
                f"UPDATE {tabela} SET nome=?, ingredientes=?, tipo=?, preco=? WHERE id=? AND loja_id=?",
                (data["nome"], data.get("ingredientes"), data.get("tipo"), float(data.get("preco", 0)), item_id, loja_id),
            )
        else:
            conn.execute(
                f"UPDATE {tabela} SET nome=?, preco=?, descricao=? WHERE id=? AND loja_id=?",
                (data["nome"], float(data["preco"]), data.get("descricao", ""), item_id, loja_id),
            )
        conn.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "erro": str(e)}
    finally:
        conn.close()

@router.delete("/api/cardapio/{categoria}/{item_id}")
async def excluir_item_cardapio(request: Request, categoria: str, item_id: int):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        tabela = get_nome_tabela(categoria)
        check = conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{tabela}'").fetchone()
        if not check:
            check_fallback = conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{categoria}'").fetchone()
            if check_fallback: tabela = categoria
            
        conn.execute(f"DELETE FROM {tabela} WHERE id=? AND loja_id=?", (item_id, loja_id))
        
        try: conn.execute("DELETE FROM promocoes WHERE produto_id=? AND categoria=? AND loja_id=?", (item_id, categoria, loja_id))
        except Exception: pass
        try: conn.execute("DELETE FROM destaques_dia WHERE produto_id=? AND categoria=? AND loja_id=?", (item_id, categoria, loja_id))
        except Exception: pass
        try: conn.execute("DELETE FROM produto_variacoes WHERE produto_id=? AND tabela_referencia=? AND loja_id=?", (item_id, tabela, loja_id))
        except Exception: pass
        try: conn.execute("DELETE FROM sabor_apelido WHERE sabor_produto_id=? AND categoria=? AND loja_id=?", (item_id, categoria, loja_id))
        except Exception: pass
        try: conn.execute("DELETE FROM ficha_tecnica_produto WHERE produto_id=? AND categoria_id=? AND loja_id=?", (item_id, categoria, loja_id))
        except Exception: pass
        
        try:
            conn.execute("DELETE FROM produto_adicionais WHERE grupo IN (SELECT id FROM grupos_adicionais WHERE produto_alvo_id=? AND loja_id=?) AND loja_id=?", (item_id, loja_id, loja_id))
            conn.execute("DELETE FROM grupos_adicionais WHERE produto_alvo_id=? AND loja_id=?", (item_id, loja_id))
        except Exception: pass

        conn.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "erro": str(e)}
    finally:
        conn.close()

@router.post("/api/grupos_adicionais")
async def salvar_grupo_adicional(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        garantir_coluna_loja(conn, "grupos_adicionais")
        garantir_coluna_loja(conn, "produto_adicionais")
        
        grupo_id = data.get("id")
        limite_gratis = int(data.get("limite_gratis", 0))
        prod_alvo = data.get("produto_alvo_id") if data.get("produto_alvo_id") != "" else None
        var_alvo = data.get("variacao_alvo_id") if data.get("variacao_alvo_id") != "" else None
        minimo = int(data.get("minimo_escolha", 0))
        maximo = int(data.get("maximo_escolha", 1))

        if grupo_id:
            conn.execute(
                """
                UPDATE grupos_adicionais 
                SET categoria_alvo=?, titulo=?, descricao=?, tipo=?, ordem=?, limite_gratis=?, produto_alvo_id=?, variacao_alvo_id=?, minimo_escolha=?, maximo_escolha=?
                WHERE id=? AND loja_id=?
                """,
                (data["categoria_alvo"], data["titulo"], data["descricao"], data["tipo"], data["ordem"], limite_gratis, prod_alvo, var_alvo, minimo, maximo, grupo_id, loja_id)
            )
        else:
            cur = conn.execute(
                """
                INSERT INTO grupos_adicionais 
                (categoria_alvo, titulo, descricao, tipo, ordem, limite_gratis, produto_alvo_id, variacao_alvo_id, minimo_escolha, maximo_escolha, loja_id) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (data["categoria_alvo"], data["titulo"], data["descricao"], data["tipo"], data["ordem"], limite_gratis, prod_alvo, var_alvo, minimo, maximo, loja_id)
            )
            grupo_id = cur.lastrowid

        conn.execute("DELETE FROM produto_adicionais WHERE grupo = ? AND loja_id = ?", (str(grupo_id), loja_id))
        for op in data.get("opcoes", []):
            if op.get("nome"):
                conn.execute(
                    "INSERT INTO produto_adicionais (categoria_alvo, grupo, nome, preco_adicional, limite_gratis, loja_id) VALUES (?, ?, ?, ?, ?, ?)",
                    (data["categoria_alvo"], str(grupo_id), op["nome"], float(op["preco"]), int(op.get("limite_gratis", 0)), loja_id)
                )
        conn.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "erro": str(e)}
    finally:
        conn.close()

@router.delete("/api/grupos_adicionais/{id}")
async def excluir_grupo(request: Request, id: int):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM grupos_adicionais WHERE id=? AND loja_id=?", (id, loja_id))
        conn.execute("DELETE FROM produto_adicionais WHERE grupo=? AND loja_id=?", (str(id), loja_id))
        conn.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "erro": str(e)}
    finally:
        conn.close()

@router.post("/api/variacoes")
async def salvar_variacao(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        garantir_coluna_loja(conn, "produto_variacoes")
        try:
            conn.execute("ALTER TABLE produto_variacoes ADD COLUMN fatias INTEGER DEFAULT 0")
            conn.execute("ALTER TABLE produto_variacoes ADD COLUMN max_sabores INTEGER DEFAULT 1")
            conn.execute("ALTER TABLE produto_variacoes ADD COLUMN tamanho_cm TEXT")
            conn.execute("ALTER TABLE produto_variacoes ADD COLUMN sigla TEXT")
        except Exception:
            pass

        var_id = data.get("id")
        fatias = int(data.get("fatias", 0))
        max_sabores = int(data.get("max_sabores", 1))
        tamanho_cm = data.get("tamanho_cm", "")
        sigla = data.get("sigla", "").strip().upper()

        if var_id and str(var_id).strip():
            conn.execute(
                """
                UPDATE produto_variacoes 
                SET categoria=?, nome=?, preco=?, fatias=?, max_sabores=?, tamanho_cm=?, sigla=?
                WHERE id=? AND loja_id=?
                """,
                (data["categoria"], data["nome"], float(data["preco"]), fatias, max_sabores, tamanho_cm, sigla, var_id, loja_id)
            )
        else:
            conn.execute(
                """
                INSERT INTO produto_variacoes 
                (categoria, nome, preco, fatias, max_sabores, tamanho_cm, sigla, loja_id) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (data["categoria"], data["nome"], float(data["preco"]), fatias, max_sabores, tamanho_cm, sigla, loja_id)
            )
        conn.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "erro": str(e)}
    finally:
        conn.close()

@router.delete("/api/variacoes/{id}")
async def excluir_variacao(request: Request, id: int):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM produto_variacoes WHERE id=? AND loja_id=?", (id, loja_id))
        conn.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "erro": str(e)}
    finally:
        conn.close()

@router.post("/api/grupos_adicionais/reordenar")
async def reordenar_grupos_adicionais(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        garantir_coluna_loja(conn, "grupos_adicionais")
        try: conn.execute("ALTER TABLE grupos_adicionais ADD COLUMN ordem INTEGER DEFAULT 99")
        except Exception: pass

        for item in data.get("ordem", []):
            conn.execute(
                "UPDATE grupos_adicionais SET ordem = ? WHERE id = ? AND loja_id = ?",
                (int(item.get("ordem")), item.get("id"), loja_id),
            )
        conn.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "erro": str(e)}
    finally:
        conn.close()

@router.get("/meu-menu")
async def redirecionar_meu_menu(request: Request):
    # Pode ser acessado por qualquer funcionário, apenas redireciona
    usuario_id = request.cookies.get("session_user_id")
    if not usuario_id:
        usuario_id = getattr(request.state, "usuario_id", None)
    if not usuario_id:
        return RedirectResponse(url="/login")
        
    with get_db_connection() as conn:
        row = conn.execute("SELECT loja_id FROM usuarios WHERE id = ?", (int(usuario_id),)).fetchone()
        if row and row["loja_id"]:
            loja_id = int(row["loja_id"])
        else:
            return RedirectResponse(url="/login")
            
    return RedirectResponse(url=f"/menu/{loja_id}")