# storage/configuracoes.py

import json
import re
import sqlite3
import logging
from .connection import get_db_connection

# --- LISTAS INICIAIS DE BAIRROS (IMPORTAÇÃO AUTOMÁTICA) ---
BAIRROS_VALIDOS_INIT = [
    "Alto Capelinha", "Alto da Serra", "Café", "Caixa D' Água", "Campo de Aviação",
    "Celina", "Centro", "Chácara", "Córrego da Prata", "Estância Bela Vista",
    "Faisqueira", "Jardim das Palmeiras", "Jardim Esperança", "João XXIII",
    "Loteamento", "Mata do Macuco", "Monte Verde", "Morada do Sol", "Niterói",
    "Nova Suíça", "Piteiras", "Pito Aceso", "Populares", "Recanto Verde",
    "Santa Edwiges", "Santa Rosa", "São Vicente", "Varginha", "Vila Esperança",
    "Vila Gomes", "Vila Nova", "Vila Reis",
]

BAIRROS_COM_TAXA_FIXA_INIT = [
    "Alto Capelinha", "Café", "Caixa D' Água", "Mata do Macuco",
    "Monte Verde", "Pito Aceso", "Santa Rosa", "Vila Reis",
]

def init_bairros_padrao(usuario_id=1):
    try:
        with get_db_connection() as conn:
            try:
                conn.execute("SELECT count(*) FROM bairros_entrega WHERE usuario_id = ?", (usuario_id,))
            except sqlite3.OperationalError:
                return

            qtd = conn.execute("SELECT count(*) FROM bairros_entrega WHERE usuario_id = ?", (usuario_id,)).fetchone()[0]
            if qtd == 0:
                print("📥 Importando lista de bairros padrão...")
                for bairro in BAIRROS_VALIDOS_INIT:
                    taxa = 10.00 if bairro in BAIRROS_COM_TAXA_FIXA_INIT else None
                    conn.execute(
                        "INSERT OR IGNORE INTO bairros_entrega (nome, taxa, usuario_id) VALUES (?, ?, ?)",
                        (bairro, taxa, usuario_id),
                    )
                conn.commit()
    except Exception as e:
        logging.error(f"Erro ao importar bairros: {e}")

# --- FUNÇÕES DINÂMICAS DE BAIRROS ---

def obter_lista_bairros_nomes(usuario_id=1):
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT nome FROM bairros_entrega WHERE usuario_id = ? ORDER BY nome ASC", (usuario_id,)
            ).fetchall()
            return [r["nome"] for r in rows]
    except Exception:
        return []

def obter_mensagem_bairros_formatada(usuario_id=1):
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT nome, taxa FROM bairros_entrega WHERE usuario_id = ? ORDER BY nome ASC", (usuario_id,)
            ).fetchall()

        if not rows:
            return "Consulte a taxa informando seu bairro."

        padrao = obter_config_valor("taxa_entrega_padrao", "0.00", usuario_id)
        try:
            padrao_fl = float(padrao)
        except Exception:
            padrao_fl = 0.0

        grupos = {}
        for r in rows:
            val = r["taxa"] if r["taxa"] is not None else padrao_fl
            if val not in grupos:
                grupos[val] = []
            grupos[val].append(r["nome"])

        linhas = ["🛵 *Áreas de Entrega & Taxas:*", ""]
        for valor, lista in sorted(grupos.items()):
            v_txt = "Grátis" if valor == 0 else f"R$ {valor:.2f}".replace(".", ",")
            linhas.append(f"*{v_txt}:* {', '.join(lista)}")

        return "\n".join(linhas)
    except Exception:
        return "Erro ao listar bairros."

# --- FUNÇÃO INTELIGENTE DE NOME DE TABELA ---

