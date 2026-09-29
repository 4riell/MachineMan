from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import sqlite3
import json
from datetime import datetime

router = APIRouter(tags=["Controladoria ERP"])
templates = Jinja2Templates(directory="templates")

# Caminho oficial e único da base de dados
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
            except Exception as e: print(f"Erro ao adicionar {col} em {tabela}: {e}")

# ==========================================
# INICIALIZAÇÃO DO BANCO DE DADOS (SCHEMAS OTIMIZADOS)
# ==========================================
def init_db_controladoria():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    tabelas = {
        "erp_emitentes": {
            "cnpj": "VARCHAR(20)", "razao_social": "VARCHAR(150)", "fantasia": "VARCHAR(150)", 
            "atividade": "VARCHAR(100)", "ie": "VARCHAR(20)", "im": "VARCHAR(20)", "cnae": "VARCHAR(50)",
            "email": "VARCHAR(100)", "telefone": "VARCHAR(20)", "multi_estoque": "VARCHAR(1) DEFAULT 'N'",
            "cep": "VARCHAR(10)", "logradouro": "VARCHAR(150)", "numero": "VARCHAR(20)",
            "complemento": "VARCHAR(100)", "bairro": "VARCHAR(100)", "municipio": "VARCHAR(100)",
            "uf": "VARCHAR(2)", "contabilidade": "VARCHAR(150)", "crt": "VARCHAR(50)",
            "aliq_cred_simpl": "REAL", "base_iss": "REAL", "perc_iss": "REAL",
            "base_inss": "REAL", "perc_inss": "REAL", "base_ir": "REAL", "perc_ir": "REAL",
            "base_csll": "REAL", "perc_csll": "REAL", "base_pis": "REAL", "perc_pis": "REAL",
            "base_cofins": "REAL", "perc_cofins": "REAL", "inativo": "VARCHAR(1) DEFAULT 'N'",
            "impostos_retidos": "VARCHAR(1) DEFAULT 'N'"
        },
        "erp_contadores": {
            "nome": "VARCHAR(150)", "crc": "VARCHAR(50)", 
            "email": "VARCHAR(100)", "telefone": "VARCHAR(20)", "celular": "VARCHAR(20)", 
            "inativo": "VARCHAR(1) DEFAULT 'N'", "cpf_resp_contabil": "VARCHAR(20)", 
            "cep": "VARCHAR(10)", "numero": "VARCHAR(20)", "bairro": "VARCHAR(100)"
        },
        "erp_usuarios": {
            "nome": "VARCHAR(150)", "senha": "VARCHAR(100)", "usuario": "VARCHAR(50)", 
            "telefone": "VARCHAR(20)", "email": "VARCHAR(100)"
        },
        "erp_tabelas_preco": {
            "nome": "VARCHAR(100)"
        },
        "erp_tributacoes": {
            "finalidade": "VARCHAR(100)", "tipo_pessoa": "VARCHAR(50)",
            "consumidor_final": "VARCHAR(50)",
            "integracao_fiscal": "VARCHAR(150)", "tipo_tributacao": "VARCHAR(100)",
            "uf": "VARCHAR(2)", "inativo": "VARCHAR(1) DEFAULT 'N'", "data_registro": "VARCHAR(20)"
        },
        "erp_portarias": {
            "nome": "VARCHAR(150)", "mensagem": "TEXT", "tipo": "VARCHAR(50)"
        },
        "erp_operacoes": {
            "codigo_cfop": "VARCHAR(20)", "nome": "VARCHAR(150)", "descricao": "TEXT", 
            "plano_conta": "VARCHAR(100)", "tipo": "VARCHAR(50)", "nat_credito": "VARCHAR(50)",
            "movimenta_estoque": "VARCHAR(1) DEFAULT 'N'"
        },
        "erp_plano_contas": {
            "tipo": "VARCHAR(20)", "nome": "VARCHAR(150)", "natureza": "VARCHAR(50)",
            "codigo_cta": "VARCHAR(20)", "nivel": "VARCHAR(20)", "classificacao": "VARCHAR(50)",
            "ocorrencia": "VARCHAR(50)", "codigo_referencia": "VARCHAR(50)", "inativo": "VARCHAR(1) DEFAULT 'N'",
            "plan_naturezas_json": "TEXT"
        }
    }

    for tabela, colunas in tabelas.items():
        cursor.execute(f"CREATE TABLE IF NOT EXISTS {tabela} (id INTEGER PRIMARY KEY AUTOINCREMENT)")
        garantir_colunas(cursor, tabela, colunas)

    conn.commit()
    conn.close()

