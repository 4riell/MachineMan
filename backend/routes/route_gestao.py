# routes/route_gestao.py

import sqlite3
import re
import calendar
import unicodedata
from datetime import datetime, date
from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from storage import templates, get_db_connection
from storage.configuracoes import get_nome_tabela

import pandas as pd
import io
router = APIRouter()

# ==========================================
# FUNÇÕES DE SEGURANÇA E AUTO-CURA (SAAS)
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
            
        if perfil not in ["dono", "admin"]:
            raise HTTPException(
                status_code=403, 
                detail="Acesso restrito. Apenas administradores podem acessar a Gestão Financeira e Estoque."
            )
            
        return int(usuario_data["loja_id"])

def adicionar_meses(data_original, meses_a_adicionar):
    mes = data_original.month - 1 + meses_a_adicionar
    ano = data_original.year + mes // 12
    mes = mes % 12 + 1
    dia = min(data_original.day, calendar.monthrange(ano, mes)[1])
    return date(ano, mes, dia)

def remover_acentos(txt):
    if not txt: return ""
    return unicodedata.normalize('NFKD', str(txt)).encode('ASCII', 'ignore').decode('utf-8').lower()

def get_formas_pagamento_validas(conn, loja_id):
    try:
        rows = conn.execute("SELECT nome FROM formas_pagamento WHERE loja_id=? ORDER BY nome ASC", (loja_id,)).fetchall()
        if rows: return [r["nome"] for r in rows]
    except Exception: pass
    return ["Dinheiro", "Pix", "Cartão de Crédito", "Cartão de Débito"]

def categorizar_metodo_dinamico(m_str, formas_validas):
    m = remover_acentos(str(m_str)).strip()
    for f in formas_validas:
        if remover_acentos(f) == m: return f
    for f in sorted(formas_validas, key=len, reverse=True):
        if remover_acentos(f) in m: return f
    return 'Outros'

def inicializar_tabelas_gestao():
    conn = get_db_connection()
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS estoque_insumos (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, unidade_medida TEXT NOT NULL, quantidade_atual REAL DEFAULT 0, estoque_minimo REAL DEFAULT 0, custo_medio REAL DEFAULT 0, loja_id INTEGER DEFAULT 1)")
        conn.execute("CREATE TABLE IF NOT EXISTS estoque_entradas (id INTEGER PRIMARY KEY AUTOINCREMENT, insumo_id INTEGER, data_compra DATETIME DEFAULT CURRENT_TIMESTAMP, quantidade_adicionada REAL, custo_total REAL, loja_id INTEGER DEFAULT 1, FOREIGN KEY(insumo_id) REFERENCES estoque_insumos(id))")
        conn.execute("CREATE TABLE IF NOT EXISTS despesas (id INTEGER PRIMARY KEY AUTOINCREMENT, descricao TEXT NOT NULL, valor REAL NOT NULL, data_vencimento DATE, data_pagamento DATE, status TEXT DEFAULT 'pendente', categoria TEXT DEFAULT 'fixa', despesa_fixa_id INTEGER, loja_id INTEGER DEFAULT 1)")
        conn.execute("CREATE TABLE IF NOT EXISTS ficha_tecnica_produto (id INTEGER PRIMARY KEY AUTOINCREMENT, produto_id INTEGER, categoria_id TEXT, insumo_id INTEGER, quantidade_gasta REAL, tamanho TEXT DEFAULT 'UNICO', loja_id INTEGER DEFAULT 1, FOREIGN KEY(insumo_id) REFERENCES estoque_insumos(id))")
        conn.execute("CREATE TABLE IF NOT EXISTS despesas_fixas (id INTEGER PRIMARY KEY AUTOINCREMENT, descricao TEXT NOT NULL, valor REAL NOT NULL, dia_vencimento INTEGER NOT NULL, categoria TEXT DEFAULT 'fixa', loja_id INTEGER DEFAULT 1)")
        conn.execute("CREATE TABLE IF NOT EXISTS entregadores (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, telefone TEXT, taxa_padrao REAL DEFAULT 0, ativo INTEGER DEFAULT 1, loja_id INTEGER DEFAULT 1)")
        conn.execute("CREATE TABLE IF NOT EXISTS taxas_pagamento (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, taxa_percentual REAL DEFAULT 0, loja_id INTEGER DEFAULT 1)")
        conn.execute("CREATE TABLE IF NOT EXISTS funcionarios (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, cargo TEXT, salario_base REAL DEFAULT 0, dia_pagamento INTEGER DEFAULT 5, ativo INTEGER DEFAULT 1, loja_id INTEGER DEFAULT 1)")
        conn.execute("CREATE TABLE IF NOT EXISTS funcionario_extrato (id INTEGER PRIMARY KEY AUTOINCREMENT, funcionario_id INTEGER, tipo_lancamento TEXT, valor REAL NOT NULL, data_lancamento DATE, descricao TEXT, despesa_id INTEGER, loja_id INTEGER DEFAULT 1, FOREIGN KEY(funcionario_id) REFERENCES funcionarios(id), FOREIGN KEY(despesa_id) REFERENCES despesas(id))")
        conn.execute("CREATE TABLE IF NOT EXISTS motoboy_extrato (id INTEGER PRIMARY KEY AUTOINCREMENT, entregador_id INTEGER, tipo_lancamento TEXT, valor REAL NOT NULL, data_lancamento DATE, descricao TEXT, loja_id INTEGER DEFAULT 1)")
        
        tabelas = [
            "estoque_insumos", "estoque_entradas", "despesas", "ficha_tecnica_produto", 
            "despesas_fixas", "entregadores", "taxas_pagamento", "funcionarios", 
            "funcionario_extrato", "motoboy_extrato", "formas_pagamento"
        ]
        for t in tabelas:
            try: conn.execute(f"ALTER TABLE {t} ADD COLUMN loja_id INTEGER DEFAULT 1")
            except: pass

        try: conn.execute("ALTER TABLE pedidos ADD COLUMN entregador_id INTEGER")
        except: pass
        try: conn.execute("ALTER TABLE pedidos ADD COLUMN taxa_entrega REAL DEFAULT 0")
        except: pass
        try: conn.execute("ALTER TABLE entregadores ADD COLUMN tipo_repasse TEXT DEFAULT 'padrao'")
        except: pass

        conn.commit()
    except Exception as e:
        print("Erro ao inicializar tabelas de gestão:", e)
    finally:
        conn.close()