def get_nome_tabela(cat_id, usuario_id=1):
    cat_id = str(cat_id).strip()
    MAPA_PLURAIS = {
        "pao": "paes", "mao": "maos", "pastel": "pasteis", "kebab": "kebabs",
        "hamburguer": "hamburgueres", "acai": "acais", "sushi": "sushis",
        "marmitex": "marmitexs", "porcao": "porcoes", "lanche_gourmet": "lanches_gourmet",
        "esfiha": "esfihas", "salgado": "salgados", "bebida": "bebidas",
        "sobremesa": "sobremesas", "combo": "combos", "massa": "massas", "salada": "saladas",
    }
    candidatos = {cat_id, cat_id + "s"}
    if cat_id in MAPA_PLURAIS:
        candidatos.add(MAPA_PLURAIS[cat_id])
    elif cat_id.endswith("r"):
        candidatos.add(cat_id + "es")

    tabela_vencedora = None
    maior_qtd = -1

    try:
        with get_db_connection() as conn:
            rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            reais = {r[0] for r in rows}
            existentes = [c for c in candidatos if c in reais]

            if not existentes:
                return MAPA_PLURAIS.get(cat_id, cat_id + "s")

            if len(existentes) == 1:
                return existentes[0]

            for tbl in existentes:
                try:
                    qtd = conn.execute(f"SELECT count(*) FROM {tbl} WHERE usuario_id = ?", (usuario_id,)).fetchone()[0]
                    if qtd > maior_qtd:
                        maior_qtd = qtd
                        tabela_vencedora = tbl
                    elif qtd == maior_qtd:
                        if tabela_vencedora is None or len(tbl) > len(tabela_vencedora):
                            tabela_vencedora = tbl
                except Exception:
                    pass
    except Exception:
        return cat_id + "s"

    return tabela_vencedora if tabela_vencedora else (cat_id + "s")

def init_tabela_categorias(usuario_id=1):
    try:
        with get_db_connection() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS categorias_cardapio (id TEXT PRIMARY KEY, nome TEXT, emoji TEXT, ordem INTEGER DEFAULT 99, ativa INTEGER DEFAULT 1, usuario_id INTEGER DEFAULT 1)"
            )
            for c in ["emoji TEXT", "ordem INTEGER DEFAULT 99", "usuario_id INTEGER DEFAULT 1"]:
                try:
                    conn.execute(f"ALTER TABLE categorias_cardapio ADD COLUMN {c}")
                except Exception:
                    pass

            conn.execute(
                "CREATE TABLE IF NOT EXISTS bairros_entrega (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE, taxa REAL, usuario_id INTEGER DEFAULT 1)"
            )
            conn.commit()

            todas_cats = conn.execute("SELECT id FROM categorias_cardapio WHERE usuario_id = ?", (usuario_id,)).fetchall()
            for row in todas_cats:
                tabela = get_nome_tabela(row[0], usuario_id)
                conn.execute(
                    f"CREATE TABLE IF NOT EXISTS {tabela} (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, preco REAL, descricao TEXT, disponivel INTEGER DEFAULT 1, ingredientes TEXT, tipo TEXT, usuario_id INTEGER DEFAULT 1)"
                )
                for col in ["descricao TEXT", "disponivel INTEGER DEFAULT 1", "ingredientes TEXT", "tipo TEXT", "usuario_id INTEGER DEFAULT 1"]:
                    try:
                        conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {col}")
                    except Exception:
                        pass
            conn.commit()
        init_bairros_padrao(usuario_id)
    except Exception as e:
        logging.error(f"Erro init categorias: {e}")

def obter_todas_categorias_db(usuario_id=1):
    try:
        init_tabela_categorias(usuario_id)
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            return [
                dict(r) for r in conn.execute(
                    "SELECT * FROM categorias_cardapio WHERE usuario_id = ? ORDER BY ordem ASC, nome ASC", (usuario_id,)
                ).fetchall()
            ]
    except Exception:
        return []

def obter_categorias_ativas(usuario_id=1):
    try:
        return {c["id"]: bool(c["ativa"]) for c in obter_todas_categorias_db(usuario_id)}
    except Exception:
        return {}

# --- FUNÇÕES GERAIS ---

def calcular_desconto(preco_base, desc_str):
    try:
        if not desc_str:
            return float(preco_base)
        preco = float(preco_base)
        d = str(desc_str).replace(",", ".").strip()
        val_str = re.sub(r"[^\d.]", "", d)
        if not val_str:
            return preco
        val = float(val_str)
        if "%" in d:
            preco_final = preco * (1 - (val / 100))
        else:
            preco_final = preco - val
        return round(max(0.0, preco_final), 2)
    except Exception as e:
        logging.error(f"Erro ao calcular desconto: {e}")
        return float(preco_base)

