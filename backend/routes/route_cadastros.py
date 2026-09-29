from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import sqlite3
import json
from typing import Optional

router = APIRouter(tags=["Cadastros ERP"])
templates = Jinja2Templates(directory="templates")

# ==========================================
# FUNÇÃO INTELIGENTE DE ATUALIZAÇÃO DE SCHEMAS
# ==========================================
def garantir_colunas(cursor, tabela, colunas):
    cursor.execute(f"PRAGMA table_info({tabela})")
    colunas_existentes = [row[1] for row in cursor.fetchall()]
    for col, tipo in colunas.items():
        if col not in colunas_existentes:
            try: 
                cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN {col} {tipo}")
            except Exception as e: 
                pass

# ==========================================
# ALIAS INTELIGENTE DE TABELAS APAGADAS
# ==========================================
def get_real_table_name(tabela: str) -> str:
    """Interceptador para redirecionar tabelas que foram apagadas para suas novas versões."""
    t = tabela.replace("fin_", "").replace("erp_", "")
    
    if t == "empresas": return "erp_emitentes"
    if t == "categorias": return "erp_grupos_produtos"
    
    return f"erp_{t}"

# ==========================================
# INICIALIZAÇÃO DO BANCO DE DADOS (100% ERP)
# ==========================================
def init_db_cadastros_completos():
    conn = sqlite3.connect('database/pizzaria.db')
    try:
        cursor = conn.cursor()
        
        tabelas = {
            "erp_clientes": {
                "nome": "VARCHAR(100)", "telefone": "VARCHAR(20)", "tipo_cliente": "VARCHAR(1) DEFAULT 'F'", 
                "situacao": "VARCHAR(20) DEFAULT 'NORMAL'", "limite_credito": "REAL", 
                "nascimento": "DATE", "email": "VARCHAR(100)", 
                "cpf_cnpj": "VARCHAR(20)", "uf": "VARCHAR(2)"
            },
            
            "erp_fornecedores": {
                "tipo_fornecedor": "VARCHAR(1) DEFAULT 'J'", "numero": "VARCHAR(20)", 
                "bairro": "VARCHAR(100)", "uf": "VARCHAR(2)", "cep": "VARCHAR(20)",
                "email": "VARCHAR(100)", "telefone": "VARCHAR(20)", "contato": "VARCHAR(100)"
            },
            
            "erp_funcionarios": {
                "nome": "VARCHAR(100)", "rg": "VARCHAR(20)", "cpf": "VARCHAR(20)", "ctps": "VARCHAR(50)", 
                "telefone": "VARCHAR(20)", "celular": "VARCHAR(20)",
                "email": "VARCHAR(100)", "numero": "VARCHAR(20)", "bairro": "VARCHAR(100)", 
                "senha": "VARCHAR(100)",
                "remuneracoes_json": "TEXT", "frequencias_json": "TEXT", "periodicos_json": "TEXT" 
            },
            
            "erp_convenios": {
                "nome": "VARCHAR(150)", "email": "VARCHAR(100)", "telefone": "VARCHAR(20)"
            },
            
            "erp_marcas": {
                "nome": "VARCHAR(100)"
            },
            
            "erp_tabelas_preco": {
                "nome": "VARCHAR(100)"
            }, 
            
            "erp_produtos": {
                "nome": "VARCHAR(100)", "marca_id": "INTEGER", "grupo_id": "INTEGER",
                "tipo_lucro": "VARCHAR(10) DEFAULT 'MARGEM'", 
                "estoque_min": "REAL", "estoque_max": "REAL", 
                "enviar_balanca": "VARCHAR(1) DEFAULT 'N'", "inserir_gtin_nfe": "VARCHAR(1) DEFAULT 'S'", 
                "monitorar_estoque": "VARCHAR(1) DEFAULT 'S'", "mva": "REAL", "red_bc_icms": "REAL", 
                "pis": "REAL", "ipi": "REAL", "difer_icms": "REAL", "red_bc_icms_st": "REAL", 
                "cofins": "REAL", "cod_indice_part_municipios": "VARCHAR(50)",
                "vlr_compra": "REAL", "vlr_medio": "REAL", "perc_comissao": "REAL", 
                "perc_max_desconto": "REAL", "saldo_fisico": "REAL", "reserva": "REAL", 
                "saldo_previsto": "REAL", "sku": "VARCHAR(50)", "localizacao": "VARCHAR(100)", 
                "ncm": "VARCHAR(50)"
            },
            
            "erp_produto_precos": {
                "produto_id": "INTEGER", "tabela": "VARCHAR(100)", "markup": "REAL", "valor": "REAL", 
                "minimo": "REAL", "custo_medio": "REAL"
            },
            
            "erp_transportadoras": {
                "nome": "VARCHAR(150)", "cpf_cnpj": "VARCHAR(20)", "telefone": "VARCHAR(20)", 
                "email": "VARCHAR(100)", "uf": "VARCHAR(2)"
            },
            
            "erp_operacoes": {
                "codigo_cfop": "VARCHAR(20)", "descricao": "TEXT", "tipo": "VARCHAR(20)", 
                "nome": "VARCHAR(150)", "nat_credito": "VARCHAR(100)", "plano_conta": "VARCHAR(100)", 
                "movimenta_estoque": "VARCHAR(1)"
            },
            
            "erp_bancos": {
                "codigo": "VARCHAR(10)", "nome": "VARCHAR(100)"
            },
            
            "erp_contas_bancarias": {
                "nome": "VARCHAR(100)", 
                "banco": "VARCHAR(50)", "agencia": "VARCHAR(20)", "digito_ag": "VARCHAR(5)", 
                "conta_corrente": "VARCHAR(20)", "digito_cc": "VARCHAR(5)", 
                "juros_mes": "REAL", "multa": "REAL", "dias_de_carencia": "INTEGER", 
                "data_saldo": "DATE", "saldo_inicial": "REAL",
                "ultimo_fechamento": "DATE", "fluxo_caixa": "VARCHAR(1)", "boleto": "VARCHAR(1)", "inativo": "VARCHAR(1)"
            },
            
            "erp_formas_pagamento": {
                "descricao": "VARCHAR(100)", "codigo_fiscal": "VARCHAR(20)", 
                "conta_banco": "VARCHAR(100)", "parcela_minima": "REAL", "inativo": "VARCHAR(1)", 
                "gera_financeiro": "VARCHAR(1)", "baixa_automatica": "VARCHAR(1)"
            },
            
            "erp_condicoes_pagamento": {
                "forma_pgto": "VARCHAR(100)", 
                "nome": "VARCHAR(100)",
                "no_parcelas": "INTEGER", "dia_1a_parcela": "INTEGER", "dias_entre_parcelas": "INTEGER", 
                "inativo": "VARCHAR(1)"
            },
            
            "erp_grupos_produtos": {
                "nome_grupo": "VARCHAR(100)"
            },
            "erp_grade_cor": {
                "nome": "VARCHAR(50)", "status": "VARCHAR(20) DEFAULT 'ATIVO'", "ordem": "INTEGER"
            },
            "erp_grade_tamanho": {
                "nome": "VARCHAR(50)", "status": "VARCHAR(20) DEFAULT 'ATIVO'", "ordem": "INTEGER"
            },
            "erp_carteiras": {
                "carteira": "VARCHAR(100)", "vendedor": "VARCHAR(100)"
            },
            "erp_indicacoes": {
                "cliente": "VARCHAR(150)", "porcentagem": "REAL"
            }
        }

        for tabela, colunas in tabelas.items():
            cursor.execute(f"CREATE TABLE IF NOT EXISTS {tabela} (id INTEGER PRIMARY KEY AUTOINCREMENT)")
            garantir_colunas(cursor, tabela, colunas)
            
        cursor.execute("SELECT COUNT(*) FROM erp_tabelas_preco")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO erp_tabelas_preco (nome) VALUES ('Geral'), ('Atacado'), ('Revenda')")

        conn.commit()
    finally:
        conn.close()

