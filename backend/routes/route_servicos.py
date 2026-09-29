from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import sqlite3
import json
from datetime import datetime

router = APIRouter(tags=["Serviços ERP"])
templates = Jinja2Templates(directory="templates")

# Caminho oficial
DB_PATH = 'database/pizzaria.db'

# ==========================================
# FUNÇÃO INTELIGENTE DE ATUALIZAÇÃO DE SCHEMAS
# ==========================================
def garantir_colunas(cursor, tabela, colunas):
    cursor.execute(f"PRAGMA table_info({tabela})")
    colunas_existentes = [row[1] for row in cursor.fetchall()]
    for col, tipo in colunas.items():
        if col not in colunas_existentes:
            try: cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN {col} {tipo}")
            except: pass

# ==========================================
# INICIALIZAÇÃO DO BANCO DE DADOS (SCHEMAS LIMPOS)
# ==========================================
def init_db_servicos():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    tabelas = {
        "erp_identificadores": {
            "nome": "VARCHAR(100)"
        },
        "erp_serv_itens": {
            "nome": "VARCHAR(150)", 
            "identificadores_json": "TEXT"
        },
        "erp_ordens_servico": {
            "numero": "VARCHAR(50)", "data_registro": "VARCHAR(20)", 
            "cliente_nome": "VARCHAR(150)", "cliente_id": "INTEGER",
            "atendente_nome": "VARCHAR(150)", "tabela_preco": "VARCHAR(100)", 
            "finalidade": "VARCHAR(100)", "item_servico_nome": "VARCHAR(150)", 
            "descricao": "TEXT", "problema": "TEXT", "solucao": "TEXT",
            "itens_json": "TEXT", "financeiro_json": "TEXT", "cobranca_json": "TEXT",
            "total_produtos": "REAL", "total_servicos": "REAL", "despesas": "REAL",
            "desconto_percent": "REAL", "desconto_valor": "REAL", "total_geral": "REAL",
            "portarias": "TEXT", "notas": "TEXT", "status": "VARCHAR(50) DEFAULT 'Aberto'"
        }
    }

    for tabela, colunas in tabelas.items():
        cursor.execute(f"CREATE TABLE IF NOT EXISTS {tabela} (id INTEGER PRIMARY KEY AUTOINCREMENT)")
        garantir_colunas(cursor, tabela, colunas)

    conn.commit()
    conn.close()

init_db_servicos()

# ==========================================
# HELPERS DE CRUD E ROTAS
# ==========================================
def generic_get(tabela):
    try:
        conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
        res = [dict(r) for r in conn.execute(f"SELECT * FROM {tabela} ORDER BY id DESC").fetchall()]
        conn.close(); return res
    except Exception: return []

def generic_post(tabela, payload):
    try:
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        
        if 'id' in payload and payload['id'] in ["", None]:
            del payload['id']
            
        cursor.execute(f"PRAGMA table_info({tabela})")
        colunas_tabela = [row[1] for row in cursor.fetchall()]
        for key in payload.keys():
            if key not in colunas_tabela and key != 'id':
                try: cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN {key} TEXT")
                except: pass
                
        if payload.get('id'):
            id_val = payload.pop('id')
            campos = list(payload.keys())
            set_query = ", ".join([f"{c}=?" for c in campos])
            cursor.execute(f"UPDATE {tabela} SET {set_query} WHERE id=?", list(payload.values()) + [id_val])
        else:
            if tabela == "erp_ordens_servico" and "data_registro" not in payload:
                payload["data_registro"] = datetime.now().strftime("%Y-%m-%d")
            
            if tabela == "erp_ordens_servico" and "numero" not in payload:
                # Gera um número sequencial simples
                cursor.execute(f"SELECT COUNT(id) FROM {tabela}")
                count = cursor.fetchone()[0]
                payload["numero"] = f"OS-{datetime.now().strftime('%Y%m')}-{count+1:04d}"

            campos = list(payload.keys())
            valores = list(payload.values())
            cursor.execute(f"INSERT INTO {tabela} ({','.join(campos)}) VALUES ({','.join(['?']*len(campos))})", valores)
        
        conn.commit(); conn.close(); return {"sucesso": True}
    except Exception as e: return {"sucesso": False, "erro": str(e)}

def generic_delete(tabela, id):
    try:
        conn = sqlite3.connect(DB_PATH); conn.execute(f"DELETE FROM {tabela} WHERE id=?", (id,)); conn.commit(); conn.close(); return {"sucesso": True}
    except Exception: return {"sucesso": False}

# ==========================================
# ROTAS DA API
# ==========================================
@router.get("/servicos", response_class=HTMLResponse)
async def pagina_servicos(request: Request): 
    return templates.TemplateResponse("servicos.html", {"request": request})

