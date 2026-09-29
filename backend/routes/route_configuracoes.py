# routes/route_configuracoes.py

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from storage import get_db_connection, templates, remover_acentos
from storage.configuracoes import get_nome_tabela
import sqlite3
import json

router = APIRouter()

# ==========================================
# FUNÇÕES DE SEGURANÇA E AUTO-CURA (SAAS)
# ==========================================
def obter_loja_logada(request: Request) -> int:
    """Retorna o loja_id e bloqueia o acesso caso seja funcionário."""
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
        if perfil not in ["dono", "admin"]:
            raise HTTPException(
                status_code=403, 
                detail="Acesso Negado. Apenas o administrador da loja possui acesso a esta área."
            )
            
        return int(usuario_data["loja_id"])

def obter_perfil_logado(request: Request) -> str:
    """Busca o perfil do usuário logado para controle de permissões no template e API."""
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
    except Exception:
        pass

def garantir_tabelas_sistema(conn, loja_id: int):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS config_cadastro (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            coluna TEXT,      
            label TEXT,              
            pergunta_wpp TEXT,       
            ativo_wpp INTEGER DEFAULT 1,
            obrigatorio INTEGER DEFAULT 0,
            ordem INTEGER DEFAULT 99,
            loja_id INTEGER DEFAULT 1
        )
    """)
    garantir_coluna_loja(conn, "config_cadastro")

    count_config = conn.execute("SELECT COUNT(*) FROM config_cadastro WHERE loja_id = ?", (loja_id,)).fetchone()[0]
    if count_config == 0:
        padroes = [
            ('nome', 'Nome Completo', 'Qual é o seu *Nome*?', 1, 1, 1, loja_id),
            ('cpf', 'CPF (Nota Fiscal)', 'Deseja incluir o CPF na nota fiscal? Se sim, digite seu *CPF*. (Caso não queira, responda "não").', 1, 0, 2, loja_id),
            ('rua', 'Rua', 'Qual o nome da sua *Rua*?', 1, 1, 3, loja_id),
            ('numero_casa', 'Número', 'Qual o *Número* da casa?', 1, 1, 4, loja_id),
            ('bairro', 'Bairro', 'Qual o seu *Bairro*?', 1, 1, 5, loja_id),
            ('ponto_referencia', 'Referência', 'Algum *Ponto de Referência*?', 1, 0, 6, loja_id)
        ]
        for p in padroes:
            try:
                conn.execute("INSERT INTO config_cadastro (coluna, label, pergunta_wpp, ativo_wpp, obrigatorio, ordem, loja_id) VALUES (?, ?, ?, ?, ?, ?, ?)", p)
            except Exception: pass
            try: conn.execute(f"ALTER TABLE cliente ADD COLUMN {p[0]} TEXT")
            except Exception: pass 
        conn.commit()

    def add_column_safe(table_name, column_def):
        try: conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_def}")
        except Exception: pass

    conn.execute("CREATE TABLE IF NOT EXISTS reservas (id INTEGER PRIMARY KEY AUTOINCREMENT, data_reserva TEXT, horario TEXT, qtd_pessoas INTEGER, nome_cliente TEXT, telefone_cliente TEXT, pre_pedido TEXT, status TEXT DEFAULT 'confirmada', criado_em DATETIME DEFAULT CURRENT_TIMESTAMP, loja_id INTEGER DEFAULT 1)")
    garantir_coluna_loja(conn, "reservas")
    colunas_reservas = ["data_reserva TEXT", "horario TEXT", "qtd_pessoas INTEGER", "nome_cliente TEXT", "telefone_cliente TEXT", "pre_pedido TEXT", "status TEXT DEFAULT 'confirmada'", "criado_em DATETIME DEFAULT CURRENT_TIMESTAMP"]
    for col in colunas_reservas: add_column_safe("reservas", col)

    conn.execute("CREATE TABLE IF NOT EXISTS sabor_apelido (id INTEGER PRIMARY KEY AUTOINCREMENT, sabor_produto_id INTEGER, apelido TEXT, categoria TEXT, loja_id INTEGER DEFAULT 1)")
    garantir_coluna_loja(conn, "sabor_apelido")
    add_column_safe("sabor_apelido", "categoria TEXT")
    
    conn.execute("CREATE TABLE IF NOT EXISTS categoria_apelido (id INTEGER PRIMARY KEY AUTOINCREMENT, categoria_id TEXT, apelido TEXT, loja_id INTEGER DEFAULT 1)")
    garantir_coluna_loja(conn, "categoria_apelido")

    conn.execute("CREATE TABLE IF NOT EXISTS promocoes (id INTEGER PRIMARY KEY AUTOINCREMENT, categoria TEXT, produto_id INTEGER, nome_produto TEXT, desconto TEXT, loja_id INTEGER DEFAULT 1)")
    conn.execute("CREATE TABLE IF NOT EXISTS destaques_dia (id INTEGER PRIMARY KEY AUTOINCREMENT, categoria TEXT, produto_id INTEGER, nome_produto TEXT, loja_id INTEGER DEFAULT 1)")
    conn.execute("CREATE TABLE IF NOT EXISTS mais_pedidos (id INTEGER PRIMARY KEY AUTOINCREMENT, categoria TEXT, produto_id INTEGER, nome_produto TEXT, loja_id INTEGER DEFAULT 1)")
    
    for tabela in ["promocoes", "destaques_dia", "mais_pedidos"]: 
        garantir_coluna_loja(conn, tabela)
        add_column_safe(tabela, "categoria TEXT")

    garantir_coluna_loja(conn, "categorias_cardapio")
    add_column_safe("categorias_cardapio", "emoji TEXT")
    add_column_safe("categorias_cardapio", "ordem INTEGER DEFAULT 99")
    
    conn.execute("CREATE TABLE IF NOT EXISTS bairros_entrega (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, taxa REAL, loja_id INTEGER DEFAULT 1)")
    garantir_coluna_loja(conn, "bairros_entrega")
    conn.commit()

    conn.execute("CREATE TABLE IF NOT EXISTS mensagens_agendadas (id INTEGER PRIMARY KEY AUTOINCREMENT, texto TEXT, imagem_base64 TEXT, data_hora_envio DATETIME, status TEXT DEFAULT 'pendente', criado_em DATETIME DEFAULT CURRENT_TIMESTAMP, loja_id INTEGER DEFAULT 1)")
    garantir_coluna_loja(conn, "mensagens_agendadas")
    conn.commit()

@router.get("/configuracoes", response_class=HTMLResponse)
def ver_config(request: Request):
    loja_id = obter_loja_logada(request)
    perfil_usuario = obter_perfil_logado(request) # Injeta perfil para sumir as lixeiras
    
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row

    garantir_tabelas_sistema(conn, loja_id)
    garantir_coluna_loja(conn, "configuracoes")
    garantir_coluna_loja(conn, "chaves_pix")

    try:
        conn.execute("CREATE TABLE IF NOT EXISTS formas_pagamento (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, disponivel_wpp INTEGER DEFAULT 1, pede_detalhe INTEGER DEFAULT 0, pergunta_detalhe TEXT, loja_id INTEGER DEFAULT 1)")
        garantir_coluna_loja(conn, "formas_pagamento")
        try: conn.execute("ALTER TABLE formas_pagamento ADD COLUMN disponivel_wpp INTEGER DEFAULT 1")
        except: pass
        try: conn.execute("ALTER TABLE formas_pagamento ADD COLUMN pede_detalhe INTEGER DEFAULT 0")
        except: pass
        try: conn.execute("ALTER TABLE formas_pagamento ADD COLUMN pergunta_detalhe TEXT")
        except: pass

        count = conn.execute("SELECT COUNT(*) FROM formas_pagamento WHERE loja_id = ?", (loja_id,)).fetchone()[0]
        if count == 0:
            para_inserir = [("Dinheiro", 1, 1, "Vai precisar de troco para quanto? (Ou digite 'sem troco')", loja_id), ("Pix", 1, 0, "", loja_id), ("Cartão de Crédito", 1, 0, "", loja_id), ("Cartão de Débito", 1, 0, "", loja_id)]
            for f in para_inserir:
                try: conn.execute("INSERT INTO formas_pagamento (nome, disponivel_wpp, pede_detalhe, pergunta_detalhe, loja_id) VALUES (?, ?, ?, ?, ?)", f)
                except: pass
            conn.commit()
    except Exception: pass

    try:
        conn.execute("CREATE TABLE IF NOT EXISTS modos_envio (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, pede_endereco INTEGER DEFAULT 0, pede_horario INTEGER DEFAULT 0, pergunta_horario TEXT, disponivel_wpp INTEGER DEFAULT 1, pede_pagamento INTEGER DEFAULT 1, pede_obs_final INTEGER DEFAULT 1, pergunta_obs_final TEXT, loja_id INTEGER DEFAULT 1)")
        garantir_coluna_loja(conn, "modos_envio")
        def add_col_modo(coluna, definicao):
            try: conn.execute(f"ALTER TABLE modos_envio ADD COLUMN {coluna} {definicao}")
            except Exception: pass
            
        add_col_modo("pede_pagamento", "INTEGER DEFAULT 1")
        add_col_modo("pede_obs_final", "INTEGER DEFAULT 1")
        add_col_modo("pergunta_obs_final", "TEXT")

        count_modos = conn.execute("SELECT COUNT(*) FROM modos_envio WHERE loja_id = ?", (loja_id,)).fetchone()[0]
        if count_modos == 0:
            modos_init = [("Entrega", 1, 0, "", 1, 1, 1, "📝 Alguma observação geral para o pedido?\nDigite a observação ou 'não'.", loja_id),("Retirada", 0, 1, "Para qual horário você gostaria de agendar a retirada?", 1, 1, 1, "📝 Alguma observação geral para o pedido?\nDigite a observação ou 'não'.", loja_id)]
            for m in modos_init:
                try: conn.execute("INSERT INTO modos_envio (nome, pede_endereco, pede_horario, pergunta_horario, disponivel_wpp, pede_pagamento, pede_obs_final, pergunta_obs_final, loja_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", m)
                except: pass
            conn.commit()
    except Exception as e: pass

    try:
        conn.execute("CREATE TABLE IF NOT EXISTS plataformas_delivery (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, loja_id INTEGER DEFAULT 1)")
        garantir_coluna_loja(conn, "plataformas_delivery")
        count_plat = conn.execute("SELECT COUNT(*) FROM plataformas_delivery WHERE loja_id = ?", (loja_id,)).fetchone()[0]
        if count_plat == 0:
            for p in [("iFood", loja_id), ("Aiboo", loja_id), ("Plus Delivery", loja_id)]:
                try: conn.execute("INSERT INTO plataformas_delivery (nome, loja_id) VALUES (?, ?)", p)
                except: pass
            conn.commit()
    except Exception: pass

    rows = conn.execute("SELECT * FROM configuracoes WHERE loja_id = ?", (loja_id,)).fetchall()
    config = {row["chave"]: row["valor"] for row in rows}

    horarios = {}
    if config.get("horario_json"):
        try: horarios = json.loads(config["horario_json"])
        except Exception: horarios = {}

    pix_keys = [dict(r) for r in conn.execute("SELECT * FROM chaves_pix WHERE loja_id = ?", (loja_id,)).fetchall()]
    promocoes = [dict(r) for r in conn.execute("SELECT * FROM promocoes WHERE loja_id = ?", (loja_id,)).fetchall()]
    destaques = [dict(r) for r in conn.execute("SELECT * FROM destaques_dia WHERE loja_id = ?", (loja_id,)).fetchall()]
    mais_pedidos = [dict(r) for r in conn.execute("SELECT * FROM mais_pedidos WHERE loja_id = ?", (loja_id,)).fetchall()]
    
    formas_pagamento = []
    try: formas_pagamento = [dict(r) for r in conn.execute("SELECT * FROM formas_pagamento WHERE loja_id = ? ORDER BY nome ASC", (loja_id,)).fetchall()]
    except: pass

    modos_envio = []
    try: modos_envio = [dict(r) for r in conn.execute("SELECT * FROM modos_envio WHERE loja_id = ? ORDER BY id ASC", (loja_id,)).fetchall()]
    except: pass

    plataformas = []
    try: plataformas = [dict(r) for r in conn.execute("SELECT * FROM plataformas_delivery WHERE loja_id = ? ORDER BY nome ASC", (loja_id,)).fetchall()]
    except: pass

    reservas_db = []
    try: reservas_db = conn.execute("SELECT * FROM reservas WHERE loja_id = ? ORDER BY data_reserva DESC, horario DESC LIMIT 50", (loja_id,)).fetchall()
    except Exception: pass
    reservas = [dict(r) for r in reservas_db]

    categorias_db = [dict(r) for r in conn.execute("SELECT * FROM categorias_cardapio WHERE loja_id = ? ORDER BY ordem ASC, nome ASC", (loja_id,)).fetchall()]
    mapa_emojis = {c["id"]: (c["emoji"] or "📦") for c in categorias_db}

    bairros = [dict(r) for r in conn.execute("SELECT * FROM bairros_entrega WHERE loja_id = ? ORDER BY CASE WHEN taxa IS NOT NULL THEN 0 ELSE 1 END, nome ASC", (loja_id,)).fetchall()]

    todos_produtos = []
    mapa_produtos = {}
    tabelas_existentes = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

    for cat in categorias_db:
        cat_id = cat["id"]
        tabela = get_nome_tabela(cat_id)
        existe = False
        if tabela in tabelas_existentes: existe = True
        elif cat_id in tabelas_existentes: tabela = cat_id; existe = True

        if existe:
            try:
                garantir_coluna_loja(conn, tabela)
                itens = conn.execute(f"SELECT id, nome, disponivel, preco FROM {tabela} WHERE loja_id = ? ORDER BY nome", (loja_id,)).fetchall()
                for item in itens:
                    prod_obj = {"id": item["id"], "nome": item["nome"], "categoria": cat_id, "label_categoria": cat.get("nome", cat_id), "emoji_categoria": mapa_emojis.get(cat_id, "📦"), "disponivel": item["disponivel"] if item["disponivel"] is not None else 1, "preco": item["preco"]}
                    todos_produtos.append(prod_obj)
                    mapa_produtos[f"{cat_id}_{item['id']}"] = item["nome"]
            except Exception: pass

    adicionais_db = []
    mapa_adicionais = {}
    try:
        garantir_coluna_loja(conn, "produto_adicionais")
        adicionais_db = [dict(r) for r in conn.execute("SELECT id, nome, preco_adicional FROM produto_adicionais WHERE loja_id = ? ORDER BY nome", (loja_id,)).fetchall()]
        for ad in adicionais_db: mapa_adicionais[ad["id"]] = ad["nome"]
    except Exception: pass

    apelidos = []
    apelidos_vistos = set()
    try:
        raw_sabor = conn.execute("SELECT * FROM sabor_apelido WHERE loja_id = ? ORDER BY apelido", (loja_id,)).fetchall()
        for row in raw_sabor:
            r = dict(row)
            apelido_str = r["apelido"].lower().strip()
            if apelido_str in apelidos_vistos: continue
            apelidos_vistos.add(apelido_str)
            cat = r.get("categoria") or "pizza"
            pid = r.get("sabor_produto_id")
            if cat == "adicional":
                nome_prod = mapa_adicionais.get(pid, "Adicional/Opção")
                r["sabor_nome"] = f"➕ {nome_prod}"
            else:
                chave = f"{cat}_{pid}"
                nome_prod = mapa_produtos.get(chave, "Produto")
                emoji = mapa_emojis.get(cat, "📦")
                r["sabor_nome"] = f"{emoji} {nome_prod}"
            r["origin"] = "sabor"
            apelidos.append(r)

        raw_cat = conn.execute("SELECT * FROM categoria_apelido WHERE loja_id = ? ORDER BY apelido", (loja_id,)).fetchall()
        mapa_cat_nomes = {c["id"]: c.get("nome", c["id"]) for c in categorias_db}
        for row in raw_cat:
            r = dict(row)
            cat_id = r["categoria_id"]
            nome_cat = mapa_cat_nomes.get(cat_id, cat_id)
            r["sabor_nome"] = f"📂 CATEGORIA: {nome_cat}"
            r["origin"] = "categoria"
            apelidos.append(r)
    except Exception: pass

    conn.close()
    todos_produtos.sort(key=lambda x: (x["label_categoria"], x["nome"]))

    return templates.TemplateResponse(
        "configuracoes.html",
        {
            "request": request, "perfil": perfil_usuario, "config": config, "horarios": horarios, "pix_keys": pix_keys,
            "apelidos": apelidos, "promocoes": promocoes, "destaques": destaques,
            "mais_pedidos": mais_pedidos, "todos_produtos": todos_produtos,
            "adicionais_db": adicionais_db, "reservas": reservas, "active_page": "config",
            "categorias_db": categorias_db, "bairros": bairros, "mapa_emojis": mapa_emojis,
            "formas_pagamento": formas_pagamento, "plataformas": plataformas,
            "modos_envio": modos_envio
        },
    )

# ... (As demais rotas POST, PUT e DELETE da API de configurações continuam iguais)
# (Mas o bloqueio na função `obter_loja_logada` lá no início já protege todas elas simultaneamente!)

@router.post("/api/plataformas")
def criar_plataforma(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        nome = data.get("nome", "").strip()
        if not nome: return {"ok": False}
        conn.execute("INSERT INTO plataformas_delivery (nome, loja_id) VALUES (?, ?)", (nome, loja_id))
        conn.commit()
        return {"ok": True}
    except Exception as e: return {"ok": False, "erro": str(e)}
    finally: conn.close()

@router.put("/api/plataformas/{id}")
def atualizar_plataforma(request: Request, id: int, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        conn.execute("UPDATE plataformas_delivery SET nome=? WHERE id=? AND loja_id=?", (data.get("nome", "").strip(), id, loja_id))
        conn.commit()
        return {"ok": True}
    except Exception as e: return {"ok": False, "erro": str(e)}
    finally: conn.close()

@router.delete("/api/plataformas/{id}")
def excluir_plataforma(request: Request, id: int):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.execute("DELETE FROM plataformas_delivery WHERE id=? AND loja_id=?", (id, loja_id))
    conn.commit()
    conn.close()
    return {"ok": True}

@router.post("/api/formas_pagamento")
def criar_forma_pagamento(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        nome = data.get("nome", "").strip()
        wpp = 1 if data.get("disponivel_wpp") else 0
        det = 1 if data.get("pede_detalhe") else 0
        perg = data.get("pergunta_detalhe", "").strip()
        if not nome: return {"ok": False, "erro": "Nome inválido"}
        conn.execute("INSERT INTO formas_pagamento (nome, disponivel_wpp, pede_detalhe, pergunta_detalhe, loja_id) VALUES (?, ?, ?, ?, ?)", (nome, wpp, det, perg, loja_id))
        conn.commit()
        return {"ok": True}
    except Exception as e: return {"ok": False, "erro": str(e)}
    finally: conn.close()

@router.put("/api/formas_pagamento/{id}")
def atualizar_forma_pagamento(request: Request, id: int, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        nome = data.get("nome", "").strip()
        wpp = 1 if data.get("disponivel_wpp") else 0
        det = 1 if data.get("pede_detalhe") else 0
        perg = data.get("pergunta_detalhe", "").strip()
        if not nome: return {"ok": False, "erro": "Nome inválido"}
        conn.execute("UPDATE formas_pagamento SET nome=?, disponivel_wpp=?, pede_detalhe=?, pergunta_detalhe=? WHERE id=? AND loja_id=?", (nome, wpp, det, perg, id, loja_id))
        conn.commit()
        return {"ok": True}
    except Exception as e: return {"ok": False, "erro": str(e)}
    finally: conn.close()

@router.delete("/api/formas_pagamento/{id}")
def excluir_forma_pagamento(request: Request, id: int):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.execute("DELETE FROM formas_pagamento WHERE id=? AND loja_id=?", (id, loja_id))
    conn.commit()
    conn.close()
    return {"ok": True}

@router.post("/api/mais_pedidos")
def adicionar_mais_pedido(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        cat, pid, nome = data["produto"].split("|")
        conn.execute("INSERT INTO mais_pedidos (categoria, produto_id, nome_produto, loja_id) VALUES (?, ?, ?, ?)", (cat, int(pid), nome, loja_id))
        conn.commit()
        return {"ok": True}
    except Exception as e: return {"ok": False, "erro": str(e)}
    finally: conn.close()

@router.delete("/api/mais_pedidos/{id}")
def remover_mais_pedido(request: Request, id: int):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.execute("DELETE FROM mais_pedidos WHERE id=? AND loja_id=?", (id, loja_id))
    conn.commit()
    conn.close()
    return {"ok": True}

@router.post("/api/produtos/toggle")
def toggle_produto_disponivel(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        cat_id = data.get("categoria")
        prod_id = int(data.get("id"))
        novo_status = 1 if data.get("ativo") else 0
        tabela = get_nome_tabela(cat_id)
        check = conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{tabela}'").fetchone()
        if not check: tabela = cat_id
        
        conn.execute(f"UPDATE {tabela} SET disponivel = ? WHERE id = ? AND loja_id = ?", (novo_status, prod_id, loja_id))
        conn.commit()
        return {"ok": True}
    except Exception as e: return {"ok": False, "erro": str(e)}
    finally: conn.close()

@router.post("/api/configuracoes/geral")
async def salvar_config_geral(request: Request):
    loja_id = obter_loja_logada(request)
    form = await request.form()
    updates = {
        "loja_aberta": "1" if form.get("loja_aberta") else "0",
        "chat_ativo": "1" if form.get("chat_ativo") else "0",
        "restrito_cadastrados": "1" if form.get("restrito_cadastrados") else "0",
        "modo_reserva": form.get("modo_reserva", "humano"),
        "reserva_max_pessoas": form.get("reserva_max_pessoas", ""), 
        "tempo_entrega": form.get("tempo_entrega", ""),
        "taxa_entrega_padrao": form.get("taxa_entrega_padrao", "").replace(",", "."),
        "valor_minimo_pedido": form.get("valor_minimo_pedido", "").replace(",", "."),
        "msg_saudacao_nome": form.get("msg_saudacao_nome", ""),
        "msg_saudacao_padrao": form.get("msg_saudacao_padrao", ""),
        "msg_texto_cardapio": form.get("msg_texto_cardapio", ""),
        "msg_tempo_entrega": form.get("msg_tempo_entrega", ""),
        "msg_fila_estimativa": form.get("msg_fila_estimativa", ""),
        "msg_fila_vazia": form.get("msg_fila_vazia", ""),
        "msg_agradecimento": form.get("msg_agradecimento", ""),
    }
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    try:
        cats = conn.execute("SELECT id FROM categorias_cardapio WHERE loja_id = ?", (loja_id,)).fetchall()
        for c in cats:
            cat_id = c["id"]
            ativo = 1 if form.get(f"cat_{cat_id}") else 0
            conn.execute("UPDATE categorias_cardapio SET ativa=? WHERE id=? AND loja_id=?", (ativo, cat_id, loja_id))
    except Exception: pass
    
    dias = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]
    horario_dict = {}
    for dia in dias:
        horario_dict[dia] = {"inicio": form.get(f"h_{dia}_inicio", ""), "fim": form.get(f"h_{dia}_fim", ""), "fechado": True if form.get(f"h_{dia}_fechado") else False}
    updates["horario_json"] = json.dumps(horario_dict)
    
    garantir_coluna_loja(conn, "configuracoes")
    for chave, valor in updates.items():
        exists = conn.execute("SELECT 1 FROM configuracoes WHERE chave=? AND loja_id=?", (chave, loja_id)).fetchone()
        if exists: conn.execute("UPDATE configuracoes SET valor=? WHERE chave=? AND loja_id=?", (str(valor), chave, loja_id))
        else: conn.execute("INSERT OR REPLACE INTO configuracoes (chave, valor, loja_id) VALUES (?, ?, ?)", (chave, str(valor), loja_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/configuracoes", status_code=303)

@router.post("/api/categorias")
def criar_categoria(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        nome = data["nome"].strip()
        emoji = data.get("emoji", "📦").strip()
        cat_id = remover_acentos(nome.lower()).replace(" ", "_")
        
        garantir_coluna_loja(conn, "categorias_cardapio")
        conn.execute("INSERT INTO categorias_cardapio (id, nome, ativa, emoji, ordem, loja_id) VALUES (?, ?, 1, ?, 99, ?)", (cat_id, nome, emoji, loja_id))
        
        nome_tabela = cat_id 
        conn.execute(f"CREATE TABLE IF NOT EXISTS {nome_tabela} (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, preco REAL, descricao TEXT, disponivel INTEGER DEFAULT 1, ingredientes TEXT, tipo TEXT, loja_id INTEGER DEFAULT 1)")
        for col in ["ingredientes TEXT", "tipo TEXT", "loja_id INTEGER DEFAULT 1"]:
            try: conn.execute(f"ALTER TABLE {nome_tabela} ADD COLUMN {col}")
            except Exception: pass
        conn.commit()
        return {"ok": True}
    except Exception as e: return {"ok": False, "erro": str(e)}
    finally: conn.close()

@router.put("/api/categorias/{id}")
def atualizar_categoria(request: Request, id: str, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        if "ativa" in data and "nome" not in data:
            ativo = 1 if data["ativa"] else 0
            conn.execute("UPDATE categorias_cardapio SET ativa=? WHERE id=? AND loja_id=?", (ativo, id, loja_id))
        else:
            if "emoji" in data:
                conn.execute("UPDATE categorias_cardapio SET nome=?, emoji=? WHERE id=? AND loja_id=?", (data["nome"], data["emoji"], id, loja_id))
            else:
                conn.execute("UPDATE categorias_cardapio SET nome=? WHERE id=? AND loja_id=?", (data["nome"], id, loja_id))
        conn.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "erro": str(e)}
    finally:
        conn.close()

@router.delete("/api/categorias/{id}")
def excluir_categoria(request: Request, id: str):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        tabela = get_nome_tabela(id)
        tabelas_protegidas = ["configuracoes", "pedidos", "notificacoes", "sabor_apelido", "chaves_pix", "pedido_outros_itens", "cliente", "grupos_adicionais", "reservas", "categorias_cardapio", "sqlite_sequence", "bairros_entrega", "formas_pagamento", "plataformas_delivery"]
        if tabela in tabelas_protegidas or id in tabelas_protegidas: 
            return {"ok": False, "erro": "Tabela protegida!"}
        
        tabelas_auxiliares = [
            "promocoes", "destaques_dia", "mais_pedidos", 
            "produto_adicionais", "grupos_adicionais", "produto_variacoes", 
            "categoria_apelido", "sabor_apelido", "categorias_cardapio"
        ]
        for t in tabelas_auxiliares:
            garantir_coluna_loja(conn, t)

        queries_limpeza = [
            ("DELETE FROM promocoes WHERE categoria=? AND loja_id=?", (id, loja_id)),
            ("DELETE FROM destaques_dia WHERE categoria=? AND loja_id=?", (id, loja_id)),
            ("DELETE FROM mais_pedidos WHERE categoria=? AND loja_id=?", (id, loja_id)),
            ("DELETE FROM produto_adicionais WHERE grupo IN (SELECT id FROM grupos_adicionais WHERE categoria_alvo=? AND loja_id=?) AND loja_id=?", (id, loja_id, loja_id)),
            ("DELETE FROM grupos_adicionais WHERE categoria_alvo=? AND loja_id=?", (id, loja_id)),
            ("DELETE FROM produto_adicionais WHERE categoria_alvo=? AND loja_id=?", (id, loja_id)),
            ("DELETE FROM produto_variacoes WHERE categoria=? AND loja_id=?", (id, loja_id)),
            ("DELETE FROM categoria_apelido WHERE categoria_id=? AND loja_id=?", (id, loja_id)),
            ("DELETE FROM sabor_apelido WHERE categoria=? AND loja_id=?", (id, loja_id))
        ]

        for query, params in queries_limpeza:
            try: conn.execute(query, params)
            except Exception: pass 

        conn.execute("DELETE FROM categorias_cardapio WHERE id=? AND loja_id=?", (id, loja_id))
        try: conn.execute(f"DELETE FROM {tabela} WHERE loja_id=?", (loja_id,))
        except Exception: pass

        conn.commit()
        return {"ok": True}
    except Exception as e: return {"ok": False, "erro": str(e)}
    finally: conn.close()

@router.post("/api/destaques")
def adicionar_destaque(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        cat, pid, nome = data["produto"].split("|")
        conn.execute("INSERT INTO destaques_dia (categoria, produto_id, nome_produto, loja_id) VALUES (?, ?, ?, ?)", (cat, int(pid), nome, loja_id))
        conn.commit()
        return {"ok": True}
    except Exception as e: return {"ok": False, "erro": str(e)}
    finally: conn.close()

@router.delete("/api/destaques/{id}")
def remover_destaque(request: Request, id: int):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.execute("DELETE FROM destaques_dia WHERE id=? AND loja_id=?", (id, loja_id))
    conn.commit()
    conn.close()
    return {"ok": True}

@router.post("/api/promocoes")
def adicionar_promocao(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        cat, pid_str, nome_ref = data["produto"].split("|")
        conn.execute("INSERT INTO promocoes (categoria, produto_id, nome_produto, desconto, loja_id) VALUES (?, ?, ?, ?, ?)", (cat, int(pid_str), nome_ref, data["desconto"], loja_id))
        conn.commit()
        return {"ok": True}
    except Exception as e: return {"ok": False, "erro": str(e)}
    finally: conn.close()

@router.delete("/api/promocoes/{id}")
def remover_promocao(request: Request, id: int):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.execute("DELETE FROM promocoes WHERE id=? AND loja_id=?", (id, loja_id))
    conn.commit()
    conn.close()
    return {"ok": True}

@router.post("/api/pix")
def adicionar_pix(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    garantir_coluna_loja(conn, "chaves_pix")
    conn.execute("INSERT INTO chaves_pix (chave, titular, banco, loja_id) VALUES (?, ?, ?, ?)", (data["chave"], data["titular"], data["banco"], loja_id))
    conn.commit()
    conn.close()
    return {"ok": True}

@router.put("/api/pix/{id}")
def editar_pix(request: Request, id: int, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.execute("UPDATE configuracoes SET valor=? WHERE chave='pix_ativo_id' AND loja_id=?", (str(id), loja_id))
    conn.execute("UPDATE chaves_pix SET chave=?, titular=?, banco=? WHERE id=? AND loja_id=?", (data["chave"], data["titular"], data["banco"], id, loja_id))
    conn.commit()
    conn.close()
    return {"ok": True}

@router.delete("/api/pix/{id}")
def remover_pix(request: Request, id: int):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.execute("DELETE FROM chaves_pix WHERE id=? AND loja_id=?", (id, loja_id))
    conn.commit()
    conn.close()
    return {"ok": True}

@router.post("/api/pix/selecionar")
def selecionar_pix_ativo(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    
    exists = conn.execute("SELECT 1 FROM configuracoes WHERE chave='pix_ativo_id' AND loja_id=?", (loja_id,)).fetchone()
    if exists:
        conn.execute("UPDATE configuracoes SET valor=? WHERE chave='pix_ativo_id' AND loja_id=?", (str(data["id"]), loja_id))
    else:
        conn.execute("INSERT INTO configuracoes (chave, valor, loja_id) VALUES (?, ?, ?)", ('pix_ativo_id', str(data["id"]), loja_id))
        
    conn.commit()
    conn.close()
    return {"ok": True}

@router.post("/api/apelidos")
def adicionar_apelido(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        try: conn.execute("ALTER TABLE sabor_apelido ADD COLUMN categoria TEXT")
        except: pass
        parts = data["produto"].split("|", 2)
        if len(parts) < 3: return {"ok": False, "erro": "Inválido"}
        cat, pid, nome = parts
        apelido_limpo = data.get("apelido").lower().strip()
        if cat == "sistema_categoria": conn.execute("INSERT INTO categoria_apelido (categoria_id, apelido, loja_id) VALUES (?, ?, ?)", (pid, apelido_limpo, loja_id))
        elif cat == "adicional": conn.execute("INSERT INTO sabor_apelido (sabor_produto_id, apelido, categoria, loja_id) VALUES (?, ?, 'adicional', ?)", (int(pid), apelido_limpo, loja_id))
        else: conn.execute("INSERT INTO sabor_apelido (sabor_produto_id, apelido, categoria, loja_id) VALUES (?, ?, ?, ?)", (int(pid) if pid.isdigit() else 0, apelido_limpo, cat, loja_id))
        conn.commit()
        return {"ok": True}
    except Exception as e: return {"ok": False, "erro": str(e)}
    finally: conn.close()

@router.delete("/api/apelidos/{origin}/{id}")
def remover_apelido(request: Request, origin: str, id: int):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        if origin == "categoria": conn.execute("DELETE FROM categoria_apelido WHERE id=? AND loja_id=?", (id, loja_id))
        else: conn.execute("DELETE FROM sabor_apelido WHERE id=? AND loja_id=?", (id, loja_id))
        conn.commit()
        return {"ok": True}
    except Exception as e: return {"ok": False, "erro": str(e)}
    finally: conn.close()

@router.post("/api/bairros")
def adicionar_bairro(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        nome = data.get("nome", "").strip()
        taxa_str = str(data.get("taxa", ""))
        taxa_val = float(taxa_str.replace(",", ".")) if taxa_str.strip() else None
        if not nome: return {"ok": False, "erro": "Nome inválido"}
        conn.execute("INSERT INTO bairros_entrega (nome, taxa, loja_id) VALUES (?, ?, ?)", (nome, taxa_val, loja_id))
        conn.commit()
        return {"ok": True}
    except Exception as e: return {"ok": False, "erro": str(e)}
    finally: conn.close()

@router.put("/api/bairros/{id}")
def editar_bairro(request: Request, id: int, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        nome = data.get("nome", "").strip()
        taxa_str = str(data.get("taxa", ""))
        taxa_val = float(taxa_str.replace(",", ".")) if taxa_str.strip() else None
        if not nome: return {"ok": False, "erro": "Nome inválido"}
        conn.execute("UPDATE bairros_entrega SET nome=?, taxa=? WHERE id=? AND loja_id=?", (nome, taxa_val, id, loja_id))
        conn.commit()
        return {"ok": True}
    except Exception as e: return {"ok": False, "erro": str(e)}
    finally: conn.close()

@router.delete("/api/bairros/{id}")
def remover_bairro(request: Request, id: int):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.execute("DELETE FROM bairros_entrega WHERE id=? AND loja_id=?", (id, loja_id))
    conn.commit()
    conn.close()
    return {"ok": True}

@router.post("/api/reservas")
def criar_reserva_manual(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        for col in ["status TEXT DEFAULT 'confirmada'", "pre_pedido TEXT", "telefone_cliente TEXT"]:
            try: conn.execute(f"ALTER TABLE reservas ADD COLUMN {col}")
            except Exception: pass
        conn.execute("INSERT INTO reservas (data_reserva, horario, qtd_pessoas, nome_cliente, telefone_cliente, pre_pedido, status, loja_id) VALUES (?, ?, ?, ?, ?, ?, 'manual', ?)", (data.get("data"), data.get("horario"), int(data.get("pessoas", 1)), data.get("nome"), data.get("telefone", ""), data.get("obs"), loja_id))
        conn.commit()
        return {"ok": True}
    except Exception as e: return {"ok": False, "erro": str(e)}
    finally: conn.close()

@router.delete("/api/reservas/{id}")
def excluir_reserva(request: Request, id: int):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.execute("DELETE FROM reservas WHERE id=? AND loja_id=?", (id, loja_id))
    conn.commit()
    conn.close()
    return {"ok": True}

@router.post("/api/categorias/reordenar")
def reordenar_categorias(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        for item in data.get("ordem", []):
            conn.execute("UPDATE categorias_cardapio SET ordem = ? WHERE id = ? AND loja_id = ?", (int(item.get("ordem")), item.get("id"), loja_id))
        conn.commit()
        return {"ok": True}
    except Exception as e: return {"ok": False, "erro": str(e)}
    finally: conn.close()

# ==========================================
# ROTAS PARA MODOS DE ENVIO / ENTREGA
# ==========================================
@router.get("/api/modos_envio")
def listar_modos_envio(request: Request):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute("SELECT * FROM modos_envio WHERE loja_id = ? ORDER BY id", (loja_id,)).fetchall()]
    except Exception as e: 
        return []
    finally: conn.close()

@router.post("/api/modos_envio")
def criar_modo_envio(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO modos_envio 
            (nome, pede_endereco, pede_horario, pergunta_horario, disponivel_wpp, pede_pagamento, pede_obs_final, pergunta_obs_final, loja_id) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data["nome"], data.get("pede_endereco", 0), data.get("pede_horario", 0), data.get("pergunta_horario", ""), 
            data.get("disponivel_wpp", 1), data.get("pede_pagamento", 1), data.get("pede_obs_final", 1), data.get("pergunta_obs_final", ""), loja_id
        ))
        conn.commit()
        return {"ok": True}
    finally: conn.close()

@router.put("/api/modos_envio/{id}")
def editar_modo_envio(request: Request, id: int, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        if "apenas_status" in data:
            conn.execute("UPDATE modos_envio SET disponivel_wpp=? WHERE id=? AND loja_id=?", (data["disponivel_wpp"], id, loja_id))
        else:
            conn.execute("""
                UPDATE modos_envio 
                SET nome=?, pede_endereco=?, pede_horario=?, pergunta_horario=?, pede_pagamento=?, pede_obs_final=?, pergunta_obs_final=? 
                WHERE id=? AND loja_id=?
            """, (
                data["nome"], data.get("pede_endereco", 0), data.get("pede_horario", 0), data.get("pergunta_horario", ""),
                data.get("pede_pagamento", 1), data.get("pede_obs_final", 1), data.get("pergunta_obs_final", ""), id, loja_id
            ))
        conn.commit()
        return {"ok": True}
    finally: conn.close()

@router.delete("/api/modos_envio/{id}")
def deletar_modo_envio(request: Request, id: int):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM modos_envio WHERE id=? AND loja_id=?", (id, loja_id))
        conn.commit()
        return {"ok": True}
    finally: conn.close()

@router.get("/api/config_cadastro")
def listar_config_cadastro(request: Request):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    garantir_tabelas_sistema(conn, loja_id)
    
    conn.row_factory = sqlite3.Row
    res = [dict(r) for r in conn.execute("SELECT * FROM config_cadastro WHERE loja_id = ? ORDER BY ordem ASC", (loja_id,)).fetchall()]
    conn.close()
    return res

@router.post("/api/config_cadastro")
def adicionar_campo_cadastro(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        coluna = remover_acentos(data['label'].lower()).replace(" ", "_")
        conn.execute("""
            INSERT INTO config_cadastro (coluna, label, pergunta_wpp, ativo_wpp, obrigatorio, ordem, loja_id)
            VALUES (?, ?, ?, 1, ?, 99, ?)
        """, (coluna, data['label'], data['pergunta'], 1 if data.get('obrigatorio') else 0, loja_id))
        
        try: conn.execute(f"ALTER TABLE cliente ADD COLUMN {coluna} TEXT")
        except Exception: pass 
        
        conn.commit()
        return {"ok": True}
    finally: conn.close()

@router.delete("/api/config_cadastro/{id}")
def remover_campo_cadastro(request: Request, id: int):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    
    campo = conn.execute("SELECT coluna FROM config_cadastro WHERE id = ? AND loja_id = ?", (id, loja_id)).fetchone()
    if campo and campo["coluna"] in ['nome', 'cpf', 'rua', 'numero_casa', 'bairro', 'ponto_referencia']:
        conn.close()
        return {"ok": False, "erro": "Este é um campo padrão e não pode ser desmarcado ou removido."}
        
    conn.execute("DELETE FROM config_cadastro WHERE id = ? AND loja_id = ?", (id, loja_id))
    conn.commit()
    conn.close()
    return {"ok": True}

@router.put("/api/config_cadastro/{id}")
def atualizar_campo_cadastro(request: Request, id: int, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        conn.execute("""
            UPDATE config_cadastro 
            SET label = ?, pergunta_wpp = ?, ativo_wpp = ?, obrigatorio = ?
            WHERE id = ? AND loja_id = ?
        """, (data['label'], data['pergunta'], 1 if data.get('ativo') else 0, 1 if data.get('obrigatorio') else 0, id, loja_id))
        conn.commit()
        return {"ok": True}
    except Exception as e: return {"ok": False, "erro": str(e)}
    finally: conn.close()

@router.post("/api/config_cadastro/reordenar")
def reordenar_config_cadastro(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        lista_ordem = data.get("ordem", [])
        for item in lista_ordem:
            item_id = item.get("id")
            item_ordem = item.get("ordem")
            if item_id is not None and item_ordem is not None:
                conn.execute("UPDATE config_cadastro SET ordem = ? WHERE id = ? AND loja_id = ?", (int(item_ordem), int(item_id), loja_id))
        conn.commit()
        return {"ok": True}
    except Exception as e: return {"ok": False, "erro": str(e)}
    finally: conn.close()

def garantir_colunas_mensagens(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mensagens_agendadas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            texto TEXT,
            imagem_base64 TEXT,
            horario_envio TEXT,
            ativo INTEGER DEFAULT 1,
            ultima_data_envio TEXT,
            loja_id INTEGER DEFAULT 1
        )
    """)
    garantir_coluna_loja(conn, "mensagens_agendadas")
    try: conn.execute("ALTER TABLE mensagens_agendadas ADD COLUMN horario_envio TEXT")
    except: pass
    try: conn.execute("ALTER TABLE mensagens_agendadas ADD COLUMN ativo INTEGER DEFAULT 1")
    except: pass
    try: conn.execute("ALTER TABLE mensagens_agendadas ADD COLUMN ultima_data_envio TEXT")
    except: pass
    conn.commit()

