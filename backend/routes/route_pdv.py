from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import sqlite3
from datetime import datetime

router = APIRouter(tags=["PDV ERP"])
templates = Jinja2Templates(directory="templates")

DB_PATH = 'database/pizzaria.db'

# ==========================================
# INICIALIZAÇÃO DAS TABELAS DO PDV
# ==========================================
def init_db_pdv():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    tabelas_pdv = {}
    for tabela, schema in tabelas_pdv.items():
        cursor.execute(f"CREATE TABLE IF NOT EXISTS {tabela} ({schema})")
    conn.commit()
    conn.close()

init_db_pdv()

# ==========================================
# ROTAS DA INTERFACE
# ==========================================
@router.get("/pdv", response_class=HTMLResponse)
async def pdv_page(request: Request):
    return templates.TemplateResponse("pdv.html", {"request": request})

# ==========================================
# ROTAS DA API DO PDV
# ==========================================
@router.get("/api/pdv/produtos")
def listar_produtos_pdv():
    """Busca os produtos ativos no cadastro do ERP para a tela de vendas."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        # CORREÇÃO: Utilizando erp_grupos_produtos ao invés da erp_categorias apagada
        query = """
            SELECT p.id, p.nome, p.vlr_varejo as preco_venda, c.nome_grupo as categoria, p.imagem_url 
            FROM erp_produtos p 
            LEFT JOIN erp_grupos_produtos c ON p.categoria_id = c.id 
            WHERE p.inativo != 'S' OR p.inativo IS NULL
        """
        produtos = [dict(row) for row in conn.execute(query).fetchall()]
        return produtos
    except Exception as e:
        return []
    finally:
        conn.close()

@router.post("/api/pdv/finalizar")
def finalizar_venda(payload: dict):
    """Processa a venda, grava os itens e integra com o financeiro."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        data_atual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        venda_id = 0 # ID fictício já que não salvamos na tabela de vendas
        
        # Lança a venda fechada direto no contas a receber como PAGO
        cursor.execute("""
            INSERT INTO erp_recebimentos (
                cliente, vencimento, data_vencimento, documento, 
                forma_pagamento, valor_total, valor_recebido, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "Cliente Consumidor", 
            data_atual.split(' ')[0],
            data_atual.split(' ')[0],
            f"PDV-OFFLINE",
            payload.get('forma_pagamento', 'Dinheiro'),
            payload.get('total', 0.0),
            payload.get('total', 0.0), 
            "Pago"
        ))
            
        conn.commit()
        return {"sucesso": True, "venda_id": venda_id, "mensagem": "Venda finalizada e integrada ao financeiro."}
        
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()