@router.get("/api/servicos/opcoes_formularios")
def get_opcoes_servicos():
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    data = {}
    def fetch_col(query, col="nome"):
        try: return [r[col] for r in conn.execute(query).fetchall() if r[col]]
        except: return []

    data["tecnicos"] = fetch_col("SELECT nome FROM erp_funcionarios ORDER BY nome")
    data["tabelas_preco"] = fetch_col("SELECT nome FROM erp_tabelas_preco ORDER BY nome")
    if not data["tabelas_preco"]: data["tabelas_preco"] = ["Padrão", "Atacado", "Tabela Serviço"]
    
    data["formas_pgto"] = fetch_col("SELECT descricao as nome FROM erp_formas_pagamento", "nome")
    if not data["formas_pgto"]: data["formas_pgto"] = ["Dinheiro", "PIX", "Cartão Crédito", "Cartão Débito", "Boleto"]
    
    data["condicoes"] = fetch_col("SELECT nome FROM erp_condicoes_pagamento")
    if not data["condicoes"]: data["condicoes"] = ["À Vista", "30 Dias", "30/60/90"]
    
    data["bancos"] = fetch_col("SELECT nome FROM erp_contas_bancarias")
    if not data["bancos"]: data["bancos"] = ["Banco do Brasil", "Caixa", "Itaú", "Bradesco", "Santander", "Nubank", "Inter"]
    
    try:
        data["portarias_list"] = [{"nome": r["nome"], "mensagem": r["mensagem"]} for r in conn.execute("SELECT nome, mensagem FROM erp_portarias").fetchall()]
    except: data["portarias_list"] = []

    try:
        data["clientes"] = [{"id": r["id"], "nome": r["nome"]} for r in conn.execute("SELECT id, nome FROM erp_clientes ORDER BY nome").fetchall()]
    except: data["clientes"] = []
    
    try:
        data["atendentes"] = [{"id": r["id"], "nome": r["nome"]} for r in conn.execute("SELECT id, nome FROM erp_funcionarios ORDER BY nome").fetchall()]
    except: data["atendentes"] = []
    
    try:
        data["itens_servico"] = fetch_col("SELECT nome FROM erp_serv_itens ORDER BY nome")
    except: data["itens_servico"] = []

    conn.close()
    return data

@router.get("/api/servicos/{tabela}")
def listar_servicos(tabela: str): 
    base_tabela = tabela.replace("erp_", "")
    unificadas = {"ordens_servico": "erp_ordens_servico", "identificadores": "erp_identificadores", "itens_servico": "erp_serv_itens"}
    real_table = unificadas.get(base_tabela, f"erp_{base_tabela}")
    return generic_get(real_table)

@router.post("/api/servicos/{tabela}")
def salvar_servicos(tabela: str, payload: dict): 
    base_tabela = tabela.replace("erp_", "")
    unificadas = {"ordens_servico": "erp_ordens_servico", "identificadores": "erp_identificadores", "itens_servico": "erp_serv_itens"}
    real_table = unificadas.get(base_tabela, f"erp_{base_tabela}")
    return generic_post(real_table, payload)

@router.delete("/api/servicos/{tabela}/{id}")
def excluir_servicos(tabela: str, id: int): 
    base_tabela = tabela.replace("erp_", "")
    unificadas = {"ordens_servico": "erp_ordens_servico", "identificadores": "erp_identificadores", "itens_servico": "erp_serv_itens"}
    real_table = unificadas.get(base_tabela, f"erp_{base_tabela}")
    return generic_delete(real_table, id)

@router.get("/api/servicos/pesquisar/{entidade}")
def pesquisar_entidade_serv(entidade: str, q: str = ""):
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    try:
        q_like = f"%{q}%"
        if entidade == 'clientes':
            return [dict(r) for r in conn.execute("SELECT id, nome FROM erp_clientes WHERE nome LIKE ? LIMIT 20", (q_like,)).fetchall()]
        elif entidade == 'atendentes':
            return [dict(r) for r in conn.execute("SELECT id, nome FROM erp_funcionarios WHERE nome LIKE ? LIMIT 20", (q_like,)).fetchall()]
        elif entidade == 'produtos_servicos':
            itens = []
            try:
                for r in conn.execute("SELECT id, nome, preco_venda as vlr FROM erp_produtos WHERE nome LIKE ? LIMIT 10", (q_like,)).fetchall():
                    itens.append({"id": r["id"], "nome": r["nome"], "vlr": r["vlr"], "tipo": "produto"})
            except: pass
            try:
                for r in conn.execute("SELECT id, nome, 0 as vlr FROM erp_serv_itens WHERE nome LIKE ? LIMIT 10", (q_like,)).fetchall():
                    itens.append({"id": r["id"], "nome": r["nome"], "vlr": r["vlr"], "tipo": "servico"})
            except: pass
            return itens
        elif entidade == 'identificadores':
            return [dict(r) for r in conn.execute("SELECT id, nome FROM erp_identificadores WHERE nome LIKE ? LIMIT 20", (q_like,)).fetchall()]
        return []
    except Exception as e: print(e); return []
    finally: conn.close()