@router.get("/api/mensagens_agendadas")
def listar_mensagens_agendadas(request: Request):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    garantir_colunas_mensagens(conn)
    try:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute("SELECT * FROM mensagens_agendadas WHERE loja_id = ? ORDER BY horario_envio ASC", (loja_id,)).fetchall()]
    except Exception as e: 
        return []
    finally: conn.close()

@router.post("/api/mensagens_agendadas")
def criar_mensagem_agendada(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO mensagens_agendadas (texto, imagem_base64, horario_envio, ativo, loja_id) 
            VALUES (?, ?, ?, ?, ?)
        """, (data.get("texto"), data.get("imagem_base64"), data.get("horario_envio"), 1 if data.get("ativo") else 0, loja_id))
        conn.commit()
        return {"ok": True}
    except Exception as e: return {"ok": False, "erro": str(e)}
    finally: conn.close()

@router.put("/api/mensagens_agendadas/{id}")
def editar_mensagem_agendada(request: Request, id: int, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        if "apenas_status" in data:
            conn.execute("UPDATE mensagens_agendadas SET ativo=? WHERE id=? AND loja_id=?", (1 if data.get("ativo") else 0, id, loja_id))
        else:
            ativo_val = 1 if data.get("ativo") else 0
            if data.get("atualizar_imagem"):
                conn.execute("UPDATE mensagens_agendadas SET texto=?, imagem_base64=?, horario_envio=?, ativo=? WHERE id=? AND loja_id=?", 
                             (data.get("texto"), data.get("imagem_base64"), data.get("horario_envio"), ativo_val, id, loja_id))
            else:
                conn.execute("UPDATE mensagens_agendadas SET texto=?, horario_envio=?, ativo=? WHERE id=? AND loja_id=?", 
                             (data.get("texto"), data.get("horario_envio"), ativo_val, id, loja_id))
        conn.commit()
        return {"ok": True}
    except Exception as e: return {"ok": False, "erro": str(e)}
    finally: conn.close()

@router.delete("/api/mensagens_agendadas/{id}")
def deletar_mensagem_agendada(request: Request, id: int):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM mensagens_agendadas WHERE id=? AND loja_id=?", (id, loja_id))
        conn.commit()
        return {"ok": True}
    except Exception as e: return {"ok": False, "erro": str(e)}
    finally: conn.close()