def get_pedidos_filtrados(conn, filtro_tipo, valor_filtro, loja_id):
    try:
        colunas_info = conn.execute("PRAGMA table_info(pedidos)").fetchall()
        if not colunas_info: return []
        col_nomes = [c["name"].lower() for c in colunas_info]
        
        col_data = "data_hora"
        for c in ["data_hora", "data", "criado_em", "data_pedido", "horario"]:
            if c in col_nomes: 
                col_data = c
                break
                
        col_status = "status" if "status" in col_nomes else None
        
        if filtro_tipo == 'dia':
            try:
                p_ano, p_mes, p_dia = valor_filtro.split('-')
                br_data = f"{p_dia}/{p_mes}/{p_ano}"
            except: br_data = valor_filtro
            sql = f"SELECT * FROM pedidos WHERE ({col_data} LIKE ? OR {col_data} LIKE ? OR {col_data} LIKE ?) AND loja_id = ?"
            params = [f"{valor_filtro}%", f"{br_data}%", f"%{br_data}%", loja_id]
        else:
            try:
                p_ano, p_mes = valor_filtro.split('-')
                br_data = f"%/{p_mes}/{p_ano}%"
            except: br_data = valor_filtro
            sql = f"SELECT * FROM pedidos WHERE ({col_data} LIKE ? OR {col_data} LIKE ?) AND loja_id = ?"
            params = [f"{valor_filtro}%", br_data, loja_id]
            
        if col_status:
            sql += f" AND (LOWER({col_status}) LIKE '%preparo%' OR LOWER({col_status}) LIKE '%saiu%' OR LOWER({col_status}) LIKE '%conclu%' OR LOWER({col_status}) LIKE '%entregue%' OR LOWER({col_status}) LIKE '%pronto%' OR LOWER({col_status}) LIKE '%finalizado%')"
            
        return conn.execute(sql, params).fetchall()
    except Exception as e:
        return []

@router.get("/gestao", response_class=HTMLResponse)
def page_gestao(request: Request):
    loja_id = obter_loja_logada(request)
    inicializar_tabelas_gestao()
    conn = get_db_connection()
    try:
        formas = get_formas_pagamento_validas(conn, loja_id)
        formas_pagamento = [{"nome": f} for f in formas]
        
        try:
            plats = conn.execute("SELECT nome FROM plataformas_delivery WHERE loja_id=? ORDER BY nome ASC", (loja_id,)).fetchall()
            for p in plats:
                formas_pagamento.append({"nome": "App: " + p["nome"]})
        except Exception:
            pass

    finally: conn.close()
    return templates.TemplateResponse("gestao.html", {"request": request, "formas_pagamento": formas_pagamento})

def sincronizar_despesas_fixas(conn, mes_ano: str, loja_id: int):
    ano, mes = map(int, mes_ano.split('-'))
    ultimo_dia_mes = calendar.monthrange(ano, mes)[1]
    fixas = conn.execute("SELECT * FROM despesas_fixas WHERE loja_id = ?", (loja_id,)).fetchall()
    
    for f in fixas:
        existe = conn.execute("SELECT id FROM despesas WHERE despesa_fixa_id = ? AND strftime('%Y-%m', data_vencimento) = ? AND loja_id = ?", (f["id"], mes_ano, loja_id)).fetchone()
        if not existe:
            dia_venc = min(f["dia_vencimento"], ultimo_dia_mes)
            vencimento_str = f"{ano}-{str(mes).zfill(2)}-{str(dia_venc).zfill(2)}"
            conn.execute("INSERT INTO despesas (descricao, valor, data_vencimento, categoria, status, despesa_fixa_id, loja_id) VALUES (?, ?, ?, ?, 'pendente', ?, ?)", 
                         (f["descricao"], f["valor"], vencimento_str, f["categoria"], f["id"], loja_id))
    conn.commit()

@router.get("/api/gestao/resumo")
def api_resumo_financeiro(request: Request, mes_ano: str):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    try:
        pedidos_mes = get_pedidos_filtrados(conn, 'mes', mes_ano, loja_id)
        formas_validas = get_formas_pagamento_validas(conn, loja_id)
        
        taxas_processadas = []
        
        try:
            taxas_db = conn.execute("SELECT * FROM taxas_pagamento WHERE loja_id=?", (loja_id,)).fetchall()
            for t in taxas_db:
                colunas = t.keys()
                n = t["nome"] if "nome" in colunas else (t["metodo"] if "metodo" in colunas else "")
                pct = float(t["taxa_percentual"]) if "taxa_percentual" in colunas else (float(t["valor"]) if "valor" in colunas else 0.0)
                if n: taxas_processadas.append({"nome_exato_limpo": remover_acentos(n), "percentual": pct})
        except Exception as e:
            print(f"Erro ignorado nas taxas: {e}")

        receita = 0.0
        total_taxas_cartao = 0.0
        breakdown_pagamentos = {f: 0.0 for f in formas_validas}
        breakdown_pagamentos["Outros"] = 0.0

        for p in pedidos_mes:
            def g(col, default=""):
                try: return p[col] if p[col] is not None else default
                except: return default

            try:
                val_raw = str(g("valor_total", "0")).replace(",", ".")
                try:
                    valor_db = float(val_raw)
                except:
                    valor_db = 0.0

                if valor_db <= 0:
                    try:
                        itens = conn.execute("SELECT SUM(preco_vendido * quantidade) as soma FROM pedido_outros_itens WHERE pedido_id = ? AND loja_id = ?", (g("id", 0), loja_id)).fetchone()
                        if itens and itens["soma"]:
                            valor_db = float(itens["soma"])
                    except: pass
                
                forma_str = str(g("forma_pagamento", "")).strip()
                detalhe_str = str(g("detalhe_pagamento", g("detalhes_pagamento", ""))).strip()
                texto_global = remover_acentos(forma_str + " " + detalhe_str)
                soma_text = 0.0
                pagamentos_identificados = []
                
                if "|" in detalhe_str and ":" in detalhe_str and "R$" in detalhe_str:
                    partes = detalhe_str.split("|")
                    for parte in partes:
                        match = re.search(r"([A-Za-zÀ-ÿ0-9_ ]+):\s*R\$\s*(\d+[.,]\d{2})", parte)
                        if match:
                            val = float(match.group(2).replace(",", "."))
                            soma_text += val
                            pagamentos_identificados.append({"metodo_exato": match.group(1).strip(), "valor": val})
                else:
                    match = re.search(r"([A-Za-zÀ-ÿ0-9_ ]+):\s*R\$\s*(\d+[.,]\d{2})", detalhe_str)
                    if match and ":" in detalhe_str and "R$" in detalhe_str:
                        val = float(match.group(2).replace(",", "."))
                        soma_text += val
                        pagamentos_identificados.append({"metodo_exato": match.group(1).strip(), "valor": val})
                    elif "R$" in detalhe_str:
                        match2 = re.search(r"R\$\s*(\d+[.,]\d{2})", detalhe_str)
                        if match2:
                            val = float(match2.group(1).replace(",", "."))
                            soma_text += val
                            pagamentos_identificados.append({"metodo_exato": forma_str, "valor": val})
                
                receita_pedido = soma_text if soma_text > 0 else valor_db
                receita += receita_pedido

                if pagamentos_identificados:
                    for pag in pagamentos_identificados:
                        cat = categorizar_metodo_dinamico(pag["metodo_exato"], formas_validas)
                        breakdown_pagamentos[cat] = breakdown_pagamentos.get(cat, 0) + pag["valor"]
                else:
                    cat = categorizar_metodo_dinamico(forma_str, formas_validas)
                    breakdown_pagamentos[cat] = breakdown_pagamentos.get(cat, 0) + receita_pedido

                for t in taxas_processadas:
                    if t["nome_exato_limpo"] in texto_global:
                        total_taxas_cartao += receita_pedido * (t["percentual"] / 100.0)

            except Exception as e:
                print(f"Erro ignorado no pedido {g('id')}: {e}")
                continue

        total_saidas_pagas = conn.execute("SELECT SUM(valor) as total FROM despesas WHERE status = 'pago' AND strftime('%Y-%m', data_pagamento) = ? AND loja_id = ?", (mes_ano, loja_id)).fetchone()["total"] or 0.0
        compras_estoque_pagas = conn.execute("SELECT SUM(valor) as total FROM despesas WHERE status = 'pago' AND descricao LIKE 'Compra%' AND strftime('%Y-%m', data_pagamento) = ? AND loja_id = ?", (mes_ano, loja_id)).fetchone()["total"] or 0.0
        despesas_operacionais = total_saidas_pagas - compras_estoque_pagas
        lucro_liquido = receita - total_saidas_pagas - total_taxas_cartao
        
        return { 
            "receita": receita, 
            "despesas": despesas_operacionais, 
            "compras_estoque": compras_estoque_pagas, 
            "taxas_cartao": total_taxas_cartao, 
            "lucro_liquido": lucro_liquido, 
            "breakdown_pagamentos": breakdown_pagamentos 
        }
    except Exception as e:
        print(f"Erro fatal no dashboard: {e}")
        return {"receita": 0, "despesas": 0, "compras_estoque": 0, "taxas_cartao": 0, "lucro_liquido": 0, "breakdown_pagamentos": {}}
    finally:
        conn.close()

