# route_pedidos.py

import requests
import os
import unicodedata
import sqlite3
import re
import time
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from storage import get_db_connection, templates
from storage import buscar_itens_do_pedido, buscar_cliente_completo
from storage.pedidos import migrar_status_confirmado
from storage.configuracoes import obter_config_valor

router = APIRouter()

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

def garantir_estrutura_tabelas(conn):
    tabelas = ['pedidos', 'pedido_outros_itens']
    try:
        for tabela in tabelas:
            cursor = conn.execute(f"PRAGMA table_info({tabela})")
            colunas = [row[1] for row in cursor.fetchall()]
            if "loja_id" not in colunas:
                conn.execute(f"ALTER TABLE {tabela} ADD COLUMN loja_id INTEGER DEFAULT 1")
                conn.commit()
    except Exception as e:
        print(f"⚠️ Erro ao checar estrutura em route_pedidos: {e}")

def aplicar_motoboy_padrao(pedido_id: int, conn, loja_id: int):
    try:
        p = conn.execute("SELECT entregador_id, tipo_entrega FROM pedidos WHERE id=? AND loja_id=?", (pedido_id, loja_id)).fetchone()
        if p and p["tipo_entrega"] and "Entrega" in str(p["tipo_entrega"]):
            if not p["entregador_id"] or str(p["entregador_id"]).strip() == "0":
                mb = conn.execute("SELECT valor FROM configuracoes WHERE chave='motoboy_padrao_id' AND loja_id=?", (loja_id,)).fetchone()
                if mb and mb[0] and str(mb[0]).strip():
                    conn.execute("UPDATE pedidos SET entregador_id=? WHERE id=? AND loja_id=?", (int(mb[0]), pedido_id, loja_id))
    except Exception as e:
        pass

def _resolver_prod_id(conn, prod_id, nome_item_db, cat_id, loja_id):
    if prod_id > 0: return prod_id
    if not nome_item_db or not cat_id: return 0
    try:
        from storage.configuracoes import get_nome_tabela
        tabela = get_nome_tabela(cat_id)
        check_tb = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tabela,)).fetchone()
        if not check_tb:
            tabela = cat_id
            check_tb = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tabela,)).fetchone()
        
        if check_tb:
            p_row = conn.execute(f"SELECT id FROM {tabela} WHERE nome = ? AND loja_id = ?", (nome_item_db, loja_id)).fetchone()
            if not p_row:
                p_row = conn.execute(f"SELECT id FROM {tabela} WHERE ? LIKE nome || '%' AND loja_id = ?", (nome_item_db, loja_id)).fetchone()
            if p_row:
                return int(p_row["id"])
    except Exception: pass
    return 0

