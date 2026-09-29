from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import sqlite3
import json

router = APIRouter(tags=["Comercial ERP"])
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
# INICIALIZAÇÃO DO BANCO DE DADOS
# ==========================================
def init_db_comercial():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    tabelas = {
        "erp_pedidos": {
            "numero": "VARCHAR(50)", "data_pedido": "DATE", "data_finalizacao": "DATE", "cliente_nome": "VARCHAR(150)", 
            "cliente_id": "INTEGER", "vlr_total": "REAL", 
            "frete": "REAL", "acrescimos": "REAL", "desconto_percent": "REAL",
            "status": "VARCHAR(50)", 
            "vendedor_nome": "VARCHAR(100)", "vendedor_id": "INTEGER", "tabela_preco": "VARCHAR(100)",
            "itens_json": "TEXT", "financeiro_json": "TEXT", "cobranca_json": "TEXT", "notas_internas": "TEXT",
            "transportadora": "VARCHAR(150)",
            "veiculo_placa": "VARCHAR(20)", "veiculo_uf": "VARCHAR(2)", "rntrc": "VARCHAR(50)",
            "reboque_placa": "VARCHAR(20)", "reboque_uf": "VARCHAR(2)", "reboque_rntrc": "VARCHAR(50)",
            "comissao": "REAL", "data_faturamento": "DATE"
        },
        "erp_nfe": {
            "tipo_nota": "VARCHAR(20)", "serie": "VARCHAR(10)", 
            "chave_acesso": "VARCHAR(100)", "data_emissao": "DATE", "data_saida": "DATE",
            "cliente_nome": "VARCHAR(150)", "cliente_id": "INTEGER",
            "vendedor_nome": "VARCHAR(150)", "vendedor_id": "INTEGER", 
            "tabela_preco": "VARCHAR(100)", "finalidade": "VARCHAR(50)", "operacao": "VARCHAR(100)",
            "consumidor_final": "VARCHAR(10)", "ind_presenca": "VARCHAR(50)", "ind_intermediador": "VARCHAR(50)",
            "transp_id": "INTEGER", "transp_nome": "VARCHAR(150)", "transportador": "VARCHAR(150)", "mod_frete": "VARCHAR(50)",
            "placa": "VARCHAR(10)", "veiculo_uf": "VARCHAR(2)", "rntrc": "VARCHAR(50)", 
            "reboque_placa": "VARCHAR(20)", "reboque_uf": "VARCHAR(2)", "reboque_rntrc": "VARCHAR(50)",
            "qtd_vol": "INTEGER", "numeracao_vol": "VARCHAR(100)", "marca_vol": "VARCHAR(100)", 
            "especie_vol": "VARCHAR(100)", "peso_b": "REAL", "peso_l": "REAL",
            "base_icms": "REAL", "valor_icms": "REAL", "base_icms_st": "REAL", "valor_icms_st": "REAL",
            "valor_ipi": "REAL", "valor_frete": "REAL", "valor_seguro": "REAL", "despesas": "REAL",
            "desconto_percent": "REAL", "desconto_valor": "REAL", "total_produtos": "REAL",
            "vlr_total": "REAL", "total_nota": "REAL", "status": "VARCHAR(50)", 
            "xml_ref": "TEXT", "protocolo": "VARCHAR(100)", "info_comp": "TEXT",
            "itens_json": "TEXT", "financeiro_json": "TEXT", "cobranca_json": "TEXT"
        },
        "erp_nfce": {
            "tipo_nota": "VARCHAR(20)", "numero": "VARCHAR(50)", "serie": "VARCHAR(10)", 
            "chave_acesso": "VARCHAR(100)", "data_emissao": "DATE", 
            "cliente_nome": "VARCHAR(150)", "cliente_id": "INTEGER",
            "operador": "VARCHAR(150)", "convenio": "VARCHAR(150)",
            "vlr_total": "REAL", "valor": "REAL", "status": "VARCHAR(50)", 
            "xml_ref": "TEXT", "protocolo": "VARCHAR(100)",
            "itens_json": "TEXT", "financeiro_json": "TEXT", "cobranca_json": "TEXT"
        },
        "erp_nfse": {
            "tipo_nota": "VARCHAR(20)", 
            "data_emissao": "DATE", "data_inicio": "DATE", "data_termino": "DATE",
            "cliente_nome": "VARCHAR(150)", "cliente_id": "INTEGER",
            "vendedor_nome": "VARCHAR(150)", "vendedor_id": "INTEGER", "tabela_preco": "VARCHAR(100)",
            "vlr_iss": "REAL", "inss": "REAL", "ir": "REAL", "csll": "REAL", "pis": "REAL", "cofins": "REAL", 
            "acrescimos": "REAL", "desconto_percent": "REAL", "desconto_valor": "REAL",
            "total_servicos": "REAL", "vlr_total": "REAL", "total": "REAL", "reter_impostos": "VARCHAR(1)",
            "status": "VARCHAR(50)", "notas": "TEXT",
            "itens_json": "TEXT", "financeiro_json": "TEXT", "cobranca_json": "TEXT"
        },
        "erp_canais_venda": {
            "data_criacao": "DATE", "mkt_integracao": "VARCHAR(100)", "mkt_tabela_preco": "VARCHAR(100)"
        },
        "erp_promocoes": {
            "valor_percentual": "REAL", "emitentes": "TEXT",
            "inativo": "VARCHAR(1) DEFAULT 'N'", "produtos_especificos_json": "TEXT",
            "apenas_estoque": "VARCHAR(1)"
        },
        "erp_metas": {
            "periodo": "VARCHAR(20)", "nivel": "VARCHAR(50)", 
            "valor_meta": "REAL", "comissao": "REAL", "status": "VARCHAR(50)", 
            "funcionarios": "TEXT", "valor_vendido": "REAL"
        },
        "erp_relatorios": {
            "modelo": "VARCHAR(150)", "data_geracao": "DATE", "periodo_base": "VARCHAR(100)", 
            "usuario": "VARCHAR(100)", "status": "VARCHAR(50)"
        },
        "erp_tabelas_preco": {
            "nome": "VARCHAR(100)","status": "VARCHAR(20)"
        },
        "erp_portarias": {
           "status": "VARCHAR(20)",
            "nome": "VARCHAR(150)", "tipo": "VARCHAR(50)", "mensagem": "TEXT",
            "inativo": "VARCHAR(1)"
        },
        # TABELA 1: CONFIGURAÇÕES E CONEXÕES DA INTEGRAÇÃO
        "erp_integracoes_config": {
            "entidade": "VARCHAR(100)", "plataforma": "VARCHAR(100)",
            "canal_venda": "VARCHAR(100)", "tabela_preco": "VARCHAR(100)", "opcoes_json": "TEXT",
            "token_acesso": "TEXT", "token_reconexao": "TEXT", "token_validade": "DATE",
            "data_criacao": "DATETIME"
        },
    }

    for tabela, colunas in tabelas.items():
        cursor.execute(f"CREATE TABLE IF NOT EXISTS {tabela} (id INTEGER PRIMARY KEY AUTOINCREMENT)")
        garantir_colunas(cursor, tabela, colunas)

    conn.commit()
    conn.close()

