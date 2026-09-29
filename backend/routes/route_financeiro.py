from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import sqlite3
import json
from datetime import date

router = APIRouter(tags=["Financeiro ERP"])
templates = Jinja2Templates(directory="templates")

DB_PATH = 'database/pizzaria.db'

def garantir_colunas(cursor, tabela, colunas):
    cursor.execute(f"PRAGMA table_info({tabela})")
    colunas_existentes = [row[1] for row in cursor.fetchall()]
    for col, tipo in colunas.items():
        if col not in colunas_existentes:
            try: cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN {col} {tipo}")
            except Exception as e: print(f"Erro ao adicionar {col} em {tabela}: {e}")

def init_db_financeiro():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Adicionadas colunas faltantes (status, _json) para resolver grids que não salvavam
    tabelas = {
        "erp_recebimentos": {
            "cliente": "VARCHAR(150)", "vencimento": "DATE", "data_vencimento": "DATE", "data_emissao": "DATE",
            "data_criacao": "DATE", "num_documento": "VARCHAR(50)", "conta_banco": "VARCHAR(100)", 
            "centro_custo": "VARCHAR(100)", "forma_pagamento": "VARCHAR(100)", 
            "status": "VARCHAR(50)", "pagamento": "DATE", "valor": "REAL", "tarifa": "REAL", 
            "desconto": "REAL", "juros": "REAL", "encargos": "REAL", "amortizado": "REAL", 
            "valor_recebido": "REAL", "notas": "TEXT", "itens_baixas_json": "TEXT", 
            "planos_contas_json": "TEXT", "cheques_json": "TEXT", "saldo_aberto": "REAL"
        },
        "erp_pagamentos": {
            "fornecedor": "VARCHAR(150)", "vencimento": "DATE", "data_vencimento": "DATE", "data_emissao": "DATE",
            "data_criacao": "DATE", "num_documento": "VARCHAR(50)", "conta_banco": "VARCHAR(100)", 
            "centro_custo": "VARCHAR(100)", "forma_pagamento": "VARCHAR(100)", "status": "VARCHAR(50)", 
            "pagamento": "DATE", "valor": "REAL", "desconto": "REAL", 
            "juros": "REAL", "encargos": "REAL", "amortizado": "REAL", 
            "notas": "TEXT", "itens_baixas_json": "TEXT", "planos_contas_json": "TEXT", 
            "valor_pago": "REAL", "saldo_aberto": "REAL"
        },
        "erp_transferencias_financeiras": {"data": "DATE", "valor": "REAL", "origem": "VARCHAR(100)", "destino": "VARCHAR(100)", "notas": "TEXT"},
        "erp_renegociacoes": {
            "tipo": "VARCHAR(50)", "para_quem": "VARCHAR(150)", "conferencia_status": "VARCHAR(50)"
        },
        "erp_plano_contas": {
            "nome": "VARCHAR(150)", "codigo_cta": "VARCHAR(20)","tipo": "VARCHAR(50)", 
            "classificacao": "VARCHAR(50)", "ocorrencia": "VARCHAR(50)", "natureza": "TEXT", 
            "codigo_referencia": "VARCHAR(50)", "inativo": "VARCHAR(1)", "nivel": "VARCHAR(50)", "plan_naturezas_json": "TEXT"
        },
        "erp_condicoes_pagamento": {
            "nome": "VARCHAR(100)", "no_parcelas": "INTEGER", "dia_1a_parcela": "INTEGER", 
            "dias_entre_parcelas": "INTEGER", "inativo": "VARCHAR(1)"
        },
        "erp_cheques": {
            "cmc7": "VARCHAR(100)", "numero": "VARCHAR(50)", "n_numero": "VARCHAR(50)", "vencimento": "DATE", 
            "data_vencimento": "DATE", "valor": "REAL", "banco": "VARCHAR(50)", "agencia": "VARCHAR(20)", 
            "conta": "VARCHAR(20)", "portador": "VARCHAR(150)", "emissor": "VARCHAR(150)", 
            "telefone": "VARCHAR(20)", "notas": "TEXT", "status": "VARCHAR(50)", "data_status": "DATE", 
            "referencias_json": "TEXT", "historico_json": "TEXT"
        },
        "erp_bandeiras_cartao": {
            "nome": "VARCHAR(100)", "operadora": "VARCHAR(100)", "prazo_rcto": "INTEGER", "bandeira_nfe": "VARCHAR(10)", 
            "f_pgto": "VARCHAR(100)", "inativo": "VARCHAR(1)", "faixas_json": "TEXT"
        },
        "erp_contas_bancarias": {
            "nome": "VARCHAR(100)", "banco": "VARCHAR(50)", "agencia": "VARCHAR(20)", "digito_ag": "VARCHAR(5)", 
            "conta_corrente": "VARCHAR(20)", "digito_cc": "VARCHAR(5)", "juros_mes": "REAL", "multa": "REAL", 
            "dias_de_carencia": "INTEGER", "data_saldo": "DATE", "saldo_inicial": "REAL", "ultimo_fechamento": "DATE", 
            "fluxo_caixa": "VARCHAR(1)", "boleto": "VARCHAR(1)", "inativo": "VARCHAR(1)"
        },
        "erp_bancos": {"nome": "VARCHAR(150)", "codigo": "VARCHAR(10)"},
        "erp_status_financeiro": {"nome": "VARCHAR(50)"}
    }

    for tabela, colunas in tabelas.items():
        cursor.execute(f"CREATE TABLE IF NOT EXISTS {tabela} (id INTEGER PRIMARY KEY AUTOINCREMENT)")
        garantir_colunas(cursor, tabela, colunas)

    conn.commit()
    conn.close()

