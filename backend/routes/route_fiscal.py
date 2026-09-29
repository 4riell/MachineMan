from fastapi import APIRouter, UploadFile, File, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Optional
import xmltodict
import sqlite3
import os
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
import requests
import time

router = APIRouter(tags=["Fiscal e Tributário"])
templates = Jinja2Templates(directory="templates")

# ==========================================
# FUNÇÃO MULTI-TENANT
# ==========================================
def obter_loja_logada(request: Request) -> int:
    """Busca o ID da Loja/Tenant correspondente ao usuário logado."""
    usuario_id = request.cookies.get("session_user_id")
    if not usuario_id:
        usuario_id = getattr(request.state, "usuario_id", None)
    if not usuario_id:
        raise HTTPException(status_code=401, detail="Não autorizado. Faça login novamente.")
        
    conn = sqlite3.connect('database/pizzaria.db')
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT loja_id FROM usuarios WHERE id = ?", (int(usuario_id),)).fetchone()
    conn.close()
    
    if row and row["loja_id"]:
        return int(row["loja_id"])
    raise HTTPException(status_code=403, detail="Este usuário não está vinculado a nenhuma loja.")

# ==========================================
# INICIALIZAÇÃO DO BANCO DE DADOS FISCAL
# ==========================================
def init_db_fiscal():
    """Garante que as tabelas de configuração fiscal existam no banco."""
    conn = sqlite3.connect('database/pizzaria.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS empresa_fiscal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cnpj VARCHAR(14), razao_social VARCHAR(150), inscricao_estadual VARCHAR(20),
            crt INTEGER DEFAULT 1, cep VARCHAR(8), logradouro VARCHAR(100), numero VARCHAR(10),
            bairro VARCHAR(50), codigo_municipio_ibge VARCHAR(7), uf VARCHAR(2),
            certificado_path VARCHAR(255), certificado_senha VARCHAR(255),
            csc_id VARCHAR(10), csc_codigo VARCHAR(255), ambiente INTEGER DEFAULT 2,
            loja_id INTEGER DEFAULT 1
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS produto_fiscal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tabela_origem TEXT NOT NULL, produto_id INTEGER NOT NULL,
            ncm VARCHAR(8), cest VARCHAR(7), cfop_venda VARCHAR(4) DEFAULT '5102',
            csosn VARCHAR(4) DEFAULT '102',
            loja_id INTEGER DEFAULT 1,
            UNIQUE(tabela_origem, produto_id, loja_id)
        )
    """)
    
    # Recriação segura da tabela que havia corrompido
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS taxas_pagamento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao VARCHAR(100),
            taxa REAL DEFAULT 0,
            loja_id INTEGER DEFAULT 1
        )
    """)

    # Adiciona colunas para migração segura multi-tenant
    tabelas = ["empresa_fiscal", "produto_fiscal", "taxas_pagamento", "estoque_insumos", "estoque_entradas"]
    for tab in tabelas:
        try: cursor.execute(f"ALTER TABLE {tab} ADD COLUMN loja_id INTEGER DEFAULT 1")
        except: pass

    # Adiciona colunas em 'pedidos' caso não existam
    try: cursor.execute("ALTER TABLE pedidos ADD COLUMN status_fiscal VARCHAR(20) DEFAULT 'pendente'")
    except: pass
    try: cursor.execute("ALTER TABLE pedidos ADD COLUMN chave_acesso_nfe VARCHAR(44)")
    except: pass
    try: cursor.execute("ALTER TABLE pedidos ADD COLUMN url_danfe VARCHAR(255)")
    except: pass
    try: cursor.execute("ALTER TABLE pedidos ADD COLUMN motivo_rejeicao TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE pedidos ADD COLUMN loja_id INTEGER DEFAULT 1")
    except: pass
    
    conn.commit()
    conn.close()

init_db_fiscal()

# ==========================================
# MODELOS DE DADOS (PYDANTIC)
# ==========================================
class ItemVinculo(BaseModel):
    n_item: str
    insumo_id: int
    quantidade_xml: float
    fator_conversao: float
    custo_total_real: float
    cfop: str

class EfetivarEntradaPayload(BaseModel):
    chave_acesso: str
    numero_nota: str
    itens: List[ItemVinculo]

