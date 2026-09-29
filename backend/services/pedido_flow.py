# services/pedido_flow.py

import re
import difflib
import sqlite3
import logging

from core import (
    MSG_MENU_O_QUE_DESEJA,
    MSG_NUMERO_INVALIDO_TENTE_NOVAMENTE,
    MSG_CARRINHO_VAZIO,
    MSG_MENU_REMOVER,
    MSG_DIGITE_APENAS_NUMERO,
    MSG_ITEM_REMOVIDO_SUCESSO,
)

from storage import (
    create_response,
    salvar_pedido_completo_db,
    resumo_carrinho,
    get_db_connection,
    validar_sabores_db,
    listar_bordas_db,
    normalizar_tamanho,
    obter_taxa_entrega,
    buscar_cliente_completo,
    obter_tempo_entrega_config,
)
from storage.configuracoes import (
    gerar_menu_opcoes,
    gerar_opcoes_carrinho,
    obter_texto_horario_dinamico,
    obter_valor_minimo_pedido,
    obter_variacoes_pizza_db,
    get_nome_tabela
)
from services.finalizacao_flow import obter_modos_envio_wpp 
from services.extras_flow import iniciar_fluxo_completo, processar_extras

MSG_PEDIR_SABORES_LISTA = "🍕 *Quais sabores você deseja?*\n\n(Digite os sabores separados por vírgula ou 'e')"


# ==============================================================================
# 1. RESOLUÇÃO DE AMBIGUIDADES (SMART SEARCH FALLBACK)
# ==============================================================================

def resolver_pendencia_item(fluxo, user_message, user_phone, msgs_intro=[]):
    """Lida com a escolha do usuário quando o Smart Search retorna mais de um item."""
    user_message = user_message or ""
    pendencias = fluxo.get("itens_ambiguos_pendentes", [])

    if not pendencias:
        return create_response("Não há itens pendentes.")

    pendencia = pendencias[0]
    candidatos = pendencia["matches"]
    quantidade = int(pendencia.get("quantidade") or 1)

    # Exibe as opções se não houver resposta
    if not user_message:
        opcoes_txt = ""
        for i, cand in enumerate(candidatos):
            preco_un = float(cand["preco"] or 0)
            if quantidade > 1:
                total_item = preco_un * quantidade
                opcoes_txt += f"*{i + 1}.* {cand['nome']} - {quantidade}x R$ {preco_un:.2f} *(Total: R$ {total_item:.2f})*\n"
            else:
                opcoes_txt += f"*{i + 1}.* {cand['nome']} *(R$ {preco_un:.2f})*\n"

        nome_busca = pendencia.get("nome_busca", "produto")
        prefixo_qtd = f"*{quantidade}x* " if quantidade > 1 else ""
        msg_base = f"🤔 Sobre {prefixo_qtd}*'{nome_busca}'*, encontrei opções parecidas. Qual delas você quer?\n\n{opcoes_txt}\n(Digite o número correspondente)"

        intro_txt = msgs_intro if isinstance(msgs_intro, str) else "\n".join(msgs_intro)
        return create_response(f"{intro_txt}\n\n{msg_base}" if intro_txt else msg_base)

    # Processa a escolha
    msg_clean = user_message.strip()
    if msg_clean.isdigit():
        idx = int(msg_clean) - 1
        if 0 <= idx < len(candidatos):
            escolha = candidatos[idx]
            
            item_obj = {
                "tipo": pendencia.get("tipo", "extra"),
                "nome": escolha["nome"],
                "preco": escolha["preco"],
                "id": escolha["id"],
                "quantidade": quantidade,
                "observacao": pendencia.get("observacao", ""),
                "adicionais_list": [],
                "contexto": f"Escolhido: {escolha['nome']}",
                "info_local": pendencia.get("info_local")
            }

            fluxo["itens_ambiguos_pendentes"].pop(0)
            prefixo_conf = f"*{quantidade}x* " if quantidade > 1 else ""
            return iniciar_fluxo_completo(fluxo, item_obj, user_phone, msg_intro=f"✅ Você escolheu: {prefixo_conf}*{escolha['nome']}*")
        else:
            return create_response(MSG_NUMERO_INVALIDO_TENTE_NOVAMENTE)

    return create_response("⚠️ Por favor, digite o número da opção desejada.")

