from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import sqlite3
from datetime import datetime
import calendar

router = APIRouter(tags=["Dashboard ERP"])
templates = Jinja2Templates(directory="templates")

DB_PATH = 'database/pizzaria.db'

def formatar_moeda(valor):
    """Formata float para string de moeda no padrão PT-BR."""
    if valor is None: return "0,00"
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

@router.get('/dashboard', response_class=HTMLResponse)
async def render_dashboard(request: Request):
    """Renderiza a página HTML do Dashboard."""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@router.get('/api/dashboard/dados')
async def get_dashboard_dados():
    """
    API que retorna os dados consolidados do banco pizzaria.db
    utilizando as tabelas do padrão erp_.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # --- 1. BUSCA DE KPIs (Vendas / Pedidos) ---
    kpis = {
        "vendas_total_periodo": 0, "vendas_mes_atual": 0, "vendas_mes_anterior": 0,
        "num_vendas_total": 0, "num_vendas_mes_atual": 0, "num_vendas_mes_anterior": 0,
        "ticket_medio_total": 0, "ticket_medio_mes_atual": 0, "ticket_medio_mes_anterior": 0
    }
    
    try:
        # Busca somatórios e contagens separando por mês atual e anterior
        query_kpis = """
            SELECT 
                SUM(vlr_total) as total_geral,
                COUNT(id) as qtd_geral,
                SUM(CASE WHEN strftime('%Y-%m', data_pedido) = strftime('%Y-%m', 'now') THEN vlr_total ELSE 0 END) as total_atual,
                COUNT(CASE WHEN strftime('%Y-%m', data_pedido) = strftime('%Y-%m', 'now') THEN 1 END) as qtd_atual,
                SUM(CASE WHEN strftime('%Y-%m', data_pedido) = strftime('%Y-%m', 'now', '-1 month') THEN vlr_total ELSE 0 END) as total_ant,
                COUNT(CASE WHEN strftime('%Y-%m', data_pedido) = strftime('%Y-%m', 'now', '-1 month') THEN 1 END) as qtd_ant
            FROM erp_pedidos 
            WHERE status != 'Cancelado'
        """
        row = cursor.execute(query_kpis).fetchone()
        
        if row and row['qtd_geral'] > 0:
            kpis["vendas_total_periodo"] = row['total_geral'] or 0
            kpis["vendas_mes_atual"] = row['total_atual'] or 0
            kpis["vendas_mes_anterior"] = row['total_ant'] or 0
            
            kpis["num_vendas_total"] = row['qtd_geral'] or 0
            kpis["num_vendas_mes_atual"] = row['qtd_atual'] or 0
            kpis["num_vendas_mes_anterior"] = row['qtd_ant'] or 0

            kpis["ticket_medio_total"] = kpis["vendas_total_periodo"] / kpis["num_vendas_total"] if kpis["num_vendas_total"] > 0 else 0
            kpis["ticket_medio_mes_atual"] = kpis["vendas_mes_atual"] / kpis["num_vendas_mes_atual"] if kpis["num_vendas_mes_atual"] > 0 else 0
            kpis["ticket_medio_mes_anterior"] = kpis["vendas_mes_anterior"] / kpis["num_vendas_mes_anterior"] if kpis["num_vendas_mes_anterior"] > 0 else 0
    except Exception as e:
        print(f"Erro ao buscar KPIs: {e}")

    # --- 2. BUSCA FINANCEIRA (Contas a Receber e Pagar) ---
    fin = {
        "receber": {"atraso": 0, "semana": 0, "hoje": 0},
        "pagar": {"atraso": 0, "semana": 0, "hoje": 0}
    }

    try:
        # Contas a Receber
        query_rec = """
            SELECT 
                SUM(CASE WHEN data_vencimento < date('now') THEN valor ELSE 0 END) as atraso,
                SUM(CASE WHEN data_vencimento = date('now') THEN valor ELSE 0 END) as hoje,
                SUM(CASE WHEN data_vencimento > date('now') AND data_vencimento <= date('now', '+7 days') THEN valor ELSE 0 END) as semana
            FROM erp_recebimentos 
            WHERE status NOT IN ('Pago', 'Baixado', 'Cancelado')
        """
        row_rec = cursor.execute(query_rec).fetchone()
        if row_rec:
            fin["receber"]["atraso"] = row_rec['atraso'] or 0
            fin["receber"]["hoje"] = row_rec['hoje'] or 0
            fin["receber"]["semana"] = row_rec['semana'] or 0

        # Contas a Pagar
        query_pag = """
            SELECT 
                SUM(CASE WHEN data_vencimento < date('now') THEN valor ELSE 0 END) as atraso,
                SUM(CASE WHEN data_vencimento = date('now') THEN valor ELSE 0 END) as hoje,
                SUM(CASE WHEN data_vencimento > date('now') AND data_vencimento <= date('now', '+7 days') THEN valor ELSE 0 END) as semana
            FROM erp_pagamentos 
            WHERE status NOT IN ('Pago', 'Baixado', 'Cancelado')
        """
        row_pag = cursor.execute(query_pag).fetchone()
        if row_pag:
            fin["pagar"]["atraso"] = row_pag['atraso'] or 0
            fin["pagar"]["hoje"] = row_pag['hoje'] or 0
            fin["pagar"]["semana"] = row_pag['semana'] or 0
    except Exception as e:
        print(f"Erro ao buscar Financeiro: {e}")

    # --- 3. DADOS DOS GRÁFICOS ---
    graficos = {
        "grupos_vendidos": {"labels": [], "data": []},
        "marcas_vendidas": {"labels": [], "data": []},
        "vendas_hora": {"labels": [f"{i}h" for i in range(24)], "data": [0]*24},
        "vendas_dia": {
            "labels": [f"Dia {i}" for i in range(1, 32)],
            "fev_data": [0]*31,
            "mar_data": [0]*31 
        }
    }

    try:
        query_hora = "SELECT strftime('%H', data_pedido) as hora, COUNT(id) as qtd FROM erp_pedidos WHERE status != 'Cancelado' GROUP BY hora"
        for row in cursor.execute(query_hora).fetchall():
            if row['hora']:
                hora_int = int(row['hora'])
                graficos["vendas_hora"]["data"][hora_int] = row['qtd']
    except Exception: pass

    try:
        query_dia_atual = "SELECT CAST(strftime('%d', data_pedido) AS INTEGER) as dia, SUM(vlr_total) as total FROM erp_pedidos WHERE strftime('%Y-%m', data_pedido) = strftime('%Y-%m', 'now') AND status != 'Cancelado' GROUP BY dia"
        for row in cursor.execute(query_dia_atual).fetchall():
            graficos["vendas_dia"]["mar_data"][row['dia'] - 1] = row['total']

        query_dia_ant = "SELECT CAST(strftime('%d', data_pedido) AS INTEGER) as dia, SUM(vlr_total) as total FROM erp_pedidos WHERE strftime('%Y-%m', data_pedido) = strftime('%Y-%m', 'now', '-1 month') AND status != 'Cancelado' GROUP BY dia"
        for row in cursor.execute(query_dia_ant).fetchall():
            graficos["vendas_dia"]["fev_data"][row['dia'] - 1] = row['total']
    except Exception: pass

    # CORREÇÃO: Agrupamento pelas novas categorias (erp_grupos_produtos) em vez de erp_categorias
    try:
        query_cat = """
            SELECT COALESCE(c.nome_grupo, 'Sem Categoria') as nome, SUM(pi.quantidade) as qtd
            FROM erp_pedidos_itens pi
            JOIN erp_produtos p ON pi.produto_id = p.id
            LEFT JOIN erp_grupos_produtos c ON p.categoria_id = c.id
            GROUP BY c.nome_grupo
            ORDER BY qtd DESC LIMIT 5
        """
        cat_rows = cursor.execute(query_cat).fetchall()
        if cat_rows:
            graficos["grupos_vendidos"]["labels"] = [r['nome'] for r in cat_rows]
            graficos["grupos_vendidos"]["data"] = [r['qtd'] for r in cat_rows]
        else:
            graficos["grupos_vendidos"]["labels"] = ["Sem Dados"]
            graficos["grupos_vendidos"]["data"] = [1]
    except Exception as e:
        graficos["grupos_vendidos"]["labels"] = ["Sem Categoria"]
        graficos["grupos_vendidos"]["data"] = [1]

    try:
        query_marca = """
            SELECT COALESCE(m.nome, 'Sem Marca') as nome, SUM(pi.quantidade) as qtd
            FROM erp_pedidos_itens pi
            JOIN erp_produtos p ON pi.produto_id = p.id
            LEFT JOIN erp_marcas m ON p.marca_id = m.id
            GROUP BY m.nome
            ORDER BY qtd DESC LIMIT 5
        """
        marca_rows = cursor.execute(query_marca).fetchall()
        if marca_rows:
            graficos["marcas_vendidas"]["labels"] = [r['nome'] for r in marca_rows]
            graficos["marcas_vendidas"]["data"] = [r['qtd'] for r in marca_rows]
        else:
            graficos["marcas_vendidas"]["labels"] = ["Sem Marca"]
            graficos["marcas_vendidas"]["data"] = [1]
    except Exception:
        graficos["marcas_vendidas"]["labels"] = ["Sem Marca"]
        graficos["marcas_vendidas"]["data"] = [1]

    # --- 4. DADOS FINANCEIROS DETALHADOS ---
    fin_detalhado = {"receitas_mes": 0, "despesas_mes": 0, "saldo_mes": 0}
    try:
        req_rec = cursor.execute("SELECT SUM(valor) as total FROM erp_recebimentos WHERE strftime('%Y-%m', data_vencimento) = strftime('%Y-%m', 'now') AND status != 'Cancelado'").fetchone()
        fin_detalhado["receitas_mes"] = req_rec['total'] or 0

        req_pag = cursor.execute("SELECT SUM(valor) as total FROM erp_pagamentos WHERE strftime('%Y-%m', data_vencimento) = strftime('%Y-%m', 'now') AND status != 'Cancelado'").fetchone()
        fin_detalhado["despesas_mes"] = req_pag['total'] or 0

        fin_detalhado["saldo_mes"] = fin_detalhado["receitas_mes"] - fin_detalhado["despesas_mes"]
    except Exception: pass

    # --- 5. DADOS CLIENTES ---
    clientes_detalhado = {"total": 0, "novos_mes": 0, "top_clientes": []}
    try:
        req_cli = cursor.execute("SELECT COUNT(id) as total FROM erp_clientes").fetchone()
        clientes_detalhado["total"] = req_cli["total"] or 0

        try:
            req_cli_novos = cursor.execute("SELECT COUNT(id) as total FROM erp_clientes WHERE strftime('%Y-%m', data_cadastro) = strftime('%Y-%m', 'now')").fetchone()
            clientes_detalhado["novos_mes"] = req_cli_novos["total"] or 0
        except: pass

        query_top_cli = """
            SELECT c.nome, COUNT(p.id) as qtd_pedidos, SUM(p.vlr_total) as valor_gasto
            FROM erp_pedidos p
            JOIN erp_clientes c ON p.cliente_id = c.id
            WHERE p.status != 'Cancelado'
            GROUP BY c.id
            ORDER BY valor_gasto DESC
            LIMIT 5
        """
        top_cli_rows = cursor.execute(query_top_cli).fetchall()
        clientes_detalhado["top_clientes"] = [dict(r) for r in top_cli_rows]
    except Exception: pass

    conn.close()

    dados_formatados = {
        "kpis": {
            "vendas_total_periodo": formatar_moeda(kpis["vendas_total_periodo"]),
            "vendas_mes_atual": formatar_moeda(kpis["vendas_mes_atual"]),
            "vendas_mes_anterior": formatar_moeda(kpis["vendas_mes_anterior"]),
            "num_vendas_total": kpis["num_vendas_total"],
            "num_vendas_mes_atual": kpis["num_vendas_mes_atual"],
            "num_vendas_mes_anterior": kpis["num_vendas_mes_anterior"],
            "ticket_medio_total": formatar_moeda(kpis["ticket_medio_total"]),
            "ticket_medio_mes_atual": formatar_moeda(kpis["ticket_medio_mes_atual"]),
            "ticket_medio_mes_anterior": formatar_moeda(kpis["ticket_medio_mes_anterior"])
        },
        "graficos": graficos,
        "financeiro": {
            "receber": {
                "atraso": formatar_moeda(fin["receber"]["atraso"]),
                "semana": formatar_moeda(fin["receber"]["semana"]),
                "hoje": formatar_moeda(fin["receber"]["hoje"])
            },
            "pagar": {
                "atraso": formatar_moeda(fin["pagar"]["atraso"]),
                "semana": formatar_moeda(fin["pagar"]["semana"]),
                "hoje": formatar_moeda(fin["pagar"]["hoje"])
            }
        },
        "financeiro_detalhado": {
            "receitas_mes": formatar_moeda(fin_detalhado["receitas_mes"]),
            "despesas_mes": formatar_moeda(fin_detalhado["despesas_mes"]),
            "saldo_mes": formatar_moeda(fin_detalhado["saldo_mes"])
        },
        "clientes_detalhado": {
            "total": clientes_detalhado["total"],
            "novos_mes": clientes_detalhado["novos_mes"],
            "top_clientes": [
                {
                    "nome": c["nome"] or "Cliente Sem Nome", 
                    "qtd_pedidos": c["qtd_pedidos"], 
                    "valor_gasto": formatar_moeda(c["valor_gasto"])
                } for c in clientes_detalhado["top_clientes"]
            ]
        }
    }
    
    return dados_formatados