def deduzir_estoque_pedido(pedido_id: int, loja_id: int):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row  
    try:
        try: conn.execute("ALTER TABLE ficha_tecnica_produto ADD COLUMN adicional_nome TEXT DEFAULT ''")
        except: pass
        try: conn.execute("ALTER TABLE pedidos ADD COLUMN estoque_baixado INTEGER DEFAULT 0")
        except: pass
        
        check = conn.execute("SELECT estoque_baixado FROM pedidos WHERE id = ? AND loja_id = ?", (pedido_id, loja_id)).fetchone()
        if check and check["estoque_baixado"] == 1: return 
            
        itens = conn.execute("SELECT * FROM pedido_outros_itens WHERE pedido_id = ? AND loja_id = ?", (pedido_id, loja_id)).fetchall()
        for item in itens:
            try: prod_id = int(item["produto_id"])
            except: prod_id = 0
            
            cat_id = str(item["tipo"]).strip()
            qtd_vendida = float(item["quantidade"])
            obs = item["observacao"] or ""
            
            nome_item_db = str(item["nome_item"] or "").strip()
            if not nome_item_db and obs:
                match_nm = re.search(r"\[NM:(.*?)\]", obs)
                if match_nm: nome_item_db = match_nm.group(1).strip()
            
            prod_id = _resolver_prod_id(conn, prod_id, nome_item_db, cat_id, loja_id)
            
            var_nome = "UNICO"
            match_tam = re.search(r"Tamanho:\s*([^.]*)", obs)
            if match_tam: var_nome = match_tam.group(1).strip()

            if prod_id > 0:
                f_prod = conn.execute("SELECT insumo_id, quantidade_gasta FROM ficha_tecnica_produto WHERE produto_id = ? AND tamanho IN (?, 'UNICO') AND (adicional_nome = '' OR adicional_nome IS NULL) AND loja_id = ?", (prod_id, var_nome, loja_id)).fetchall()
                for f in f_prod:
                    conn.execute("UPDATE estoque_insumos SET quantidade_atual = quantidade_atual - ? WHERE id = ? AND loja_id = ?", (f["quantidade_gasta"] * qtd_vendida, f["insumo_id"], loja_id))
            
            if cat_id:
                f_cat = conn.execute("SELECT insumo_id, quantidade_gasta FROM ficha_tecnica_produto WHERE categoria_id = ? AND produto_id = 0 AND tamanho IN (?, 'UNICO') AND (adicional_nome = '' OR adicional_nome IS NULL) AND loja_id = ?", (cat_id, var_nome, loja_id)).fetchall()
                for f in f_cat:
                    conn.execute("UPDATE estoque_insumos SET quantidade_atual = quantidade_atual - ? WHERE id = ? AND loja_id = ?", (f["quantidade_gasta"] * qtd_vendida, f["insumo_id"], loja_id))
                    
            adds_raw = item["adicionais"]
            if adds_raw:
                lista_adds = [x.strip() for x in adds_raw.split(",") if x.strip()]
                for add_nome in lista_adds:
                    f_add = []
                    if prod_id > 0: f_add = conn.execute("SELECT insumo_id, quantidade_gasta FROM ficha_tecnica_produto WHERE produto_id = ? AND tamanho IN (?, 'UNICO') AND adicional_nome = ? AND loja_id = ?", (prod_id, var_nome, add_nome, loja_id)).fetchall()
                    if not f_add and cat_id: f_add = conn.execute("SELECT insumo_id, quantidade_gasta FROM ficha_tecnica_produto WHERE categoria_id = ? AND produto_id = 0 AND tamanho IN (?, 'UNICO') AND adicional_nome = ? AND loja_id = ?", (cat_id, var_nome, add_nome, loja_id)).fetchall()
                    for f in f_add: conn.execute("UPDATE estoque_insumos SET quantidade_atual = quantidade_atual - ? WHERE id = ? AND loja_id = ?", (f["quantidade_gasta"] * qtd_vendida, f["insumo_id"], loja_id))

        try:
            pizzas = conn.execute("SELECT * FROM pedido_itens WHERE pedido_id = ?", (pedido_id,)).fetchall()
            for pizza in pizzas:
                qtd_vendida = float(pizza["quantidade"])
                tamanho = pizza["tamanho"] or "UNICO"
                
                f_cat = conn.execute("SELECT insumo_id, quantidade_gasta FROM ficha_tecnica_produto WHERE categoria_id = 'pizza' AND produto_id = 0 AND tamanho IN (?, 'UNICO') AND (adicional_nome = '' OR adicional_nome IS NULL) AND loja_id = ?", (tamanho, loja_id)).fetchall()
                for f in f_cat: conn.execute("UPDATE estoque_insumos SET quantidade_atual = quantidade_atual - ? WHERE id = ? AND loja_id = ?", (f["quantidade_gasta"] * qtd_vendida, f["insumo_id"], loja_id))
                
                borda = pizza["borda"]
                if borda:
                    f_add = conn.execute("SELECT insumo_id, quantidade_gasta FROM ficha_tecnica_produto WHERE categoria_id = 'pizza' AND produto_id = 0 AND tamanho IN (?, 'UNICO') AND adicional_nome = ? AND loja_id = ?", (tamanho, borda, loja_id)).fetchall()
                    for f in f_add: conn.execute("UPDATE estoque_insumos SET quantidade_atual = quantidade_atual - ? WHERE id = ? AND loja_id = ?", (f["quantidade_gasta"] * qtd_vendida, f["insumo_id"], loja_id))
        except Exception: pass

        conn.execute("UPDATE pedidos SET estoque_baixado = 1 WHERE id = ? AND loja_id = ?", (pedido_id, loja_id))
        conn.commit()
    except Exception as e: print(f"Erro ao deduzir estoque: {e}")
    finally: conn.close()