def processar_resolucao_ambiguidade(fluxo, user_message, user_phone):
    return resolver_pendencia_item(fluxo, user_message, user_phone)


# ==============================================================================
# 2. FLUXO MANUAL DE MONTAGEM DE PIZZA (STEP-BY-STEP)
# ==============================================================================

def _lidar_comandos_de_escape(msg_lower, fluxo, user_message, user_phone):
    """Trata comandos globais que interrompem a montagem da pizza."""
    if msg_lower in ["cancelar", "voltar", "menu", "reiniciar", "sair"]:
        fluxo["etapa"] = None
        fluxo["item_em_construcao"] = {}
        for chave in ["lote_pizzas_pendentes", "matches_escolha_atual", "itens_ambiguos_pendentes", "itens_com_perguntas_pendentes"]:
            fluxo[chave] = []
        
        if msg_lower in ["reiniciar", "sair"]:
            fluxo["carrinho_atual"] = []
            salvar_pedido_completo_db(user_phone, fluxo)
            return create_response("🔄 Sistema Reiniciado!\n\n" + MSG_MENU_O_QUE_DESEJA)
        return create_response(MSG_MENU_O_QUE_DESEJA)

    termos_escape = ["bebida", "bebidas", "refrigerante", "refri", "sobremesa", "sobremesas", "doce", "doces"]
    if any(t == msg_lower or t in msg_lower.split() for t in termos_escape):
        fluxo["item_em_construcao"] = {}
        fluxo["etapa"] = None
        nova_intencao = "listar_sobremesas" if any(t in msg_lower for t in ["sobremesa", "doce"]) else "listar_bebidas"
        return processar_extras(fluxo, user_message, {}, user_phone, nova_intencao)

    if "tempo" in msg_lower and ("entrega" in msg_lower or "demora" in msg_lower):
        tempo = obter_tempo_entrega_config()
        return create_response(f"🕒 Nosso tempo médio de entrega é de *{tempo}*.\n\nAgora, voltando ao pedido: **Qual tamanho de pizza você deseja?**")

    if "horario" in msg_lower or "funcionamento" in msg_lower or "aberto" in msg_lower:
        horario_msg = obter_texto_horario_dinamico()
        return create_response(f"{horario_msg}\n\nVamos continuar? **Qual tamanho de pizza você deseja?**")
        
    return None

def _extrair_tamanho_manual(msg_upper, tamanhos_db):
    """Tenta adivinhar o tamanho da pizza na string digitada."""
    if msg_upper.isdigit():
        idx = int(msg_upper) - 1
        if 0 <= idx < len(tamanhos_db):
            return tamanhos_db[idx]["nome"]
    
    for t in tamanhos_db:
        if t["nome"].upper() == msg_upper: return t["nome"]
        
    for t in tamanhos_db:
        sigla = t["nome"][0].upper()
        if msg_upper == sigla or msg_upper in t["nome"].upper():
            return t["nome"]
    return None