class ProdutoFiscalItem(BaseModel):
    tabela_origem: str
    produto_id: int
    ncm: str
    cfop_venda: str

class SalvarCardapioPayload(BaseModel):
    itens: List[ProdutoFiscalItem]

# ==========================================
# ROTA DA PÁGINA WEB
# ==========================================
@router.get("/fiscal", response_class=HTMLResponse)
async def pagina_fiscal(request: Request):
    loja_id = obter_loja_logada(request)
    return templates.TemplateResponse("fiscal.html", {"request": request})

# ==========================================
# ABA 1: ENTRADAS (XML E ESTOQUE)
# ==========================================
def extrair_valor_imposto(imposto_dict, tag_imposto, tag_valor):
    try:
        if tag_imposto in imposto_dict:
            regime = list(imposto_dict[tag_imposto].keys())[0]
            if tag_valor in imposto_dict[tag_imposto][regime]:
                return float(imposto_dict[tag_imposto][regime][tag_valor])
    except Exception: pass
    return 0.0

def sugerir_cfop_entrada(cfop_saida):
    """Converte CFOP de saída do fornecedor para CFOP de entrada do sistema."""
    cfop_saida = str(cfop_saida)
    if cfop_saida.startswith('5'): return '1' + cfop_saida[1:] # Dentro do estado
    if cfop_saida.startswith('6'): return '2' + cfop_saida[1:] # Fora do estado
    if cfop_saida.startswith('7'): return '3' + cfop_saida[1:] # Exterior
    return cfop_saida