def obter_config_valor(chave, default=None, usuario_id=1):
    try:
        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT valor FROM configuracoes WHERE chave=? AND usuario_id=?", (chave, usuario_id)
            ).fetchone()
            if row and row[0]:
                return row[0]
    except Exception:
        pass
    return default

def gerar_menu_opcoes(usuario_id=1):
    ativas = obter_categorias_ativas(usuario_id)
    cats = obter_todas_categorias_db(usuario_id)
    linhas = ["O que deseja agora?\n"]
    for c in cats:
        if ativas.get(c["id"]):
            linhas.append(f"{c.get('emoji') or '📦'} {c['nome'].upper()}")
    linhas.append("\n✅ FINALIZAR PEDIDO")
    return "\n".join(linhas)

def gerar_opcoes_carrinho(usuario_id=1):
    ativas = obter_categorias_ativas(usuario_id)
    cats = obter_todas_categorias_db(usuario_id)
    mapa = {c["id"]: c["nome"] for c in cats}
    nomes = []
    for p in ["pizza", "lanche", "bebida", "acai", "sobremesa"]:
        if ativas.get(p):
            nomes.append(mapa.get(p, p).upper())

    if len(nomes) < 3:
        for c in cats:
            if ativas.get(c["id"]) and c["id"] not in ["pizza", "lanche", "bebida", "acai", "sobremesa"]:
                if c["nome"].upper() not in nomes:
                    nomes.append(c["nome"].upper())
                if len(nomes) >= 3:
                    break

    lista_str = ", ".join(nomes) or "MAIS ITENS"
    return f"O que deseja fazer agora?\n- Adicionar outra {lista_str} ou OUTROS\n- FINALIZAR PEDIDO\n(Se errou, digite DESCARTAR, LIMPAR CARRINHO ou REINICIAR)"

def obter_apelidos_categorias_db(usuario_id=1):
    try:
        with get_db_connection() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS categoria_apelido (id INTEGER PRIMARY KEY, categoria_id TEXT, apelido TEXT, usuario_id INTEGER DEFAULT 1)"
            )
            return {
                r[1].lower(): r[0] for r in conn.execute(
                    "SELECT categoria_id, apelido FROM categoria_apelido WHERE usuario_id = ?", (usuario_id,)
                ).fetchall()
            }
    except Exception:
        return {}

def obter_apelidos_adicionais_db(usuario_id=1):
    try:
        with get_db_connection() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS sabor_apelido (id INTEGER PRIMARY KEY, sabor_produto_id INTEGER, apelido TEXT, categoria TEXT, usuario_id INTEGER DEFAULT 1)"
            )
            rows = conn.execute(
                "SELECT sabor_produto_id, apelido FROM sabor_apelido WHERE categoria='adicional' AND usuario_id = ?", (usuario_id,)
            ).fetchall()
            if not rows:
                return {}
            ids = ",".join([str(r[0]) for r in rows])
            if ids:
                nomes = {
                    r[0]: r[1].lower() for r in conn.execute(
                        f"SELECT id, nome FROM produto_adicionais WHERE id IN ({ids}) AND usuario_id = ?", (usuario_id,)
                    ).fetchall()
                }
                return {r[1].lower(): nomes[r[0]] for r in rows if r[0] in nomes}
            return {}
    except Exception:
        return {}

def obter_todos_adicionais_db(usuario_id=1):
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            return [
                dict(r) for r in conn.execute(
                    "SELECT * FROM produto_adicionais WHERE usuario_id = ? ORDER BY nome", (usuario_id,)
                ).fetchall()
            ]
    except Exception:
        return []

def obter_mais_pedidos_db(categoria=None, usuario_id=1):
    try:
        with get_db_connection() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS mais_pedidos (id INTEGER PRIMARY KEY, categoria TEXT, produto_id INTEGER, nome_produto TEXT, usuario_id INTEGER DEFAULT 1)"
            )
            if categoria:
                return [
                    r[0] for r in conn.execute(
                        "SELECT produto_id FROM mais_pedidos WHERE categoria = ? AND usuario_id = ?", (categoria, usuario_id)
                    ).fetchall()
                ]
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute("SELECT * FROM mais_pedidos WHERE usuario_id = ?", (usuario_id,)).fetchall()]
    except Exception:
        return []