init_db_comercial()

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
    except Exception: return []

def generic_post(tabela, payload):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        if 'id' in payload and not str(payload['id']).strip():
            del payload['id']

        cursor.execute(f"CREATE TABLE IF NOT EXISTS {tabela} (id INTEGER PRIMARY KEY AUTOINCREMENT)")
        cursor.execute(f"PRAGMA table_info({tabela})")
        colunas_tabela = [row[1] for row in cursor.fetchall()]
        
        for key in payload.keys():
            if key not in colunas_tabela and key != 'id':
                try: cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN {key} TEXT")
                except Exception as e: print(f"Aviso coluna {key}: {e}")

        campos = list(payload.keys())
        if payload.get('id'):
            id_val = payload.pop('id')
            campos.remove('id')
            if not campos: return {"sucesso": True}
            set_query = ", ".join([f"{c}=?" for c in campos])
            cursor.execute(f"UPDATE {tabela} SET {set_query} WHERE id=?", [payload[c] for c in campos] + [id_val])
        else:
            if 'id' in campos: 
                campos.remove('id')
                payload.pop('id', None)
            if not campos: return {"sucesso": False, "erro": "Payload vazio"}
            valores = [payload[c] for c in campos]
            marcadores = ",".join(["?"] * len(campos))
            cursor.execute(f"INSERT INTO {tabela} ({','.join(campos)}) VALUES ({marcadores})", valores)
        
        conn.commit()
        conn.close()
        return {"sucesso": True}
    except Exception as e: 
        print(f"Erro fatal ao salvar em {tabela}: {e}")
        return JSONResponse(status_code=400, content={"sucesso": False, "erro": str(e)})

