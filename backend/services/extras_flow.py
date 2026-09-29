# services/extras_flow.py

import re
import difflib
import sqlite3
import logging

from storage import (
    create_response,
    salvar_pedido_completo_db,
    resumo_carrinho,
    get_db_connection,
    remover_acentos,
    listar_bordas_db,
)
from storage.configuracoes import (
    get_nome_tabela,
    gerar_menu_opcoes,
    gerar_opcoes_carrinho,
    obter_promocoes_ativas,
    obter_mais_pedidos_db,
    calcular_desconto,
    obter_variacoes_pizza_db,
    obter_todas_categorias_db,
    obter_apelidos_adicionais_db,
)
from storage.produtos import buscar_produto_db

# --- IMPORTAÇÃO DAS NOVAS CAMADAS ---
from storage.extras_repository import (
    buscar_variacoes_por_categoria,
    buscar_grupos_adicionais_db,
    buscar_apelidos_adicionais_por_grupo
)
from utils.nlp_parser import (
    detectar_adicionais_na_frase,
    limpar_observacao_pos_extracao,
    expandir_multiplicadores
)


# ==============================================================================
# 1. FUNÇÕES AUXILIARES DE FINALIZAÇÃO E KEYWORDS
# ==============================================================================

def finalizar_item_extra_real(fluxo, user_phone):
    """Finaliza a montagem do item e o adiciona ao carrinho."""
    item = fluxo["item_extra_pendente"]
    qtd = item.get("quantidade", 1)
    if qtd < 1: qtd = 1

    # CORREÇÃO DO CÁLCULO MÁGICO: Salva apenas o valor unitário. O carrinho cuida do * qtd depois!
    total = float(item.get("preco", 0.0)) 
    obs_final = str(item.get("observacao") or "").strip(" ,.-|")
    
    info_local = item.get("info_local")
    if info_local:
        if obs_final: obs_final = f"{obs_final} | {info_local}"
        else: obs_final = info_local
        
    adicionais_str = ", ".join(item.get("adicionais_list", []))
    borda_val = item.get("borda")
    # Mostra a borda independentemente de qual seja
    if item.get("tipo") == "pizza" and borda_val:
        adicionais_str = f"{borda_val}, {adicionais_str}".strip(", ")

    fluxo["carrinho_atual"].append(
        {
            "tipo": item.get("tipo"),
            "nome": item.get("nome"),
            "preco": total,
            "quantidade": qtd,
            "observacao": obs_final,
            "adicionais": adicionais_str,
        }
    )

    for k in ["item_extra_pendente", "grupos_perguntas_db", "idx_pergunta_atual", "opcoes_temp", "lista_bordas_temp", "selecoes_grupo_atual", "tamanho_obj"]:
        fluxo.pop(k, None)

    if fluxo.get("itens_com_perguntas_pendentes") and len(fluxo["itens_com_perguntas_pendentes"]) > 0:
        next_item = fluxo["itens_com_perguntas_pendentes"].pop(0)
        return iniciar_fluxo_completo(fluxo, next_item, user_phone, msg_intro=f"✅ Adicionado: {item['nome']}")

    fluxo["etapa"] = None
    from storage import salvar_pedido_completo_db, resumo_carrinho
    from storage.configuracoes import gerar_opcoes_carrinho
    salvar_pedido_completo_db(user_phone, fluxo)
    return create_response(f"✅ *Pedido Atualizado!*\n\n{resumo_carrinho(fluxo)}\n\n{gerar_opcoes_carrinho()}")


def get_keywords_categoria():
    """Gera keywords buscando categorias e apelidos no BD."""
    candidates = {}
    try:
        cats = obter_todas_categorias_db()
        mapa_nomes = {remover_acentos(str(c['nome']).lower().strip()): str(c['id']) for c in cats}
        mapa_ids = {str(c['id']): str(c['id']) for c in cats}

        def add_cand(kw, prio, target_action):
            if not kw or len(kw) < 2: return
            kw = kw.strip()
            if kw not in candidates: candidates[kw] = []
            peso_tipo = 0 if prio == 1 else 2
            candidates[kw].append((peso_tipo, len(kw), target_action))

        for cat in cats:
            nome_original = cat.get("nome", "")
            if not nome_original: continue
            cat_id = cat["id"]
            target = f"listar_{cat_id}"
            nome_norm = remover_acentos(nome_original.lower().strip())
            add_cand(nome_norm, 1, target)
            if nome_norm.endswith("s"): add_cand(nome_norm[:-1], 1, target)
            else: add_cand(nome_norm + "s", 1, target)

        with get_db_connection() as conn:
            try:
                rows_cat = conn.execute("SELECT apelido, categoria_id FROM categoria_apelido").fetchall()
                for r in rows_cat:
                    nick = remover_acentos(str(r["apelido"] or "").lower().strip())
                    cat_ref = str(r["categoria_id"] or "").strip() 
                    target_id = None
                    cat_ref_norm = remover_acentos(cat_ref.lower())
                    if cat_ref in mapa_ids: target_id = cat_ref
                    elif cat_ref_norm in mapa_nomes: target_id = mapa_nomes[cat_ref_norm]
                    if target_id and nick: add_cand(nick, 1, f"listar_{target_id}")
            except Exception: pass

            try:
                rows_sabor = conn.execute("SELECT apelido, categoria FROM sabor_apelido WHERE categoria IS NOT NULL AND categoria != ''").fetchall()
                for r in rows_sabor:
                    nick = remover_acentos(str(r["apelido"] or "").lower().strip())
                    cat_ref = str(r["categoria"] or "").strip()
                    target_id = None
                    cat_ref_norm = remover_acentos(cat_ref.lower())
                    if cat_ref in mapa_ids: target_id = cat_ref
                    elif cat_ref_norm in mapa_nomes: target_id = mapa_nomes[cat_ref_norm]
                    if target_id and nick: add_cand(nick, 1, f"listar_{target_id}")
            except Exception: pass
    except Exception as e:
        logging.error(f"Erro geral keywords: {e}")

    final_keywords = {}
    for kw, lista_cands in candidates.items():
        lista_cands.sort(key=lambda x: (x[0], x[1]))
        final_keywords[kw] = lista_cands[0][2]

    return final_keywords


