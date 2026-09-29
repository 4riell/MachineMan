from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import sqlite3
import json

router = APIRouter(tags=["Produção ERP"])
templates = Jinja2Templates(directory="templates")

# Caminho oficial do banco de dados
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
            except Exception as e: print(f"Erro ao adicionar {col} na {tabela}: {e}")

# ==========================================
# INICIALIZAÇÃO DO BANCO DE DADOS
# ==========================================
def init_db_producao():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # erp_insumos, erp_unidades e erp_fichas_itens removidos a pedido
    tabelas = {
        # Fichas Técnicas (Receita Pai) - MANTIDA
        "erp_fichas_tecnicas": {
            "produto_final_id": "INTEGER",
            "produto_final_nome": "VARCHAR(150)",
            "descricao": "TEXT",
            "rendimento": "REAL",
            "unidade_rendimento": "VARCHAR(20)",
            "tempo_preparo_min": "INTEGER",
            "produto_pai_nome": "VARCHAR(150)", 
            "produto_id": "INTEGER", 
            "receita": "VARCHAR(150)", 
            "produto_pai_id": "INTEGER", 
            "rendimento_padrao": "REAL", 
            "tempo_preparo": "VARCHAR(50)", 
            "custo_estimado": "REAL", 
            "instrucoes": "TEXT", 
            "custo_total_estimado": "REAL", 
            "itens_json": "TEXT"
        },
        # Ordens de Produção (OP) - MANTIDA
        "erp_ordens_producao": {
            "numero": "VARCHAR(50)", 
            "data_emissao": "DATE", 
            "ficha_tecnica_id": "INTEGER",
            "produto_nome": "VARCHAR(150)",
            "status": "VARCHAR(50)",
            "tipo": "VARCHAR(50)",           
            "responsavel": "VARCHAR(100)",   
            "anotacoes": "TEXT",
            "data": "DATE", 
            "qtd_planejada": "REAL", 
            "unidade": "VARCHAR(20)", 
            "data_inicio": "DATE", 
            "data_fim": "DATE", 
            "produto_id": "INTEGER", 
            "qtd_produzida": "REAL", 
            "custo_total": "REAL", 
            "notas": "TEXT", 
            "previsao_conclusao": "DATE", 
            "quantidade_produzida": "REAL", 
            "custo_realizado": "REAL", 
            "lote_gerado": "VARCHAR(50)", 
            "validade_lote": "DATE"
        }
    }

    for tabela, colunas in tabelas.items():
        cursor.execute(f"CREATE TABLE IF NOT EXISTS {tabela} (id INTEGER PRIMARY KEY AUTOINCREMENT)")
        garantir_colunas(cursor, tabela, colunas)

    conn.commit()
    conn.close()

init_db_producao()

# ==========================================
# HELPERS DE CRUD GERAIS
# ==========================================
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
        
        if 'id' in payload and not str(payload['id']).strip():
            del payload['id']

        cursor.execute(f"PRAGMA table_info({tabela})")
        colunas_tabela = [row[1] for row in cursor.fetchall()]
        
        # Cria colunas extras na hora caso ainda existam campos json novos
        for key in payload.keys():
            if key not in colunas_tabela and key != 'id':
                try: cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN {key} TEXT")
                except: pass

        campos = list(payload.keys())
        if payload.get('id'):
            id_val = payload.pop('id')
            campos.remove('id')
            set_query = ", ".join([f"{c}=?" for c in payload.keys()])
            cursor.execute(f"UPDATE {tabela} SET {set_query} WHERE id=?", list(payload.values()) + [id_val])
        else:
            if 'id' in campos: 
                campos.remove('id')
                payload.pop('id', None)
            valores = list(payload.values())
            cursor.execute(f"INSERT INTO {tabela} ({','.join(campos)}) VALUES ({','.join(['?']*len(campos))})", valores)
        
        conn.commit()
        conn.close()
        return {"sucesso": True}
    except Exception as e: 
        print(f"Erro ao salvar em {tabela}: {e}")
        return JSONResponse(status_code=400, content={"sucesso": False, "erro": str(e)})

def generic_delete(tabela, id):
    try:
        conn = sqlite3.connect(DB_PATH); conn.execute(f"DELETE FROM {tabela} WHERE id=?", (id,)); conn.commit(); conn.close(); return {"sucesso": True}
    except Exception: return {"sucesso": False}

def get_real_table_name(tabela: str) -> str:
    return f"erp_{tabela}"

# ==========================================
# ROTAS DA API
# ==========================================
@router.get("/producao", response_class=HTMLResponse)
async def pagina_producao(request: Request): 
    return templates.TemplateResponse("producao.html", {"request": request})

@router.get("/api/producao/opcoes_formularios")
def get_opcoes_producao():
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    data = {"unidades": [], "fornecedores": []}
    
    # Retorna uma lista estática já que a tabela erp_unidades foi apagada
    data["unidades"] = [
        {"nome": "UN", "descricao": "Unidade"}, {"nome": "KG", "descricao": "Quilograma"},
        {"nome": "L", "descricao": "Litro"}, {"nome": "G", "descricao": "Grama"}
    ]
        
    try:
        fornecedores = conn.execute("SELECT id, nome_razao as nome FROM erp_fornecedores ORDER BY nome_razao").fetchall()
        data["fornecedores"] = [{"id": f["id"], "nome": f["nome"]} for f in fornecedores if f["nome"]]
    except Exception:
        pass
        
    conn.close()
    return data

@router.get("/api/producao/fichas_itens/{ficha_id}")
def listar_ficha_itens(ficha_id: int):
    # A tabela erp_fichas_itens foi apagada. Retornando array vazio blindado.
    return []

@router.get("/api/producao/pesquisar/{entidade}")
def pesquisar_entidade(entidade: str, q: str = ""):
    tabela = get_real_table_name(entidade)
    try:
        conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
        col_nome = "nome"
        if entidade == "funcionarios" or entidade == "clientes": col_nome = "nome"
        elif entidade == "fornecedores": col_nome = "nome_razao"
        
        query = f"SELECT id, {col_nome} as nome FROM {tabela} WHERE {col_nome} LIKE ? LIMIT 20"
        res = conn.execute(query, (f"%{q}%",)).fetchall()
        conn.close()
        return [dict(r) for r in res]
    except Exception as e:
        return []

@router.get("/api/producao/{tabela}")
def listar_producao(tabela: str): return generic_get(get_real_table_name(tabela))

@router.post("/api/producao/{tabela}")
def salvar_producao(tabela: str, payload: dict): return generic_post(get_real_table_name(tabela), payload)

@router.delete("/api/producao/{tabela}/{id}")
def excluir_producao(tabela: str, id: int): return generic_delete(get_real_table_name(tabela), id)