def processar_pizza(fluxo, user_message, analise, user_phone, intencao):
    """Roteador principal da montagem manual de pizza."""
    user_message = user_message or ""
    msg_lower = user_message.lower().strip()
    msg_upper = user_message.upper().strip()

    # 1. Checa Comandos Globais de Escape
    escape_response = _lidar_comandos_de_escape(msg_lower, fluxo, user_message, user_phone)
    if escape_response: return escape_response

    # 2. Verifica Cadastro
    if not fluxo.get("cadastro", {}).get("nome"):
        cliente_db = buscar_cliente_completo(user_phone)
        if cliente_db and cliente_db.get("nome"): fluxo["cadastro"] = cliente_db
        else:
            fluxo["etapa"] = "cadastro_nome"
            return create_response("👋 Olá! Antes de anotarmos o seu pedido, precisamos de um rápido cadastro.\n\n**Qual é o seu nome?**")

    # 3. Inicializa ou Recupera Item
    tamanhos_db = obter_variacoes_pizza_db()
    if intencao == "pedir_pizza":
        fluxo["etapa"] = "pizza_flow"
        tamanho_ia = analise.get("tamanho")
        tamanho_final = None
        if tamanho_ia:
            nome_puro = tamanho_ia.split('(')[0].strip().lower()
            if nome_puro in msg_lower or any(sigla in msg_upper.split() for sigla in ["P", "M", "G", "GG"]):
                tamanho_final = normalizar_tamanho(tamanho_ia)
                
        fluxo["item_em_construcao"] = {
            "tipo": "pizza", "tamanho": tamanho_final, "sabores": analise.get("sabores", []),
            "borda": analise.get("borda"), "observacao": analise.get("observacao"), "quantidade": analise.get("quantidade", 1),
        }

    item = fluxo.get("item_em_construcao", {})
    if not item:
        item = {"tipo": "pizza", "sabores": [], "quantidade": 1}
        fluxo["item_em_construcao"] = item

    # 4. PREENCHE AS LACUNAS (Tamanho -> Sabor -> Borda)
    
    # A. Tamanho
    if user_message and not item.get("tamanho"):
        novo_tamanho = _extrair_tamanho_manual(msg_upper, tamanhos_db)
        if novo_tamanho:
            item["tamanho"] = novo_tamanho
            item["borda"] = None

    if not item.get("tamanho"):
        msg = "📏 *Qual o tamanho/opção?*\n\n"
        for i, t in enumerate(tamanhos_db):
            detalhe = f"{t['fatias']} fatias"
            if t["tamanho_cm"]: detalhe += f", {t['tamanho_cm']}"
            msg += f"👉 *{i + 1}. {t['nome']}* - {t['max_sabores']} Sabores (R$ {t['preco']:.2f})\n   _({detalhe})_\n\n"
        return create_response(msg)

    # B. Sabores
    termos = [t.strip() for t in re.split(r",| e | \+ ", user_message) if t.strip()]
    termos_limpos = [re.sub(r"^(metade|meia|1/2|parte)\s+(de\s+)?", "", t, flags=re.IGNORECASE).strip() for t in termos]
    
    # Se a IA já tinha extraído, usamos, senão usamos o regex acima
    fonte_sabores = analise.get("sabores") if intencao == "pedir_pizza" else termos_limpos
    
    if fonte_sabores:
        sabores_validos, sabores_ruins = validar_sabores_db(fonte_sabores)
        
        # Filtra falsos positivos de borda
        _, lista_bordas_check = listar_bordas_db()
        termo_borda_safe = ["sem", "borda", "recheio", "tradicional", "normal", "nada"] + [b.lower() for b in lista_bordas_check]
        sabores_ruins = [s for s in sabores_ruins if s.lower() not in termo_borda_safe]
        
        if sabores_ruins:
            return create_response(f"⚠️ Desculpe, não reconheci o sabor: **{', '.join(sabores_ruins)}**.\n\nPor favor, verifique se escreveu corretamente.")
            
        if sabores_validos:
            if not item.get("sabores") or "mudar" in msg_lower or "trocar" in msg_lower:
                item["sabores"] = sabores_validos
            else:
                novos = [s for s in sabores_validos if s not in item.get("sabores", [])]
                item["sabores"].extend(novos)

    if not item.get("sabores"):
        return create_response(MSG_PEDIR_SABORES_LISTA)

    # C. Limites de Sabor
    tam_upper = item["tamanho"].upper()
    limite = 2
    for t in tamanhos_db:
        if t["nome"].upper() == tam_upper:
            limite = t["max_sabores"]
            item["preco_base"] = t["preco"]
            break

    if len(item["sabores"]) > limite:
        return create_response(f"❌ A pizza {item['tamanho']} aceita só {limite} sabores. Você escolheu {len(item['sabores'])}. Digite 'cancelar' para recomeçar ou digite os sabores corretos.")

    # D. Borda
    msg_bordas, lista_bordas = listar_bordas_db()
    escolha_borda = next((b for b in lista_bordas if b.lower() in msg_lower), None)
    if not escolha_borda:
        matches = difflib.get_close_matches(msg_lower, lista_bordas, n=1, cutoff=0.7)
        if matches: escolha_borda = matches[0]

    # Prevenção: "Pizza de Catupiry" não deve virar "Borda de Catupiry" acidentalmente
    sabores_atuais = [s.lower() for s in item.get("sabores", [])]
    if escolha_borda and any(escolha_borda.lower() in s for s in sabores_atuais):
        if "borda" not in msg_lower and "recheio" not in msg_lower: escolha_borda = None

    if any(t in msg_lower for t in ["sem borda", "sem recheio", "tradicional"]) or msg_lower.strip() == "sem":
        item["borda"] = "Sem Borda Recheada"
    elif escolha_borda:
        item["borda"] = escolha_borda.title()

    if not item.get("borda"):
        return create_response(f"🧀 *Deseja adicionar borda recheada?*\n\n{msg_bordas}\n👇 *Digite o número ou 'Sem':*")


    # 5. FINALIZA O ITEM E COLOCA NO CARRINHO
    qtd = int(item.get("quantidade", 1))
    for _ in range(qtd):
        fluxo.setdefault("carrinho_atual", []).append(item.copy())
        
    fluxo["item_em_construcao"] = {}
    fluxo["etapa"] = None
    salvar_pedido_completo_db(user_phone, fluxo)

    return create_response(f"✅ Anotado!\n\n{resumo_carrinho(fluxo)}\n\n{gerar_opcoes_carrinho()}")