def listar_itens_categoria(cat_id, fluxo):
    """Lista os produtos de uma categoria e salva em cache para escolha."""
    tabela = get_nome_tabela(cat_id)

    try:
        cats_db = obter_todas_categorias_db()
        mapa_nomes = {str(c["id"]): c["nome"] for c in cats_db}
        nome_cat = mapa_nomes.get(str(cat_id), str(cat_id)).upper()
    except Exception:
        nome_cat = str(cat_id).upper()

    promocoes = obter_promocoes_ativas()
    mais_pedidos = obter_mais_pedidos_db(cat_id)

    variacoes_cat = buscar_variacoes_por_categoria(cat_id)
    min_preco_var = 0.0
    tem_variacao = False

    if variacoes_cat and len(variacoes_cat) > 0:
        tem_variacao = True
        min_preco_var = min(v["preco"] for v in variacoes_cat)

    with get_db_connection() as conn:
        try:
            conn.row_factory = sqlite3.Row
            rows = []
            tabelas_tentativa = [tabela]
            if not tabela.endswith("s"):
                tabelas_tentativa.append(tabela + "s")
            else:
                tabelas_tentativa.append(tabela[:-1])

            for tbl in tabelas_tentativa:
                try:
                    r = conn.execute(f"SELECT * FROM {tbl} ORDER BY nome").fetchall()
                    if r:
                        rows = r
                        break
                except Exception: continue

            if not rows:
                return create_response(f"⚠️ Não encontrei itens nesta categoria ({nome_cat}).")

            opcoes_display = []
            for r in rows:
                it = dict(r)
                item_id = it["id"]
                preco_base_produto = it.get("preco", 0.0)

                if tem_variacao:
                    preco_original = preco_base_produto + min_preco_var
                    prefixo_preco = "A partir de "
                else:
                    preco_original = preco_base_produto
                    prefixo_preco = ""

                it["preco_final"] = preco_original
                it["destaque_icon"] = "⭐ " if item_id in mais_pedidos else ""
                it["promo_txt"] = ""
                it["prefixo_preco"] = prefixo_preco

                for p in promocoes:
                    if str(p.get("categoria")) == str(cat_id):
                        p_id = str(p.get("produto_id", "0"))
                        if p_id == str(item_id) or p_id in ["0", "None", ""]:
                            try:
                                novo_preco = calcular_desconto(preco_original, p.get("desconto"))
                                if novo_preco <= 0.01 and str(p.get("desconto")).replace("%", "") != "100":
                                    pass
                                else:
                                    if novo_preco < preco_original:
                                        it["preco_final"] = novo_preco
                                        it["promo_txt"] = f" ~({preco_original:.2f})~ 🔥"
                            except Exception: pass
                            break

                opcoes_display.append(it)

            opcoes_display.sort(
                key=lambda x: (
                    0 if x.get("disponivel", 1) != 0 else 1,
                    0 if "⭐" in x["destaque_icon"] else 1,
                    x["nome"],
                )
            )

            fluxo["opcoes_temp"] = opcoes_display
            fluxo["etapa"] = "selecionar_da_lista"
            fluxo["categoria_temp"] = cat_id

            msg = f"📍 *Opções de {nome_cat}:*\n\n"
            for i, it in enumerate(opcoes_display):
                if it.get("disponivel", 1) == 0:
                    msg += f"*{i + 1}.* ~{it['nome']}~ (🚫 Esgotado)\n"
                else:
                    msg += f"*{i + 1}.* {it['destaque_icon']}{it['nome']}{it['promo_txt']} ({it['prefixo_preco']}R$ {it['preco_final']:.2f})\n"
            msg += "\n👇 Digite o número desejado."
            return create_response(msg)
        except Exception as e:
            return create_response(f"Erro ao carregar lista: {e}")


# ==============================================================================
# 2. HANDLERS (ESPECIALISTAS DE ESTADO PARA O ROUTER)
# ==============================================================================

def lidar_selecao_lista(fluxo, msg_l, user_phone):
    """Lida com a escolha do produto a partir da lista da categoria."""
    if msg_l.isdigit():
        idx = int(msg_l) - 1
        opcoes = fluxo.get("opcoes_temp", [])
        if 0 <= idx < len(opcoes):
            it = opcoes[idx]
            if it.get("disponivel", 1) == 0:
                return create_response(f"🚫 O item *{it['nome']}* está esgotado.")

            item_obj = {
                "tipo": fluxo.get("categoria_temp"),
                "nome": it["nome"],
                "sabores": [it["nome"]],
                "preco": it.get("preco_final", it.get("preco", 0.0)),
                "id": it["id"],
                "quantidade": 1,
                "observacao": "",
                "adicionais_list": [],
            }
            return iniciar_fluxo_completo(fluxo, item_obj, user_phone)

    # Saída de Emergência
    palavras_chave_complexas = ["pizza", "quero", "com", "de", "e", "metade", "meia"]
    if not msg_l.isdigit() and (len(msg_l.split()) > 2 or any(k in msg_l for k in palavras_chave_complexas)):
        fluxo["etapa"] = None
        return None

    keywords = get_keywords_categoria()
    if msg_l in keywords:
        fluxo["etapa"] = None
        return listar_itens_categoria(keywords[msg_l].replace("listar_", ""), fluxo)

    return create_response("⚠️ Opção inválida. Digite o número correspondente.")


