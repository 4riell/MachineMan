from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import sqlite3
import json

router = APIRouter(tags=["Suprimentos ERP"])
templates = Jinja2Templates(directory="templates")

DB_PATH = 'database/pizzaria.db'

def garantir_colunas(cursor, tabela, colunas):
    cursor.execute(f"PRAGMA table_info({tabela})")
    colunas_existentes = [row[1] for row in cursor.fetchall()]
    for col, tipo in colunas.items():
        if col not in colunas_existentes:
            try: cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN {col} {tipo}")
            except Exception: pass

def init_db_suprimentos():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Compras Completas
    cursor.execute("CREATE TABLE IF NOT EXISTS erp_compras (id INTEGER PRIMARY KEY AUTOINCREMENT)")
    garantir_colunas(cursor, "erp_compras", {
        "operacao": "VARCHAR(100)", "numero": "VARCHAR(50)", "serie": "VARCHAR(20)", "modelo": "VARCHAR(50)", 
        "data_emissao": "DATE", "data_entrada": "DATE", "fornecedor_id": "INTEGER", "fornecedor_nome": "VARCHAR(150)", 
        "chave_nfe_link": "TEXT",
        
        "frete": "VARCHAR(50)", "volume": "VARCHAR(50)",

        "despesas": "REAL", "descontos": "REAL",
        "base_icms": "REAL",
        "total_produtos": "REAL",

        "itens_json": "TEXT", "financeiro_json": "TEXT"
    })

    # Balanços
    cursor.execute("CREATE TABLE IF NOT EXISTS erp_balancos (id INTEGER PRIMARY KEY AUTOINCREMENT)")
    garantir_colunas(cursor, "erp_balancos", {
        "data": "DATE", "status": "VARCHAR(50)", 
        "grupo": "VARCHAR(100)", "marca": "VARCHAR(100)"
    })
    
    # Transferências
    cursor.execute("CREATE TABLE IF NOT EXISTS erp_transferencias (id INTEGER PRIMARY KEY AUTOINCREMENT)")
    garantir_colunas(cursor, "erp_transferencias", {
        "numero": "VARCHAR(50)", "data": "DATE", "origem": "VARCHAR(100)", "destino": "VARCHAR(100)", 
        "status": "VARCHAR(50)", "itens_json": "TEXT",
        "notas": "TEXT", "responsavel": "VARCHAR(150)"
    })

    # Série e Lote (removido a definicao da coluna id_produto para limpar)
    cursor.execute("CREATE TABLE IF NOT EXISTS erp_serie_lote (id INTEGER PRIMARY KEY AUTOINCREMENT)")
    garantir_colunas(cursor, "erp_serie_lote", {
        "numero": "VARCHAR(100)", "produto_id": "INTEGER", "produto_nome": "VARCHAR(150)",
        "data_fabricacao": "DATE", "data_validade": "DATE", "pmc": "REAL", 
        "qtd_entrada": "REAL", "qtd_saida": "REAL", "saldo": "REAL",
        "historico_json": "TEXT"
    })

    # Descartes
    cursor.execute("CREATE TABLE IF NOT EXISTS erp_descartes (id INTEGER PRIMARY KEY AUTOINCREMENT)")
    garantir_colunas(cursor, "erp_descartes", {
        "data": "DATE", "usuario": "VARCHAR(100)", "notas": "TEXT", "itens_json": "TEXT"
    })

    conn.commit()
    conn.close()

init_db_suprimentos()

# ==========================================
# API DE OPÇÕES CRUZADAS P/ DATALISTS E GRIDS
# ==========================================
@router.get("/api/suprimentos/opcoes_formularios")
def get_opcoes_suprimentos():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    data = {}
    
    def get_todas_opcoes(tabela, campos_nome):
        items = set()
        try:
            rows = conn.execute(f"SELECT * FROM {tabela}").fetchall()
            for row in rows:
                d = dict(row)
                nome = None
                for c in campos_nome:
                    if d.get(c) and str(d.get(c)).strip():
                        nome = str(d.get(c)).strip()
                        break
                if nome:
                    items.add(nome)
        except Exception:
            pass
        return [{"nome": name} for name in sorted(list(items))]

    try: 
        prod_rows = conn.execute("SELECT * FROM erp_produtos").fetchall()
        data["produtos"] = [{"nome": dict(r).get("nome", ""), "custo": dict(r).get("vlr_custo", 0)} for r in prod_rows if dict(r).get("nome")]
    except Exception: 
        data["produtos"] = []
        
    try:
        cfop_rows = conn.execute("SELECT * FROM erp_operacoes").fetchall()
        data["cfops"] = [{"codigo": dict(r).get("codigo_cfop", ""), "descricao": dict(r).get("descricao", "")} for r in cfop_rows if dict(r).get("codigo_cfop")]
    except Exception:
        data["cfops"] = []
    
    data["fornecedores"] = get_todas_opcoes("erp_fornecedores", ["nome_razao", "nome_fantasia", "nome", "razao_social"])
    data["transportadoras"] = get_todas_opcoes("erp_transportadoras", ["razao_social", "nome_fantasia", "nome"])
    data["formas_pagamento"] = get_todas_opcoes("erp_formas_pagamento", ["descricao", "nome"])
    data["condicoes"] = get_todas_opcoes("erp_condicoes_pagamento", ["nome", "descricao"]) 
    data["funcionarios"] = get_todas_opcoes("erp_funcionarios", ["nome"])
    data["entregadores"] = get_todas_opcoes("erp_funcionarios", ["nome"])
    
    # Removido a busca em erp_categorias pois a tabela foi apagada
    data["categorias"] = []
    
    data["grupos"] = get_todas_opcoes("erp_grupos_produtos", ["nome_grupo", "nome", "descricao"])
    data["clientes"] = get_todas_opcoes("erp_clientes", ["nome", "nome_fantasia"])
    data["marcas"] = get_todas_opcoes("erp_marcas", ["descricao", "nome"])
    data["bancos"] = get_todas_opcoes("erp_bancos", ["nome", "descricao"])
    
    # Ajuste: removido a busca em erp_empresas, mantendo apenas erp_emitentes
    emitentes_ctrl = get_todas_opcoes("erp_emitentes", ["razao_social", "fantasia", "nome"])
    todas_filiais = {e["nome"] for e in emitentes_ctrl}
    data["empresas"] = [{"nome": n} for n in sorted(list(todas_filiais))]
    
    conn.close()
    return data

