# storage/produtos.py

import sqlite3
from .connection import get_db_connection
from .utils import remover_acentos


def buscar_produto_db(nome_busca):
    # ... (MANTENHA O CÓDIGO DA FUNÇÃO buscar_produto_db IGUAL, SÓ MUDAREMOS A DE BAIXO) ...
    if not nome_busca:
        return None
    nome_clean = remover_acentos(nome_busca.lower().strip())
    tabelas = ["pizza", "lanches", "bebidas", "acai", "combos", "sobremesas"]
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        try:
            apelido_row = conn.execute(
                "SELECT sabor_produto_id FROM sabor_apelido WHERE apelido = ?",
                (nome_clean,),
            ).fetchone()
            if apelido_row:
                prod_real = conn.execute(
                    "SELECT * FROM pizza WHERE id = ?",
                    (apelido_row["sabor_produto_id"],),
                ).fetchone()
                if prod_real:
                    d = dict(prod_real)
                    d["tabela_origem"] = "pizza"
                    return d
        except Exception:
            pass
        for tabela in tabelas:
            try:
                row = conn.execute(
                    f"SELECT * FROM {tabela} WHERE LOWER(nome) = ?", (nome_clean,)
                ).fetchone()
                if row:
                    d = dict(row)
                    d["tabela_origem"] = tabela
                    return d
            except Exception:
                continue
        for tabela in tabelas:
            try:
                row = conn.execute(
                    f"SELECT * FROM {tabela} WHERE LOWER(nome) LIKE ? LIMIT 1",
                    (f"%{nome_clean}%",),
                ).fetchone()
                if row:
                    d = dict(row)
                    d["tabela_origem"] = tabela
                    return d
            except Exception:
                continue
    return None


def listar_bordas_db():
    """
    Retorna a mensagem formatada de bordas e a lista de nomes para seleção numérica.
    Evita duplicar 'Sem Borda' se já existir no banco.
    """
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT pa.nome, pa.preco_adicional 
                FROM produto_adicionais pa
                JOIN grupos_adicionais ga ON pa.grupo = ga.id
                WHERE ga.titulo LIKE '%Borda%'
                ORDER BY pa.preco_adicional ASC
            """).fetchall()

            msg = "📌 *Escolha a Borda*\n_Selecione o recheio da borda_\n\n"
            lista_nomes = []
            tem_sem_borda = False  # Flag de controle

            if rows:
                for i, r in enumerate(rows):
                    msg += (
                        f"🔹 *{i + 1}.* {r['nome']} (+R$ {r['preco_adicional']:.2f})\n"
                    )
                    lista_nomes.append(r["nome"])
                    # Verifica se esta opção é a "sem borda"
                    if "sem borda" in r["nome"].lower():
                        tem_sem_borda = True

            # Só adiciona manualmente se NÃO veio do banco
            if not tem_sem_borda:
                idx_sem = len(lista_nomes) + 1
                msg += f"🔹 *{idx_sem}.* Sem Borda Recheada (+R$ 0.00)\n"
                lista_nomes.append("Sem Borda Recheada")

            return msg, lista_nomes
    except Exception as e:
        print(f"Erro ao listar bordas: {e}")
        return "⚠️ Erro ao buscar bordas no sistema.", []


def validar_sabores_db(lista_sabores):
    # ... (MANTENHA O CÓDIGO DA FUNÇÃO validar_sabores_db IGUAL) ...
    if not lista_sabores:
        return [], []
    validos = []
    invalidos = []
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        tabelas_sabor = ["pizza", "lanches", "esfihas", "pastas"]
        for sabor in lista_sabores:
            sabor_clean = remover_acentos(sabor.lower().strip())
            encontrado = False
            try:
                apelido = conn.execute(
                    "SELECT sabor_produto_id FROM sabor_apelido WHERE apelido = ?",
                    (sabor_clean,),
                ).fetchone()
                if apelido:
                    prod = conn.execute(
                        "SELECT nome FROM pizza WHERE id=?",
                        (apelido["sabor_produto_id"],),
                    ).fetchone()
                    if prod:
                        validos.append(prod["nome"])
                        encontrado = True
            except Exception:
                pass
            if encontrado:
                continue
            for tab in tabelas_sabor:
                try:
                    res = conn.execute(
                        f"SELECT nome FROM {tab} WHERE LOWER(nome) = ?",
                        (sabor.lower().strip(),),
                    ).fetchone()
                    if res:
                        validos.append(res["nome"])
                        encontrado = True
                        break
                except Exception:
                    pass
            if encontrado:
                continue
            for tab in tabelas_sabor:
                try:
                    res = conn.execute(
                        f"SELECT nome FROM {tab} WHERE LOWER(nome) LIKE ?",
                        (f"%{sabor_clean}%",),
                    ).fetchone()
                    if res:
                        validos.append(res["nome"])
                        encontrado = True
                        break
                except Exception:
                    pass
            if not encontrado:
                if len(sabor) > 2:
                    validos.append(sabor.title())
                else:
                    invalidos.append(sabor)
    return validos, invalidos