def lidar_escolha_variacao(fluxo, msg_l, user_phone):
    """Lida com a escolha do tamanho ou tipo de variação (Broto, 2 Litros, etc)."""
    opcoes = fluxo.get("opcoes_temp", [])
    var_selecionada = None

    if msg_l.isdigit():
        idx = int(msg_l) - 1
        if 0 <= idx < len(opcoes):
            var_selecionada = opcoes[idx]

    if not var_selecionada:
        match_num = re.search(r'\d+', msg_l)
        val_user = int(match_num.group()) if match_num else None

        for v in opcoes:
            nome_v = remover_acentos(str(v.get("nome") or "").lower().strip())
            sigla_v = remover_acentos(str(v.get("sigla") or "").lower().strip())
            
            if msg_l == nome_v or msg_l == sigla_v:
                var_selecionada = v
                break
            
            if val_user is not None:
                if v.get("fatias") and int(v.get("fatias")) == val_user:
                    var_selecionada = v; break
                
                t_cm_limpo = "".join(filter(str.isdigit, str(v.get("tamanho_cm") or "")))
                if t_cm_limpo and int(t_cm_limpo) == val_user:
                    var_selecionada = v; break

    if var_selecionada:
        item = fluxo["item_extra_pendente"]
        limite = var_selecionada.get("max_sabores", 1)
        qtd_sabores = len(item.get("sabores", []))

        if qtd_sabores > limite:
            return create_response(f"❌ O tamanho *{var_selecionada['nome']}* aceita no máximo *{limite} sabor(es)*.")

        prod_db = buscar_produto_db(item["nome"])
        preco_base = prod_db["preco"] if prod_db and prod_db.get("preco") else 0.0

        item["nome"] = f"{item['nome']} ({var_selecionada['nome']})"
        item["preco"] = preco_base + var_selecionada["preco"]
        item["tamanho_obj"] = var_selecionada

        # Re-aplica desconto
        try:
            promos = obter_promocoes_ativas()
            melhor_preco = item["preco"]
            for p in promos:
                if str(p.get("categoria")) == str(item["tipo"]):
                    p_id = str(p.get("produto_id", "0"))
                    if p_id in ["0", "None", ""] or p_id == str(item.get("id")) or p_id == str(var_selecionada["id"]):
                        novo_preco = calcular_desconto(item["preco"], p.get("desconto"))
                        if not (novo_preco <= 0.01 and str(p.get("desconto")).replace("%", "") != "100"):
                            if novo_preco < melhor_preco: melhor_preco = novo_preco
            item["preco"] = melhor_preco
        except Exception: pass

        if item.get("tipo") == "pizza" and limite > qtd_sabores:
            fluxo["etapa"] = "adicionar_sabores_extras"
            salvar_pedido_completo_db(user_phone, fluxo)
            msg_sabores = f"🍕 Você escolheu *{var_selecionada['nome']}* (Até {limite} sabores).\nJá temos: *{', '.join(item['sabores'])}*.\n\n👉 Digite o nome do *próximo sabor* ou digite *'Não'*."
            return create_response(msg_sabores)

        return seguir_para_adicionais_ou_borda(fluxo, item, user_phone)

    return create_response("⚠️ Opção inválida. Digite o número, o nome (ex: Broto) ou a sigla.")


def lidar_sabores_extras(fluxo, msg_l, user_phone):
    """Lida com a adição de múltiplos sabores na pizza (Loop)."""
    stop_words = ["nao", "não", "sem", "seguir", "continuar", "ok", "pronto", "fechar", "so", "só", "apenas", "somente", "só isso", "pode mandar", "n", "nop", "chega", "finalizar", "concluir", "já deu", "tá bom", "ta bom", "tabom"]

    if msg_l in stop_words or any(msg_l.startswith(sw + " ") for sw in ["so", "só", "apenas", "somente"]):
        return seguir_para_adicionais_ou_borda(fluxo, fluxo["item_extra_pendente"], user_phone)

    partes_sabor = re.split(r"\s+(?:e|com|metade|meia|ou|\/)\s+", msg_l, flags=re.IGNORECASE)
    sabores_encontrados = []

    for parte in partes_sabor:
        parte = parte.strip()
        if len(parte) > 2:
            res_busca = buscar_produto_db(parte)
            prods = [res_busca] if isinstance(res_busca, dict) else res_busca if isinstance(res_busca, list) else []
            prods = [p for p in prods if p.get("tabela_origem") == "pizza" or p.get("categoria") == "pizza"]
            if prods:
                sabores_encontrados.append(prods[0]["nome"])

    if sabores_encontrados:
        item = fluxo["item_extra_pendente"]
        limite = item.get("tamanho_obj", {}).get("max_sabores", 1)
        sabores_adicionados_agora = []

        for novo_sabor in sabores_encontrados:
            if novo_sabor not in item["sabores"] and len(item["sabores"]) < limite:
                item["sabores"].append(novo_sabor)
                sabores_adicionados_agora.append(novo_sabor)

        qtd_agora = len(item["sabores"])

        if sabores_adicionados_agora:
            salvar_pedido_completo_db(user_phone, fluxo)
            nomes_add = ", ".join(sabores_adicionados_agora)
            msg_cont = f"✅ Adicionado(s): *{nomes_add}*.\nPizza Atual: {', '.join(item['sabores'])}\n\n"
            msg_cont += f"Ainda cabe mais {limite - qtd_agora}. Digite o próximo ou 'Não':"
            return create_response(msg_cont)
        else:
            return seguir_para_adicionais_ou_borda(fluxo, item, user_phone)
    else:
        return create_response("❌ Não encontrei sabores na sua mensagem. Tente digitar apenas o nome (ex: Frango).")


