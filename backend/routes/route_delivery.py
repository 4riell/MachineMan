from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import sqlite3
import json

router = APIRouter(tags=["Delivery ERP"])
templates = Jinja2Templates(directory="templates")

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
            except Exception: pass

# ==========================================
# INICIALIZAÇÃO DO BANCO DE DADOS (100% erp_)
# ==========================================
def init_db_delivery():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    tabelas = {
        "erp_menu_grupos": {
            "ordem": "INTEGER", 
            "nome_grupo": "VARCHAR(100)", 
            "descricao": "VARCHAR(250)", 
            "disponivel": "INTEGER DEFAULT 1", 
            "icone": "VARCHAR(50)"
        },
        "erp_menu_itens": {
            "grupo_id": "INTEGER", 
            "produto_id": "INTEGER", 
            "codigo_pdv": "VARCHAR(50)", 
            "nome_personalizado": "VARCHAR(150)", 
            "descricao": "TEXT", 
            "preco_venda": "REAL", 
            "disponivel": "INTEGER DEFAULT 1", 
            "destaque": "INTEGER DEFAULT 0",
            "produto_nome": "VARCHAR(150)", 
            "ativo": "INTEGER DEFAULT 1", 
            "imagem_url": "TEXT"
        },
        "erp_adicionais_grupos": {
            "nome_grupo": "VARCHAR(100)", 
            "obrigatorio": "INTEGER DEFAULT 0", 
            "minimo": "INTEGER DEFAULT 0", 
            "maximo": "INTEGER DEFAULT 1", 
            "disponivel": "INTEGER DEFAULT 1",
            "descricao": "TEXT" 
        },
        "erp_adicionais_itens": {
            "grupo_id": "INTEGER", 
            "produto_id": "INTEGER", 
            "nome": "VARCHAR(150)", 
            "preco_adicional": "REAL", 
            "disponivel": "INTEGER DEFAULT 1"
        }
    }

    for tabela, colunas in tabelas.items():
        cursor.execute(f"CREATE TABLE IF NOT EXISTS {tabela} (id INTEGER PRIMARY KEY AUTOINCREMENT)")
        garantir_colunas(cursor, tabela, colunas)

    conn.commit()
    conn.close()

init_db_delivery()

# ==========================================
# ALIAS INTELIGENTE PARA TABELAS APAGADAS
# ==========================================
def get_real_table_name(tabela: str) -> str:
    """Interceptador para redirecionar o front-end para as tabelas corretas."""
    t = tabela.replace("del_", "").replace("erp_", "")
    
    if t == "empresas": return "erp_emitentes"
    if t == "categorias": return "erp_grupos_produtos"
    
    return f"erp_{t}"

# ==========================================
# HELPERS DE CRUD GERAIS BLINDADOS
# ==========================================
def generic_get(tabela, order_by="id DESC"):
    try:
        conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
        res = [dict(r) for r in conn.execute(f"SELECT * FROM {tabela} ORDER BY {order_by}").fetchall()]
        conn.close(); return res
    except Exception: return []

def generic_post(tabela, payload):
    try:
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        if 'id' in payload and not payload['id']: del payload['id']

        cursor.execute(f"PRAGMA table_info({tabela})")
        colunas_tabela = [row[1] for row in cursor.fetchall()]
        for key in payload.keys():
            if key not in colunas_tabela and key != 'id':
                try: cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN {key} TEXT")
                except: pass

        campos = list(payload.keys())
        if payload.get('id'):
            id_val = payload.pop('id'); campos.remove('id')
            set_query = ", ".join([f"{c}=?" for c in payload.keys()])
            cursor.execute(f"UPDATE {tabela} SET {set_query} WHERE id=?", list(payload.values()) + [id_val])
        else:
            if 'id' in campos: campos.remove('id'); payload.pop('id', None)
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
@router.get("/delivery", response_class=HTMLResponse)
async def pagina_delivery(request: Request): 
    return templates.TemplateResponse("delivery.html", {"request": request})

@router.get("/api/delivery/produtos_erp")
def get_produtos_venda():
    try:
        conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
        res = [dict(r) for r in conn.execute("SELECT id, nome, vlr_varejo as preco_venda FROM erp_produtos ORDER BY nome").fetchall()]
        if not res:
            res = [{"id": 1, "nome": "Pizza Calabresa (Mock)", "preco_venda": 45.0}, {"id": 204, "nome": "Borda Catupiry (Mock)", "preco_venda": 10.0}]
        return res
    except: return []
    finally: conn.close()

@router.get("/api/delivery/{tabela}")
def listar_delivery(tabela: str): 
    real_table = get_real_table_name(tabela)
    order_col = "id DESC"
    try:
        conn = sqlite3.connect(DB_PATH)
        cols = [c[1] for c in conn.execute(f"PRAGMA table_info({real_table})").fetchall()]
        if "ordem" in cols: order_col = "ordem ASC"
        conn.close()
    except: pass
    return generic_get(real_table, order_col)

@router.get("/api/delivery/{tabela}/{fk_id}")
def listar_delivery_fk(tabela: str, fk_id: int):
    real_table = get_real_table_name(tabela)
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    res = [dict(r) for r in conn.execute(f"SELECT * FROM {real_table} WHERE grupo_id = ? ORDER BY id ASC", (fk_id,)).fetchall()]
    conn.close()
    return res

@router.post("/api/delivery/{tabela}")
def salvar_delivery(tabela: str, payload: dict): return generic_post(get_real_table_name(tabela), payload)

@router.delete("/api/delivery/{tabela}/{id}")
def excluir_delivery(tabela: str, id: int): return generic_delete(get_real_table_name(tabela), id)