init_db_financeiro()

# =========================================================================
# HELPERS E ROTAS
# =========================================================================
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
        colunas_validas = [row[1] for row in cursor.fetchall()]
        
        payload_db = {}
        for k, v in payload.items():
            if k in colunas_validas or k == 'id':
                payload_db[k] = None if v == "" else v
                
        hoje_str = date.today().isoformat()
        
        if payload_db.get('id'):
            id_val = payload_db.pop('id')
            campos = list(payload_db.keys())
            if not campos: return {"sucesso": True} 
            set_query = ", ".join([f"{c}=?" for c in campos])
            valores = [payload_db[c] for c in campos] + [id_val]
            cursor.execute(f"UPDATE {tabela} SET {set_query} WHERE id=?", valores)
        else:
            if 'id' in payload_db: payload_db.pop('id')
            
            # AUTOMATIZAÇÃO: Força a salvar a data de emissão/criação como a data do momento do cadastro
            if 'data_emissao' in colunas_validas and not payload_db.get('data_emissao'):
                payload_db['data_emissao'] = hoje_str
            if 'data_criacao' in colunas_validas and not payload_db.get('data_criacao'):
                payload_db['data_criacao'] = hoje_str
                
            campos = list(payload_db.keys())
            if not campos: return {"sucesso": False, "erro": "Formulário vazio."}
            valores = [payload_db[c] for c in campos]
            marcadores = ",".join(["?"] * len(campos))
            cursor.execute(f"INSERT INTO {tabela} ({','.join(campos)}) VALUES ({marcadores})", valores)
            
        conn.commit()
        conn.close()
        return {"sucesso": True}
    except Exception as e: 
        print(f"Erro POST na tabela {tabela}: {e}")
        return {"sucesso": False, "erro": str(e)}

def generic_delete(tabela, id):
    try:
        conn = sqlite3.connect(DB_PATH); conn.execute(f"DELETE FROM {tabela} WHERE id=?", (id,)); conn.commit(); conn.close(); return {"sucesso": True}
    except Exception: return {"sucesso": False}

@router.get("/financeiro", response_class=HTMLResponse)
async def pagina_financeiro(request: Request): 
    return templates.TemplateResponse("financeiro.html", {"request": request})

@router.get("/api/financeiro/opcoes_formularios")
def get_opcoes_financeiro():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    data = {}

    def get_erp_data(tabela):
        try:
            rows = conn.execute(f"SELECT * FROM {tabela}").fetchall()
            res = []
            seen = set()
            for r in rows:
                row_dict = dict(r)
                name_val = row_dict.get('nome') or row_dict.get('descricao') or row_dict.get('nome_razao') or row_dict.get('razao_social') or row_dict.get('numero') or row_dict.get('n_numero')
                if name_val:
                    name_str = str(name_val).strip()
                    if name_str and name_str.lower() not in ['null', 'none']:
                        if name_str not in seen:
                            row_dict['nome'] = name_str
                            res.append(row_dict)
                            seen.add(name_str)
            return res
        except Exception: return []

    # Corrigido: Listas não estão mais vazias
    data["funcionarios"] = get_erp_data("erp_funcionarios")
    data["contas_bancarias"] = get_erp_data("erp_contas_bancarias")
    data["clientes"] = get_erp_data("erp_clientes")
    data["fornecedores"] = get_erp_data("erp_fornecedores")
    data["status_financeiro"] = get_erp_data("erp_status_financeiro")
    data["bancos"] = get_erp_data("erp_bancos")
    data["plano_contas"] = get_erp_data("erp_plano_contas")
    data["cheques"] = get_erp_data("erp_cheques")
    data["formas_pagamento"] = get_erp_data("erp_formas_pagamento")
    data["centro_custo"] = get_erp_data("erp_centros_custo")
    data["natureza"] = get_erp_data("erp_natureza_operacao")
    data["naturezas"] = data["natureza"]
    data["caixas_pdv"] = get_erp_data("erp_contas_bancarias") # Caixas derivam de contas bancárias
    data["operadoras"] = [{"nome": "Cielo"}, {"nome": "Rede"}, {"nome": "Getnet"}, {"nome": "Stone"}, {"nome": "PagSeguro"}]

    conn.close()
    return data

