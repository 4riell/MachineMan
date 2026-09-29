# flows/complex_flow.py

import re
import logging
from storage import (
    create_response,
    remover_acentos,
    resumo_carrinho,
)
from storage.configuracoes import (
    get_nome_tabela,
    gerar_opcoes_carrinho,
    obter_promocoes_ativas,
    calcular_desconto,
    obter_todas_categorias_db,
    obter_variacoes_pizza_db
)

from storage.complex_repository import (
    obter_cliente_bairro_taxa,
    obter_menor_preco_variacao_db,
    obter_mapa_pizzas_e_apelidos,
    resolver_apelido_geral_db,
    obter_produtos_por_tabela
)
from utils.smart_search import (
    normalizar_tamanho_fuzzy,
    motor_busca_produto,
    resolver_sabores_pizza_avancado
)


def _tentar_antecipar_taxa(fluxo, user_phone):
    try:
        taxa_final = 0.0
        taxa_bairro = obter_cliente_bairro_taxa(user_phone)
        fluxo.setdefault("pedido_info", {})["tipo_entrega"] = "Entrega"
        if taxa_bairro is not None: taxa_final = taxa_bairro
        else:
            from storage import obter_taxa_entrega
            try: taxa_final = float(obter_taxa_entrega())
            except Exception: taxa_final = 0.0
        fluxo["pedido_info"]["taxa_entrega"] = taxa_final
        fluxo["taxa_entrega"] = taxa_final
    except Exception as e: logging.error(f"Erro ao antecipar taxa: {e}")

def _buscar_produto_interno_smart(tabela, nome_busca, cat_id=None):
    if not nome_busca: return None
    id_real, cat_real = resolver_apelido_geral_db(remover_acentos(nome_busca.lower().strip()))
    if id_real:
        tabela_correta = get_nome_tabela(cat_real) if cat_real else tabela
        if tabela_correta:
            res = obter_produtos_por_tabela(tabela_correta, id_real)
            if res: return res

    if cat_id:
        id_alias_legado, _ = resolver_apelido_geral_db(remover_acentos(nome_busca.lower().strip()))
        if id_alias_legado:
            res = obter_produtos_por_tabela(tabela, id_alias_legado)
            if res: return res

    produtos_db = obter_produtos_por_tabela(tabela)
    if not produtos_db: return None
    return motor_busca_produto(produtos_db, nome_busca, remover_acentos)


