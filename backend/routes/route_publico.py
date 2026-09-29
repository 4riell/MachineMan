# routes/route_publico.py

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from storage import get_db_connection, templates
from storage.configuracoes import get_nome_tabela
import sqlite3

router = APIRouter()

@router.get("/menu/{loja_id}", response_class=HTMLResponse)
async def ver_menu_publico(request: Request, loja_id: int):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    try:
        try:
            loja = conn.execute("SELECT * FROM usuarios WHERE id = ? OR loja_id = ? LIMIT 1", (loja_id, loja_id)).fetchone()
            loja_nome = loja["nome"] if loja and "nome" in loja.keys() else f"Cardápio"
        except Exception:
            loja_nome = "Cardápio"

        categorias = conn.execute(
            "SELECT * FROM categorias_cardapio WHERE ativa = 1 AND loja_id = ? ORDER BY id", 
            (loja_id,)
        ).fetchall()

        menu_completo = []
        todos_produtos_ids = []
        
        for cat in categorias:
            cat_dict = dict(cat)
            cat_id = cat_dict["id"]
            tabela = get_nome_tabela(cat_id)
            
            tabelas_busca = [str(tabela), str(cat_id)]
            
            if "gourmet" in str(cat_id).lower() or "gourmet" in str(tabela).lower():
                tabelas_busca.append("lanches_gourmet")
            elif "lanche" in str(cat_id).lower() or "lanche" in str(tabela).lower():
                tabelas_busca.append("lanches")
                
            tabelas_busca.extend([f"{tabela}s", f"{cat_id}s"])
            tabelas_busca = list(set(tabelas_busca))
            placeholders = ", ".join(["?"] * len(tabelas_busca))
            
            check_table = conn.execute(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name COLLATE NOCASE IN ({placeholders})", 
                tuple(tabelas_busca)
            ).fetchone()
            
            produtos_lista = []
            if check_table:
                nome_tabela_real = check_table["name"]
                
                try:
                    prods = conn.execute(f"SELECT * FROM {nome_tabela_real} WHERE loja_id = ? ORDER BY nome", (loja_id,)).fetchall()
                except sqlite3.OperationalError:
                    prods = conn.execute(f"SELECT * FROM {nome_tabela_real} ORDER BY nome").fetchall()
                
                for p in prods:
                    p_dict = dict(p)
                    if "preco" not in p_dict or p_dict["preco"] is None:
                        p_dict["preco"] = 0.0
                    produtos_lista.append(p_dict)
                    todos_produtos_ids.append(p_dict["id"])
                    
            if produtos_lista:
                cat_dict["produtos"] = produtos_lista
                menu_completo.append(cat_dict)

        try:
            variacoes = conn.execute("SELECT * FROM produto_variacoes WHERE loja_id = ?", (loja_id,)).fetchall()
            variacoes_lista = [dict(v) for v in variacoes]
        except sqlite3.OperationalError:
            variacoes_lista = []

        grupos_adicionais = []
        try:
            grupos = conn.execute("SELECT * FROM grupos_adicionais WHERE loja_id = ? ORDER BY ordem", (loja_id,)).fetchall()
            for g in grupos:
                g_dict = dict(g)
                opcoes = conn.execute(
                    "SELECT * FROM produto_adicionais WHERE grupo = ? AND loja_id = ? ORDER BY nome", 
                    (str(g_dict["id"]), loja_id)
                ).fetchall()
                g_dict["opcoes"] = [dict(op) for op in opcoes]
                grupos_adicionais.append(g_dict)
        except sqlite3.OperationalError:
            pass

    finally:
        conn.close()

    return templates.TemplateResponse(
        "public_menu.html",
        {
            "request": request,
            "loja_id": loja_id,
            "loja_nome": loja_nome,
            "menu_completo": menu_completo,
            "variacoes": variacoes_lista,
            "grupos_adicionais": grupos_adicionais
        }
    )