# ==============================================================================
# 3. FLUXO DE FINALIZAÇÃO DE PEDIDO (CHECKOUT)
# ==============================================================================

def finalizar_pedido(fluxo, user_message, user_phone):
    """
    Roteador de Checkout.
    (Nota: Idealmente mover para finalizacao_flow.py no futuro)
    """
    carrinho = fluxo.get("carrinho_atual", [])
    if not carrinho: return create_response(MSG_CARRINHO_VAZIO)

    # Validação do Mínimo
    subtotal = sum(float(item.get("preco", 0.0)) * int(item.get("quantidade", 1)) for item in carrinho)
    minimo = float(obter_valor_minimo_pedido())
    if subtotal < minimo:
        return create_response(f"🚫 O valor mínimo para pedidos é *R$ {minimo:.2f}*.\nSeu subtotal é R$ {subtotal:.2f}.\n\nPor favor, adicione mais itens.")

    etapa = fluxo.get("etapa")
    msg_lower = (user_message or "").lower().strip()

    # ESTADO 1: Perguntar Modo de Entrega
    if not etapa or etapa == "finalizar_pedido":
        modos = obter_modos_envio_wpp()
        fluxo["modos_envio_cache"] = modos
        txt = "📦 *Como deseja receber seu pedido?*\n\n"
        for i, m in enumerate(modos): txt += f"*{i+1}* - {m['nome']}\n"
        txt += "\n(Digite o número correspondente)"
        fluxo["etapa"] = "finalizar_escolher_tipo"
        return create_response(txt)

    # ESTADO 2: Processar Modo de Entrega
    if etapa == "finalizar_escolher_tipo":
        if msg_lower in ["1", "entrega", "entregar"]:
            fluxo.setdefault("pedido_info", {})["tipo_entrega"] = "Entrega"
        elif msg_lower in ["2", "retirada", "buscar", "viagem", "pegar", "balcao"]:
            fluxo.setdefault("pedido_info", {})["tipo_entrega"] = "Retirada"
        else:
            return create_response("⚠️ Opção inválida. Digite *1 para Entrega* ou *2 para Retirada*.")

        # Se for entrega e não tiver endereço, pede endereço. Senão, pula pra confirmação.
        if fluxo["pedido_info"]["tipo_entrega"] == "Entrega" and not fluxo.get("cadastro", {}).get("rua"):
            fluxo["etapa"] = "finalizar_endereco_manual"
            return create_response("📍 Para entrega, preciso do seu endereço.\nDigite *Rua, Número e Bairro* (ou ponto de referência):")
        else:
            fluxo["etapa"] = "finalizar_confirma_tudo"

    # ESTADO 3: Capturar Endereço Manual (Correção de Bug)
    if etapa == "finalizar_endereco_manual":
        if len(msg_lower) < 5:
            return create_response("⚠️ O endereço parece muito curto. Por favor, digite Rua, Número e Bairro completos:")
        fluxo.setdefault("cadastro", {})["rua"] = user_message.strip()
        fluxo["cadastro"]["numero"] = "S/N" # Preenchimento de segurança
        fluxo["cadastro"]["bairro"] = ""
        fluxo["etapa"] = "finalizar_confirma_tudo"

    # ESTADO 4: Exibir Resumo e Confirmar
    if fluxo.get("etapa") == "finalizar_confirma_tudo":
        tipo_entrega = fluxo.get("pedido_info", {}).get("tipo_entrega", "Entrega")
        taxa = 0.0

        if tipo_entrega == "Retirada":
            fluxo.setdefault("pedido_info", {})["taxa_entrega"] = 0.0
        else:
            taxa_bairro = fluxo.get("pedido_info", {}).get("taxa_entrega")
            taxa = float(taxa_bairro) if taxa_bairro is not None else float(obter_taxa_entrega())
            fluxo.setdefault("pedido_info", {})["taxa_entrega"] = taxa

        fluxo["pedido_info"]["valor_total_final"] = subtotal + taxa

        # Processar resposta de confirmação (Se o usuário já estiver respondendo à confirmação)
        if etapa == "finalizar_confirma_tudo" and msg_lower:
            if msg_lower in ["sim", "s", "ok", "confirmo", "pode", "isso", "correto"]:
                from storage.pedidos import confirmar_pedido_db
                confirmar_pedido_db(user_phone, fluxo)
                fluxo["carrinho_atual"] = []
                fluxo["etapa"] = None
                fluxo["pedido_info"] = {}
                salvar_pedido_completo_db(user_phone, fluxo)
                return create_response("✅ *PEDIDO CONFIRMADO!* 🎉\n\nSeu pedido foi enviado para a cozinha.\nQual a forma de pagamento? (Pix, Dinheiro ou Cartão)")
            
            elif msg_lower in ["alterar", "mudar", "trocar", "não", "nao"]:
                fluxo["etapa"] = "finalizar_escolher_tipo"
                return create_response("Voltei! 🛵 Como deseja receber seu pedido?\n\n1. *Entrega* 🛵\n2. *Retirada* (Buscar no local) 🥡")

        # Gerar Texto de Confirmação (Primeira vez entrando na etapa)
        endereco_txt = ""
        if tipo_entrega == "Entrega":
            cad = fluxo.get("cadastro", {})
            endereco_txt = f"\n📍 *Endereço:* {cad.get('rua')}\n(Taxa: R$ {taxa:.2f})"
        else: endereco_txt = "\n🥡 *Retirada no Balcão*"

        return create_response(f"📝 *Confirma o pedido?*\n\n{resumo_carrinho(fluxo)}\n{endereco_txt}\n\nDigite *SIM* para confirmar ou *ALTERAR* para mudar o tipo de entrega.")

    return create_response("Erro no fluxo de finalização.")