# ==========================================
# ROTAS DE SUPRIMENTOS (CRUD E API)
# ==========================================
@router.get("/suprimentos", response_class=HTMLResponse)
async def pagina_suprimentos(request: Request):
    return templates.TemplateResponse("suprimentos.html", {"request": request})

def get_real_table_name(tabela: str) -> str:
    base_tabela = tabela.replace("sup_", "").replace("erp_", "")
    return f"erp_{base_tabela}"

@router.get("/api/suprimentos/{tabela}")
def listar_suprimentos(tabela: str):
    real_table = get_real_table_name(tabela)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try: res = [dict(r) for r in conn.execute(f"SELECT * FROM {real_table} ORDER BY id DESC").fetchall()]
    except Exception as e: res = []
    conn.close()
    return res

@router.post("/api/suprimentos/{tabela}")
def salvar_suprimentos(tabela: str, payload: dict): 
    real_table = get_real_table_name(tabela)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if 'id' in payload and not str(payload['id']).strip():
        del payload['id']
        
    # --- NOVO: BLINDAGEM DE SCHEMA ---
    # Verifica quais colunas de fato existem na tabela do banco
    # e descarta qualquer coisa que você tenha apagado (como o 'guia_st').
    cursor.execute(f"PRAGMA table_info({real_table})")
    colunas_existentes = [row[1] for row in cursor.fetchall()]
    
    payload_filtrado = {}
    for chave, valor in payload.items():
        if chave in colunas_existentes:
            payload_filtrado[chave] = valor

    campos = list(payload_filtrado.keys())
    try:
        if payload_filtrado.get('id'):
            id_val = payload_filtrado.pop('id')
            campos.remove('id')
            set_query = ", ".join([f"{c}=?" for c in campos])
            cursor.execute(f"UPDATE {real_table} SET {set_query} WHERE id=?", list(payload_filtrado.values()) + [id_val])
        else:
            if 'id' in campos: campos.remove('id')
            valores = list(payload_filtrado.values())
            cursor.execute(f"INSERT INTO {real_table} ({','.join(campos)}) VALUES ({','.join(['?']*len(campos))})", valores)
        conn.commit()
    except Exception as e:
        print(f"Erro ao salvar {real_table}: {e}")
        conn.rollback()
        return JSONResponse(status_code=400, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()
    return {"sucesso": True}

@router.delete("/api/suprimentos/{tabela}/{id}")
def excluir_suprimentos(tabela: str, id: int):
    real_table = get_real_table_name(tabela)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(f"DELETE FROM {real_table} WHERE id=?", (id,))
        conn.commit()
    except Exception as e: return {"sucesso": False, "erro": str(e)}
    finally: conn.close()
    return {"sucesso": True}

# ==========================================
# ROTA DEDICADA DE PESQUISA DO SUPRIMENTOS
# ==========================================
@router.get("/api/suprimentos/pesquisar/{entidade}")
def pesquisar_entidade(entidade: str, q: str = ""):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        tabela_map = {
            "fornecedores": ["erp_fornecedores"],
            "transportadoras": ["erp_transportadoras"],
            "funcionarios": ["erp_funcionarios"],
            "empresas": ["erp_emitentes"], # <- Removido 'erp_empresas' daqui
            "produtos": ["erp_produtos"],
            "grupos": ["erp_grupos_produtos"]
        }
        
        tabelas_alvo = tabela_map.get(entidade, [f"erp_{entidade}"])
        
        rows = []
        for tab in tabelas_alvo:
            try:
                rows.extend(conn.execute(f"SELECT * FROM {tab}").fetchall())
            except Exception:
                pass
            
        q_lower = q.lower()
        res = []
        
        for row in rows:
            d = dict(row)
            match = False
            nome_display = "Sem Nome"
            
            for col in ["nome_razao", "razao_social", "fantasia", "nome_fantasia", "nome", "nome_grupo", "descricao"]:
                if d.get(col) and str(d.get(col)).strip():
                    nome_display = str(d.get(col)).strip()
                    break
                    
            if q_lower:
                for val in d.values():
                    if val and q_lower in str(val).lower():
                        match = True
                        break
            else:
                match = True
                
            if match:
                item = {
                    "id": d.get("id"),
                    "nome": nome_display,
                    "vlr_custo": d.get("vlr_custo", 0),
                    "preco": d.get("preco", 0),
                    "unidade_medida": d.get("unidade_medida", "UN"),
                    "cfop": d.get("cfop", d.get("codigo_cfop", ""))
                }
                res.append(item)
                
            if len(res) >= 15:
                break
                
        return res
    except Exception as e:
        print(f"Erro pesquisa suprimentos: {e}")
        return []
    finally:
        conn.close()