def lidar_escolha_borda(fluxo, msg_l, user_message, user_phone):
    """Lida com a seleção da borda da pizza."""
    item = fluxo["item_extra_pendente"]
    lista_bordas = fluxo.get("lista_bordas_temp", [])
    
    if msg_l.isdigit():
        idx = int(msg_l) - 1
        if 0 <= idx < len(lista_bordas):
            item["borda"] = lista_bordas[idx]
            return iniciar_fluxo_adicionais_complexos(fluxo, item, user_phone)
            
    if any(t in msg_l for t in ["sem", "nada", "normal", "tradicional"]):
        item["borda"] = "Sem Borda Recheada"
        return iniciar_fluxo_adicionais_complexos(fluxo, item, user_phone)
        
    matches = difflib.get_close_matches(user_message, lista_bordas, n=1, cutoff=0.6)
    if matches:
        item["borda"] = matches[0].title()
        return iniciar_fluxo_adicionais_complexos(fluxo, item, user_phone)
        
    return create_response("⚠️ Borda não reconhecida. Escolha o número ou diga 'sem'.")


# ==============================================================================
# 3. ROTERADOR PRINCIPAL (ROUTER PATTERN)
# ==============================================================================

# Roteia os estados para suas respectivas funções especialistas
ROTEADOR_EXTRAS = {
    "selecionar_da_lista": lidar_selecao_lista,
    "escolher_variacao_complexa": lidar_escolha_variacao,
    "adicionar_sabores_extras": lidar_sabores_extras,
    "escolher_borda_pizza_extra": lidar_escolha_borda,
    "processar_perguntas_db": lambda f, msg, u, phone: processar_perguntas_db(f, msg, phone)
}

def processar_extras(fluxo, user_message, analise, user_phone, intencao_forca=None):
    """
    Função Principal do Módulo de Extras. 
    Descobre qual a etapa atual e delega para a função responsável.
    """
    user_message = user_message or ""
    msg_l = remover_acentos(user_message.lower().strip().replace("!", ""))
    etapa = fluxo.get("etapa")

    # Tratamento de intenções forçadas por botão ou comando rápido
    if intencao_forca and intencao_forca.startswith("listar_"):
        cat_id = intencao_forca.replace("listar_", "")
        return listar_itens_categoria(cat_id, fluxo)

    # Verifica se a etapa existe no nosso roteador
    if etapa in ROTEADOR_EXTRAS:
        handler = ROTEADOR_EXTRAS[etapa]
        
        # Ajuste fino de parâmetros dependendo do handler
        if etapa == "processar_perguntas_db":
            return processar_perguntas_db(fluxo, user_message, user_phone)
        elif etapa == "escolher_borda_pizza_extra":
            return handler(fluxo, msg_l, user_message, user_phone)
        else:
            return handler(fluxo, msg_l, user_phone)

    # Fallback caso a etapa se perca
    return create_response(gerar_menu_opcoes())


# ==============================================================================
# 4. PREPARAÇÃO DO ITEM E PERGUNTAS COMPLEXAS
# ==============================================================================

def seguir_para_adicionais_ou_borda(fluxo, item, user_phone):
    """
    Decide se pergunta borda, adicionais ou se finaliza o item.
    Implementa a 'Via Rápida' (Fast Track) de forma segura.
    """
    is_fast_track = item.get("observacao_perguntada", False)

    # 1. Formata o nome bonitinho da pizza (ex: Pizza Família - Calabresa/Frango)
    if item.get("tipo") == "pizza" and len(item.get("sabores", [])) > 0:
        tamanho_nome = item.get("tamanho_obj", {}).get("nome", "")
        if tamanho_nome: item["nome"] = f"Pizza {tamanho_nome} - {'/'.join(item['sabores'])}"
        else: item["nome"] = f"Pizza - {'/'.join(item['sabores'])}"

    # 2. Pergunta da Borda (Pula se for Fast Track ou se o cliente já pediu)
    if item.get("tipo") == "pizza" and not item.get("borda_perguntada") and not item.get("borda"):
        from storage import listar_bordas_db
        from storage import salvar_pedido_completo_db
        
        resultado_bordas = listar_bordas_db()
        if resultado_bordas:
            # Desempacota corretamente a tupla original do seu sistema
            msg_b, lista_nomes = resultado_bordas
            if lista_nomes:
                fluxo["lista_bordas_temp"] = lista_nomes
                fluxo["etapa"] = "escolher_borda_pizza_extra"
                salvar_pedido_completo_db(user_phone, fluxo)
                return create_response(f"🧀 *Deseja adicionar borda recheada?*\n\n{msg_b}\n👇 *Digite o número ou 'Sem':*")

    # 3. Vai para a etapa de Grupos/Adicionais Opcionais
    from services.extras_flow import iniciar_fluxo_adicionais_complexos
    
    # MÁGICA DA VIA RÁPIDA: Se o pedido for muito grande, injetamos a palavra 
    # "sem adicionais" de forma invisível. O seu sistema vai ler isso, pular 
    # todas as perguntas chatas e depois apagar a palavra sozinho!
    if is_fast_track:
        obs_atual = str(item.get("observacao") or "")
        if "sem adicionais" not in obs_atual.lower():
            item["observacao"] = f"{obs_atual} | sem adicionais".strip(" |")

    return iniciar_fluxo_adicionais_complexos(fluxo, item, user_phone)