# ==============================================================================
# 4. CARRINHO E STORIES
# ==============================================================================

def iniciar_remocao(fluxo):
    carrinho = fluxo.get("carrinho_atual", [])
    if not carrinho: return create_response(MSG_CARRINHO_VAZIO)
    
    lista_txt = ""
    for i, item in enumerate(carrinho):
        desc = f"{item.get('nome')} ({item.get('quantidade')}x)"
        if item.get("tipo") == "pizza":
            desc = f"Pizza {item.get('tamanho')} - {', '.join(item.get('sabores', []))}"
        if item.get("adicionais"): desc += f" + {item['adicionais']}"
        lista_txt += f"*{i + 1}* - {desc}\n"
        
    fluxo["etapa"] = "remover_item"
    return create_response(MSG_MENU_REMOVER.format(lista=lista_txt))

def processar_remocao(fluxo, user_message, user_phone):
    msg = (user_message or "").strip().lower()
    if msg in ["cancelar", "voltar", "sair"]:
        fluxo["etapa"] = None
        return create_response(f"Operação cancelada.\n\n{resumo_carrinho(fluxo)}\n\n{gerar_opcoes_carrinho()}")
        
    if not msg.isdigit(): return create_response(MSG_DIGITE_APENAS_NUMERO)
    
    idx = int(msg) - 1
    carrinho = fluxo.get("carrinho_atual", [])
    if 0 <= idx < len(carrinho):
        item_removido = carrinho.pop(idx)
        salvar_pedido_completo_db(user_phone, fluxo)
        fluxo["etapa"] = None
        return create_response(MSG_ITEM_REMOVIDO_SUCESSO.format(nome=item_removido.get("nome") or "Item", carrinho=resumo_carrinho(fluxo), opcoes=gerar_opcoes_carrinho()))
    else:
        return create_response(MSG_NUMERO_INVALIDO_TENTE_NOVAMENTE)