def restaurar_estoque_pedido(pedido_id: int, loja_id: int):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    try:
        check = conn.execute("SELECT estoque_baixado FROM pedidos WHERE id = ? AND loja_id = ?", (pedido_id, loja_id)).fetchone()
        if not check or check["estoque_baixado"] == 0: return 
            
        itens = conn.execute("SELECT * FROM pedido_outros_itens WHERE pedido_id = ? AND loja_id = ?", (pedido_id, loja_id)).fetchall()
        for item in itens:
            try: prod_id = int(item["produto_id"])
            except: prod_id = 0
            
            cat_id = str(item["tipo"]).strip()
            qtd_vendida = float(item["quantidade"])
            obs = item["observacao"] or ""
            
            nome_item_db = str(item["nome_item"] or "").strip()
            if not nome_item_db and obs:
                match_nm = re.search(r"\[NM:(.*?)\]", obs)
                if match_nm: nome_item_db = match_nm.group(1).strip()
            
            prod_id = _resolver_prod_id(conn, prod_id, nome_item_db, cat_id, loja_id)
            
            var_nome = "UNICO"
            match_tam = re.search(r"Tamanho:\s*([^.]*)", obs)
            if match_tam: var_nome = match_tam.group(1).strip()

            if prod_id > 0:
                f_prod = conn.execute("SELECT insumo_id, quantidade_gasta FROM ficha_tecnica_produto WHERE produto_id = ? AND tamanho IN (?, 'UNICO') AND (adicional_nome = '' OR adicional_nome IS NULL) AND loja_id = ?", (prod_id, var_nome, loja_id)).fetchall()
                for f in f_prod: conn.execute("UPDATE estoque_insumos SET quantidade_atual = quantidade_atual + ? WHERE id = ? AND loja_id = ?", (f["quantidade_gasta"] * qtd_vendida, f["insumo_id"], loja_id))
            
            if cat_id:
                f_cat = conn.execute("SELECT insumo_id, quantidade_gasta FROM ficha_tecnica_produto WHERE categoria_id = ? AND produto_id = 0 AND tamanho IN (?, 'UNICO') AND (adicional_nome = '' OR adicional_nome IS NULL) AND loja_id = ?", (cat_id, var_nome, loja_id)).fetchall()
                for f in f_cat: conn.execute("UPDATE estoque_insumos SET quantidade_atual = quantidade_atual + ? WHERE id = ? AND loja_id = ?", (f["quantidade_gasta"] * qtd_vendida, f["insumo_id"], loja_id))
                    
            adds_raw = item["adicionais"]
            if adds_raw:
                lista_adds = [x.strip() for x in adds_raw.split(",") if x.strip()]
                for add_nome in lista_adds:
                    f_add = []
                    if prod_id > 0: f_add = conn.execute("SELECT insumo_id, quantidade_gasta FROM ficha_tecnica_produto WHERE produto_id = ? AND tamanho IN (?, 'UNICO') AND adicional_nome = ? AND loja_id = ?", (prod_id, var_nome, add_nome, loja_id)).fetchall()
                    if not f_add and cat_id: f_add = conn.execute("SELECT insumo_id, quantidade_gasta FROM ficha_tecnica_produto WHERE categoria_id = ? AND produto_id = 0 AND tamanho IN (?, 'UNICO') AND adicional_nome = ? AND loja_id = ?", (cat_id, var_nome, add_nome, loja_id)).fetchall()
                    for f in f_add: conn.execute("UPDATE estoque_insumos SET quantidade_atual = quantidade_atual + ? WHERE id = ? AND loja_id = ?", (f["quantidade_gasta"] * qtd_vendida, f["insumo_id"], loja_id))

        try:
            pizzas = conn.execute("SELECT * FROM pedido_itens WHERE pedido_id = ?", (pedido_id,)).fetchall()
            for pizza in pizzas:
                qtd_vendida = float(pizza["quantidade"])
                tamanho = pizza["tamanho"] or "UNICO"
                
                f_cat = conn.execute("SELECT insumo_id, quantidade_gasta FROM ficha_tecnica_produto WHERE categoria_id = 'pizza' AND produto_id = 0 AND tamanho IN (?, 'UNICO') AND (adicional_nome = '' OR adicional_nome IS NULL) AND loja_id = ?", (tamanho, loja_id)).fetchall()
                for f in f_cat: conn.execute("UPDATE estoque_insumos SET quantidade_atual = quantidade_atual + ? WHERE id = ? AND loja_id = ?", (f["quantidade_gasta"] * qtd_vendida, f["insumo_id"], loja_id))
                
                borda = pizza["borda"]
                if borda:
                    f_add = conn.execute("SELECT insumo_id, quantidade_gasta FROM ficha_tecnica_produto WHERE categoria_id = 'pizza' AND produto_id = 0 AND tamanho IN (?, 'UNICO') AND adicional_nome = ? AND loja_id = ?", (tamanho, borda, loja_id)).fetchall()
                    for f in f_add: conn.execute("UPDATE estoque_insumos SET quantidade_atual = quantidade_atual + ? WHERE id = ? AND loja_id = ?", (f["quantidade_gasta"] * qtd_vendida, f["insumo_id"], loja_id))
        except Exception: pass

        conn.execute("UPDATE pedidos SET estoque_baixado = 0 WHERE id = ? AND loja_id = ?", (pedido_id, loja_id))
        conn.commit()
    except Exception as e: print(f"Erro ao estornar estoque: {e}")
    finally: conn.close()

def enviar_notificacao_whats(telefone, texto):
    try:
        from automate import enviar_mensagem_texto
        enviar_mensagem_texto(telefone, texto)
        return
    except ImportError: pass
    base_url = os.getenv("EVOLUTION_BASE_URL") or os.getenv("API_URL")
    api_key = os.getenv("EVOLUTION_APIKEY") or os.getenv("API_KEY")
    instance = os.getenv("EVOLUTION_INSTANCE") or os.getenv("INSTANCE_NAME", "cooking")
    if base_url and api_key:
        try:
            numero_envio = telefone.replace("+", "").replace("-", "").strip()
            if "@" not in numero_envio: numero_envio = f"{numero_envio}@s.whatsapp.net"
            requests.post(f"{base_url}/message/sendText/{instance}", json={"number": numero_envio, "text": texto}, headers={"apikey": api_key, "Content-Type": "application/json"}, timeout=5)
        except Exception: pass