init_db_cadastros_completos()

# ==========================================
# ROTAS E API REST (CASCATA BLINDADA)
# ==========================================
@router.get("/cadastros", response_class=HTMLResponse)
async def pagina_cadastros(request: Request):
    return templates.TemplateResponse("cadastros.html", {"request": request})

def generic_get(tabela, order_by="id"):
    conn = sqlite3.connect('database/pizzaria.db')
    conn.row_factory = sqlite3.Row
    try:
        res = [dict(r) for r in conn.execute(f"SELECT * FROM {tabela} ORDER BY {order_by}").fetchall()]
        return res
    except Exception as e:
        return []
    finally:
        conn.close()

def generic_post(tabela, payload):
    conn = sqlite3.connect('database/pizzaria.db')
    try:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({tabela})")
        colunas_tabela = [row[1] for row in cursor.fetchall()]
        
        for key, value in payload.items():
            if key in ['listasExtras', 'tabelasPreco']: continue 
            
            if key not in colunas_tabela and key != 'id':
                tipo_sql = "TEXT"
                if isinstance(value, int):
                    tipo_sql = "INTEGER"
                elif isinstance(value, float):
                    tipo_sql = "REAL"
                    
                try:
                    cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN {key} {tipo_sql}")
                    colunas_tabela.append(key)
                except: pass

        payload_limpo = {k: v for k, v in payload.items() if k in colunas_tabela}
        campos = list(payload_limpo.keys())
        novo_id = None
        sucesso = False

        if payload_limpo.get('id'):
            campos.remove('id')
            valores_update = [payload_limpo[c] for c in campos] + [payload_limpo['id']]
            set_query = ", ".join([f"{c}=?" for c in campos])
            cursor.execute(f"UPDATE {tabela} SET {set_query} WHERE id=?", valores_update)
            novo_id = payload_limpo['id']
        else:
            if 'id' in campos: campos.remove('id')
            valores = [payload_limpo[c] for c in campos]
            cursor.execute(f"INSERT INTO {tabela} ({','.join(campos)}) VALUES ({','.join(['?']*len(campos))})", valores)
            novo_id = cursor.lastrowid
            
        conn.commit()
        sucesso = True
        return {"sucesso": sucesso, "id": novo_id}
    except Exception as e:
        return {"sucesso": False, "id": None}
    finally:
        conn.close()