@router.post("/api/public/pedido/{loja_id}")
async def receber_pedido_publico(request: Request, loja_id: int, pedido_data: dict):
    conn = get_db_connection()
    try:
        nome = str(pedido_data.get("cliente_nome", "Cliente")).strip()
        telefone = str(pedido_data.get("cliente_telefone", "")).strip()
        valor_total = float(pedido_data.get("valor_total", 0))
        tipo_entrega = pedido_data.get("tipo_entrega", "Entrega")
        pagamento = pedido_data.get("forma_pagamento", "Dinheiro")
        endereco = pedido_data.get("endereco", {})
        itens = pedido_data.get("itens", [])

        # 1. Atualiza ou insere o cliente no banco
        cliente_existente = conn.execute("SELECT id FROM cliente WHERE telefone = ? AND loja_id = ?", (telefone, loja_id)).fetchone()
        
        if cliente_existente:
            conn.execute("""
                UPDATE cliente 
                SET nome = ?, rua = ?, numero_casa = ?, bairro = ?, ponto_referencia = ? 
                WHERE telefone = ? AND loja_id = ?
            """, (nome, endereco.get("rua", ""), endereco.get("numero", ""), endereco.get("bairro", ""), endereco.get("ref", ""), telefone, loja_id))
        else:
            conn.execute("""
                INSERT INTO cliente (telefone, nome, rua, numero_casa, bairro, ponto_referencia, chat_ativo, loja_id) 
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
            """, (telefone, nome, endereco.get("rua", ""), endereco.get("numero", ""), endereco.get("bairro", ""), endereco.get("ref", ""), loja_id))

        # 2. Cria o pedido na aba ABERTO para aparecer no painel
        cursor = conn.execute("""
            INSERT INTO pedidos (cliente_telefone, data_hora, status, tipo_entrega, forma_pagamento, valor_total, loja_id) 
            VALUES (?, datetime('now', 'localtime'), 'ABERTO', ?, ?, ?, ?)
        """, (telefone, tipo_entrega, pagamento, valor_total, loja_id))
        
        pedido_id = cursor.lastrowid

        # 3. Insere os itens
        for item in itens:
            conn.execute("""
                INSERT INTO pedido_outros_itens (pedido_id, tipo, nome_item, quantidade, preco_vendido, loja_id) 
                VALUES (?, 'diversos', ?, ?, ?, ?)
            """, (pedido_id, item.get("nome"), item.get("quantidade", 1), item.get("preco", 0), loja_id))

        conn.commit()
        return {"status": "success", "message": "Pedido recebido com sucesso"}
        
    except Exception as e:
        conn.rollback()
        print(f"Erro ao processar pedido publico: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/api/public/cliente/{loja_id}/{telefone}")
def buscar_cliente_publico(loja_id: int, telefone: str):
    """
    Busca os dados do cliente (para auto-preenchimento no app) de forma segura por loja.
    """
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    try:
        nums = "".join([c for c in telefone if c.isdigit()])
        # Busca pelas três variações possíveis de telefone que podem ter sido salvas
        row = conn.execute(
            "SELECT nome, rua, numero_casa, bairro, ponto_referencia FROM cliente WHERE telefone IN (?, ?, ?) AND loja_id = ?", 
            (nums, "55" + nums, nums.replace("55", "", 1), loja_id)
        ).fetchone()
        
        if row:
            return {"encontrado": True, "dados": dict(row)}
        return {"encontrado": False}
    except Exception as e:
        return {"encontrado": False, "erro": str(e)}
    finally:
        conn.close()
    
@router.get("/debug/menu/{loja_id}")
async def debug_menu(loja_id: int):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    relatorio = {
        "loja_buscada": loja_id,
        "categorias_encontradas": [],
        "erros": []
    }
    
    try:
        categorias = conn.execute("SELECT * FROM categorias_cardapio WHERE loja_id = ?", (loja_id,)).fetchall()
        if not categorias:
            relatorio["erros"].append(f"NENHUMA categoria encontrada para loja_id={loja_id}.")
            
        for cat in categorias:
            cat_dict = dict(cat)
            cat_id = cat_dict["id"]
            
            try:
                tabela_base = get_nome_tabela(cat_id)
            except Exception as e:
                tabela_base = str(cat_id)
                
            info_cat = {
                "id_categoria": cat_id,
                "nome": cat_dict.get("nome", "Sem nome"),
                "ativa": cat_dict.get("ativa"),
                "tabelas_tentadas": [],
                "tabela_encontrada_no_banco": None,
                "produtos_nesta_loja": 0
            }
            
            tabelas_busca = [str(tabela_base), str(cat_id)]
            if "gourmet" in str(cat_id).lower() or "gourmet" in str(tabela_base).lower():
                tabelas_busca.append("lanches_gourmet")
            elif "lanche" in str(cat_id).lower() or "lanche" in str(tabela_base).lower():
                tabelas_busca.append("lanches")
            tabelas_busca.extend([f"{tabela_base}s", f"{cat_id}s"])
            tabelas_busca = list(set(tabelas_busca))
            
            info_cat["tabelas_tentadas"] = tabelas_busca
            
            placeholders = ", ".join(["?"] * len(tabelas_busca))
            check_table = conn.execute(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name COLLATE NOCASE IN ({placeholders})", 
                tuple(tabelas_busca)
            ).fetchone()
            
            if check_table:
                nome_real = check_table["name"]
                info_cat["tabela_encontrada_no_banco"] = nome_real
                
                try:
                    qtd = conn.execute(f"SELECT COUNT(*) as total FROM {nome_real} WHERE loja_id = ?", (loja_id,)).fetchone()
                    info_cat["produtos_nesta_loja"] = qtd["total"]
                except Exception as e:
                    info_cat["erro_ao_buscar_produtos"] = str(e)
            else:
                info_cat["tabela_encontrada_no_banco"] = "FALHOU - Nenhuma tabela com esses nomes existe no banco."
                
            relatorio["categorias_encontradas"].append(info_cat)
            
    finally:
        conn.close()
        
    return relatorio