def get_real_table_name(tabela: str) -> str:
    base_tabela = tabela
    for prefixo in ["fin_", "erp_", "ctrl_", "ope_", "fis_"]:
        if base_tabela.startswith(prefixo):
            base_tabela = base_tabela[len(prefixo):]
            
    unificadas = {
        "formas": "erp_formas_pagamento", "formas_pgto": "erp_formas_pagamento", "formas_pagamento": "erp_formas_pagamento",
        "condicoes": "erp_condicoes_pagamento", "condicoes_pgto": "erp_condicoes_pagamento",
        "operadoras": "erp_operadoras_cartao", "operadoras_cartao": "erp_operadoras_cartao",
        "bandeiras": "erp_bandeiras_cartao", "bandeiras_cartao": "erp_bandeiras_cartao",
        "contas_bancarias": "erp_contas_bancarias", "contas_banc": "erp_contas_bancarias",
        "bancos": "erp_bancos",
        "centro_custo": "erp_centros_custo", "centros_custo": "erp_centros_custo",
        "plano_contas": "erp_plano_contas",
        "natureza": "erp_natureza_operacao", "natureza_financeira": "erp_natureza_operacao",
        "status_financeiro": "erp_status_financeiro", "status": "erp_status_financeiro",
        "fluxo": "erp_fluxo_caixa", "fluxo_caixa": "erp_fluxo_caixa", "fluxo_movimentos": "erp_fluxo_caixa", "fluxo_financeiro": "erp_fluxo_caixa",
        "recebimentos": "erp_recebimentos",
        "pagamentos": "erp_pagamentos",
        "fechamento_pdv": "erp_fechamento_caixa", "fechamento_caixa": "erp_fechamento_caixa",
        "transferencias": "erp_transferencias_financeiras",
        "conciliacoes": "erp_conciliacoes", "conciliacao": "erp_conciliacoes",
        "renegociacoes": "erp_renegociacoes",
        "comissoes": "erp_comissoes",
        "cheques": "erp_cheques", "cheque": "erp_cheques",
        "boletos": "erp_boletos", "boleto": "erp_boletos"
    }
    return unificadas.get(base_tabela, f"erp_{base_tabela}")

@router.get("/api/financeiro/pesquisar/{tabela}")
def pesquisar_financeiro(tabela: str, q: str = ""):
    real_table = get_real_table_name(tabela)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({real_table})")
        cols = [row[1] for row in cursor.fetchall()]
        
        conds = []
        params = []
        for col in ['nome', 'razao_social', 'nome_razao', 'fantasia', 'descricao', 'cpf_cnpj', 'cnpj', 'cpf']:
            if col in cols:
                conds.append(f"{col} LIKE ?")
                params.append(f"%{q}%")
                
        if not conds:
            return []
            
        query = f"SELECT * FROM {real_table} WHERE {' OR '.join(conds)} LIMIT 50"
        res = [dict(r) for r in cursor.execute(query, params).fetchall()]
        return res
    except Exception as e:
        print(f"Erro pesquisa financeira: {e}")
        return []
    finally:
        conn.close()

@router.get("/api/financeiro/{tabela}")
def listar_financeiro(tabela: str): 
    real_table = get_real_table_name(tabela)
    data = generic_get(real_table)
    
    aliases = {
        'vencimento': 'data_vencimento', 'numero': 'n_numero', 'abertura': 'data_abertura',
        'fechamento': 'data_fechamento', 'pdc': 'caixa', 'data': 'data_conciliacao',
        'codigo_cta': 'codigo', 'no_parcelas': 'parcelas', 'dias_entre_parcelas': 'dias_intervalo',
        'forma_pagamento': 'forma_pgto', 'num_documento': 'documento',
        'obs': 'observacao'
    }
    
    for item in data:
        if 'descricao' in item and 'nome' not in item: item['nome'] = item['descricao']
        elif 'nome' in item and 'descricao' not in item: item['descricao'] = item['nome']
        
        if 'data_emissao' in item and not item.get('data_emissao'):
            item['data_emissao'] = item.get('data_criacao') or item.get('vencimento') or item.get('data')
        
        for db_key, front_key in aliases.items():
            if db_key in item and front_key not in item:
                item[front_key] = item[db_key]
            if front_key in item and db_key not in item:
                item[db_key] = item[front_key]
                
    return data

@router.post("/api/financeiro/{tabela}")
def salvar_financeiro(tabela: str, payload: dict): 
    real_table = get_real_table_name(tabela)
    return generic_post(real_table, payload)

@router.delete("/api/financeiro/{tabela}/{id}")
def excluir_financeiro(tabela: str, id: int): 
    real_table = get_real_table_name(tabela)
    return generic_delete(real_table, id)