@router.get("/", response_class=HTMLResponse)
@router.get("/pedidos", response_class=HTMLResponse)
def ver_pedidos(request: Request, filtro: str = "hoje", tipo: str = "todos", status: str = "todos", data_filtro: str = None):
    loja_id = obter_loja_logada(request)
    perfil_usuario = obter_perfil_logado(request) # Captura o perfil para a tela
    
    migrar_status_confirmado()
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    try:
        categorias = conn.execute("SELECT * FROM categorias_cardapio WHERE ativa = 1 AND loja_id = ? ORDER BY ordem ASC", (loja_id,)).fetchall()

        try:
            formas_pagamento = [dict(r) for r in conn.execute("SELECT * FROM formas_pagamento WHERE loja_id = ? ORDER BY nome ASC", (loja_id,)).fetchall()]
        except Exception:
            formas_pagamento = [{"nome": "Dinheiro", "pede_detalhe": 1}, {"nome": "Pix", "pede_detalhe": 0}, {"nome": "Cartão de Crédito", "pede_detalhe": 0}, {"nome": "Cartão de Débito", "pede_detalhe": 0}]

        try: plataformas = [dict(r) for r in conn.execute("SELECT * FROM plataformas_delivery WHERE loja_id = ? ORDER BY nome ASC", (loja_id,)).fetchall()]
        except Exception: plataformas = []

        colunas_fixas = ['nome', 'cpf', 'rua', 'numero_casa', 'bairro', 'ponto_referencia']
        colunas_extras = []
        try:
            valid_cols = [row[1] for row in conn.execute("PRAGMA table_info(cliente)").fetchall()]
            campos_cadastro = conn.execute("SELECT coluna, label FROM config_cadastro WHERE loja_id = ? ORDER BY ordem ASC", (loja_id,)).fetchall()
            for c_cad in campos_cadastro:
                if c_cad["coluna"] not in colunas_fixas and c_cad["coluna"] in valid_cols:
                    colunas_extras.append({"coluna": c_cad["coluna"], "label": c_cad["label"]})
        except Exception: pass

        extra_cols_sql = ", ".join([f"c.{ex['coluna']}" for ex in colunas_extras])
        if extra_cols_sql: extra_cols_sql = ", " + extra_cols_sql

        query = f"""
            SELECT p.id, p.status, STRFTIME('%H:%M', p.data_hora) as hora, STRFTIME('%d/%m', p.data_hora) as dia, 
            p.valor_total, p.tipo_entrega, p.forma_pagamento, p.detalhe_pagamento, p.entregador_id, COALESCE(c.nome, 'Cliente') as cliente_nome, 
            p.cliente_telefone as telefone, c.rua, c.numero_casa, c.bairro, c.ponto_referencia{extra_cols_sql}
            FROM pedidos p LEFT JOIN cliente c ON p.cliente_telefone = c.telefone AND c.loja_id = p.loja_id
            WHERE p.loja_id = {loja_id}
        """

        if filtro == "cancelados":
            query += " AND p.status IN ('CANCELADO', 'ABANDONADO')"
            if data_filtro: query += f" AND date(p.data_hora) = '{data_filtro}'"
        elif filtro == "todos":
            query += " AND p.status NOT IN ('CANCELADO', 'ABANDONADO', 'EXCLUIDO')"
            if data_filtro: query += f" AND date(p.data_hora) = '{data_filtro}'"
        else:
            if data_filtro: query += f" AND p.status NOT IN ('CANCELADO', 'ABANDONADO', 'EXCLUIDO') AND date(p.data_hora) = '{data_filtro}'"
            else: query += " AND p.status NOT IN ('CANCELADO', 'ABANDONADO', 'EXCLUIDO') AND date(p.data_hora) = date('now', 'localtime')"

        if tipo == "mesa": query += " AND p.tipo_entrega = 'Mesa'"
        elif tipo == "entrega": query += " AND p.tipo_entrega IN ('Entrega', 'Retirada')"

        if status in ["ABERTO", "EM_PREPARO", "SAIU_PARA_ENTREGA", "CONCLUIDO"]: query += f" AND p.status = '{status}'"

        query += " ORDER BY p.id DESC"

        pedidos_db = conn.execute(query).fetchall()
        lista_final = []
        totais = {"Dinheiro": 0.0, "Pix": 0.0, "Crédito": 0.0, "Débito": 0.0, "Total": 0.0}

        def clean_metodo(txt):
            if not txt: return "Outros"
            t = unicodedata.normalize('NFKD', str(txt)).encode('ASCII', 'ignore').decode('utf-8').lower()
            if "dinheiro" in t: return "Dinheiro"
            if "pix" in t: return "Pix"
            if "credito" in t: return "Crédito"
            if "debito" in t: return "Débito"
            return "Outros"

        for row in pedidos_db:
            p = dict(row)
            if not p["cliente_nome"] or str(p["cliente_nome"]).strip() == "None": p["cliente_nome"] = "Cliente"

            if p["tipo_entrega"] == "Entrega":
                end_parts = [p[k] for k in ["rua", "numero_casa", "bairro"] if p[k]]
                p["endereco_resumo"] = ", ".join([str(x) for x in end_parts])
            else: p["endereco_resumo"] = ""

            try: p["itens_pizzas"], p["itens_extras"] = buscar_itens_do_pedido(p["id"])
            except Exception: p["itens_pizzas"], p["itens_extras"] = [], []

            if not p["valor_total"]: p["valor_total"] = sum(i.get("preco", 0) * i.get("quantidade", 1) for i in p["itens_pizzas"] + p["itens_extras"])
                
            if p["status"] in ("EM_PREPARO", "SAIU_PARA_ENTREGA", "CONCLUIDO"):
                valor_pedido = float(p["valor_total"]) if p["valor_total"] else 0.0
                forma = str(p["forma_pagamento"] or "").strip()
                detalhe = str(p["detalhe_pagamento"] or "").strip()
                
                if "|" in detalhe and ":" in detalhe and "R$" in detalhe:
                    partes = detalhe.split("|")
                    for parte in partes:
                        match = re.search(r"([A-Za-zÀ-ÿ0-9_ ]+):\s*R\$\s*(\d+[.,]\d{2})", parte)
                        if match:
                            method = clean_metodo(match.group(1))
                            val = float(match.group(2).replace(",", "."))
                            if method in totais: totais[method] += val
                            totais["Total"] += val
                else:
                    match = re.search(r"([A-Za-zÀ-ÿ0-9_ ]+):\s*R\$\s*(\d+[.,]\d{2})", detalhe)
                    if match and ":" in detalhe and "R$" in detalhe:
                        method = clean_metodo(match.group(1))
                        val = float(match.group(2).replace(",", "."))
                        if method in totais: totais[method] += val
                        totais["Total"] += val
                    else:
                        m_final = clean_metodo(forma)
                        if m_final in totais: totais[m_final] += valor_pedido
                        totais["Total"] += valor_pedido

            lista_final.append(p)

        try:
            entregadores = conn.execute("SELECT id, nome FROM entregadores WHERE ativo = 1 AND loja_id = ? ORDER BY nome ASC", (loja_id,)).fetchall()
            lista_entregadores = [dict(e) for e in entregadores]
        except Exception: lista_entregadores = []

        return templates.TemplateResponse("pedidos.html", { 
            "request": request,
            "perfil": perfil_usuario, # <- ENVIANDO PARA O TEMPLATE BASE.HTML
            "pedidos": lista_final, 
            "categorias": [dict(c) for c in categorias], 
            "entregadores": lista_entregadores,
            "formas_pagamento": formas_pagamento,
            "plataformas": plataformas, 
            "colunas_extras": colunas_extras, 
            "filtro_atual": filtro, 
            "tipo_atual": tipo, 
            "status_atual": status, 
            "data_filtro": data_filtro,
            "totais": totais, 
            "page_title": "Pedidos" 
        })
    finally: conn.close()