def generic_delete(tabela, id):
    try:
        conn = sqlite3.connect(DB_PATH); conn.execute(f"DELETE FROM {tabela} WHERE id=?", (id,))
        conn.commit(); conn.close(); return {"sucesso": True}
    except Exception: return {"sucesso": False}

# ==========================================
# ROTAS DO COMERCIAL (UI E API)
# ==========================================
@router.get("/comercial", response_class=HTMLResponse)
async def pagina_comercial(request: Request):
    return templates.TemplateResponse("comercial.html", {"request": request})

@router.get("/api/comercial/opcoes_formularios")
def get_opcoes_comercial():
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
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

    def fetch_erp(query):
        try: return [dict(r) for r in conn.execute(query).fetchall()]
        except Exception as e: return []

    data["clientes"] = get_todas_opcoes("erp_clientes", ["nome", "nome_fantasia"])
    data["vendedores"] = get_todas_opcoes("erp_funcionarios", ["nome"])
    data["canais"] = get_todas_opcoes("erp_canais_venda", ["mkt_integracao", "id"])
    
    # DROPDOWNS FINANCEIROS E COBRANÇA
    data["bancos"] = get_todas_opcoes("erp_bancos", ["nome", "descricao"])
    data["formas_pgto"] = get_todas_opcoes("erp_formas_pagamento", ["descricao", "nome"])
    data["condicoes"] = get_todas_opcoes("erp_condicoes_pagamento", ["nome", "descricao"])
    
    data["produtos"] = fetch_erp("SELECT * FROM erp_produtos ORDER BY nome")
    
    # Busca apenas em erp_emitentes, pois erp_empresas foi excluída
    emitentes_ctrl = get_todas_opcoes("erp_emitentes", ["razao_social", "fantasia", "nome"])
    data["empresas"] = [{"nome": n} for n in sorted(list({e["nome"] for e in emitentes_ctrl}))]
    
    data["categorias"] = []
    data["unidades"] = []
    data["veiculos"] = []
    
    data["marcas"] = get_todas_opcoes("erp_marcas", ["descricao", "nome"])
    data["grupos"] = get_todas_opcoes("erp_grupos_produtos", ["nome_grupo", "nome", "descricao"])
    
    data["cfops"] = fetch_erp("SELECT codigo_cfop, descricao FROM erp_operacoes ORDER BY codigo_cfop")
    data["convenios"] = get_todas_opcoes("erp_convenios", ["nome"])
    
    data["transportadoras"] = get_todas_opcoes("erp_transportadoras", ["razao_social", "nome_fantasia", "nome"])
    data["tabelas"] = get_todas_opcoes("erp_tabelas_preco", ["nome"]) 
    
    # CORREÇÃO PORTARIAS: Removido ORDER BY numero (coluna inexistente) e ajustado para ORDER BY id
    data["portarias"] = fetch_erp("SELECT * FROM erp_portarias WHERE inativo != 'S' OR inativo IS NULL ORDER BY id")
    
    conn.close()
    return data

def get_real_table_name(tabela: str) -> str:
    base_tabela = tabela.replace("com_", "").replace("erp_", "")
    unificadas = {
        "pedidos": "erp_pedidos",
        "nfe": "erp_nfe",
        "nfce": "erp_nfce",
        "nfse": "erp_nfse",
        "canais": "erp_canais_venda",
        "canais_venda": "erp_canais_venda",
        "promocoes": "erp_promocoes",
        "metas": "erp_metas",
        "relatorios": "erp_relatorios",
        "integracoes_config": "erp_integracoes_config", # MAPEADO NOVA TABELA CONFIG
        "integracoes_logs": "erp_integracoes_logs",     # MAPEADO NOVA TABELA LOGS
        "integracoes": "erp_integracoes_config"         # Alias padrão
    }
    return unificadas.get(base_tabela, f"erp_{base_tabela}")

