import sqlite3

def encontrar_colunas_vazias(caminho_db):
    conn = sqlite3.connect(caminho_db)
    cursor = conn.cursor()

    # Busca todas as tabelas que começam com 'erp_'
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'erp_%'")
    tabelas = [linha[0] for linha in cursor.fetchall()]

    relatorio_vazias = {}
    tabelas_verificadas = 0

    for tabela in tabelas:
        # 1. Verifica se a tabela tem pelo menos um registro
        cursor.execute(f'SELECT COUNT(*) FROM "{tabela}"')
        total_linhas = cursor.fetchone()[0]
        
        # Ignora tabelas que não possuem dados (totalmente em branco)
        if total_linhas == 0:
            continue
            
        tabelas_verificadas += 1
        
        # 2. Busca a estrutura de colunas da tabela
        cursor.execute(f"PRAGMA table_info('{tabela}')")
        colunas = [linha[1] for linha in cursor.fetchall()]
        
        colunas_vazias = []
        for coluna in colunas:
            # Conta se existe pelo menos um registro que seja um "dado real"
            # Ignorando nulos reais, strings vazias, e as strings textuais 'null' e 'none'
            query = f"""
                SELECT COUNT(*) 
                FROM "{tabela}" 
                WHERE "{coluna}" IS NOT NULL 
                  AND TRIM(CAST("{coluna}" AS TEXT)) != '' 
                  AND LOWER(TRIM(CAST("{coluna}" AS TEXT))) != 'null'
                  AND LOWER(TRIM(CAST("{coluna}" AS TEXT))) != 'none'
            """
            cursor.execute(query)
            quantidade_preenchida = cursor.fetchone()[0]
            
            # Se a contagem for 0, todos os dados dessa coluna são nulos ou a palavra 'null'
            if quantidade_preenchida == 0:
                colunas_vazias.append(coluna)
        
        if colunas_vazias:
            relatorio_vazias[tabela] = colunas_vazias

    conn.close()

    # Exibe o relatório
    print(f"Encontradas {len(tabelas)} tabelas com prefixo 'erp_'.")
    print(f"Analisando {tabelas_verificadas} tabelas que possuem dados gravados...\n")
    
    if not relatorio_vazias:
        print("Nenhuma coluna 100% vazia (ou contendo apenas 'null') foi encontrada nas tabelas com dados.")
    else:
        for tabela, colunas in relatorio_vazias.items():
            print(f"Tabela: {tabela}")
            for col in colunas:
                print(f"  - {col}")
            print("-" * 30)

# Execute apontando para o seu banco
encontrar_colunas_vazias('database/pizzaria.db')