def iniciar_fluxo_completo(fluxo, item, user_phone, msg_intro=""):
    fluxo["item_extra_pendente"] = item
    if "adicionais_list" not in item: item["adicionais_list"] = []
    if "sabores" not in item: item["sabores"] = [item["nome"]]

    artigo = "sua" if item.get("tipo") == "pizza" else "seu"
    intro = f"📝 *Vamos personalizar {artigo} {item['nome']}...*"
    if msg_intro: intro = f"{msg_intro}\n\n{intro}"

    from storage.extras_repository import buscar_variacoes_por_categoria
    from storage.configuracoes import obter_variacoes_pizza_db, obter_promocoes_ativas
    from storage import remover_acentos
    from storage.produtos import buscar_produto_db
    from storage.configuracoes import calcular_desconto

    variacoes = obter_variacoes_pizza_db() if item["tipo"] == "pizza" else buscar_variacoes_por_categoria(item["tipo"])

    if variacoes and "(" not in str(item.get("nome")):
        t_ia = remover_acentos(str(item.get("tamanho") or "").lower())
        var_enc = None

        for v in variacoes:
            v_nome = remover_acentos(str(v.get("nome") or "").lower())
            v_sigla = remover_acentos(str(v.get("sigla") or "").lower())
            match_found = (t_ia and (t_ia == v_nome or t_ia == v_sigla))

            if not match_found and t_ia:
                t_ia_clean, v_nome_clean = t_ia.replace(" ", ""), v_nome.replace(" ", "")
                if t_ia_clean == v_nome_clean: match_found = True
                elif t_ia_clean in v_nome_clean or v_nome_clean in t_ia_clean:
                    if len(t_ia_clean) > 1 and any(char.isdigit() for char in t_ia_clean):
                        match_found = True
            if match_found:
                var_enc = v
                break

        if not var_enc:
            opcoes_variacoes = []
            promos = obter_promocoes_ativas()
            prod_db = buscar_produto_db(item["nome"])
            preco_base_produto = prod_db["preco"] if prod_db and prod_db.get("preco") else 0.0

            for v in variacoes:
                v_copy = dict(v)
                v_copy["preco_display"] = preco_base_produto + v["preco"]
                preco_total_final = v_copy["preco_display"]
                v_copy["promo_txt"] = ""

                for p in promos:
                    if str(p.get("categoria")) == str(item["tipo"]):
                        p_id = str(p.get("produto_id", "0"))
                        if p_id in ["0", "None", ""] or p_id == str(item.get("id")) or p_id == str(v["id"]):
                            try:
                                novo_valor = calcular_desconto(v_copy["preco_display"], p.get("desconto"))
                                if not (novo_valor <= 0.01 and str(p.get("desconto")).replace("%", "") != "100"):
                                    if novo_valor < v_copy["preco_display"]:
                                        preco_total_final = novo_valor
                                        v_copy["promo_txt"] = f" ~({v_copy['preco_display']:.2f})~ 🔥"
                            except Exception: pass

                v_copy["preco_display"] = preco_total_final
                opcoes_variacoes.append(v_copy)

            fluxo["opcoes_temp"] = opcoes_variacoes
            fluxo["etapa"] = "escolher_variacao_complexa"
            from storage import salvar_pedido_completo_db
            salvar_pedido_completo_db(user_phone, fluxo)

            msg_v = f"{intro}\n\n📏 *Qual o tamanho/opção?*\n\n"
            qtd_sabores = len(item.get("sabores", []))

            for i, v in enumerate(opcoes_variacoes):
                limite_msg = ""
                is_blocked = False
                if item.get("tipo") == "pizza":
                    max_s = v.get("max_sabores", 1)
                    s_txt = "Sabor" if max_s == 1 else "Sabores"
                    limite_msg = f"- {max_s} {s_txt}"
                    if qtd_sabores > max_s: is_blocked = True

                icon = " 🚫 (Muitos sabores)" if is_blocked else ""
                msg_v += f"👉 *{i + 1}.* {v['nome']} {limite_msg} {icon}{v['promo_txt']} _(R$ {v['preco_display']:.2f})_\n"
            return create_response(msg_v)
        else:
            if item.get("tipo") == "pizza":
                limite = var_enc.get("max_sabores", 1)
                qtd_sabores = len(item.get("sabores", []))
                item["tamanho_obj"] = var_enc
                if qtd_sabores > limite:
                    item.pop("tamanho", None)
                    return iniciar_fluxo_completo(fluxo, item, user_phone, msg_intro=f"⚠️ O tamanho {var_enc['nome']} não aceita {qtd_sabores} sabores.")

                # FAST TRACK: Se a pessoa pediu 1 sabor na pizza família, ela leva 1 sabor!
                # Removemos a pergunta invasiva de "Você quer completar com mais sabores?".

            prod_db = buscar_produto_db(item["nome"])
            preco_base = prod_db["preco"] if prod_db and prod_db.get("preco") else 0.0

            item["nome"] = f"{item['nome']} ({var_enc['nome']})"
            item["preco"] = preco_base + var_enc["preco"]
            item["tamanho_obj"] = var_enc 

            try:
                promos = obter_promocoes_ativas()
                melhor_preco = item["preco"]
                for p in promos:
                    if str(p.get("categoria")) == str(item["tipo"]):
                        p_id = str(p.get("produto_id", "0"))
                        if p_id in ["0", "None", ""] or p_id == str(item.get("id")) or p_id == str(var_enc["id"]):
                            novo_preco = calcular_desconto(item["preco"], p.get("desconto"))
                            if not (novo_preco <= 0.01 and str(p.get("desconto")).replace("%", "") != "100"):
                                if novo_preco < melhor_preco: melhor_preco = novo_preco
                item["preco"] = melhor_preco
            except Exception: pass

    from services.extras_flow import seguir_para_adicionais_ou_borda
    return seguir_para_adicionais_ou_borda(fluxo, item, user_phone)


