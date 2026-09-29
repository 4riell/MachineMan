from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List
import sqlite3
import datetime
import sys
import os

router = APIRouter(tags=["Documentos Fiscais ERP"])
templates = Jinja2Templates(directory="templates")

# Caminho oficial e único da base de dados
DB_PATH = 'database/pizzaria.db'

class ManifestacaoReq(BaseModel):
    ids: List[int]
    tipo_evento: str

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
def init_db_fiscais():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try: cursor.execute("DROP TABLE IF EXISTS erp_notas_fiscais")
    except Exception: pass

    tabelas = {
        "erp_mdfe": {
            "numero": "VARCHAR(50)", "serie": "VARCHAR(10)", "data_emissao": "DATE",
            "motorista_nome": "VARCHAR(150)", "placa_veiculo": "VARCHAR(20)",
            "uf_origem": "VARCHAR(2)", "uf_destino": "VARCHAR(2)", "status": "VARCHAR(50)",
            "valor_carga": "REAL", "chaves_nfe_json": "TEXT", "notas": "TEXT"
        },
        "erp_ciap": {
            "numero": "VARCHAR(50)", "modelo": "VARCHAR(50)", "serie": "VARCHAR(20)",
            "data_entrada": "DATE", "chave_fornecedor": "VARCHAR(100)", "tipo_movimentacao": "VARCHAR(50)",
            "bem": "VARCHAR(150)", "produto": "VARCHAR(150)", "plano_conta": "VARCHAR(150)",
            "c_custo": "VARCHAR(150)", "nota_fiscal": "VARCHAR(50)", "data_aquisicao": "DATE",
            "valor_icms": "REAL", "parcelas": "INTEGER", "parcela_atual": "INTEGER", "fornecedor": "VARCHAR(150)"
        },
        "erp_inventario": {
            "data_inventario": "DATE", "n_livro": "VARCHAR(50)", "tipo_estoque": "VARCHAR(50)", 
            "tipo_valor": "VARCHAR(50)", "total": "REAL"
        },
        "erp_sped_downloads": {
            "num_serie": "VARCHAR(50)", "data": "DATE", "cliente_fornecedor": "VARCHAR(150)",
            "doc": "VARCHAR(50)", "status": "VARCHAR(50)"
        }
    }

    for tabela, colunas in tabelas.items():
        cursor.execute(f"CREATE TABLE IF NOT EXISTS {tabela} (id INTEGER PRIMARY KEY AUTOINCREMENT)")
        garantir_colunas(cursor, tabela, colunas)

    conn.commit()
    conn.close()
    
init_db_fiscais()

# ==========================================
# HELPERS DE CRUD 
# ==========================================
def get_real_table_name(tabela: str) -> str:
    base_tabela = tabela.replace("fis_", "").replace("erp_", "")
    unificadas = {
        "nfe": "erp_nfe", "nfce": "erp_nfce", "nfse": "erp_nfse", "mdfe": "erp_mdfe",
        "ciap": "erp_ciap", "inventario": "erp_inventario", "downloads": "erp_sped_downloads"
    }
    return unificadas.get(base_tabela, f"erp_{base_tabela}")

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
        
        payload_filtrado = {}
        for k, v in payload.items():
            if k in colunas_reais or k == 'id':
                if v == "" and ("INT" in colunas_reais.get(k, "").upper() or "REAL" in colunas_reais.get(k, "").upper()):
                    payload_filtrado[k] = 0 
                else: payload_filtrado[k] = v
        
        campos = list(payload_filtrado.keys())
        if payload_filtrado.get('id'):
            id_val = payload_filtrado.pop('id')
            campos.remove('id')
            set_query = ", ".join([f"{c}=?" for c in payload_filtrado.keys()])
            cursor.execute(f"UPDATE {tabela} SET {set_query} WHERE id=?", list(payload_filtrado.values()) + [id_val])
        else:
            valores = list(payload_filtrado.values())
            cursor.execute(f"INSERT INTO {tabela} ({','.join(campos)}) VALUES ({','.join(['?']*len(campos))})", valores)
            
        conn.commit(); conn.close(); return {"sucesso": True}
    except Exception as e: return {"sucesso": False, "erro": str(e)}

def generic_delete(tabela, id):
    try:
        conn = sqlite3.connect(DB_PATH); conn.execute(f"DELETE FROM {tabela} WHERE id=?", (id,)); conn.commit(); conn.close(); return {"sucesso": True}
    except Exception: return {"sucesso": False}

# ==========================================
# ROTAS DA API FISCAL
# ==========================================
@router.get("/documentos-fiscais", response_class=HTMLResponse)
async def pagina_documentos(request: Request):
    return templates.TemplateResponse("doc_fiscais.html", {"request": request})

@router.post("/api/docs/mde/consultar")
def consultar_mde_sefaz():
    """ Rota que aciona o Motor Python para ir à SEFAZ buscar novas notas (NSU) """
    try:
        # Tenta importar o motor dinamicamente
        sys.path.append(os.path.abspath('motor_fiscal'))
        from orquestrador_sefaz import consultar_documentos_sefaz
        
        # Dispara a consulta!
        consultar_documentos_sefaz()
        return {"sucesso": True, "mensagem": "Consulta concluída! Novas notas processadas (se existirem)."}
    except ImportError:
        return {"sucesso": False, "erro": "Módulo motor_fiscal não encontrado ou não importável."}
    except Exception as e:
        return {"sucesso": False, "erro": f"Falha ao consultar: {str(e)}"}

@router.post("/api/docs/mde/manifestar")
def manifestar_mde(req: ManifestacaoReq):
    """ Regista as Ciências, Confirmações e Desconhecimentos no Banco """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        mapa_status = {
            "210210": "Ciência da Operação",
            "210200": "Confirmação da Operação",
            "210220": "Desconhecimento da Operação",
            "210240": "Operação Não Realizada"
        }
        novo_status = mapa_status.get(req.tipo_evento, "Manifestado")
        
        # Num cenário real, aqui entraria o `assinador_sefaz.py` para gerar o XML e assinar o evento.
        # Por enquanto, atualizamos a base para que o cliente veja a mudança de status instantaneamente.
        for id_nota in req.ids:
            cursor.execute("UPDATE erp_nfe SET status = ? WHERE id = ?", (novo_status, id_nota))
            
        conn.commit()
        conn.close()
        return {"sucesso": True, "mensagem": f"Evento de '{novo_status}' gravado com sucesso!"}
    except Exception as e:
        return {"sucesso": False, "erro": str(e)}

@router.get("/api/docs/{tabela}")
def listar_fiscais(tabela: str): return generic_get(get_real_table_name(tabela))

@router.post("/api/docs/{tabela}")
def salvar_fiscais(tabela: str, payload: dict): return generic_post(get_real_table_name(tabela), payload)

@router.delete("/api/docs/{tabela}/{id}")
def excluir_fiscais(tabela: str, id: int): return generic_delete(get_real_table_name(tabela), id)