def generic_delete(tabela, id):
    conn = sqlite3.connect('database/pizzaria.db')
    try:
        conn.execute(f"DELETE FROM {tabela} WHERE id=?", (id,))
        conn.commit()
        return {"sucesso": True}
    except Exception as e:
        return {"sucesso": False, "erro": str(e)}
    finally:
        conn.close()

# ==========================================
# ENDPOINTS ESPECÍFICOS
# ==========================================
@router.get("/api/cadastros/produtos")
def get_produtos():
    conn = sqlite3.connect('database/pizzaria.db')
    conn.row_factory = sqlite3.Row
    try:
        query = """
            SELECT p.* FROM erp_produtos p 
            ORDER BY p.nome
        """
        produtos = [dict(r) for r in conn.execute(query).fetchall()]
        
        precos = [dict(r) for r in conn.execute("SELECT * FROM erp_produto_precos").fetchall()]
        from collections import defaultdict
        precos_dict = defaultdict(list)
        for pr in precos:
            precos_dict[pr['produto_id']].append(pr)
            
        for p in produtos:
            p['tabelasPreco'] = precos_dict.get(p['id'], [])
            
        return produtos
    finally:
        conn.close()

@router.get("/api/cadastros/grupos_produtos")
def get_grupos_produtos():
    conn = sqlite3.connect('database/pizzaria.db')
    conn.row_factory = sqlite3.Row
    try:
        # Puxa o grupo e calcula dinamicamente quantos produtos estão vinculados a ele
        query = """
            SELECT g.*, 
                   (SELECT COUNT(*) FROM erp_produtos p WHERE p.grupo_id = g.id) as n_produtos
            FROM erp_grupos_produtos g
            ORDER BY g.nome_grupo
        """
        return [dict(r) for r in conn.execute(query).fetchall()]
    finally:
        conn.close()

@router.post("/api/cadastros/produtos")
def save_produto(payload: dict):
    tabelas_preco = payload.pop('tabelasPreco', [])
    result = generic_post("erp_produtos", payload)
    
    if result.get('sucesso') and result.get('id'):
        prod_id = result['id']
        conn = sqlite3.connect('database/pizzaria.db')
        try:
            conn.execute("DELETE FROM erp_produto_precos WHERE produto_id=?", (prod_id,))
            for tab in tabelas_preco:
                conn.execute(
                    "INSERT INTO erp_produto_precos (produto_id, tabela, custo_medio, markup, valor, minimo) VALUES (?, ?, ?, ?, ?, ?)",
                    (prod_id, tab.get('tabela'), tab.get('custo_medio'), tab.get('markup'), tab.get('valor'), tab.get('minimo'))
                )
            conn.commit()
        except: pass
        finally: conn.close()
            
    return result

@router.delete("/api/cadastros/produtos/{id}")
def delete_produto(id: int): 
    conn = sqlite3.connect('database/pizzaria.db')
    try:
        conn.execute("DELETE FROM erp_produto_precos WHERE produto_id=?", (id,))
        conn.execute("DELETE FROM erp_produtos WHERE id=?", (id,))
        conn.commit()
        return {"sucesso": True}
    finally:
        conn.close()

@router.get("/api/cadastros/tabelas_preco")
def get_tabelas_preco():
    conn = sqlite3.connect('database/pizzaria.db')
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("SELECT nome FROM erp_tabelas_preco ORDER BY nome").fetchall()]
    finally:
        conn.close()

@router.get("/api/cadastros/opcoes_cliente")
def get_opcoes_cliente():
    conn = sqlite3.connect('database/pizzaria.db')
    conn.row_factory = sqlite3.Row
    try:
        convenios = [dict(r) for r in conn.execute("SELECT id, nome FROM erp_convenios ORDER BY nome").fetchall()]
        carteiras = [dict(r) for r in conn.execute("SELECT id, carteira FROM erp_carteiras ORDER BY carteira").fetchall()]
        return {"convenios": convenios, "carteiras": carteiras}
    except Exception: return {}
    finally: conn.close()