def processar_pedido_complexo(fluxo, analise, user_phone, user_message="", preservar_pendentes=False):
    from services.extras_flow import iniciar_fluxo_completo, listar_itens_categoria

    user_message_raw = str(user_message or "").lower()
    msgs_retorno = []
    
    itens_ia = analise.get("itens") or []
    end_ia = analise.get("endereco_completo") or {}
    dados_entrega_legacy = analise.get("dados_entrega") or {}
    
    horario_req = end_ia.get("horario") or dados_entrega_legacy.get("horario")
    tipo_entrega = end_ia.get("tipo_entrega") or dados_entrega_legacy.get("tipo_entrega")

    if not horario_req:
        match_hora = re.search(r"(\d{1,2}[:h]\d{2})", user_message_raw)
        if match_hora:
            horario_req = match_hora.group(1).replace("h", ":")

    termos_local = ["comer ai", "comer aí", "comer no local", "mesa", "no estabelecimento", "comer aqui", "no salao", "no salão"]
    eh_pra_comer_local = any(t in user_message_raw for t in termos_local) or (tipo_entrega and "local" in tipo_entrega.lower())

    if eh_pra_comer_local:
        fluxo.setdefault("pedido_info", {})["tipo_entrega"] = "Retirada"
        if "taxa_entrega" in fluxo.get("pedido_info", {}): fluxo["pedido_info"].pop("taxa_entrega")
        if "taxa_entrega" in fluxo: fluxo.pop("taxa_entrega")
    elif tipo_entrega:
        fluxo.setdefault("pedido_info", {})["tipo_entrega"] = tipo_entrega

    if horario_req:
        fluxo.setdefault("pedido_info", {})["horario"] = horario_req

    if fluxo.get("pedido_info", {}).get("tipo_entrega") == "Entrega":
        _tentar_antecipar_taxa(fluxo, user_phone)

    obs_geral_ia = analise.get("observacao_geral")
    if obs_geral_ia:
        atual_obs = fluxo.setdefault("pedido_info", {}).get("observacoes_gerais", "")
        fluxo["pedido_info"]["observacoes_gerais"] = f"{atual_obs} | {obs_geral_ia}".strip(" |")

    if not preservar_pendentes:
        fluxo["itens_com_perguntas_pendentes"] = []
        fluxo["itens_ambiguos_pendentes"] = []

    if not itens_ia:
        return _concluir_e_rotear_fluxo(fluxo, msgs_retorno, user_phone)

    db_pizzas, db_apelidos = obter_mapa_pizzas_e_apelidos()

    # --- NOVO: Contagem Global para Inteligência da Via Rápida ---
    contagem_por_categoria = {}
    for x in itens_ia:
        cat_temp = str(x.get("categoria") or x.get("tipo") or "").lower()
        qtd_temp = int(x.get("quantidade") or 1)
        contagem_por_categoria[cat_temp] = contagem_por_categoria.get(cat_temp, 0) + qtd_temp

    for i, item in enumerate(itens_ia):
        categoria = str(item.get("categoria") or item.get("tipo") or "").lower()
        
        # A Mágica: Só ativa a via rápida se tiver MAIS de 1 item desta categoria no pedido
        is_fast_track = contagem_por_categoria.get(categoria, 1) > 1

        sabores_raw = item.get("sabores") or []
        nome_ia = str(item.get("nome") or (sabores_raw[0] if sabores_raw else ""))

        termos_x = ["tudo", "salada", "bacon", "burguer", "egg", "frango", "calabresa", "pernil", "picanha"]
        nome_lower = remover_acentos(nome_ia.lower().strip())
        if nome_lower in termos_x:
            pattern_x = rf"\bx[\s-]*{re.escape(nome_lower)}\b"
            if re.search(pattern_x, user_message_raw):
                nome_ia = f"X-{nome_lower.title()}"

        if not nome_ia and categoria and categoria != "pizza":
            tabela = get_nome_tabela(categoria)
            if tabela:
                produtos = obter_produtos_por_tabela(tabela)
                if produtos:
                    for p in produtos:
                        if p["nome"].lower() in user_message_raw:
                            nome_ia = p["nome"]
                            break

        if not nome_ia and categoria and categoria != "pizza":
            if len(itens_ia) == 1: return listar_itens_categoria(categoria, fluxo)
            else:
                msgs_retorno.append(f"⚠️ Identifiquei um item de *{categoria}*, mas não entendi qual.")
                continue

        if not nome_ia and not categoria == "pizza": continue

        obs_raw = str(item.get("observacao") or "").strip()
        clean_terms = [r"sem\s+borda\s+recheada", r"sem\s+borda", r"sem\s+recheio", r"borda\s+tradicional", r"borda\s+normal", r"sem\s+a\s+borda"]
        for pattern in clean_terms: obs_raw = re.sub(pattern, "", obs_raw, flags=re.IGNORECASE).strip()
        obs_raw = re.sub(r"^[\.,\-\s\|]+|[\.,\-\s\|]+$", "", obs_raw).strip()
        
        info_local = None
        if eh_pra_comer_local:
            info_local = "Comer no Local"
            if horario_req: info_local += f": {horario_req}"
        elif fluxo.get("pedido_info", {}).get("tipo_entrega") and "entrega" not in fluxo.get("pedido_info", {}).get("tipo_entrega").lower():
            info_ret = str(fluxo.get("pedido_info", {}).get("tipo_entrega")).title()
            if horario_req: info_ret += f" às {horario_req}"
            info_local = info_ret
        elif horario_req:
            info_local = f"Para às {horario_req}"

        if categoria == "pizza" or "pizza" in nome_ia.lower():
            sabores_alvo = sabores_raw if sabores_raw else [nome_ia]
            sabores_validos, sabores_ruins = resolver_sabores_pizza_avancado(sabores_alvo, db_pizzas, db_apelidos, remover_acentos)
            tamanho_norm = normalizar_tamanho_fuzzy(item.get("tamanho"), obter_variacoes_pizza_db())
            sabores_ruins = [s for s in sabores_ruins if s.lower().strip() not in ["pizza", "pizzas", "1 pizza", "uma pizza"]]
            
            # Assume "Sem Borda Recheada" APENAS se o cliente pediu ou se for Fast Track
            borda_pre = item.get("borda")
            pediu_sem_borda = borda_pre == "Sem Borda" or any(t in user_message_raw for t in ["sem borda", "borda normal", "tradicional", "sem a borda"])
            
            if pediu_sem_borda:
                borda_pre = "Sem Borda Recheada"
            elif not borda_pre and is_fast_track:
                borda_pre = "Sem Borda Recheada"

            if sabores_ruins:
                if sabores_validos:
                    fluxo["item_em_construcao"] = {
                        "tipo": "pizza", "sabores": sabores_validos, "tamanho": tamanho_norm, 
                        "quantidade": item.get("quantidade", 1), "observacao": obs_raw, 
                        "borda": borda_pre, "quantidade_resolvida": True, "info_local": info_local,
                        "observacao_perguntada": is_fast_track, "borda_perguntada": is_fast_track
                    }
                    itens_restantes = itens_ia[i + 1 :]
                    if itens_restantes:
                        fluxo["fila_itens_pendentes_ia"] = itens_restantes
                        fluxo["contexto_entrega_pendente"] = end_ia
                    fluxo["etapa"] = "pedir_sabor_restante"
                    sabor_ruim_str = ", ".join(sabores_ruins)
                    sabor_bom_str = ", ".join(sabores_validos)
                    return create_response(f"🍕 Entendi *{sabor_bom_str}*, mas não achei *{sabor_ruim_str}*. Qual sabor entra no lugar?")
                else:
                    msgs_retorno.append(f"⚠️ Não reconheci o sabor: *{', '.join(sabores_ruins)}*.")
                    continue

            if not sabores_validos:
                fluxo["item_em_construcao"] = {
                    "tipo": "pizza", "sabores": [], "tamanho": tamanho_norm,
                    "quantidade": item.get("quantidade", 1), "observacao": obs_raw,
                    "borda": borda_pre, "quantidade_resolvida": True, "info_local": info_local,
                    "observacao_perguntada": is_fast_track, "borda_perguntada": is_fast_track
                }
                fluxo["etapa"] = "pedir_sabor_restante"
                tamanho_txt = f" {tamanho_norm}" if tamanho_norm else ""
                return create_response(f"🍕 Entendi que você quer uma pizza*{tamanho_txt}*. \n\nQual o sabor?")

            pizza_obj = {
                "tipo": "pizza", "tamanho": tamanho_norm, "sabores": sabores_validos,
                "borda": borda_pre, "observacao": obs_raw, "quantidade": item.get("quantidade", 1),
                "nome": " / ".join(sabores_validos), "adicionais_list": [], "preco": 0.0,
                "quantidade_resolvida": True, "info_local": info_local,
                "observacao_perguntada": is_fast_track, "borda_perguntada": is_fast_track
            }
            fluxo["itens_com_perguntas_pendentes"].append(pizza_obj)

        else:
            tabela = get_nome_tabela(categoria) or "lanches"
            id_apelido, cat_apelido = resolver_apelido_geral_db(remover_acentos(nome_ia.lower().strip()))
            if id_apelido:
                categoria = cat_apelido
                tabela = get_nome_tabela(categoria)

            nome_busca_smart = nome_ia
            if "coca zero" in nome_busca_smart.lower(): 
                nome_busca_smart = re.sub(r"(?i)coca zero", "Coca Cola Zero", nome_busca_smart)
            elif "coca" in nome_busca_smart.lower() and "cola" not in nome_busca_smart.lower(): 
                nome_busca_smart = re.sub(r"(?i)coca", "Coca Cola", nome_busca_smart)

            match = _buscar_produto_interno_smart(tabela, nome_busca_smart, cat_id=categoria)

            if not match:
                logging.info(f"🔎 Item '{nome_busca_smart}' não encontrado em '{categoria}'. Tentando busca global...")
                todas_cats = obter_todas_categorias_db()
                for cat in todas_cats:
                    cat_id_temp = cat["id"]
                    if cat_id_temp == "pizza" or cat_id_temp == categoria: continue
                    tabela_temp = get_nome_tabela(cat_id_temp)
                    if tabela_temp:
                        match_temp = _buscar_produto_interno_smart(tabela_temp, nome_busca_smart, cat_id=cat_id_temp)
                        if match_temp:
                            match = match_temp
                            categoria = cat_id_temp 
                            break

            if isinstance(match, dict) and match.get("disponivel", 1) == 0:
                msgs_retorno.append(f"🚫 O item *{match['nome']}* está esgotado.")
                continue

            if isinstance(match, list):
                tamanho_ia = str(item.get("tamanho") or "").strip().lower()
                if tamanho_ia:
                    t_ia_clean = tamanho_ia.replace("litros", "l").replace("litro", "l").replace(" ", "").replace(".", ",")
                    candidatos_tamanho = []
                    for c in match:
                        nome_db_clean = c["nome"].lower().replace("litros", "l").replace("litro", "l").replace(" ", "").replace(".", ",")
                        if t_ia_clean in nome_db_clean:
                            candidatos_tamanho.append(c)
                    
                    if candidatos_tamanho: match = candidatos_tamanho

                if isinstance(match, list) and len(match) > 1:
                    candidatos_score = []
                    termos_msg = [t for t in user_message_raw.split() if len(t) > 1]
                    for cand in match:
                        score = sum(1 for t in termos_msg if re.search(rf"\b{re.escape(t)}\b", remover_acentos(cand["nome"].lower())))
                        candidatos_score.append((score, cand))
                    candidatos_score.sort(key=lambda x: x[0], reverse=True)
                    if candidatos_score: match = [c[1] for c in candidatos_score if c[0] == candidatos_score[0][0]]

                if isinstance(match, list) and len(match) == 1: match = match[0]

            if isinstance(match, list):
                promos = obter_promocoes_ativas()
                min_preco_var = obter_menor_preco_variacao_db(categoria)
                tem_variacao = min_preco_var > 0 or (categoria in ["pizza", "acai"])

                for cand in match:
                    preco_base = cand.get("preco", 0.0)
                    if tem_variacao:
                        preco_original = preco_base + min_preco_var
                        cand["nome"] = f"A partir de {cand['nome']}"
                    else: preco_original = preco_base
                    
                    cand["preco"] = preco_original

                    for p in promos:
                        if p.get("categoria") == categoria:
                            p_id = str(p.get("produto_id", "0"))
                            if p_id == str(cand["id"]) or p_id in ["0", "None", ""]:
                                try:
                                    novo_preco = calcular_desconto(preco_original, p.get("desconto"))
                                    if novo_preco < preco_original:
                                        cand["preco"] = novo_preco
                                        cand["nome"] = f"{cand['nome']} ~({preco_original:.2f})~ 🔥"
                                except Exception: pass
                                break
                                
                fluxo["itens_ambiguos_pendentes"].append({
                    "tipo": categoria, "matches": match, "nome_busca": nome_busca_smart,
                    "quantidade": item.get("quantidade", 1), "observacao": obs_raw, "info_local": info_local,
                    "observacao_perguntada": is_fast_track, "borda_perguntada": is_fast_track
                })
                
            elif match:
                if match.get("disponivel", 1) == 0:
                    msgs_retorno.append(f"🚫 O item *{match['nome']}* está esgotado.")
                    continue

                preco = match["preco"]
                min_preco_var = obter_menor_preco_variacao_db(categoria)
                if min_preco_var > 0 or categoria in ["pizza", "acai"]: preco += min_preco_var

                try:
                    promos = obter_promocoes_ativas()
                    for p in promos:
                        if p.get("categoria") == categoria:
                            p_id = str(p.get("produto_id", "0"))
                            if p_id == str(match["id"]) or p_id in ["0", "None", ""]:
                                preco = calcular_desconto(preco, p.get("desconto"))
                                break
                except Exception: pass

                item_obj = {
                    "tipo": categoria, "nome": match["nome"], "preco": preco,
                    "id": match["id"], "quantidade": item.get("quantidade", 1),
                    "observacao": obs_raw, "tamanho": item.get("tamanho"),
                    "adicionais_list": [], "quantidade_resolvida": True, "info_local": info_local,
                    "observacao_perguntada": is_fast_track, "borda_perguntada": is_fast_track
                }
                fluxo["itens_com_perguntas_pendentes"].append(item_obj)
            else:
                msgs_retorno.append(f"🤔 Não encontrei '{nome_busca_smart}'.")

    return _concluir_e_rotear_fluxo(fluxo, msgs_retorno, user_phone)