CACHE_PEDIDOS_CHECK = { "last_update": 0, "ttl": 5.0, "data": {} }

@router.get("/api/pedidos/check")
def check_pedidos(request: Request, filtro: str = "hoje", tipo: str = "todos", status: str = "todos", data_filtro: str = None):
    loja_id = obter_loja_logada(request) 
    key = f"{loja_id}_{filtro}_{tipo}_{status}_{data_filtro}"
    headers_cache = {"Cache-Control": "public, max-age=5"}  

    if time.time() - CACHE_PEDIDOS_CHECK["last_update"] < CACHE_PEDIDOS_CHECK["ttl"]:
        if key in CACHE_PEDIDOS_CHECK["data"]: return JSONResponse(CACHE_PEDIDOS_CHECK["data"][key], headers=headers_cache)

    conn = get_db_connection()
    try:
        base = f"SELECT COUNT(*) FROM pedidos WHERE loja_id = {loja_id}"
        if filtro == "cancelados":
            base += " AND status IN ('CANCELADO', 'ABANDONADO')"
            if data_filtro: base += f" AND date(data_hora) = '{data_filtro}'"
        elif filtro == "todos":
            base += " AND status NOT IN ('CANCELADO', 'ABANDONADO', 'EXCLUIDO')"
            if data_filtro: base += f" AND date(data_hora) = '{data_filtro}'"
        else:
            if data_filtro: base += f" AND status NOT IN ('CANCELADO', 'ABANDONADO', 'EXCLUIDO') AND date(data_hora) = '{data_filtro}'"
            else: base += " AND status NOT IN ('CANCELADO', 'ABANDONADO', 'EXCLUIDO') AND date(data_hora) = date('now', 'localtime')"
        
        if tipo == "mesa": base += " AND tipo_entrega = 'Mesa'"
        elif tipo == "entrega": base += " AND tipo_entrega IN ('Entrega', 'Retirada')"
            
        if status in ["ABERTO", "EM_PREPARO", "SAIU_PARA_ENTREGA", "CONCLUIDO"]: base += f" AND status = '{status}'"
            
        count = conn.execute(base).fetchone()[0]
        payload = {"count": count}
        CACHE_PEDIDOS_CHECK["data"][key] = payload
        CACHE_PEDIDOS_CHECK["last_update"] = time.time()
        return JSONResponse(payload, headers=headers_cache)
    except Exception: return JSONResponse({"count": -1}, headers=headers_cache)
    finally: conn.close()

@router.get("/api/pedidos/promocoes")
def api_obter_promocoes_pedidos(request: Request):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    try: return [dict(r) for r in conn.execute("SELECT * FROM promocoes WHERE loja_id = ?", (loja_id,)).fetchall()]
    except Exception: return []
    finally: conn.close()

@router.get("/api/pedidos/buscar_produtos")
def api_buscar_produtos_global(request: Request, q: str):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    resultados = []
    try:
        from storage.configuracoes import get_nome_tabela
        categorias = conn.execute("SELECT id, nome, emoji FROM categorias_cardapio WHERE ativa = 1 AND loja_id = ?", (loja_id,)).fetchall()
        termo = f"%{q.lower()}%"
        for cat in categorias:
            cat_id = cat["id"]
            tabela = get_nome_tabela(cat_id)
            check = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tabela,)).fetchone()
            if not check:
                tabela = cat_id
                check = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tabela,)).fetchone()
            
            if check:
                try:
                    prods = conn.execute(f"SELECT id, nome, preco, descricao FROM {tabela} WHERE disponivel=1 AND loja_id = ? AND LOWER(nome) LIKE ? LIMIT 15", (loja_id, termo)).fetchall()
                except:
                    prods = conn.execute(f"SELECT id, nome, preco, descricao FROM {tabela} WHERE disponivel=1 AND LOWER(nome) LIKE ? LIMIT 15", (termo,)).fetchall()
                for p in prods:
                    resultados.append({
                        "categoria_id": cat_id,
                        "categoria_nome": cat["nome"],
                        "emoji": cat["emoji"] or "",
                        "produto_id": p["id"],
                        "nome": p["nome"],
                        "preco": p["preco"],
                        "descricao": p["descricao"]
                    })
        return resultados
    except Exception as e: return []
    finally: conn.close()