@router.post("/api/fiscal/processar-xml-entrada")
async def processar_xml_entrada(request: Request, file: UploadFile = File(...)):
    loja_id = obter_loja_logada(request)
    if not file.filename.endswith('.xml'):
        raise HTTPException(status_code=400, detail="O ficheiro deve ser um XML.")
    try:
        conteudo_xml = await file.read()
        doc = xmltodict.parse(conteudo_xml, process_namespaces=False)
        nfe = doc['nfeProc']['NFe']['infNFe']
        
        ide = nfe.get('ide', {})
        chave_acesso = nfe['@Id'].replace('NFe', '')
        numero_nota = ide.get('nNF', '')
        data_emissao = ide.get('dhEmi', '')
        operacao = ide.get('natOp', '')
        serie = ide.get('serie', '')
        modelo = ide.get('mod', '')
        
        emitente = nfe.get('emit', {})
        fornecedor = {"cnpj": emitente.get('CNPJ', ''), "nome": emitente.get('xNome', '')}
        
        detalhes = nfe.get('det', [])
        if not isinstance(detalhes, list): detalhes = [detalhes]
        
        itens_processados = []
        for item in detalhes:
            prod = item.get('prod', {})
            impostos = item.get('imposto', {})
            qtd = float(prod.get('qCom', 0))
            
            v_icms = extrair_valor_imposto(impostos, 'ICMS', 'vICMS')
            v_st = extrair_valor_imposto(impostos, 'ICMS', 'vICMSST')
            v_ipi = extrair_valor_imposto(impostos, 'IPI', 'vIPI')
            v_pis = extrair_valor_imposto(impostos, 'PIS', 'vPIS')
            v_cofins = extrair_valor_imposto(impostos, 'COFINS', 'vCOFINS')
            
            custo_total_real = float(prod.get('vProd', 0)) + float(prod.get('vFrete', 0)) + v_ipi + v_st
            
            cfop_fornecedor = prod.get('CFOP', '')

            itens_processados.append({
                "n_item": item.get('@nItem', ''), 
                "nome_fornecedor": prod.get('xProd', ''),
                "ncm": prod.get('NCM', ''), 
                "cfop_fornecedor": cfop_fornecedor, 
                "cfop_sugerido": sugerir_cfop_entrada(cfop_fornecedor),
                "unidade_fornecedor": prod.get('uCom', ''),
                "quantidade_comprada": qtd, 
                "custo_unitario_nf": float(prod.get('vUnCom', 0)),
                "v_ipi": v_ipi,
                "v_pis_cofins": v_pis + v_cofins,
                "custo_total_real": round(custo_total_real, 2)
            })
            
        return {
            "sucesso": True, "chave_acesso": chave_acesso, "numero_nota": numero_nota, 
            "data_emissao": data_emissao, "operacao": operacao, "serie": serie, 
            "modelo": modelo, "fornecedor": fornecedor, "itens": itens_processados
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de parser XML: {str(e)}")

@router.get("/api/fiscal/insumos")
async def listar_insumos(request: Request):
    loja_id = obter_loja_logada(request)
    conn = sqlite3.connect('database/pizzaria.db'); conn.row_factory = sqlite3.Row
    try: return [dict(row) for row in conn.execute("SELECT id, nome, unidade_medida FROM estoque_insumos WHERE loja_id = ? ORDER BY nome", (loja_id,)).fetchall()]
    finally: conn.close()

@router.post("/api/fiscal/efetivar-entrada")
async def efetivar_entrada(request: Request, payload: EfetivarEntradaPayload):
    loja_id = obter_loja_logada(request)
    try:
        conn = sqlite3.connect('database/pizzaria.db')
        cursor = conn.cursor()
        for item in payload.itens:
            insumo_banco = cursor.execute("SELECT quantidade_atual, custo_medio FROM estoque_insumos WHERE id = ? AND loja_id = ?", (item.insumo_id, loja_id)).fetchone()
            if not insumo_banco: continue
            
            qtd_old, custo_old = float(insumo_banco[0] or 0), float(insumo_banco[1] or 0)
            qtd_nova_convertida = item.quantidade_xml * item.fator_conversao
            
            valor_estoque_antigo = qtd_old * custo_old
            nova_qtd_total = qtd_old + qtd_nova_convertida
            novo_custo_medio = (valor_estoque_antigo + item.custo_total_real) / nova_qtd_total if nova_qtd_total > 0 else 0
            
            cursor.execute("UPDATE estoque_insumos SET quantidade_atual = ?, custo_medio = ? WHERE id = ? AND loja_id = ?", (nova_qtd_total, novo_custo_medio, item.insumo_id, loja_id))
            cursor.execute("INSERT INTO estoque_entradas (insumo_id, quantidade_adicionada, custo_total, chave_acesso_nfe, numero_nota, cfop_aplicado, loja_id) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                           (item.insumo_id, qtd_nova_convertida, item.custo_total_real, payload.chave_acesso, payload.numero_nota, item.cfop, loja_id))
        conn.commit()
        return {"sucesso": True, "mensagem": "Estoque atualizado e MAC recalculado!"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/api/fiscal/exportar-entradas")
async def exportar_entradas_fiscais(request: Request):
    loja_id = obter_loja_logada(request)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Mapa de Entradas"
    headers = ["Data Entrada", "Fornecedor", "Número NF-e", "Chave de Acesso", "Produto/Insumo", "CFOP", "Qtd", "IPI / ST (R$)", "Total (R$)"]
    ws.append(headers)
    
    header_fill = PatternFill(start_color="2979FF", end_color="2979FF", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col)
        cell.fill, cell.font, cell.alignment = header_fill, header_font, Alignment(horizontal="center")
    
    try:
        conn = sqlite3.connect('database/pizzaria.db'); conn.row_factory = sqlite3.Row
        entradas = conn.execute("""
            SELECT e.data_compra, 'Fornecedor XML' as fornecedor, e.numero_nota, e.chave_acesso_nfe,
                   i.nome as insumo, e.cfop_aplicado, e.quantidade_adicionada, e.valor_icms_recuperado, e.custo_total
            FROM estoque_entradas e LEFT JOIN estoque_insumos i ON e.insumo_id = i.id
            WHERE e.chave_acesso_nfe IS NOT NULL AND e.loja_id = ? ORDER BY e.data_compra DESC
        """, (loja_id,)).fetchall()
        
        for row in entradas:
            ws.append([row['data_compra'], row['fornecedor'], row['numero_nota'] or "-", row['chave_acesso_nfe'] or "-", row['insumo'] or "Não Identificado", row['cfop_aplicado'] or "-", row['quantidade_adicionada'], row['valor_icms_recuperado'] or 0.0, row['custo_total']])
            
        for col in ws.columns:
            max_length = max((len(str(cell.value)) for cell in col if cell.value), default=0)
            ws.column_dimensions[col[0].column_letter].width = max_length + 2
    finally:
        conn.close()

    os.makedirs("exports", exist_ok=True)
    filename = f"mapa_entradas_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    filepath = os.path.join("exports", filename)
    wb.save(filepath)
    return FileResponse(filepath, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=filename)

# ==========================================
# ABA 2: DADOS DO EMITENTE
# ==========================================
@router.get("/api/fiscal/emitente")
async def get_emitente(request: Request):
    loja_id = obter_loja_logada(request)
    try:
        conn = sqlite3.connect('database/pizzaria.db'); conn.row_factory = sqlite3.Row
        emitente = conn.execute("SELECT * FROM empresa_fiscal WHERE loja_id = ? ORDER BY id DESC LIMIT 1", (loja_id,)).fetchone()
        return dict(emitente) if emitente else {}
    finally:
        conn.close()

@router.post("/api/fiscal/emitente")
async def salvar_emitente(
    request: Request,
    cnpj: str = Form(""), razao_social: str = Form(""), inscricao_estadual: str = Form(""),
    crt: int = Form(1), cep: str = Form(""), logradouro: str = Form(""), numero: str = Form(""),
    bairro: str = Form(""), codigo_municipio_ibge: str = Form(""), uf: str = Form(""),
    ambiente: int = Form(2), csc_id: str = Form(""), csc_codigo: str = Form(""),
    certificado_senha: str = Form(""), certificado: UploadFile = File(None)
):
    loja_id = obter_loja_logada(request)
    conn = sqlite3.connect('database/pizzaria.db')
    cursor = conn.cursor()
    cert_path = ""
    if certificado and certificado.filename:
        os.makedirs("certificados", exist_ok=True)
        cert_path = f"certificados/{certificado.filename}"
        with open(cert_path, "wb") as f: f.write(await certificado.read())

    existe = cursor.execute("SELECT id, certificado_path FROM empresa_fiscal WHERE loja_id = ? LIMIT 1", (loja_id,)).fetchone()
    if existe:
        path_final = cert_path if cert_path else existe[1]
        cursor.execute("""
            UPDATE empresa_fiscal SET cnpj=?, razao_social=?, inscricao_estadual=?, crt=?, cep=?, logradouro=?, numero=?,
            bairro=?, codigo_municipio_ibge=?, uf=?, ambiente=?, csc_id=?, csc_codigo=?, certificado_senha=?, certificado_path=? 
            WHERE id=? AND loja_id=?
        """, (cnpj, razao_social, inscricao_estadual, crt, cep, logradouro, numero, bairro, codigo_municipio_ibge, uf, ambiente, csc_id, csc_codigo, certificado_senha, path_final, existe[0], loja_id))
    else:
        cursor.execute("""
            INSERT INTO empresa_fiscal (cnpj, razao_social, inscricao_estadual, crt, cep, logradouro, numero, bairro, codigo_municipio_ibge, uf, ambiente, csc_id, csc_codigo, certificado_senha, certificado_path, loja_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (cnpj, razao_social, inscricao_estadual, crt, cep, logradouro, numero, bairro, codigo_municipio_ibge, uf, ambiente, csc_id, csc_codigo, certificado_senha, cert_path, loja_id))
    conn.commit()
    conn.close()
    return {"sucesso": True, "mensagem": "Dados do emitente guardados com sucesso!"}

# ==========================================
# ABA 3: TRIBUTAÇÃO DO CARDÁPIO
# ==========================================
@router.get("/api/fiscal/cardapio")
async def listar_tributacao_cardapio(request: Request):
    loja_id = obter_loja_logada(request)
    conn = sqlite3.connect('database/pizzaria.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    tabelas_cardapio = [
        'pizza', 'bebidas', 'sobremesas', 'lanches_gourmet', 'lanches', 
        'combos', 'saladas', 'massas', 'porcoes', 'salgados', 'acai', 
        'esfihas', 'pastas', 'kebabs', 'cafeteria', 'churros', 
        'milk_shakes', 'picoles', 'paes', 'sorvetes', 'tapiocas', 
        'tacas', 'sushis', 'doces', 'pasteis', 'marmitexs'
    ]
    produtos = []
    
    try:
        for tabela in tabelas_cardapio:
            if not cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tabela,)).fetchone(): 
                continue
                
            query = f"""
                SELECT '{tabela}' as tabela_origem, t.id as produto_id, t.nome as produto_nome,
                       COALESCE(f.ncm, '') as ncm, COALESCE(f.cfop_venda, '5102') as cfop_venda
                FROM {tabela} t 
                LEFT JOIN produto_fiscal f ON f.produto_id = t.id AND f.tabela_origem = '{tabela}' AND f.loja_id = {loja_id}
                WHERE t.loja_id = {loja_id}
                ORDER BY t.nome
            """
            produtos.extend([dict(row) for row in cursor.execute(query).fetchall()])
            
        return {"sucesso": True, "itens": produtos}
    except Exception as e: 
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"sucesso": False, "detail": f"Erro BD: {str(e)}"})
    finally: 
        conn.close()

@router.post("/api/fiscal/cardapio")
async def salvar_tributacao_cardapio(request: Request, payload: SalvarCardapioPayload):
    loja_id = obter_loja_logada(request)
    conn = sqlite3.connect('database/pizzaria.db'); cursor = conn.cursor()
    try:
        for item in payload.itens:
            if not item.ncm.strip(): continue
            existe = cursor.execute("SELECT id FROM produto_fiscal WHERE tabela_origem = ? AND produto_id = ? AND loja_id = ?", (item.tabela_origem, item.produto_id, loja_id)).fetchone()
            if existe: cursor.execute("UPDATE produto_fiscal SET ncm = ?, cfop_venda = ? WHERE id = ? AND loja_id = ?", (item.ncm, item.cfop_venda, existe[0], loja_id))
            else: cursor.execute("INSERT INTO produto_fiscal (tabela_origem, produto_id, ncm, cfop_venda, loja_id) VALUES (?, ?, ?, ?, ?)", (item.tabela_origem, item.produto_id, item.ncm, item.cfop_venda, loja_id))
        conn.commit()
        return {"sucesso": True, "mensagem": "Tributação do cardápio atualizada!"}
    except Exception as e: conn.rollback(); raise HTTPException(status_code=500, detail=str(e))
    finally: conn.close()

# ==========================================
# ABA 4: FILA DE EMISSÃO NFC-e
# ==========================================
API_TOKEN_FOCUS = "SEU_TOKEN_AQUI_PRODUCAO_OU_HOMOLOGACAO"

@router.get("/api/fiscal/fila-emissao")
async def listar_fila_emissao(request: Request):
    loja_id = obter_loja_logada(request)
    conn = sqlite3.connect('database/pizzaria.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        query = """
            SELECT id, COALESCE(cliente_nome, 'Consumidor') as cliente_nome, 
                   COALESCE(cliente_telefone, '') as cliente_telefone, 
                   data_hora, COALESCE(valor_total, 0) as valor_total, 
                   COALESCE(status_fiscal, 'pendente') as status_fiscal,
                   chave_acesso_nfe, url_danfe, motivo_rejeicao
            FROM pedidos 
            WHERE loja_id = ?
            ORDER BY id DESC LIMIT 50
        """
        pedidos = [dict(row) for row in cursor.execute(query, (loja_id,)).fetchall()]
        return {"sucesso": True, "pedidos": pedidos}
        
    except Exception as e:
        try:
            query_safe = "SELECT id, cliente_nome, cliente_telefone, data_hora, valor_total FROM pedidos WHERE loja_id = ? ORDER BY id DESC LIMIT 50"
            pedidos_safe = []
            for row in cursor.execute(query_safe, (loja_id,)).fetchall():
                d = dict(row)
                d['status_fiscal'] = 'pendente'
                d['valor_total'] = d.get('valor_total') or 0
                pedidos_safe.append(d)
            return {"sucesso": True, "pedidos": pedidos_safe}
        except Exception as e_safe:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=500, content={"sucesso": False, "detail": f"Erro crítico na Base de Dados: {str(e_safe)}"})
    finally: 
        conn.close()