def tratar_pedido_story(fluxo, user_message, user_phone):
    msg = (user_message or "").strip().lower()
    destaques = []
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT id, categoria, produto_id, nome_produto FROM destaques_dia ORDER BY id").fetchall()
            destaques = [dict(r) for r in rows]
    except Exception: pass

    if not destaques: return create_response("Poxa, hoje não temos destaques cadastrados nos stories. Mas você pode pedir pelo cardápio! Digite 'cardápio'.")

    if fluxo.get("etapa") == "escolher_item_story" and msg.isdigit():
        idx = int(msg) - 1
        if 0 <= idx < len(destaques):
            escolha = destaques[idx]
            fluxo["etapa"] = None
            preco = 0.0
            item_ativo = True
            try:
                tabela = get_nome_tabela(escolha["categoria"])
                with get_db_connection() as conn:
                    row = conn.execute(f"SELECT preco, disponivel FROM {tabela} WHERE id=?", (escolha["produto_id"],)).fetchone()
                    if row:
                        preco, disp = row
                        if disp == 0: item_ativo = False
            except Exception: pass
            
            if not item_ativo: return create_response(f"Poxa! O item *{escolha['nome_produto']}* acabou de esgotar. 😔")
            
            fluxo.setdefault("carrinho_atual", []).append({
                "tipo": escolha["categoria"], "nome": escolha["nome_produto"],
                "preco": preco, "quantidade": 1, "id": escolha["produto_id"],
            })
            salvar_pedido_completo_db(user_phone, fluxo)
            return create_response(f"✅ Adicionei *{escolha['nome_produto']}* ao seu pedido!\n\n{resumo_carrinho(fluxo)}\n\n{gerar_opcoes_carrinho()}")
        else:
            return create_response("⚠️ Número inválido. Digite o número correspondente à foto.")

    fluxo["etapa"] = "escolher_item_story"
    lista_msg = ["Vi que você gostou dos nossos stories! 😍\nQual dessas delícias você quer? (Digite o número)\n"]
    for i, item in enumerate(destaques): lista_msg.append(f"*{i + 1}*. {item['nome_produto']}")
    return create_response("\n".join(lista_msg))