from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import sqlite3
import json

router = APIRouter(tags=["Operacional ERP"])
templates = Jinja2Templates(directory="templates")

# Caminho oficial e único da base de dados do sistema
DB_PATH = 'database/pizzaria.db'

# ==========================================
# FUNÇÃO INTELIGENTE DE ATUALIZAÇÃO DE SCHEMAS
# ==========================================
def garantir_colunas(cursor, tabela, colunas):
    """Verifica se as colunas existem na tabela. Se não existirem, adiciona automaticamente."""
    cursor.execute(f"PRAGMA table_info({tabela})")
    colunas_existentes = [row[1] for row in cursor.fetchall()]
    for col, tipo in colunas.items():
        if col not in colunas_existentes:
            try: cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN {col} {tipo}")
            except Exception as e: print(f"Erro ao adicionar {col} na {tabela}: {e}")

# ==========================================
# INICIALIZAÇÃO DO BANCO DE DADOS (100% erp_)
# ==========================================
def init_db_operacional():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # erp_pdv_movimentos, erp_vales e erp_mdfe removidas a pedido
    tabelas = {}

    for tabela, colunas in tabelas.items():
        cursor.execute(f"CREATE TABLE IF NOT EXISTS {tabela} (id INTEGER PRIMARY KEY AUTOINCREMENT)")
        garantir_colunas(cursor, tabela, colunas)

    conn.commit()
    conn.close()

init_db_operacional()

# ==========================================
# ROTAS DA API
# ==========================================
@router.get("/operacional", response_class=HTMLResponse)
async def pagina_operacional(request: Request):
    return templates.TemplateResponse("operacional.html", {"request": request})

@router.get("/api/operacional/opcoes_formularios")
def get_opcoes_operacional():
    """Retorna dados de Cadastros para popular os dropdowns da operação com Fallbacks seguros."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    data = {}
    
    def fetch_erp(query):
        try: return [r['nome'] for r in conn.execute(query).fetchall() if r['nome']]
        except: return []

    # 1. Caixas
    data["caixas"] = fetch_erp("SELECT nome FROM erp_contas_bancarias WHERE fluxo_caixa = 'S'")
    if not data["caixas"]:
        data["caixas"] = ["Caixa 01 - Balcão", "Caixa 02 - Drive", "Caixa Cofre Central"]

    # 2. Operadores e Motoristas (Funcionários - Nomes apenas)
    data["operadores"] = fetch_erp("SELECT nome FROM erp_funcionarios")
    if not data["operadores"]:
        data["operadores"] = ["João Operador", "Maria Gerente", "Admin Sistema"]
        
    data["motoristas"] = fetch_erp("SELECT nome FROM erp_funcionarios")
    if not data["motoristas"]:
        data["motoristas"] = ["Carlos Motorista", "José Entregador Logística"]

    # 3. Clientes (Nomes apenas)
    data["clientes"] = fetch_erp("SELECT nome FROM erp_clientes")
    if not data["clientes"]:
        data["clientes"] = ["Cliente VIP 01", "Consumidor Avulso", "Empresa Parceira S/A"]
    
    # 4. Veículos
    # erp_frota foi apagada, usando fallback estático
    data["veiculos"] = ["ABC-1234", "XYZ-9876", "MOTO-01"]

    # 5. Listas com ID e Nome para a Tabela de Vales (NOVOS CAMPOS)
    try:
        data["clientes_list"] = [{"id": r["id"], "nome": r["nome"]} for r in conn.execute("SELECT id, nome FROM erp_clientes").fetchall() if r["nome"]]
    except: data["clientes_list"] = []
    
    try:
        data["funcionarios_list"] = [{"id": r["id"], "nome": r["nome"]} for r in conn.execute("SELECT id, nome FROM erp_funcionarios").fetchall() if r["nome"]]
    except: data["funcionarios_list"] = []

    conn.close()
    return data

@router.get("/api/operacional/relatorios/balanca")
def get_rel_balanca():
    """Retorna dados para a tela de monitoramento da balança"""
    return []

# ==========================================
# HELPERS DE CRUD E ROTEADOR INTELIGENTE
# ==========================================
def get_real_table_name(tabela: str) -> str:
    base_tabela = tabela.replace("ope_", "").replace("erp_", "")
    return f"erp_{base_tabela}"

def generic_get(tabela):
    try:
        conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
        res = [dict(r) for r in conn.execute(f"SELECT * FROM {tabela} ORDER BY id DESC").fetchall()]
        conn.close(); return res
    except Exception: return []

def generic_post(tabela, payload):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute(f"PRAGMA table_info({tabela})")
        colunas_reais = {row[1]: row[2] for row in cursor.fetchall()}
        
        payload_limpo = {}
        for k, v in payload.items():
            if k in colunas_reais:
                tipo = colunas_reais[k].upper()
                if v == "" and ("INT" in tipo or "REAL" in tipo):
                    payload_limpo[k] = 0
                else:
                    payload_limpo[k] = v

        id_val = payload.get('id')
        if id_val and str(id_val).strip() != "":
            payload_limpo.pop('id', None)
            set_query = ", ".join([f"{c}=?" for c in payload_limpo.keys()])
            cursor.execute(f"UPDATE {tabela} SET {set_query} WHERE id=?", list(payload_limpo.values()) + [id_val])
        else:
            payload_limpo.pop('id', None)
            campos = list(payload_limpo.keys())
            placeholders = ", ".join(["?"] * len(campos))
            cursor.execute(f"INSERT INTO {tabela} ({','.join(campos)}) VALUES ({placeholders})", list(payload_limpo.values()))
            
        conn.commit()
        conn.close()
        return {"sucesso": True}
    except Exception as e:
        print(f"ERRO CRÍTICO NO BANCO: {e}") 
        return {"sucesso": False, "erro": str(e)}

def generic_delete(tabela, id):
    try:
        conn = sqlite3.connect(DB_PATH); conn.execute(f"DELETE FROM {tabela} WHERE id=?", (id,)); conn.commit(); conn.close(); return {"sucesso": True}
    except Exception: return {"sucesso": False}

@router.get("/api/operacional/{tabela}")
def listar_operacional(tabela: str): return generic_get(get_real_table_name(tabela))

@router.post("/api/operacional/{tabela}")
def salvar_operacional(tabela: str, payload: dict): return generic_post(get_real_table_name(tabela), payload)

@router.delete("/api/operacional/{tabela}/{id}")
def excluir_operacional(tabela: str, id: int): return generic_delete(get_real_table_name(tabela), id)