@router.get("/api/comercial/{tabela}")
def listar_comercial(tabela: str): 
    real_table = get_real_table_name(tabela)
    return generic_get(real_table)

@router.post("/api/comercial/{tabela}")
def salvar_comercial(tabela: str, payload: dict): 
    real_table = get_real_table_name(tabela)
    
    if real_table == "erp_nfe":
        veic_placa = payload.get("veiculo_placa") or payload.get("placa")
        veic_uf = payload.get("veiculo_uf")
        
        if (not veic_uf or str(veic_uf).strip() in ["", "-"]) and veic_placa:
            try:
                conn = sqlite3.connect(DB_PATH)
                conn.row_factory = sqlite3.Row
                row_t = conn.execute("SELECT * FROM erp_transportadoras WHERE placa_veiculo = ?", (veic_placa,)).fetchone()
                if row_t:
                    row_dict_t = dict(row_t)
                    uf_val_t = row_dict_t.get('uf_veiculo') or row_dict_t.get('uf')
                    if uf_val_t:
                        payload["veiculo_uf"] = uf_val_t
                conn.close()
            except Exception as e:
                print(f"Erro na busca de UF do veiculo: {e}")

        txt_fields = ["veiculo_uf", "tipo_nota", "chave_acesso", "protocolo", 
                      "xml_ref", "transportador", "marca_vol", "especie_vol"]
        for f in txt_fields:
            if not payload.get(f) or str(payload.get(f)).strip() == "":
                payload[f] = "-"
                
        num_fields = ["vlr_total", "qtd_vol", "peso_b", "peso_l", 
                      "despesas", "desconto_percent", "desconto_valor", "total_nota", 
                      "total_produtos", "valor_seguro"]
        for f in num_fields:
            val = payload.get(f)
            if val is None or str(val).strip() == "":
                payload[f] = 0.0
            else:
                try: payload[f] = float(val)
                except ValueError: payload[f] = 0.0

    elif real_table == "erp_nfse":
        num_fields = ["vlr_iss", "inss", "ir", "csll", "pis", "cofins", "acrescimos", "desconto_percent", "desconto_valor", "total_servicos", "total", "vlr_total"]
        for f in num_fields:
            val = payload.get(f)
            if val is None or str(val).strip() == "":
                payload[f] = 0.0
            else:
                try: payload[f] = float(val)
                except ValueError: payload[f] = 0.0

    return generic_post(real_table, payload)

@router.delete("/api/comercial/{tabela}/{id}")
def excluir_comercial(tabela: str, id: int): 
    real_table = get_real_table_name(tabela)
    return generic_delete(real_table, id)

# ==========================================
# MOTOR DE PESQUISA OTIMIZADO DO COMERCIAL
# ==========================================
@router.get("/api/comercial/pesquisar/{entidade}")
def pesquisar_entidade(entidade: str, q: str = ""):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        tabela_map = {
            "clientes": ["erp_clientes"],
            "vendedores": ["erp_funcionarios"],
            "funcionarios": ["erp_funcionarios"],
            "empresas": ["erp_emitentes"], 
            "transportadoras": ["erp_transportadoras"],
            "integracoes": ["erp_integracoes_config"], # Otimizado para procurar pela plataforma configurada
            "servicos": ["erp_serv_itens", "erp_produtos"],
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
            
            for col in ["nome_razao", "razao_social", "fantasia", "nome_fantasia", "nome", "nome_grupo", "descricao", "plataforma"]:
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
                    "vlr_varejo": d.get("vlr_varejo", d.get("valor", d.get("preco", 0))),
                    "unidade_medida": d.get("unidade_medida", "UN"),
                    "cfop": d.get("cfop", d.get("codigo_cfop", ""))
                }
                item["preco"] = item["vlr_varejo"]
                res.append(item)
                
            if len(res) >= 15:
                break
                
        return res
    except Exception as e:
        print(f"Erro pesquisa comercial: {e}")
        return []
    finally:
        conn.close()