def _concluir_e_rotear_fluxo(fluxo, msgs_retorno, user_phone):
    from services.extras_flow import iniciar_fluxo_completo
    msg_intro = "\n".join(msgs_retorno) if msgs_retorno else ""
    if fluxo.get("itens_ambiguos_pendentes"):
        from services.pedido_flow import resolver_pendencia_item
        fluxo["etapa"] = "processar_resolucao_ambiguidade"
        return resolver_pendencia_item(fluxo, "", user_phone, msg_intro)
    if fluxo.get("itens_com_perguntas_pendentes"):
        next_item = fluxo["itens_com_perguntas_pendentes"].pop(0)
        return iniciar_fluxo_completo(fluxo, next_item, user_phone, msg_intro=msg_intro)
    return create_response(f"{msg_intro}\n\n{resumo_carrinho(fluxo)}\n\n{gerar_opcoes_carrinho()}")

def processar_sabor_restante(fluxo, user_message, user_phone):
    from services.extras_flow import iniciar_fluxo_completo
    item = fluxo.get("item_em_construcao")
    if not item or item.get("tipo") != "pizza": return create_response("Erro ao recuperar pizza.")
    db_pizzas, db_apelidos = obter_mapa_pizzas_e_apelidos()
    sabores_validos, sabores_ruins = resolver_sabores_pizza_avancado([user_message.strip()], db_pizzas, db_apelidos, remover_acentos)
    if sabores_ruins: return create_response(f"⚠️ Não encontrei *{sabores_ruins[0]}*. Tente outro:")

    item["sabores"].extend(sabores_validos)
    item["nome"] = " / ".join(item["sabores"])
    pizza_final = {
        "tipo": "pizza", "tamanho": item.get("tamanho"), "sabores": item["sabores"],
        "borda": item.get("borda"), "observacao": item.get("observacao"), "quantidade": item.get("quantidade", 1),
        "nome": item["nome"], "adicionais_list": [], "preco": 0.0, "quantidade_resolvida": True,
        "info_local": item.get("info_local"),
        "observacao_perguntada": item.get("observacao_perguntada", False), 
        "borda_perguntada": item.get("borda_perguntada", False)
    }
    fluxo["item_em_construcao"] = {}
    if "itens_com_perguntas_pendentes" not in fluxo: fluxo["itens_com_perguntas_pendentes"] = []
    fluxo["itens_com_perguntas_pendentes"].insert(0, pizza_final)

    itens_restantes = fluxo.pop("fila_itens_pendentes_ia", [])
    contexto_entrega = fluxo.pop("contexto_entrega_pendente", {})
    if itens_restantes:
        return processar_pedido_complexo(fluxo, {"itens": itens_restantes, "dados_entrega": contexto_entrega}, user_phone, preservar_pendentes=True)

    next_item = fluxo["itens_com_perguntas_pendentes"].pop(0)
    return iniciar_fluxo_completo(fluxo, next_item, user_phone, msg_intro=f"✅ Combinado: {item['nome']}")

def processar_tamanho_lote(fluxo, user_message, user_phone):
    return processar_pedido_complexo(fluxo, {}, user_phone, user_message)