# =======================================================
# --- APIS DE DESPESAS E ESTOQUE ---
# =======================================================
@router.get("/api/despesas")
def api_listar_despesas(request: Request, mes_ano: str):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    sincronizar_despesas_fixas(conn, mes_ano, loja_id)
    res = [dict(r) for r in conn.execute("SELECT * FROM despesas WHERE strftime('%Y-%m', data_vencimento) = ? AND loja_id = ? ORDER BY data_vencimento ASC", (mes_ano, loja_id)).fetchall()]
    conn.close()
    return res

@router.post("/api/despesas")
def api_add_despesa(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    if data.get("recorrente"):
        dt = datetime.strptime(data["data_vencimento"], "%Y-%m-%d")
        conn.execute("INSERT INTO despesas_fixas (descricao, valor, dia_vencimento, categoria, loja_id) VALUES (?, ?, ?, ?, ?)", (data["descricao"], float(data["valor"]), dt.day, data["categoria"], loja_id))
        conn.commit()
        sincronizar_despesas_fixas(conn, dt.strftime("%Y-%m"), loja_id)
    else:
        conn.execute("INSERT INTO despesas (descricao, valor, data_vencimento, categoria, status, loja_id) VALUES (?, ?, ?, ?, 'pendente', ?)", (data["descricao"], float(data["valor"]), data["data_vencimento"], data["categoria"], loja_id))
        conn.commit()
    conn.close()
    return {"success": True}

@router.put("/api/despesas/{id}")
def api_edit_despesa(request: Request, id: int, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.execute("UPDATE despesas SET descricao = ?, valor = ?, data_vencimento = ?, categoria = ? WHERE id = ? AND loja_id = ?", (data["descricao"], float(data["valor"]), data["data_vencimento"], data["categoria"], id, loja_id))
    conn.commit()
    conn.close()
    return {"success": True}

@router.put("/api/despesas/{id}/pagar")
def api_pagar_despesa(request: Request, id: int):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.execute("UPDATE despesas SET status = 'pago', data_pagamento = date('now', 'localtime') WHERE id = ? AND loja_id = ?", (id, loja_id))
    conn.commit()
    conn.close()
    return {"success": True}

@router.delete("/api/despesas/{id}")
def api_delete_despesa(request: Request, id: int):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM funcionario_extrato WHERE despesa_id = ? AND loja_id = ?", (id, loja_id))
        fixa = conn.execute("SELECT despesa_fixa_id FROM despesas WHERE id = ? AND loja_id = ?", (id, loja_id)).fetchone()
        if fixa and fixa["despesa_fixa_id"]:
            conn.execute("DELETE FROM despesas_fixas WHERE id = ? AND loja_id = ?", (fixa["despesa_fixa_id"], loja_id))
        
        conn.execute("DELETE FROM despesas WHERE id = ? AND loja_id = ?", (id, loja_id))
        conn.commit()
        return {"success": True}
    finally:
        conn.close()

@router.get("/api/estoque/insumos")
def api_listar_insumos(request: Request):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    res = [dict(r) for r in conn.execute("SELECT * FROM estoque_insumos WHERE loja_id = ? ORDER BY nome ASC", (loja_id,)).fetchall()]
    conn.close()
    return res

@router.post("/api/estoque/insumos")
def api_add_insumo(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.execute("INSERT INTO estoque_insumos (nome, unidade_medida, estoque_minimo, loja_id) VALUES (?, ?, ?, ?)", (data["nome"], data["unidade_medida"], float(data.get("estoque_minimo", 0)), loja_id))
    conn.commit()
    conn.close()
    return {"success": True}

@router.put("/api/estoque/insumos/{id}")
def api_edit_insumo(request: Request, id: int, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.execute("UPDATE estoque_insumos SET nome = ?, unidade_medida = ?, estoque_minimo = ? WHERE id = ? AND loja_id = ?", (data["nome"], data["unidade_medida"], float(data.get("estoque_minimo", 0)), id, loja_id))
    conn.commit()
    conn.close()
    return {"success": True}

@router.put("/api/estoque/insumos/{id}/ajuste")
def api_ajustar_estoque(request: Request, id: int, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.execute("UPDATE estoque_insumos SET quantidade_atual = ? WHERE id = ? AND loja_id = ?", (float(data["nova_quantidade"]), id, loja_id))
    conn.commit()
    conn.close()
    return {"success": True}

@router.delete("/api/estoque/insumos/{id}")
def api_delete_insumo(request: Request, id: int):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.execute("DELETE FROM estoque_entradas WHERE insumo_id = ? AND loja_id = ?", (id, loja_id))
    conn.execute("DELETE FROM ficha_tecnica_produto WHERE insumo_id = ? AND loja_id = ?", (id, loja_id))
    conn.execute("DELETE FROM estoque_insumos WHERE id = ? AND loja_id = ?", (id, loja_id))
    conn.commit()
    conn.close()
    return {"success": True}

@router.post("/api/estoque/entradas")
def api_add_entrada_estoque(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        insumo_id = data["insumo_id"]
        qtd_total = float(data["quantidade"]) * float(data["fator_conversao"])
        custo = float(data["custo_total"])
        
        conn.execute("INSERT INTO estoque_entradas (insumo_id, quantidade_adicionada, custo_total, data_compra, loja_id) VALUES (?, ?, ?, datetime('now', 'localtime'), ?)", (insumo_id, qtd_total, custo, loja_id))
        
        insumo = conn.execute("SELECT nome, quantidade_atual, custo_medio FROM estoque_insumos WHERE id = ? AND loja_id = ?", (insumo_id, loja_id)).fetchone()
        qtd_antiga = insumo["quantidade_atual"] if insumo and insumo["quantidade_atual"] else 0.0
        custo_medio_antigo = insumo["custo_medio"] if insumo and insumo["custo_medio"] else 0.0
        
        valor_estoque_antigo = qtd_antiga * custo_medio_antigo
        novo_valor_estoque = valor_estoque_antigo + custo
        nova_qtd = qtd_antiga + qtd_total
        novo_custo_medio = novo_valor_estoque / nova_qtd if nova_qtd > 0 else 0
        conn.execute("UPDATE estoque_insumos SET quantidade_atual = ?, custo_medio = ? WHERE id = ? AND loja_id = ?", (nova_qtd, novo_custo_medio, insumo_id, loja_id))
        
        forma_pagamento = data.get("forma_pagamento", "avista")
        if forma_pagamento == "prazo":
            parcelas = int(data.get("parcelas", 1))
            primeiro_venc_str = data.get("primeiro_vencimento") or date.today().strftime("%Y-%m-%d")
            primeiro_venc = datetime.strptime(primeiro_venc_str, "%Y-%m-%d").date()
            valor_parcela = custo / parcelas
            
            for i in range(parcelas):
                desc_parcela = f"Compra: {insumo['nome']} (Parcela {i+1}/{parcelas})"
                data_venc = adicionar_meses(primeiro_venc, i).strftime("%Y-%m-%d")
                conn.execute("INSERT INTO despesas (descricao, valor, data_vencimento, categoria, status, loja_id) VALUES (?, ?, ?, 'variavel', 'pendente', ?)", (desc_parcela, valor_parcela, data_venc, loja_id))
        elif forma_pagamento == "avista":
             hoje = date.today().strftime("%Y-%m-%d")
             conn.execute("INSERT INTO despesas (descricao, valor, data_vencimento, data_pagamento, categoria, status, loja_id) VALUES (?, ?, ?, ?, 'variavel', 'pago', ?)", (f"Compra à vista: {insumo['nome']}", custo, hoje, hoje, loja_id))

        conn.commit()
        return {"success": True}
    finally:
        conn.close()

# =======================================================
# --- APIS DA EQUIPE, TAXAS, MOTOBOYS ---
# =======================================================
@router.get("/api/gestao/config_motoboy")
def api_get_config_motoboy(request: Request):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    row = conn.execute("SELECT valor FROM configuracoes WHERE chave='motoboy_padrao_id' AND loja_id=?", (loja_id,)).fetchone()
    conn.close()
    return {"motoboy_padrao_id": row[0] if row and row[0] else ""}

@router.post("/api/gestao/config_motoboy")
def api_set_config_motoboy(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    exists = conn.execute("SELECT 1 FROM configuracoes WHERE chave='motoboy_padrao_id' AND loja_id=?", (loja_id,)).fetchone()
    if exists:
        conn.execute("UPDATE configuracoes SET valor=? WHERE chave='motoboy_padrao_id' AND loja_id=?", (str(data.get("motoboy_padrao_id", "")), loja_id))
    else:
        conn.execute("INSERT INTO configuracoes (chave, valor, loja_id) VALUES ('motoboy_padrao_id', ?, ?)", (str(data.get("motoboy_padrao_id", "")), loja_id))
    conn.commit()
    conn.close()
    return {"success": True}

@router.get("/api/gestao/taxas")
def api_get_taxas(request: Request):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        res = [dict(r) for r in conn.execute("SELECT * FROM taxas_pagamento WHERE loja_id=? ORDER BY id", (loja_id,)).fetchall()]
        return JSONResponse(res)
    except Exception as e:
        return JSONResponse({"erro": str(e)}, status_code=500)
    finally:
        conn.close()

@router.post("/api/gestao/taxas")
def api_post_taxa(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.execute("DELETE FROM taxas_pagamento WHERE nome = ? AND loja_id = ?", (data["nome"], loja_id))
    conn.execute("INSERT INTO taxas_pagamento (nome, taxa_percentual, loja_id) VALUES (?, ?, ?)", (data["nome"], float(data["taxa_percentual"]), loja_id))
    conn.commit()
    conn.close()
    return {"success": True}

@router.delete("/api/gestao/taxas/{id}")
def api_delete_taxa(request: Request, id: int):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.execute("DELETE FROM taxas_pagamento WHERE id = ? AND loja_id = ?", (id, loja_id))
    conn.commit()
    conn.close()
    return {"success": True}

@router.get("/api/gestao/entregadores")
def api_get_entregadores(request: Request):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    res = [dict(r) for r in conn.execute("SELECT * FROM entregadores WHERE ativo = 1 AND loja_id = ? ORDER BY nome", (loja_id,)).fetchall()]
    conn.close()
    return res

@router.post("/api/gestao/entregadores")
def api_post_entregador(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    tipo_repasse = data.get("tipo_repasse", "padrao")
    conn.execute("INSERT INTO entregadores (nome, telefone, taxa_padrao, tipo_repasse, loja_id) VALUES (?, ?, ?, ?, ?)", (data["nome"], data.get("telefone", ""), float(data["taxa_padrao"]), tipo_repasse, loja_id))
    conn.commit()
    conn.close()
    return {"success": True}

@router.put("/api/gestao/entregadores/{id}")
def api_put_entregador(request: Request, id: int, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    tipo_repasse = data.get("tipo_repasse", "padrao")
    conn.execute("UPDATE entregadores SET nome=?, telefone=?, taxa_padrao=?, tipo_repasse=? WHERE id=? AND loja_id=?", (data["nome"], data.get("telefone", ""), float(data["taxa_padrao"]), tipo_repasse, id, loja_id))
    conn.commit()
    conn.close()
    return {"success": True}

@router.delete("/api/gestao/entregadores/{id}")
def api_delete_entregador(request: Request, id: int):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.execute("UPDATE entregadores SET ativo = 0 WHERE id = ? AND loja_id = ?", (id, loja_id)) 
    conn.commit()
    conn.close()
    return {"success": True}

@router.get("/api/gestao/acerto_motoboys")
def api_acerto_motoboys(request: Request, data_acerto: str):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    try:
        formas_validas = get_formas_pagamento_validas(conn, loja_id)
        entregadores = conn.execute("SELECT * FROM entregadores WHERE ativo = 1 AND loja_id = ?", (loja_id,)).fetchall()
        res_dict = {}
        for e in entregadores:
            def ge(col, default):
                try: return e[col] if e[col] is not None else default
                except: return default
                
            e_id = str(ge("id", ""))
            res_dict[e_id] = {
                "id": ge("id", 0), 
                "nome": ge("nome", "Motoboy Desconhecido"), 
                "taxa_padrao": float(ge("taxa_padrao", 0)), 
                "tipo_repasse": ge("tipo_repasse", "padrao"),
                "qtd_entregas": 0, "valor_taxas": 0.0, "recolhido_dinheiro": 0.0,
                "total_vales": 0.0, "total_bonus": 0.0, 
                "totais_pgto": {},
                "lancamentos": [],
                "entregas": []
            }
        
        try:
            extratos = conn.execute("SELECT * FROM motoboy_extrato WHERE data_lancamento = ? AND loja_id = ?", (data_acerto, loja_id)).fetchall()
            for ext in extratos:
                eid = str(ext["entregador_id"])
                if eid in res_dict:
                    val = float(ext["valor"])
                    res_dict[eid]["lancamentos"].append({
                        "id": ext["id"], "tipo": ext["tipo_lancamento"], 
                        "valor": val, "descricao": ext["descricao"] or ""
                    })
                    if ext["tipo_lancamento"] == 'vale': res_dict[eid]["total_vales"] += val
                    elif ext["tipo_lancamento"] == 'bonus': res_dict[eid]["total_bonus"] += val
        except Exception: pass

        pedidos = get_pedidos_filtrados(conn, 'dia', data_acerto, loja_id)
        for p in pedidos:
            def gp(col, default=""):
                try: return p[col] if p[col] is not None else default
                except: return default

            e_id_str = str(gp("entregador_id", "")).strip().lower()
            if e_id_str in ("none", "null", "", "0", "nan", "undefined"): continue
            try: e_id = str(int(float(e_id_str)))
            except: continue
            
            if e_id not in res_dict: continue
            
            c_tel = gp("cliente_telefone", gp("telefone", gp("telefone_cliente", "")))
            c_nome = gp("nome_cliente", gp("cliente_nome", "Cliente"))
            if c_tel and c_nome == "Cliente":
                try:
                    crow = conn.execute("SELECT nome FROM cliente WHERE telefone = ? AND loja_id = ?", (c_tel, loja_id)).fetchone()
                    if crow: c_nome = crow["nome"]
                except: pass

            res_dict[e_id]["qtd_entregas"] += 1
            tipo = res_dict[e_id]["tipo_repasse"]
            taxa_pedido = float(gp("taxa_entrega", 0))
            taxa_padrao = float(res_dict[e_id]["taxa_padrao"])
            
            valor_ganho = taxa_padrao
            if tipo == 'bairro': valor_ganho = taxa_pedido if taxa_pedido > 0 else taxa_padrao
            elif tipo == 'maior': valor_ganho = max(taxa_padrao, taxa_pedido)
                
            res_dict[e_id]["valor_taxas"] += valor_ganho
            detalhe = str(gp("detalhe_pagamento", gp("detalhes_pagamento", ""))).strip()
            forma = str(gp("forma_pagamento", "")).strip()
            valor_total_pedido = float(gp("valor_total", 0))
            
            dinheiro_neste_pedido = 0.0
            pagamentos_pedido = []

            if "|" in detalhe and ":" in detalhe and "R$" in detalhe:
                for parte in detalhe.split("|"):
                    match = re.search(r"([A-Za-zÀ-ÿ0-9_ ]+):\s*R\$\s*(\d+[.,]\d{2})", parte)
                    if match:
                        cat_m = categorizar_metodo_dinamico(match.group(1).strip(), formas_validas)
                        val_m = float(match.group(2).replace(",", "."))
                        pagamentos_pedido.append((cat_m, val_m))
                        if "dinheiro" in remover_acentos(cat_m):
                            dinheiro_neste_pedido += val_m
            else:
                match = re.search(r"([A-Za-zÀ-ÿ0-9_ ]+):\s*R\$\s*(\d+[.,]\d{2})", detalhe)
                if match and ":" in detalhe and "R$" in detalhe:
                    cat_m = categorizar_metodo_dinamico(match.group(1).strip(), formas_validas)
                    val_m = float(match.group(2).replace(",", "."))
                    pagamentos_pedido.append((cat_m, val_m))
                    if "dinheiro" in remover_acentos(cat_m):
                        dinheiro_neste_pedido += val_m
                else:
                    cat_m = categorizar_metodo_dinamico(forma, formas_validas)
                    pagamentos_pedido.append((cat_m, valor_total_pedido))
                    if "dinheiro" in remover_acentos(cat_m):
                        dinheiro_neste_pedido += valor_total_pedido
                        
            res_dict[e_id]["recolhido_dinheiro"] += dinheiro_neste_pedido

            for cat_m, val_m in pagamentos_pedido:
                res_dict[e_id]["totais_pgto"][cat_m] = res_dict[e_id]["totais_pgto"].get(cat_m, 0) + val_m

            troco = 0.0
            match_troco = re.search(r"(?:Troco|troco|levar troco).*?(\d+[.,]\d{2}|\d+)", detalhe)
            if match_troco:
                try: troco = float(match_troco.group(1).replace(",", "."))
                except: pass

            cat_principal = pagamentos_pedido[0][0] if pagamentos_pedido else categorizar_metodo_dinamico(forma, formas_validas)
            res_dict[e_id]["entregas"].append({
                "id": gp("id", 0),
                "cliente": c_nome,
                "valor": valor_total_pedido,
                "metodo_str": forma + (" (" + detalhe + ")" if detalhe else ""),
                "cat_metodo": cat_principal,
                "taxa_motoboy": valor_ganho,
                "troco": troco
            })
            
        res = []
        for e_id, data in res_dict.items():
            if data["qtd_entregas"] > 0 or len(data["lancamentos"]) > 0:
                data["saldo"] = (data["valor_taxas"] + data["total_bonus"]) - (data["recolhido_dinheiro"] + data["total_vales"])
                res.append(data)
            
        return res
    except Exception as e:
        print(f"CRASH FATAL NO ACERTO: {e}")
        return []
    finally: conn.close()

@router.get("/api/gestao/pedidos_sem_motoboy")
def api_pedidos_sem_motoboy(request: Request, data_acerto: str):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    try:
        rows = get_pedidos_filtrados(conn, 'dia', data_acerto, loja_id)
        soltos = []
        for r in rows:
            def gp(col, default=""):
                try: return r[col] if r[col] is not None else default
                except: return default

            tipo = str(gp("tipo_entrega", "")).strip().lower()
            if "mesa" in tipo or "retirada" in tipo or "local" in tipo or "balcao" in tipo: continue
                
            e_id = str(gp("entregador_id", "")).strip().lower()
            if e_id not in ("none", "null", "", "0", "nan", "undefined"): continue
            
            c_tel = gp("cliente_telefone", gp("telefone", gp("telefone_cliente", "")))
            c_nome = gp("nome_cliente", gp("cliente_nome", "Cliente"))
            
            if c_tel and c_nome == "Cliente":
                try:
                    crow = conn.execute("SELECT nome FROM cliente WHERE telefone = ? AND loja_id = ?", (c_tel, loja_id)).fetchone()
                    if crow: c_nome = crow["nome"]
                except: pass

            soltos.append({"id": gp("id", 0), "cliente_nome": c_nome, "valor_total": float(gp("valor_total", 0)), "forma_pagamento": gp("forma_pagamento", "Não Informado")})
        return soltos
    except Exception as e:
        return []
    finally: conn.close()

@router.put("/api/gestao/vincular_motoboy/{pedido_id}")
def api_vincular_motoboy(request: Request, pedido_id: int, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.execute("UPDATE pedidos SET entregador_id = ? WHERE id = ? AND loja_id = ?", (data["entregador_id"], pedido_id, loja_id))
    conn.commit()
    conn.close()
    return {"success": True}

@router.post("/api/gestao/motoboy_extrato")
def api_post_motoboy_extrato(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO motoboy_extrato (entregador_id, tipo_lancamento, valor, data_lancamento, descricao, loja_id) VALUES (?, ?, ?, ?, ?, ?)",
                        (data["entregador_id"], data["tipo_lancamento"], float(data["valor"]), data["data_lancamento"], data.get("descricao", ""), loja_id))
        func = conn.execute("SELECT nome FROM entregadores WHERE id=? AND loja_id=?", (data["entregador_id"], loja_id)).fetchone()
        n = func["nome"] if func else "Motoboy"
        desc = f"[{data['tipo_lancamento'].upper()}] {n} - {data.get('descricao', '')}"
        conn.execute("INSERT INTO despesas (descricao, valor, data_vencimento, data_pagamento, categoria, status, loja_id) VALUES (?, ?, ?, ?, 'variavel', 'pago', ?)", 
                        (desc, float(data["valor"]), data["data_lancamento"], data["data_lancamento"], loja_id))
        conn.commit()
        return {"success": True}
    finally: conn.close()

@router.delete("/api/gestao/motoboy_extrato/{id}")
def api_delete_motoboy_extrato(request: Request, id: int):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.execute("DELETE FROM motoboy_extrato WHERE id = ? AND loja_id = ?", (id, loja_id))
    conn.commit()
    conn.close()
    return {"success": True}

# =======================================================
# --- APIS DE FUNCIONÁRIOS INTERNOS E FICHAS TÉCNICAS ---
# =======================================================
@router.get("/api/gestao/funcionarios")
def api_get_funcionarios(request: Request):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    res = [dict(r) for r in conn.execute("SELECT * FROM funcionarios WHERE ativo = 1 AND loja_id = ? ORDER BY nome", (loja_id,)).fetchall()]
    conn.close()
    return res

@router.post("/api/gestao/funcionarios")
def api_post_funcionario(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.execute("INSERT INTO funcionarios (nome, cargo, salario_base, dia_pagamento, loja_id) VALUES (?, ?, ?, ?, ?)", (data["nome"], data.get("cargo", ""), float(data["salario_base"]), int(data.get("dia_pagamento", 5)), loja_id))
    conn.commit()
    conn.close()
    return {"success": True}

@router.put("/api/gestao/funcionarios/{id}")
def api_put_funcionario(request: Request, id: int, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.execute("UPDATE funcionarios SET nome=?, cargo=?, salario_base=?, dia_pagamento=? WHERE id=? AND loja_id=?", (data["nome"], data.get("cargo", ""), float(data["salario_base"]), int(data.get("dia_pagamento", 5)), id, loja_id))
    conn.commit()
    conn.close()
    return {"success": True}

@router.delete("/api/gestao/funcionarios/{id}")
def api_delete_funcionario(request: Request, id: int):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.execute("UPDATE funcionarios SET ativo = 0 WHERE id = ? AND loja_id = ?", (id, loja_id)) 
    conn.commit()
    conn.close()
    return {"success": True}

@router.get("/api/gestao/funcionarios/{id}/extrato")
def api_get_extrato_funcionario(request: Request, id: int, mes_ano: str):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    try:
        func = conn.execute("SELECT salario_base FROM funcionarios WHERE id = ? AND loja_id = ?", (id, loja_id)).fetchone()
        salario_base = float(func["salario_base"]) if func else 0.0
        registros = conn.execute("SELECT id, tipo_lancamento, valor, data_lancamento, descricao, despesa_id FROM funcionario_extrato WHERE funcionario_id = ? AND loja_id = ? AND strftime('%Y-%m', data_lancamento) = ? ORDER BY data_lancamento DESC, id DESC", (id, loja_id, mes_ano)).fetchall()
        lista = [dict(r) for r in registros]
        total_pago = sum(r["valor"] for r in lista if r["tipo_lancamento"] in ('vale', 'salario'))
        total_bonus = sum(r["valor"] for r in lista if r["tipo_lancamento"] == 'bonus')
        saldo_a_pagar = (salario_base + total_bonus) - total_pago
        return {"salario_base": salario_base, "total_pago": total_pago, "total_bonus": total_bonus, "saldo_a_pagar": saldo_a_pagar, "extrato": lista}
    finally: conn.close()

@router.post("/api/gestao/funcionarios/{id}/extrato")
def api_post_extrato_funcionario(request: Request, id: int, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        func = conn.execute("SELECT nome FROM funcionarios WHERE id = ? AND loja_id = ?", (id, loja_id)).fetchone()
        nome_func = func["nome"] if func else "Desconhecido"
        tipo = data["tipo_lancamento"]
        valor = float(data["valor"])
        data_lanc = data["data_lancamento"]
        descricao = data.get("descricao", "")
        desc_despesa = f"[{tipo.upper()}] {nome_func}"
        if descricao: desc_despesa += f" - {descricao}"
        cursor = conn.execute("INSERT INTO despesas (descricao, valor, data_vencimento, data_pagamento, categoria, status, loja_id) VALUES (?, ?, ?, ?, 'fixa', 'pago', ?)", (desc_despesa, valor, data_lanc, data_lanc, loja_id))
        despesa_id = cursor.lastrowid
        conn.execute("INSERT INTO funcionario_extrato (funcionario_id, tipo_lancamento, valor, data_lancamento, descricao, despesa_id, loja_id) VALUES (?, ?, ?, ?, ?, ?, ?)", (id, tipo, valor, data_lanc, descricao, despesa_id, loja_id))
        conn.commit()
        return {"success": True}
    finally: conn.close()

# ----------------- INTELIGÊNCIA DE FICHAS ------------------

@router.get("/api/gestao/cardapio_lookup")
def api_cardapio_lookup(request: Request):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    try:
        try: conn.execute("ALTER TABLE ficha_tecnica_produto ADD COLUMN adicional_nome TEXT DEFAULT ''")
        except: pass

        categorias = conn.execute("SELECT id, nome FROM categorias_cardapio WHERE ativa = 1 AND loja_id = ?", (loja_id,)).fetchall()
        res = []
        for c in categorias:
            cat_id = str(c["id"])
            tabela = get_nome_tabela(cat_id)

            check = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name=? OR name=?)", (tabela, cat_id)).fetchone()
            if check:
                tabela = check["name"]
            else:
                continue

            cat_dict = {
                "id": cat_id,
                "nome": c["nome"],
                "variacoes_gerais": [],
                "adicionais_gerais": [],
                "produtos": []
            }

            try:
                vg = conn.execute("SELECT DISTINCT nome FROM produto_variacoes WHERE categoria = ? AND loja_id = ?", (cat_id, loja_id)).fetchall()
                cat_dict["variacoes_gerais"] = [v["nome"] for v in vg]
            except: pass

            try:
                ag = conn.execute("SELECT DISTINCT pa.nome FROM produto_adicionais pa JOIN grupos_adicionais ga ON pa.grupo = ga.id WHERE ga.categoria_alvo = ? AND pa.loja_id = ?", (cat_id, loja_id)).fetchall()
                cat_dict["adicionais_gerais"] = [a["nome"] for a in ag]
            except: pass

            try:
                try:
                    prods = conn.execute(f"SELECT id, nome FROM \"{tabela}\" WHERE disponivel = 1 AND loja_id = ?", (loja_id,)).fetchall()
                except:
                    prods = conn.execute(f"SELECT id, nome FROM \"{tabela}\" WHERE loja_id = ?", (loja_id,)).fetchall()

                for p in prods:
                    p_dict = {
                        "id": p["id"],
                        "nome": p["nome"],
                        "variacoes": [],
                        "adicionais": []
                    }

                    try:
                        vp = conn.execute("SELECT DISTINCT nome FROM produto_variacoes WHERE produto_id = ? AND tabela_referencia = ? AND loja_id = ?", (p["id"], tabela, loja_id)).fetchall()
                        p_dict["variacoes"] = [v["nome"] for v in vp]
                    except: pass

                    try:
                        ap = conn.execute("SELECT DISTINCT pa.nome FROM produto_adicionais pa JOIN grupos_adicionais ga ON pa.grupo = ga.id WHERE ga.produto_alvo_id = ? AND pa.loja_id = ?", (p["id"], loja_id)).fetchall()
                        p_dict["adicionais"] = [a["nome"] for a in ap]
                    except: pass

                    cat_dict["produtos"].append(p_dict)
            except Exception as e:
                print(f"Erro ignorado ao ler produtos da tabela {tabela}: {e}")

            res.append(cat_dict)
        return res
    except Exception as e:
        print(f"Erro fatal no cardapio_lookup: {e}")
        return []
    finally: conn.close()

@router.get("/api/gestao/fichas_cadastradas")
def api_get_fichas_cadastradas(request: Request):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    try:
        categorias_db = conn.execute("SELECT id, nome FROM categorias_cardapio WHERE loja_id = ?", (loja_id,)).fetchall()
        mapa_categorias = {str(c["id"]): c["nome"] for c in categorias_db}
        
        query = """
            SELECT f.categoria_id, f.produto_id, f.tamanho, f.adicional_nome,
                   COUNT(f.id) as qtd_insumos, SUM(f.quantidade_gasta * i.custo_medio) as custo_total 
            FROM ficha_tecnica_produto f 
            JOIN estoque_insumos i ON f.insumo_id = i.id 
            WHERE f.loja_id = ?
            GROUP BY f.categoria_id, f.produto_id, f.tamanho, f.adicional_nome
        """
        fichas_db = conn.execute(query, (loja_id,)).fetchall()
        resultado = []
        
        for f in fichas_db:
            cat_id = f["categoria_id"]
            prod_id = f["produto_id"]
            tamanho = f["tamanho"] or "UNICO"
            adicional_nome = f["adicional_nome"] or ""
            
            prod_nome = "⭐ Regra Geral (Massa/Base da Categoria)"
            preco_venda = 0.0
            
            if prod_id != 0:
                prod_nome = "Produto Desconhecido"
                tabela = get_nome_tabela(cat_id)
                check = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name=? OR name=?)", (tabela, cat_id)).fetchone()
                if check:
                    tabela = check["name"]
                    try:
                        p_row = conn.execute(f"SELECT nome, preco FROM \"{tabela}\" WHERE id = ? AND loja_id = ?", (prod_id, loja_id)).fetchone()
                        if p_row: 
                            prod_nome = p_row["nome"]
                            if tamanho == "UNICO" and not adicional_nome:
                                preco_venda = float(p_row["preco"] or 0.0)
                    except: pass
                    
                    if tamanho != "UNICO" and not adicional_nome:
                        try:
                            v_row = conn.execute("SELECT preco FROM produto_variacoes WHERE produto_id = ? AND nome = ? AND loja_id = ?", (prod_id, tamanho, loja_id)).fetchone()
                            if v_row: preco_venda = float(v_row["preco"] or 0.0)
                        except: pass
            
            if adicional_nome:
                try:
                    a_row = conn.execute("SELECT preco_adicional FROM produto_adicionais WHERE nome = ? AND loja_id = ?", (adicional_nome, loja_id)).fetchone()
                    if a_row: preco_venda = float(a_row["preco_adicional"] or 0.0)
                except: pass
                    
            resultado.append({
                "categoria_id": cat_id, 
                "categoria_nome": mapa_categorias.get(cat_id, "Geral"), 
                "produto_id": prod_id, 
                "produto_nome": prod_nome, 
                "tamanho": tamanho, 
                "adicional_nome": adicional_nome,
                "custo_total": f["custo_total"] or 0.0,
                "preco_venda": preco_venda
            })
        return resultado
    finally: conn.close()

@router.get("/api/gestao/ficha")
def api_get_ficha(request: Request, categoria_id: str, produto_id: int, tamanho: str = "UNICO", adicional: str = ""):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    try:
        query = """
            SELECT f.id, f.quantidade_gasta, i.nome, i.unidade_medida, i.custo_medio 
            FROM ficha_tecnica_produto f 
            JOIN estoque_insumos i ON f.insumo_id = i.id 
            WHERE f.categoria_id = ? AND f.produto_id = ? AND f.tamanho = ? AND f.loja_id = ?
            AND (f.adicional_nome = ? OR (f.adicional_nome IS NULL AND ? = ''))
        """
        rows = conn.execute(query, (categoria_id, produto_id, tamanho, loja_id, adicional, adicional)).fetchall()
        return [dict(r) for r in rows]
    finally: conn.close()

@router.post("/api/gestao/ficha")
def api_post_ficha(request: Request, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        try: conn.execute("ALTER TABLE ficha_tecnica_produto ADD COLUMN adicional_nome TEXT DEFAULT ''")
        except: pass
        
        tamanho = data.get("tamanho") or "UNICO"
        adicional = data.get("adicional_nome") or ""
        
        conn.execute("INSERT INTO ficha_tecnica_produto (categoria_id, produto_id, tamanho, adicional_nome, insumo_id, quantidade_gasta, loja_id) VALUES (?, ?, ?, ?, ?, ?, ?)", 
            (data["categoria_id"], int(data["produto_id"]), tamanho, adicional, data["insumo_id"], float(data["quantidade_gasta"]), loja_id))
        conn.commit()
    finally: conn.close()
    return {"success": True}

@router.put("/api/gestao/ficha/{id}")
def api_put_ficha(request: Request, id: int, data: dict):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.execute("UPDATE ficha_tecnica_produto SET quantidade_gasta = ? WHERE id = ? AND loja_id = ?", (float(data["quantidade_gasta"]), id, loja_id))
    conn.commit()
    conn.close()
    return {"success": True}

@router.delete("/api/gestao/ficha/{id}")
def api_delete_ficha(request: Request, id: int):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    conn.execute("DELETE FROM ficha_tecnica_produto WHERE id = ? AND loja_id = ?", (id, loja_id))
    conn.commit()
    conn.close()
    return {"success": True}
    
@router.delete("/api/gestao/ficha/completa")
def api_delete_ficha_completa(request: Request, categoria_id: str, produto_id: int, tamanho: str = "UNICO", adicional: str = ""):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        query = "DELETE FROM ficha_tecnica_produto WHERE categoria_id = ? AND produto_id = ? AND tamanho = ? AND loja_id = ? AND (adicional_nome = ? OR (adicional_nome IS NULL AND ? = ''))"
        conn.execute(query, (categoria_id, produto_id, tamanho, loja_id, adicional, adicional))
        conn.commit()
    finally: conn.close()
    return {"success": True}

# ==========================================
# EXPORTAÇÃO PARA CONTABILIDADE (CSV)
# ==========================================

@router.get("/api/gestao/exportar_contabilidade")
def api_exportar_contabilidade(request: Request, mes_ano: str):
    loja_id = obter_loja_logada(request)
    conn = get_db_connection()
    try:
        cols_info = conn.execute("PRAGMA table_info(pedidos)").fetchall()
        colunas = [c["name"].lower() for c in cols_info]
        
        col_data = "data_hora" if "data_hora" in colunas else "data_pedido"
        col_valor = "valor_total" if "valor_total" in colunas else "total" if "total" in colunas else "valor"
        col_cliente = "cliente_nome" if "cliente_nome" in colunas else "nome_cliente"
        col_telefone = "cliente_telefone" if "cliente_telefone" in colunas else "telefone" if "telefone" in colunas else "telefone_cliente"

        sel_cliente = col_cliente if col_cliente in colunas else "''"
        sel_telefone = col_telefone if col_telefone in colunas else "''"
        sel_valor = col_valor if col_valor in colunas else "0"

        query = f"""
            SELECT id as 'ID Pedido', {col_data} as 'Data', {sel_cliente} as 'Cliente', 
                   {sel_telefone} as 'Telefone_Temp', forma_pagamento as 'Pagamento', {sel_valor} as 'Valor (R$)'
            FROM pedidos 
            WHERE UPPER(status) IN ('CONCLUIDO', 'ENTREGUE') AND strftime('%Y-%m', {col_data}) = ? AND loja_id = ?
        """
        vendas = pd.read_sql_query(query, conn, params=(mes_ano, loja_id))

        for index, row in vendas.iterrows():
            cliente_atual = str(row['Cliente']).strip()
            if cliente_atual in ('', 'None', 'nan', 'Cliente'):
                telefone = str(row['Telefone_Temp']).strip()
                if telefone and telefone not in ('None', 'nan'):
                    try:
                        crow = conn.execute("SELECT nome FROM cliente WHERE telefone = ? AND loja_id = ?", (telefone, loja_id)).fetchone()
                        if crow and crow["nome"]:
                            vendas.at[index, 'Cliente'] = crow["nome"]
                    except: pass
            
            try: valor_atual = float(row['Valor (R$)'])
            except: valor_atual = 0.0
            
            if valor_atual <= 0:
                try:
                    itens = conn.execute("SELECT SUM(preco_vendido * quantidade) as soma FROM pedido_outros_itens WHERE pedido_id = ? AND loja_id = ?", (row['ID Pedido'], loja_id)).fetchone()
                    if itens and itens["soma"]:
                        vendas.at[index, 'Valor (R$)'] = float(itens["soma"])
                except: pass

        if 'Telefone_Temp' in vendas.columns:
            vendas = vendas.drop(columns=['Telefone_Temp'])

        despesas = pd.read_sql_query("""
            SELECT COALESCE(data_pagamento, data_vencimento) as 'Data', 
                   descricao as 'Descrição', categoria as 'Categoria', valor as 'Valor (R$)'
            FROM despesas 
            WHERE status = 'pago' AND strftime('%Y-%m', COALESCE(data_pagamento, data_vencimento)) = ? AND loja_id = ?
        """, conn, params=(mes_ano, loja_id))

        for df in [vendas, despesas]:
            if not df.empty:
                df['Data'] = pd.to_datetime(df['Data'], errors='coerce').dt.strftime('%d/%m/%Y')

        if not vendas.empty:
            total_vendas = vendas['Valor (R$)'].sum()
            linha_total_v = pd.DataFrame([{'ID Pedido': '', 'Data': 'TOTAL', 'Cliente': '', 'Pagamento': '', 'Valor (R$)': total_vendas}])
            vendas = pd.concat([vendas, linha_total_v], ignore_index=True)

        if not despesas.empty:
            total_despesas = despesas['Valor (R$)'].sum()
            linha_total_d = pd.DataFrame([{'Data': 'TOTAL', 'Descrição': '', 'Categoria': '', 'Valor (R$)': total_despesas}])
            despesas = pd.concat([despesas, linha_total_d], ignore_index=True)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            vendas.to_excel(writer, sheet_name='Vendas', index=False)
            despesas.to_excel(writer, sheet_name='Despesas', index=False)
            
            for sheet in writer.sheets.values():
                for col in sheet.columns:
                    max_length = max(len(str(cell.value) or "") for cell in col) + 2
                    sheet.column_dimensions[col[0].column_letter].width = max_length

        return Response(
            content=output.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=Contabilidade_{mes_ano}.xlsx"}
        )
    finally:
        conn.close()