def iniciar_fluxo_adicionais_complexos(fluxo, item, user_phone, msg_intro=""):
    prod_id = item.get("id")
    var_id = item.get("tamanho_obj", {}).get("id")

    grupos = buscar_grupos_adicionais_db([item["tipo"], item["nome"]], prod_id, var_id)

    # Tratamento para atalho "sem adicionais"
    if item.get("observacao"):
        obs = remover_acentos(item["observacao"].lower())
        if "sem adicionais" in obs or "nada de adicional" in obs or "sem extras" in obs:
            item["observacao"] = re.sub(r"\b(sem|nada de)\s*(adicionais|adicional|extras)\b", "", item["observacao"], flags=re.IGNORECASE).strip(" ,.-|")
            grupos_obrigatorios = []
            for g in grupos:
                min_esc = g.get("minimo_escolha")
                min_esc = min_esc if min_esc is not None else (1 if g.get("tipo") == "unica" else 0)
                if min_esc > 0: grupos_obrigatorios.append(g)
            grupos = grupos_obrigatorios

    if item.get("borda"):
        grupos = [g for g in grupos if not any(x in g["titulo"].lower() for x in ["borda", "recheio"])]

    if not grupos:
        return finalizar_item_extra_real(fluxo, user_phone)

    fluxo["grupos_perguntas_db"] = grupos
    fluxo["etapa"] = "processar_perguntas_db"
    fluxo["idx_pergunta_atual"] = 0
    fluxo["selecoes_grupo_atual"] = []
    salvar_pedido_completo_db(user_phone, fluxo)
    return processar_perguntas_db(fluxo, "", user_phone, inicio=True, msg_intro=msg_intro)