@router.post("/api/status/{id}/{status}")
def atualizar_status(request: Request, id: int, status: str):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        garantir_estrutura_tabelas(conn)
        status_antigo_row = conn.execute("SELECT status FROM pedidos WHERE id=? AND loja_id=?", (id, loja_id)).fetchone()
        if not status_antigo_row: return {"ok": False, "erro": "Acesso negado"}
        status_antigo = status_antigo_row[0]
        
        conn.execute("UPDATE pedidos SET status=?, data_hora=datetime('now','localtime') WHERE id=? AND loja_id=?", (status, id, loja_id))
        aplicar_motoboy_padrao(id, conn, loja_id)
        conn.commit()
        CACHE_PEDIDOS_CHECK["last_update"] = 0

        if status == "CONCLUIDO" and status_antigo != "CONCLUIDO": deduzir_estoque_pedido(id, loja_id)
        elif status in ["CANCELADO", "ABANDONADO", "ABERTO", "EM_PREPARO"] and status_antigo == "CONCLUIDO": restaurar_estoque_pedido(id, loja_id)

        if status == "SAIU_PARA_ENTREGA":
            pedido = conn.execute("SELECT p.cliente_telefone, c.nome, p.detalhe_pagamento, p.valor_total, p.forma_pagamento FROM pedidos p LEFT JOIN cliente c ON p.cliente_telefone = c.telefone AND c.loja_id = p.loja_id WHERE p.id=? AND p.loja_id=?",(id, loja_id)).fetchone()
            if pedido and pedido["cliente_telefone"] and pedido["cliente_telefone"] != "00000000000":
                nome_cli = pedido["nome"]
                if not nome_cli or str(nome_cli).strip() == "None": nome_cli = "Cliente"

                msg = f"🛵 *Seu pedido #{id} saiu para entrega!*\n\nOlá {nome_cli}, seu pedido já está com nosso entregador."
                detalhe_str = pedido["detalhe_pagamento"] or ""
                forma_str = pedido["forma_pagamento"] or ""

                if "dinheiro" in forma_str.lower() or "dinheiro" in detalhe_str.lower():
                    troco_msg = ""
                    match_entregue = re.search(r"(?:Troco|troco).*?(\d+[.,]\d{2}|\d+)", detalhe_str)
                    valor_a_pagar = float(pedido["valor_total"])
                    match_valor_cobrado = re.search(r"Dinheiro.*?R\$\s*(\d+[.,]\d{2})", detalhe_str)
                    
                    if match_valor_cobrado: valor_a_pagar = float(match_valor_cobrado.group(1).replace(",", "."))
                    if match_entregue:
                        valor_entregue = float(match_entregue.group(1).replace(",", "."))
                        if valor_entregue > valor_a_pagar:
                            troco = valor_entregue - valor_a_pagar
                            troco_msg = f"\n\n💵 *Troco:* Levar R$ {troco:.2f} (p/ R$ {valor_entregue:.2f})"
                    if troco_msg: msg += troco_msg
                    elif detalhe_str: msg += f"\n\n💵 *Obs Pagamento:* {detalhe_str}"

                msg += "\n\nBom apetite! 😋"
                enviar_notificacao_whats(pedido["cliente_telefone"], msg)

        return {"ok": True}
    except Exception as e: return {"ok": False}
    finally: conn.close()

@router.delete("/api/pedidos/{id}")
def excluir_pedido(request: Request, id: int):
    loja_id = obter_loja_logada(request)
    perfil_usuario = obter_perfil_logado(request)
    
    # BLOQUEIO DE SEGURANÇA NO BACKEND: Apenas admin pode excluir
    if perfil_usuario not in ["dono", "admin"]:
        return {"ok": False, "erro": "Acesso negado. Apenas administradores podem excluir pedidos."}
        
    conn = get_db_connection()
    if not conn.execute("SELECT 1 FROM pedidos WHERE id=? AND loja_id=?", (id, loja_id)).fetchone():
        conn.close()
        return {"ok": False, "erro": "Acesso negado"}
        
    restaurar_estoque_pedido(id, loja_id)
    conn.execute("DELETE FROM pedido_outros_itens WHERE pedido_id=? AND loja_id=?", (id, loja_id))
    conn.execute("DELETE FROM pedidos WHERE id=? AND loja_id=?", (id, loja_id))
    conn.commit()
    conn.close()
    CACHE_PEDIDOS_CHECK["last_update"] = 0
    return {"ok": True}

