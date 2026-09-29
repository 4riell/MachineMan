import sqlite3
import pandas as pd
import io
import smtplib
import os
from email.message import EmailMessage
from datetime import datetime, timedelta

# CONFIGURAÇÕES
EMAIL_REMETENTE = "suapizzaria@gmail.com"
SENHA_APP_GMAIL = "sua_senha_aqui" 
EMAIL_CONTADOR = "contador@exemplo.com"
NOME_EMPRESA = "Sua Pizzaria"

def gerar_e_enviar_relatorio():
    hoje = datetime.now()
    mes_passado_dt = hoje.replace(day=1) - timedelta(days=1)
    mes_str = mes_passado_dt.strftime('%Y-%m')
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    caminho_bd = os.path.join(os.path.dirname(base_dir), 'pizzaria.db')

    conn = sqlite3.connect(caminho_bd)
    # Ativa o Row Factory para facilitar a leitura das colunas pelo nome
    conn.row_factory = sqlite3.Row 
    
    try:
        # Detecta colunas
        cols_info = conn.execute("PRAGMA table_info(pedidos)").fetchall()
        cols = [c["name"].lower() for c in cols_info]
        
        c_dt = "data_hora" if "data_hora" in cols else "data_pedido"
        c_cli = "cliente_nome" if "cliente_nome" in cols else "nome_cliente"
        c_tel = "cliente_telefone" if "cliente_telefone" in cols else "telefone" if "telefone" in cols else "telefone_cliente"
        c_val = "valor_total" if "valor_total" in cols else "total" if "total" in cols else "valor"

        sel_cli = c_cli if c_cli in cols else "''"
        sel_tel = c_tel if c_tel in cols else "''"
        sel_val = c_val if c_val in cols else "0"

        # Puxa dados brutos
        query = f"""
            SELECT id, {c_dt} as Data, {sel_cli} as Cliente, {sel_tel} as Telefone_Temp, 
                   forma_pagamento as Pagamento, {sel_val} as Valor 
            FROM pedidos 
            WHERE UPPER(status) IN ('CONCLUIDO', 'ENTREGUE') AND strftime('%Y-%m', {c_dt}) = '{mes_str}'
        """
        df_v = pd.read_sql_query(query, conn)
        
        # Inteligência de preenchimento
        for index, row in df_v.iterrows():
            # Nome
            cliente_atual = str(row['Cliente']).strip()
            if cliente_atual in ('', 'None', 'nan', 'Cliente'):
                telefone = str(row['Telefone_Temp']).strip()
                if telefone and telefone not in ('None', 'nan'):
                    try:
                        crow = conn.execute("SELECT nome FROM cliente WHERE telefone = ?", (telefone,)).fetchone()
                        if crow and crow["nome"]:
                            df_v.at[index, 'Cliente'] = crow["nome"]
                    except: pass
            
            # Valor
            try: valor_atual = float(row['Valor'])
            except: valor_atual = 0.0
            
            if valor_atual <= 0:
                try:
                    itens = conn.execute("SELECT SUM(preco_vendido * quantidade) as soma FROM pedido_outros_itens WHERE pedido_id = ?", (row['id'],)).fetchone()
                    if itens and itens["soma"]:
                        df_v.at[index, 'Valor'] = float(itens["soma"])
                except: pass

        if 'Telefone_Temp' in df_v.columns:
            df_v = df_v.drop(columns=['Telefone_Temp'])

        # Despesas
        df_d = pd.read_sql_query(f"SELECT COALESCE(data_pagamento, data_vencimento) as Data, descricao, categoria, valor FROM despesas WHERE status = 'pago' AND strftime('%Y-%m', COALESCE(data_pagamento, data_vencimento)) = '{mes_str}'", conn)

        # Formata datas
        # Formata datas
        for df in [df_v, df_d]:
            if not df.empty: df['Data'] = pd.to_datetime(df['Data'], errors='coerce').dt.strftime('%d/%m/%Y')

        # Calcula os totais e cria as linhas no final das tabelas
        total_vendas = df_v['Valor'].sum() if not df_v.empty else 0.0
        total_despesas = df_d['valor'].sum() if not df_d.empty else 0.0

        if not df_v.empty:
            linha_total_v = pd.DataFrame([{'id': '', 'Data': 'TOTAL', 'Cliente': '', 'Pagamento': '', 'Valor': total_vendas}])
            df_v = pd.concat([df_v, linha_total_v], ignore_index=True)
            
        if not df_d.empty:
            linha_total_d = pd.DataFrame([{'Data': 'TOTAL', 'descricao': '', 'categoria': '', 'valor': total_despesas}])
            df_d = pd.concat([df_d, linha_total_d], ignore_index=True)

        # Cria Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_v.to_excel(writer, sheet_name='Vendas', index=False)
            df_d.to_excel(writer, sheet_name='Despesas', index=False)
            
            # Ajuste de largura das colunas
            for sheet in writer.sheets.values():
                for col in sheet.columns:
                    max_length = max(len(str(cell.value) or "") for cell in col) + 2
                    sheet.column_dimensions[col[0].column_letter].width = max_length

        # Envia E-mail Turbinado com os totais
        msg = EmailMessage()
        msg['Subject'] = f'📊 Relatório Contábil - {mes_str} - {NOME_EMPRESA}'
        msg['From'] = EMAIL_REMETENTE
        msg['To'] = EMAIL_CONTADOR
        
        corpo_email = f"""Olá! 
        
Segue em anexo o fechamento contábil referente a {mes_str} da {NOME_EMPRESA}.

RESUMO DO MÊS:
🟢 Total de Recebimentos (Vendas): R$ {total_vendas:.2f}
🔴 Total de Despesas (Saídas): R$ {total_despesas:.2f}
🔵 Saldo Operacional: R$ {(total_vendas - total_despesas):.2f}

Qualquer dúvida, estamos à disposição."""

        msg.set_content(corpo_email)
        msg.add_attachment(output.getvalue(), maintype='application', subtype='vnd.openxmlformats-officedocument.spreadsheetml.sheet', filename=f'Relatorio_{mes_str}.xlsx')

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_REMETENTE, SENHA_APP_GMAIL)
            smtp.send_message(msg)
        print("✅ Enviado com sucesso!")

    except Exception as e: 
        print(f"❌ Erro: {e}")
    finally: 
        conn.close()

if __name__ == "__main__":
    gerar_e_enviar_relatorio()