def init_tabela_variacoes_extras(usuario_id=1):
    try:
        with get_db_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS produto_variacoes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    categoria TEXT,
                    nome TEXT,
                    preco REAL,
                    fatias INTEGER DEFAULT 0,
                    max_sabores INTEGER DEFAULT 1,
                    tamanho_cm TEXT,
                    sigla TEXT,
                    usuario_id INTEGER DEFAULT 1
                )
            """)
            for c in ["fatias INTEGER DEFAULT 0", "max_sabores INTEGER DEFAULT 1", "tamanho_cm TEXT", "sigla TEXT", "usuario_id INTEGER DEFAULT 1"]:
                try:
                    conn.execute(f"ALTER TABLE produto_variacoes ADD COLUMN {c}")
                except Exception:
                    pass
            conn.commit()
    except Exception as e:
        logging.error(f"Erro init variacoes: {e}")

def obter_variacoes_pizza_db(usuario_id=1):
    init_tabela_variacoes_extras(usuario_id)
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            return [
                dict(r) for r in conn.execute(
                    "SELECT * FROM produto_variacoes WHERE categoria = 'pizza' AND usuario_id = ? ORDER BY preco", (usuario_id,)
                ).fetchall()
            ]
    except Exception:
        return []

# --- NOVA FUNÇÃO: CRIAR RESERVA NO BANCO ---
def criar_reserva_db(data_reserva, horario, qtd_pessoas, nome, telefone, obs="", usuario_id=1):
    try:
        with get_db_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reservas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data_reserva TEXT,
                    horario TEXT,
                    qtd_pessoas INTEGER,
                    nome_cliente TEXT,
                    telefone_cliente TEXT,
                    pre_pedido TEXT,
                    status TEXT DEFAULT 'confirmada',
                    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
                    usuario_id INTEGER DEFAULT 1
                )
            """)
            for c in ["usuario_id INTEGER DEFAULT 1"]:
                try:
                    conn.execute(f"ALTER TABLE reservas ADD COLUMN {c}")
                except Exception:
                    pass

            conn.execute(
                """
                INSERT INTO reservas (data_reserva, horario, qtd_pessoas, nome_cliente, telefone_cliente, pre_pedido, status, usuario_id)
                VALUES (?, ?, ?, ?, ?, ?, 'confirmada', ?)
            """,
                (data_reserva, horario, int(qtd_pessoas), nome, telefone, obs, usuario_id),
            )
            conn.commit()
        return True
    except Exception as e:
        logging.error(f"Erro criar reserva DB: {e}")
        return False

# --- NOTIFICAÇÕES E ESTADOS ---
def criar_notificacao(tipo, mensagem, telefone=None, usuario_id=1):
    try:
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO notificacoes (tipo, mensagem, cliente_telefone, data_hora, usuario_id) VALUES (?, ?, ?, datetime('now', 'localtime'), ?)",
                (tipo, mensagem, telefone, usuario_id),
            )
            conn.commit()
    except Exception:
        pass

def listar_notificacoes(usuario_id=1):
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            return [
                dict(r) for r in conn.execute(
                    "SELECT n.*, c.nome as cliente_nome FROM notificacoes n LEFT JOIN cliente c ON n.cliente_telefone = c.telefone WHERE n.usuario_id = ? ORDER BY n.data_hora DESC", (usuario_id,)
                ).fetchall()
            ]
    except Exception:
        return []

def marcar_notificacao_lida(nid, usuario_id=1):
    try:
        with get_db_connection() as conn:
            conn.execute("UPDATE notificacoes SET lida = 1 WHERE id = ? AND usuario_id = ?", (nid, usuario_id))
            conn.commit()
    except Exception:
        pass

def desativar_chat_e_notificar(telefone, motivo, usuario_id=1):
    try:
        with get_db_connection() as conn:
            conn.execute("UPDATE cliente SET chat_ativo = 0 WHERE telefone = ? AND usuario_id = ?", (telefone, usuario_id))
            conn.execute(
                "INSERT INTO notificacoes (tipo, mensagem, cliente_telefone, data_hora, usuario_id) VALUES ('SUPORTE', ?, ?, datetime('now', 'localtime'), ?)",
                (f"Solicitação: {motivo}", telefone, usuario_id),
            )
            conn.commit()
    except Exception:
        pass