@router.get("/pedidos/editar/{id}", response_class=HTMLResponse)
def editar_pedido_page(request: Request, id: int):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    try:
        pedido_row = conn.execute("""
            SELECT p.*, COALESCE(c.nome, '') as cliente_nome, c.cpf, c.rua, c.numero_casa, c.bairro, c.ponto_referencia 
            FROM pedidos p 
            LEFT JOIN cliente c ON p.cliente_telefone = c.telefone AND c.loja_id = p.loja_id
            WHERE p.id = ? AND p.loja_id = ?
        """, (id, loja_id)).fetchone()
        
        if not pedido_row: return HTMLResponse("Pedido não encontrado", status_code=404)
        pedido = dict(pedido_row)
        
        nome_sujo = str(pedido.get("cliente_nome", ""))
        if nome_sujo.strip().lower() in ["none", ""]:
            c_extra = buscar_cliente_completo(pedido["cliente_telefone"])
            pedido["cliente_nome"] = c_extra.get("nome", "") if c_extra else ""
        else: pedido["cliente_nome"] = nome_sujo

        if pedido.get("valor_total") is None: pedido["valor_total"] = 0.0

        pizzas, extras = buscar_itens_do_pedido(id)
        lista_itens = []
        for p in pizzas:
            nome_final = p["sabores"]
            tamanho_display = p["tamanho"]
            tamanho_core = ""
            if "Pizza (" in tamanho_display: tamanho_core = (tamanho_display.replace("Pizza (", "").replace(")", "").strip())
            if tamanho_display and tamanho_core not in nome_final: nome_final = f"{tamanho_display} - {nome_final}"
            elif not tamanho_display and "Pizza" not in nome_final: nome_final = f"Pizza - {nome_final}"
            
            detalhes = []
            if p["borda"]: detalhes.append(f"Borda: {p['borda']}")
            if p["observacao"]: detalhes.append(f"Obs: {p['observacao']}")
            
            lista_itens.append({"categoria": "pizza", "produto_id": 0, "nome": nome_final, "variacao_nome": tamanho_core, "quantidade": p["quantidade"], "total": p["preco"] * p["quantidade"], "total_unitario": p["preco"], "detalhes": " | ".join(detalhes), "observacao": p["observacao"], "lista_adicionais": [{"nome": p["borda"], "preco": 0}] if p["borda"] else []})
            
        for e in extras:
            detalhes = []
            if e["adicionais"]: detalhes.append(str(e["adicionais"]))
            if e["observacao"]: detalhes.append(f"Obs: {e['observacao']}")
            lista_itens.append({"categoria": "item", "produto_id": 0, "nome": e["nome_item"], "quantidade": e["quantidade"], "total": e["preco"] * e["quantidade"], "total_unitario": e["preco"], "detalhes": " | ".join(detalhes), "observacao": e["observacao"], "lista_adicionais": []})

        try: formas_pagamento = conn.execute("SELECT * FROM formas_pagamento WHERE loja_id = ?", (loja_id,)).fetchall()
        except: formas_pagamento = []
        
        try: plataformas = conn.execute("SELECT * FROM plataformas_delivery WHERE loja_id = ?", (loja_id,)).fetchall()
        except: plataformas = []
        
        try: bairros = conn.execute("SELECT * FROM bairros_entrega WHERE loja_id = ?", (loja_id,)).fetchall()
        except: bairros = []
        
        taxa_padrao_row = conn.execute("SELECT valor FROM configuracoes WHERE chave = 'taxa_entrega_padrao' AND loja_id = ?", (loja_id,)).fetchone()
        taxa_padrao = taxa_padrao_row["valor"] if taxa_padrao_row else "0.00"

        categorias = conn.execute("SELECT * FROM categorias_cardapio WHERE ativa = 1 AND loja_id = ? ORDER BY ordem ASC", (loja_id,)).fetchall()
        variacoes = conn.execute("SELECT nome, max_sabores FROM produto_variacoes WHERE categoria='pizza' AND loja_id = ?", (loja_id,)).fetchall()
        regras_sabores = {v["nome"].lower(): v["max_sabores"] for v in variacoes}

        return templates.TemplateResponse("imprimir_pedido.html", { "request": request, "pedido": pedido, "itens_json": lista_itens, "categorias": [dict(c) for c in categorias], "regras_sabores_json": regras_sabores, "formas_pagamento": [dict(f) for f in formas_pagamento], "plataformas": [dict(p) for p in plataformas], "bairros": [dict(b) for b in bairros], "taxa_padrao": taxa_padrao })
    finally: conn.close()