def processar_perguntas_db(fluxo, user_message, user_phone, inicio=False, msg_intro=""):
    grupos = fluxo.get("grupos_perguntas_db", [])
    idx = fluxo.get("idx_pergunta_atual", 0)

    if idx >= len(grupos):
        return finalizar_item_extra_real(fluxo, user_phone)

    g = grupos[idx]
    tipo_norm = str(g.get("tipo", "")).lower().strip()
    item = fluxo.get("item_extra_pendente", {})

    try: min_esc = int(g.get("minimo_escolha") or (1 if tipo_norm == "unica" else 0))
    except Exception: min_esc = 1 if tipo_norm == "unica" else 0

    try: max_esc = int(g.get("maximo_escolha") or (1 if tipo_norm == "unica" else 10))
    except Exception: max_esc = 1 if tipo_norm == "unica" else 10

    # --- AUTO-DETECÇÃO DE ADICIONAIS NA ENTRADA DA IA ---
    if inicio and item.get("observacao"):
        obs_temp = remover_acentos(item["observacao"].lower())
        opcoes = g.get("opcoes", [])

        # Carrega dicionário de apelidos {nome_real: [apelidos]}
        mapa_apelidos = obter_apelidos_adicionais_db()
        aliases_por_nome = {}
        for apelido, nome_real in mapa_apelidos.items():
            aliases_por_nome.setdefault(nome_real, []).append(apelido)

        # 1. Utilidade NLP faz a varredura da frase
        itens_finais, obs_temp = detectar_adicionais_na_frase(
            obs_temp, opcoes, aliases_por_nome, max_esc, remover_acentos
        )

        # 2. Limpeza da observação suja
        item["observacao"] = limpar_observacao_pos_extracao(obs_temp)

        # 3. Decisão de pulo
        if itens_finais:
            if len(itens_finais) >= max_esc:
                limite_gratis = int(g.get("limite_gratis", 0))
                itens_finais.sort(key=lambda x: x["preco_adicional"])

                for i, s in enumerate(itens_finais):
                    nome_add = f"{s['nome']} (Grátis)" if i < limite_gratis else s["nome"]
                    item["adicionais_list"].append(nome_add)
                    if i >= limite_gratis:
                        item["preco"] += s["preco_adicional"]

                fluxo["idx_pergunta_atual"] += 1
                return processar_perguntas_db(fluxo, "", user_phone, inicio=True, msg_intro=msg_intro)
            else:
                fluxo["selecoes_grupo_atual"] = itens_finais

    if inicio and tipo_norm == "quantidade" and item.get("quantidade_resolvida"):
        fluxo["idx_pergunta_atual"] += 1
        return processar_perguntas_db(fluxo, "", user_phone, inicio=True, msg_intro=msg_intro)

    if not inicio:
        tipo_grupo = str(g.get("tipo", "")).lower().strip()
        titulo_grupo = str(g.get("titulo", "")).lower()

        modo_quantidade = tipo_grupo == "quantidade"
        msg_numerica = re.sub(r"[^\d]", "", user_message)

        if tipo_grupo == "texto" and any(k in titulo_grupo for k in ["qts", "quantas", "unidades", "quantidade"]):
            if msg_numerica and len(msg_numerica) > 0:
                modo_quantidade = True

        if modo_quantidade:
            try:
                if not msg_numerica: raise ValueError
                qtd = int(msg_numerica)
                if qtd > 0:
                    fluxo["item_extra_pendente"]["quantidade"] = qtd
                    fluxo["idx_pergunta_atual"] += 1
                    fluxo["selecoes_grupo_atual"] = []
                    return processar_perguntas_db(fluxo, "", user_phone, inicio=True)
                else:
                    return create_response("⚠️ A quantidade deve ser maior que zero. Digite novamente:")
            except Exception:
                return create_response("⚠️ Por favor, digite um número válido para a quantidade.")

        if tipo_grupo == "texto":
            msg_clean = remover_acentos(user_message.lower().strip())
            ignorados = ["ok", "nao", "n", "nop", "naum", "sem", "pular", "proximo", "nada", "tks", "obg", "nao tenho", "sem obs"]
            if msg_clean not in ignorados and len(msg_clean) > 1:
                txt_obs = user_message.strip()
                item = fluxo["item_extra_pendente"]
                if item.get("observacao"): item["observacao"] += f" | {txt_obs}"
                else: item["observacao"] = txt_obs

            fluxo["idx_pergunta_atual"] += 1
            fluxo["selecoes_grupo_atual"] = []
            return processar_perguntas_db(fluxo, "", user_phone, inicio=True)

        # === TIPO: SELEÇÃO (Única/Múltipla) ===
        ops = g["opcoes"]
        user_message_expanded = expandir_multiplicadores(user_message)
        msg_l = user_message_expanded.lower().strip()
        avancar_grupo = False
        selecoes = fluxo.get("selecoes_grupo_atual", [])

        # Comandos para fechar/pular
        if msg_l in ["ok", "pular", "proximo", "próximo", "continuar", "sem", "não", "nao", "finalizar", "n", "nop", "concluir"]:
            if len(selecoes) >= min_esc: avancar_grupo = True
            else: return create_response(f"⚠️ É obrigatório escolher pelo menos *{min_esc}* opção(ões) neste item.\nVocê escolheu: {len(selecoes)}.")
        
        # Comandos de limpar
        elif msg_l in ["limpar", "zerar", "resetar", "remover", "voltar"]:
            fluxo["selecoes_grupo_atual"] = []
            return processar_perguntas_db(fluxo, "", user_phone, inicio=True, msg_intro="🗑️ Seleções removidas. Escolha novamente:")
        
        # Processar seleções manuais do usuário
        else:
            novas_selecoes = []
            nums = re.findall(r"\b\d+\b", user_message_expanded)
            for n in nums:
                o_idx = int(n) - 1
                if 0 <= o_idx < len(ops):
                    novas_selecoes.append(ops[o_idx])

            msg_text = re.sub(r"\b\d+\b", "", user_message_expanded)
            termos = re.split(r"[,\n+]|\s+(?:e|com|mais)\s+", msg_text, flags=re.IGNORECASE)
            mapa_nomes = {remover_acentos(o["nome"].lower()): o for o in ops}

            # Busca dinâmica de apelidos no BD (usando o Repository)
            try:
                ids_grupo = [str(o["id"]) for o in ops]
                res_apelidos = buscar_apelidos_adicionais_por_grupo(ids_grupo)
                for row in res_apelidos:
                    apelido_norm = remover_acentos(row[0].lower().strip())
                    for o in ops:
                        if str(o["id"]) == str(row[1]):
                            mapa_nomes[apelido_norm] = o
            except Exception as e:
                logging.error(f"Erro ao carregar apelidos do grupo: {e}")

            for termo in termos:
                termo_clean = remover_acentos(termo.strip().lower())
                if len(termo_clean) < 2: continue
                encontrado = None
                for nome_op, obj in mapa_nomes.items():
                    if termo_clean == nome_op:
                        encontrado = obj; break
                    if termo_clean in nome_op and len(termo_clean) > 3:
                        encontrado = obj
                if not encontrado:
                    matches = difflib.get_close_matches(termo_clean, list(mapa_nomes.keys()), n=1, cutoff=0.7)
                    if matches: encontrado = mapa_nomes[matches[0]]
                if encontrado:
                    novas_selecoes.append(encontrado)

            if novas_selecoes:
                if max_esc == 1:
                    fluxo["selecoes_grupo_atual"] = [novas_selecoes[-1]]
                    avancar_grupo = True
                else:
                    for nova in novas_selecoes:
                        if len(fluxo["selecoes_grupo_atual"]) < max_esc:
                            fluxo["selecoes_grupo_atual"].append(nova)
                        else:
                            return create_response(f"⚠️ Limite atingido! Você só pode escolher *{max_esc}* itens.\n\nDigite 'OK' para continuar ou 'Limpar' para recomeçar.")
                    if len(fluxo["selecoes_grupo_atual"]) == max_esc and max_esc == 1:
                        avancar_grupo = True
            else:
                return create_response("⚠️ Opção inválida. Digite o número ou nome da opção.")

        if not avancar_grupo:
            salvar_pedido_completo_db(user_phone, fluxo)
            return processar_perguntas_db(fluxo, "", user_phone, inicio=True)

        if avancar_grupo:
            selecoes = fluxo.get("selecoes_grupo_atual", [])
            limite_gratis = int(g.get("limite_gratis", 0))
            item = fluxo["item_extra_pendente"]

            if len(selecoes) > 0:
                selecoes.sort(key=lambda x: x["preco_adicional"])
                custo_extra = 0.0
                contagem_final = {}
                for s in selecoes:
                    contagem_final[s["nome"]] = contagem_final.get(s["nome"], 0) + 1

                for i, s in enumerate(selecoes):
                    if i >= limite_gratis: custo_extra += s["preco_adicional"]

                lista_formatada = []
                for nome, qtd in contagem_final.items():
                    prefixo = f"{qtd}x " if qtd > 1 else ""
                    lista_formatada.append(f"{prefixo}{nome}")

                item["preco"] += custo_extra
                item["adicionais_list"].extend(lista_formatada)

            fluxo["idx_pergunta_atual"] += 1
            fluxo["selecoes_grupo_atual"] = []
            return processar_perguntas_db(fluxo, "", user_phone, inicio=True)

    if fluxo["idx_pergunta_atual"] >= len(grupos):
        return finalizar_item_extra_real(fluxo, user_phone)

    # --- DISPLAY / EXIBIÇÃO DA PERGUNTA ---
    g = grupos[fluxo["idx_pergunta_atual"]]
    tipo_norm = str(g.get("tipo", "")).lower().strip()

    try: max_esc = int(g.get("maximo_escolha") or (1 if tipo_norm == "unica" else 10))
    except Exception: max_esc = 1 if tipo_norm == "unica" else 10

    try: min_esc = int(g.get("minimo_escolha") or (1 if tipo_norm == "unica" else 0))
    except Exception: min_esc = 1 if tipo_norm == "unica" else 0

    if tipo_norm == "quantidade":
        msg = f"🔢 *{g['titulo']}*\n_{g.get('descricao') or 'Digite a quantidade:'}_"
        return create_response(f"{msg_intro}\n\n{msg}" if msg_intro else msg)

    if tipo_norm == "texto":
        msg = f"📝 *{g['titulo']}*\n_{g.get('descricao') or 'Digite sua resposta ou OK para pular:'}_"
        return create_response(f"{msg_intro}\n\n{msg}" if msg_intro else msg)

    selecionados_buffer = fluxo.get("selecoes_grupo_atual", [])
    txt_opcoes = ""
    for i, o in enumerate(g["opcoes"]):
        qtd_item = sum(1 for s in selecionados_buffer if s["id"] == o["id"])
        marcador = "✅" if qtd_item > 0 else "🔹"
        texto_item = f"*{qtd_item}x* {o['nome']}" if qtd_item > 1 else f"*{o['nome']}*"
        preco_txt = f"(+R$ {o['preco_adicional']:.2f})" if o["preco_adicional"] > 0 else "(Grátis)"
        txt_opcoes += f"{marcador} *{i + 1}.* {texto_item} {preco_txt}\n"

    info_extra = ""
    if g.get("limite_gratis") and g["limite_gratis"] > 0: info_extra += f"\n🎁 {g['limite_gratis']} Opção(ões) Grátis!"

    if min_esc > 0: info_extra += f"\n⚠️ *Escolha exatamente {min_esc}*" if min_esc == max_esc else f"\n⚠️ *Mínimo: {min_esc} | Máximo: {max_esc}*"
    else: info_extra += f"\n(Opcional | Máx: {max_esc})"

    qtd_selecionada = len(selecionados_buffer)
    msg_rodape = ""

    if min_esc > 0 and qtd_selecionada < min_esc:
        faltam = min_esc - qtd_selecionada
        msg_rodape = f"⚠️ _Faltam escolher *{faltam}* opção(ões) obrigatória(s)._"
    elif qtd_selecionada >= max_esc:
        msg_rodape = f"✅ _Máximo de {max_esc} atingido. Digite '*OK*' para continuar._"
    else:
        restam_total = max_esc - qtd_selecionada
        txt_gratis = ""
        limite_gratis = int(g.get("limite_gratis", 0))
        if limite_gratis > 0:
            restam_gratis = max(0, limite_gratis - qtd_selecionada)
            txt_gratis = f" | 🎁 Restam *{restam_gratis}* grátis" if restam_gratis > 0 else " | 💲 Próximos serão cobrados"
        msg_rodape = f"💡 _Selecionados: {qtd_selecionada}/{max_esc} (Restam {restam_total}{txt_gratis})_\n_Digite o número para adicionar ou '*OK*' para concluir._"

    if max_esc > 1 and qtd_selecionada > 0:
        msg_rodape += "\n_(Digite 'Limpar' para reiniciar as escolhas)_"

    msg = f"📌 *{g['titulo']}*{info_extra}\n\n{txt_opcoes}\n{msg_rodape}"
    return create_response(f"{msg_intro}\n\n{msg}" if msg_intro else msg)