@router.get("/api/cadastros/opcoes_produto")
def get_opcoes_produto():
    conn = sqlite3.connect('database/pizzaria.db')
    conn.row_factory = sqlite3.Row
    try:
        res = {
            "grupos": [dict(r) for r in conn.execute("SELECT id, nome_grupo as nome FROM erp_grupos_produtos ORDER BY nome_grupo").fetchall()],
            "marcas": [dict(r) for r in conn.execute("SELECT id, nome FROM erp_marcas ORDER BY nome").fetchall()],
            "cores": [dict(r) for r in conn.execute("SELECT id, nome FROM erp_grade_cor WHERE status='ATIVO' ORDER BY nome").fetchall()],
            "tamanhos": [dict(r) for r in conn.execute("SELECT id, nome FROM erp_grade_tamanho WHERE status='ATIVO' ORDER BY nome").fetchall()]
        }
        return res
    except Exception: return {}
    finally: conn.close()

@router.get("/api/cadastros/opcoes_funcionario")
def get_opcoes_funcionario():
    conn = sqlite3.connect('database/pizzaria.db')
    conn.row_factory = sqlite3.Row
    try:
        res = {
            "funcoes": [],
            "empresas": [dict(r) for r in conn.execute("SELECT id, razao_social, nome FROM erp_emitentes ORDER BY razao_social").fetchall()],
            "caixas": []
        }
        return res
    except Exception: return {"funcoes": [], "empresas": [], "caixas": []}
    finally: conn.close()

# PESQUISA MODAIS
@router.get("/api/cadastros/pesquisa/ncms")
def pesquisar_ncms(q: str = ""):
    return []

@router.get("/api/cadastros/pesquisa/clientes")
def pesquisar_clientes(q: str = ""):
    conn = sqlite3.connect('database/pizzaria.db')
    conn.row_factory = sqlite3.Row
    try:
        query = "SELECT id, nome, cpf_cnpj FROM erp_clientes WHERE nome LIKE ? OR cpf_cnpj LIKE ? LIMIT 50"
        return [dict(r) for r in conn.execute(query, (f"%{q}%", f"%{q}%")).fetchall()]
    finally:
        conn.close()

# ==========================================
# FUNCIONÁRIOS
# ==========================================
@router.get("/api/cadastros/funcionarios")
def get_funcionarios(): 
    conn = sqlite3.connect('database/pizzaria.db')
    conn.row_factory = sqlite3.Row
    try:
        query = "SELECT f.* FROM erp_funcionarios f ORDER BY f.nome"
        res = [dict(r) for r in conn.execute(query).fetchall()]
        return res
    finally:
        conn.close()

@router.post("/api/cadastros/funcionarios")
def save_funcionario(payload: dict):
    extras = payload.pop('listasExtras', {})
    if 'remuneracoes' in extras: payload['remuneracoes_json'] = json.dumps(extras['remuneracoes'])
    if 'frequencias' in extras: payload['frequencias_json'] = json.dumps(extras['frequencias'])
    if 'periodicos' in extras: payload['periodicos_json'] = json.dumps(extras['periodicos'])
    return generic_post("erp_funcionarios", payload)

@router.delete("/api/cadastros/funcionarios/{id}")
def delete_funcionario(id: int): return generic_delete("erp_funcionarios", id)

# ==========================================
# CLIENTES
# ==========================================
@router.get("/api/cadastros/clientes")
def get_clientes():
    conn = sqlite3.connect('database/pizzaria.db')
    conn.row_factory = sqlite3.Row
    try:
        res = [dict(r) for r in conn.execute("SELECT * FROM erp_clientes ORDER BY nome").fetchall()]
        return res
    finally:
        conn.close()

@router.post("/api/cadastros/clientes")
def save_cliente(payload: dict): return generic_post("erp_clientes", payload)

@router.delete("/api/cadastros/clientes/{id}")
def delete_cliente(id: int):
    conn = sqlite3.connect('database/pizzaria.db')
    try:
        conn.execute("DELETE FROM erp_clientes WHERE id=?", (id,))
        conn.commit()
        return {"sucesso": True}
    finally:
        conn.close()

# --- ROTA CORINGA COM INTERCEPTADOR ---
@router.get("/api/cadastros/{tabela}")
def listar_cadastro(tabela: str): 
    real_tabela = get_real_table_name(tabela)
    return generic_get(real_tabela)

@router.post("/api/cadastros/{tabela}")
def salvar_cadastro(tabela: str, payload: dict): 
    real_tabela = get_real_table_name(tabela)
    return generic_post(real_tabela, payload)

@router.delete("/api/cadastros/{tabela}/{id}")
def excluir_cadastro(tabela: str, id: int): 
    real_tabela = get_real_table_name(tabela)
    return generic_delete(real_tabela, id)