@router.get("/pedidos/cupom/{id}", response_class=HTMLResponse)
def cupom_pedido_page(request: Request, id: int):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    try:
        pedido = conn.execute("SELECT p.*, c.nome as cliente_nome, c.cpf, c.telefone, STRFTIME('%d/%m/%Y %H:%M', p.data_hora) as data_formatada, c.rua || ', ' || c.numero_casa || ' - ' || c.bairro as endereco_completo, c.ponto_referencia, c.bairro FROM pedidos p LEFT JOIN cliente c ON p.cliente_telefone = c.telefone AND c.loja_id = p.loja_id WHERE p.id = ? AND p.loja_id = ?", (id, loja_id)).fetchone()
        if not pedido: return HTMLResponse("Pedido não encontrado", status_code=404)

        p_dict = dict(pedido)
        if p_dict.get("valor_total") is None: p_dict["valor_total"] = 0.0
        if p_dict.get("forma_pagamento") is None: p_dict["forma_pagamento"] = "A definir"
        if p_dict.get("detalhe_pagamento") is None: p_dict["detalhe_pagamento"] = ""

        nome_sujo = str(p_dict.get("cliente_nome", ""))
        if nome_sujo.strip() == "None" or nome_sujo.strip() == "":
            c_extra = buscar_cliente_completo(p_dict["cliente_telefone"])
            if c_extra and c_extra.get("nome"): p_dict["cliente_nome"] = c_extra["nome"]
            if c_extra and c_extra.get("cpf"): p_dict["cpf"] = c_extra["cpf"]
        else: p_dict["cliente_nome"] = nome_sujo

        pizzas, extras = buscar_itens_do_pedido(id)
        return templates.TemplateResponse("detalhe_pedido.html", {"request": request, "p": p_dict, "pizzas": pizzas, "extras": extras})
    finally: conn.close()

@router.put("/api/pedidos/{id}")
def atualizar_pedido_existente(request: Request, id: int, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        try: conn.execute("ALTER TABLE pedido_outros_itens ADD COLUMN produto_id INTEGER")
        except: pass
        try: conn.execute("ALTER TABLE pedido_outros_itens ADD COLUMN nome_item TEXT")
        except: pass

        status_row = conn.execute("SELECT status FROM pedidos WHERE id=? AND loja_id=?", (id, loja_id)).fetchone()
        if not status_row: return {"ok": False, "erro": "Acesso negado"}
        
        is_concluido = status_row and status_row[0] == "CONCLUIDO"
        if is_concluido: restaurar_estoque_pedido(id, loja_id)

        is_caixa_rapido = data.get("is_caixa_rapido", False)
        tel_raw = data.get("telefone", "")
        tel = "".join([c for c in tel_raw if c.isdigit()])
        if is_caixa_rapido or not tel: tel = "00000000000"

        nome_cliente = data.get("nome")
        if is_caixa_rapido: nome_cliente = "Caixa Rápido"
        elif not nome_cliente or str(nome_cliente).strip() == "": nome_cliente = "Cliente"

        pagamentos = data.get("pagamentos", [])
        if pagamentos:
            formas = sorted(list(set([p.get("metodo", "") for p in pagamentos])))
            forma_pgt = " + ".join(formas)
            detalhes = " | ".join([f"{p.get('metodo')}: R$ {float(p.get('valor', 0)):.2f}" + (f" ({p.get('detalhe')})" if p.get("detalhe") else "") for p in pagamentos])
        else:
            forma_pgt = data.get("forma_pagamento", "Dinheiro")
            detalhes = data.get("detalhe_pagamento", "")

        end = data.get("endereco", {})
        
        if not is_caixa_rapido:
            if conn.execute("SELECT 1 FROM cliente WHERE telefone=? AND loja_id=?", (tel, loja_id)).fetchone():
                conn.execute("UPDATE cliente SET nome=?, rua=?, numero_casa=?, bairro=?, ponto_referencia=? WHERE telefone=? AND loja_id=?", (nome_cliente, end.get("rua"), end.get("numero"), end.get("bairro"), end.get("ref"), tel, loja_id))

        conn.execute("UPDATE pedidos SET cliente_telefone=?, tipo_entrega=?, forma_pagamento=?, detalhe_pagamento=?, valor_total=?, data_hora=datetime('now', 'localtime') WHERE id=? AND loja_id=?", (tel, data.get("tipo_entrega"), forma_pgt, detalhes, float(data.get("valor_total", 0)), id, loja_id))
        aplicar_motoboy_padrao(id, conn, loja_id)

        conn.execute("DELETE FROM pedido_outros_itens WHERE pedido_id=? AND loja_id=?", (id, loja_id))
        for item in data.get("itens", []):
            obs_raw = item.get("observacao", "")
            nome_item = item.get("nome", "")
            var_nome = item.get("variacao_nome", "")
            if var_nome:
                pattern = re.compile(rf"^(Pizza\s*)?(\(?{re.escape(var_nome)}\)?\s*)?(-?\s*)?", re.IGNORECASE)
                nome_item = pattern.sub("", nome_item).strip()
            obs_final = obs_raw
            if nome_item and f"[NM:{nome_item}]" not in obs_final: obs_final = f"[NM:{nome_item}] {obs_final}".strip()
            if var_nome and "Tamanho:" not in obs_final: obs_final = f"Tamanho: {var_nome}. {obs_final}"
            str_adds = ", ".join([f"{a['nome']}" for a in item.get("lista_adicionais", [])])
            price = (item.get("total_unitario") or (item.get("total") / item.get("quantidade")) if item.get("quantidade") else 0)
            
            conn.execute("INSERT INTO pedido_outros_itens (pedido_id, tipo, produto_id, nome_item, quantidade, preco_vendido, observacao, adicionais, loja_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (id, item["categoria"], item["produto_id"], nome_item, item["quantidade"], price, obs_final, str_adds, loja_id))
            
        conn.commit()
        if is_concluido: deduzir_estoque_pedido(id, loja_id)
        CACHE_PEDIDOS_CHECK["last_update"] = 0
        return {"ok": True}
    except Exception as e: return {"ok": False, "erro": str(e)}
    finally: conn.close()