def obter_limites_sabores(usuario_id=1):
    try:
        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT nome, max_sabores FROM produto_variacoes WHERE categoria='pizza' AND usuario_id = ?", (usuario_id,)
            ).fetchall()
            return {r[0]: r[1] for r in rows}
    except Exception:
        return {}

def obter_texto_horario_dinamico(usuario_id=1):
    try:
        val = obter_config_valor("horario_json", usuario_id=usuario_id)
        if not val:
            return "Consulte horário."
        grade = json.loads(val)
        dias = {"seg": "Segunda", "ter": "Terça", "qua": "Quarta", "qui": "Quinta", "sex": "Sexta", "sab": "Sábado", "dom": "Domingo"}
        ls = []
        for k, v in grade.items():
            if not v.get("fechado"):
                ls.append(f"{dias.get(k, k)}: {v.get('inicio')} às {v.get('fim')}")
        return "🕒 *Horário:*\n" + "\n".join(ls)
    except Exception:
        return "Indisponível"

def get_chave_pix_ativa(usuario_id=1):
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            id_val = obter_config_valor("pix_ativo_id", usuario_id=usuario_id)
            if id_val:
                pix = conn.execute(
                    "SELECT * FROM chaves_pix WHERE id=? AND usuario_id=?", (int(id_val), usuario_id)
                ).fetchone()
                if pix:
                    return dict(pix)
            pix = conn.execute("SELECT * FROM chaves_pix WHERE usuario_id=? LIMIT 1", (usuario_id,)).fetchone()
            return dict(pix) if pix else None
    except Exception:
        return None

def obter_tempo_entrega_config(usuario_id=1):
    tempo_fixo = obter_config_valor("tempo_entrega", usuario_id=usuario_id)
    if tempo_fixo and tempo_fixo.strip():
        return tempo_fixo
        
    try:
        with get_db_connection() as conn:
            qtd = conn.execute("""
                SELECT count(*) FROM pedidos 
                WHERE status IN ('ABERTO', 'EM PREPARO') 
                AND date(data_pedido) = date('now', 'localtime')
                AND usuario_id = ?
            """, (usuario_id,)).fetchone()[0]
            
            tempo_min = 30 + (qtd * 10)
            tempo_max = tempo_min + 15
            return f"{tempo_min} a {tempo_max} min"
    except Exception as e:
        logging.error(f"Erro ao calcular tempo de entrega dinâmico: {e}")
        return "40 a 50 min"

def obter_taxa_entrega(bairro=None, usuario_id=1):
    taxa_padrao = obter_config_valor("taxa_entrega_padrao", usuario_id=usuario_id)
    taxa_final = float(taxa_padrao) if taxa_padrao else 0.0

    if bairro:
        try:
            with get_db_connection() as conn:
                row = conn.execute(
                    "SELECT taxa FROM bairros_entrega WHERE nome LIKE ? AND usuario_id = ?",
                    (bairro.strip(), usuario_id),
                ).fetchone()
                if row and row[0] is not None:
                    return float(row[0])
        except Exception:
            pass
    return taxa_final

def verificar_chat_geral_ativo(usuario_id=1):
    return obter_config_valor("chat_ativo", usuario_id=usuario_id) != "0"

def verificar_chat_cliente_ativo(tel, usuario_id=1):
    try:
        with get_db_connection() as conn:
            r = conn.execute(
                "SELECT chat_ativo FROM cliente WHERE telefone=? AND usuario_id=?", (tel, usuario_id)
            ).fetchone()
            return False if r and r[0] == 0 else True
    except Exception:
        return True

def verificar_loja_aberta(usuario_id=1):
    return obter_config_valor("loja_aberta", usuario_id=usuario_id) != "0"

def verificar_restricao_cadastrados(usuario_id=1):
    return obter_config_valor("restrito_cadastrados", usuario_id=usuario_id) == "1"

def obter_promocoes_ativas(usuario_id=1):
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute("SELECT * FROM promocoes WHERE usuario_id = ?", (usuario_id,)).fetchall()]
    except Exception:
        return []

def obter_valor_minimo_pedido(usuario_id=1):
    v = obter_config_valor("valor_minimo_pedido", usuario_id=usuario_id)
    return float(v) if v else 0.0