init_db_controladoria()

# ==========================================
# HELPERS DE CRUD GENÉRICO
# ==========================================
def generic_get(tabela):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        res = [dict(r) for r in conn.execute(f"SELECT * FROM {tabela} ORDER BY id DESC").fetchall()]
        conn.close()
        return res
    except Exception:
        return []

def generic_post(tabela, payload):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        if 'id' in payload and payload['id'] in ["", None]:
            del payload['id']
            
        # Blindagem de schemas
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
            # Auto-preenchimento de data de registro para novos itens
            if tabela == "erp_tributacoes" and "data_registro" not in payload:
                payload["data_registro"] = datetime.now().strftime("%Y-%m-%d")
                
            campos = list(payload.keys())
            valores = list(payload.values())
            cursor.execute(f"INSERT INTO {tabela} ({','.join(campos)}) VALUES ({','.join(['?']*len(campos))})", valores)
            
        conn.commit()
        return {"sucesso": True}
    except Exception as e:
        print(f"Erro POST em {tabela}: {e}")
        return {"sucesso": False, "erro": str(e)}
    finally:
        conn.close()

def generic_delete(tabela, id):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(f"DELETE FROM {tabela} WHERE id=?", (id,))
        conn.commit()
        return {"sucesso": True}
    except Exception:
        return {"sucesso": False}
    finally:
        conn.close()

# ==========================================
# ROTAS DA CONTROLADORIA (UI E API)
# ==========================================
@router.get("/controladoria", response_class=HTMLResponse)
async def pagina_controladoria(request: Request): 
    return templates.TemplateResponse("controladoria.html", {"request": request})

@router.get("/api/controladoria/opcoes_formularios")
def get_opcoes_controladoria():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    data = {}
    try:
        cfop_rows = conn.execute("SELECT codigo_cfop as cfop, nome FROM erp_operacoes ORDER BY codigo_cfop").fetchall()
        data["cfops"] = [dict(r) for r in cfop_rows]
    except Exception:
        data["cfops"] = []
        
    data["municipios"] = []
        
    conn.close()
    return data

@router.get("/api/controladoria/pesquisar/{entidade}")
def pesquisar_entidade(entidade: str, q: str = ""):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        if entidade == "ncms":
            res = []
        else:
            res = []
        return res
    except Exception:
        return []
    finally:
        conn.close()

def get_real_table_name(tabela: str) -> str:
    base_tabela = tabela.replace("ctrl_", "").replace("erp_", "")
    unificadas = {
        "emitentes": "erp_emitentes", "contadores": "erp_contadores", "usuarios": "erp_usuarios",
        "tabelas_preco": "erp_tabelas_preco", "tributacoes": "erp_tributacoes", "portarias": "erp_portarias",
        "cfops": "erp_operacoes", "cfop": "erp_operacoes", "plano_contas": "erp_plano_contas"
    }
    return unificadas.get(base_tabela, f"erp_{base_tabela}")

@router.get("/api/controladoria/{tabela}")
def listar_controladoria(tabela: str): 
    return generic_get(get_real_table_name(tabela))

@router.post("/api/controladoria/{tabela}")
def salvar_controladoria(tabela: str, payload: dict): 
    return generic_post(get_real_table_name(tabela), payload)

@router.delete("/api/controladoria/{tabela}/{id}")
def excluir_controladoria(tabela: str, id: int): 
    return generic_delete(get_real_table_name(tabela), id)