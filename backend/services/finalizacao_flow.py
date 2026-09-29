# services/finalizacao_flow.py

import re
import unicodedata
import sqlite3
import difflib

from core.ia import analisar_intencao
from storage import (
    create_response,
    get_db_connection,
    buscar_cliente_completo,
    obter_taxa_entrega,
    salvar_pedido_completo_db,
    confirmar_pedido_db,
    get_chave_pix_ativa,
    resumo_carrinho,
)

try:
    from automate import disparar_gatilho_site
except ImportError:
    def disparar_gatilho_site(id): pass


# ==============================================================================
# 1. FUNÇÕES AUXILIARES DE BANCO DE DADOS E FORMATAÇÃO
# ==============================================================================

def clean_text(txt):
    if not txt: return ""
    return unicodedata.normalize('NFKD', str(txt)).encode('ASCII', 'ignore').decode('utf-8').lower().strip()

def obter_config_valor_minimo():
    try:
        with get_db_connection() as conn:
            row = conn.execute("SELECT valor FROM configuracoes WHERE chave='valor_minimo_pedido'").fetchone()
            if row and row[0]: return float(str(row[0]).replace(",", "."))
    except Exception: pass
    return 0.0

def obter_formas_pagamento_wpp():
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT nome, pede_detalhe, pergunta_detalhe FROM formas_pagamento WHERE disponivel_wpp = 1 ORDER BY nome ASC").fetchall()
            if rows: return [dict(r) for r in rows]
    except Exception: pass
    
    return [
        {"nome": "Dinheiro", "pede_detalhe": 1, "pergunta_detalhe": "Vai precisar de troco para quanto? (Ou digite 'sem troco')"},
        {"nome": "Pix", "pede_detalhe": 0, "pergunta_detalhe": ""},
        {"nome": "Cartão de Crédito", "pede_detalhe": 0, "pergunta_detalhe": ""},
        {"nome": "Cartão de Débito", "pede_detalhe": 0, "pergunta_detalhe": ""}
    ]

def obter_modos_envio_wpp():
    padrao = [
        {"nome": "Entrega", "pede_endereco": 1, "pede_horario": 0, "pergunta_horario": "", "pede_pagamento": 1, "pede_obs_final": 1, "pergunta_obs_final": "📝 Alguma observação geral para o pedido? (ex: interfone estragado)\nDigite a observação ou 'não'."},
        {"nome": "Retirada", "pede_endereco": 0, "pede_horario": 1, "pergunta_horario": "Que horas você vem buscar?", "pede_pagamento": 1, "pede_obs_final": 1, "pergunta_obs_final": "📝 Alguma observação geral para o pedido?\nDigite a observação ou 'não'."}
    ]
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM modos_envio WHERE disponivel_wpp = 1 ORDER BY id").fetchall()
            if rows: return [dict(r) for r in rows]
    except Exception: pass
    return padrao

def obter_total_geral(fluxo_atual):
    carrinho = fluxo_atual.get("carrinho_atual", [])
    total_prod = sum(float(item.get("preco", 0.0)) * int(item.get("quantidade", 1)) for item in carrinho)
    tx = float(fluxo_atual.get("pedido_info", {}).get("taxa_entrega", 0.0))
    return total_prod + tx

def processar_dados_endereco_inteligente(fluxo, dados_ia):
    cad = fluxo.setdefault("cadastro", {})
    if dados_ia.get("rua"): cad["rua"] = dados_ia["rua"]
    
    raw_num = str(dados_ia.get("numero") or "").lower()
    num_match = re.search(r"(\d+)", raw_num) 
    if num_match:
        cad["numero_casa"] = num_match.group(1)
        sobra = raw_num.replace(num_match.group(1), "").replace("numero", "").replace("casa", "").strip()
        if sobra and not dados_ia.get("apartamento"): dados_ia["apartamento"] = sobra
    else:
        cad["numero_casa"] = raw_num if raw_num else cad.get("numero_casa")

    if dados_ia.get("bairro"): cad["bairro"] = dados_ia["bairro"]

    partes_ref = []
    if dados_ia.get("apartamento"): partes_ref.append(f"Apto {dados_ia['apartamento']}")
    if dados_ia.get("bloco"): partes_ref.append(f"Bloco {dados_ia['bloco']}")
    if dados_ia.get("ponto_referencia"): partes_ref.append(dados_ia["ponto_referencia"])
    
    if partes_ref: cad["ponto_referencia"] = " - ".join(partes_ref).replace("Apto Apto", "Apto")
    fluxo["cadastro"] = cad


# ==============================================================================
# 2. HANDLERS DE ESTADO DO ROTEADOR DE FINALIZAÇÃO
# ==============================================================================

def lidar_escolha_tipo_entrega(fluxo, msg_l):
    modos = fluxo.get("modos_envio_cache", obter_modos_envio_wpp())
    escolha = msg_l.strip()
    modo_selecionado = None

    if escolha.isdigit() and 1 <= int(escolha) <= len(modos):
        modo_selecionado = modos[int(escolha)-1]
    else:
        for m in modos:
            if clean_text(m["nome"]) in clean_text(escolha):
                modo_selecionado = m
                break
                
    if not modo_selecionado:
        return create_response("⚠️ Opção inválida. Digite o número correspondente.")
        
    fluxo.setdefault("pedido_info", {})["tipo_entrega"] = modo_selecionado["nome"]
    return _avancar_fluxo_finalizacao(fluxo)


def lidar_coleta_endereco_manual(fluxo, user_message, etapa_atual):
    val = user_message.strip()
    cad = fluxo.setdefault("cadastro", {})

    if len(val.split()) > 3 and etapa_atual == "finalizar_endereco_rua":
        analise = analisar_intencao(val)
        dados = analise.get("endereco_completo") or analise.get("dados_entrega") or {}
        if dados and (dados.get("rua") or dados.get("bairro")):
            processar_dados_endereco_inteligente(fluxo, dados)
            return _avancar_fluxo_finalizacao(fluxo)

    if etapa_atual == "finalizar_endereco_rua":
        cad["rua"] = val
    elif etapa_atual == "finalizar_endereco_numero":
        match_n = re.search(r"^(\d+)\s*(.*)", val, re.IGNORECASE)
        if match_n:
            cad["numero_casa"] = match_n.group(1)
            if match_n.group(2): cad["ponto_referencia"] = f"{match_n.group(2)} | {cad.get('ponto_referencia', '')}".strip(" |")
        else: cad["numero_casa"] = val
    elif etapa_atual == "finalizar_endereco_bairro":
        cad["bairro"] = val
    elif etapa_atual == "finalizar_endereco_referencia":
        if clean_text(val) not in ["nao", "n", "nada", "sem"]:
            cad["ponto_referencia"] = val

    fluxo["etapa"] = None
    return _avancar_fluxo_finalizacao(fluxo)


def lidar_confirmacao_endereco(fluxo, msg_limpa):
    if msg_limpa in ["sim", "s", "correto", "ok", "isso"]:
        fluxo["pedido_info"]["endereco_confirmado"] = True
        fluxo["etapa"] = None
        return _avancar_fluxo_finalizacao(fluxo)
        
    elif msg_limpa in ["nao", "n", "errado", "alterar", "mudar"]:
        fluxo["pedido_info"]["endereco_confirmado"] = False
        fluxo["cadastro"] = {k: None for k in ["rua", "numero_casa", "bairro", "ponto_referencia"]}
        fluxo["etapa"] = "finalizar_endereco_rua" 
        return create_response("Entendi! Vamos corrigir.\n\nQual o endereço completo ou apenas o nome da **Rua**?")
        
    return create_response("⚠️ Não entendi. O endereço está correto? Responda *Sim* ou *Não*.")


def lidar_exibir_formas_pagamento(fluxo):
    formas = obter_formas_pagamento_wpp()
    txt = "💲 *Como será a forma de pagamento?*\n\n"
    for i, f in enumerate(formas): txt += f"*{i+1}* - {f['nome']}\n"
    fluxo["etapa"] = "finalizar_pagamento"
    return create_response(txt)


def lidar_escolha_pagamento(fluxo, msg_limpa):
    formas_db = obter_formas_pagamento_wpp()
    metodos = []
    
    if "cartao" in msg_limpa and not "credito" in msg_limpa and not "debito" in msg_limpa:
        opcoes_cartao = [f["nome"] for f in formas_db if "cartao" in clean_text(f["nome"])]
        if len(opcoes_cartao) > 1:
            str_opcoes = " ou ".join([f"*{o}*" for o in opcoes_cartao])
            return create_response(f"💳 Você vai usar {str_opcoes}?")

    for f in formas_db:
        n_limpo = clean_text(f["nome"])
        if (n_limpo == "dinheiro" and any(t in msg_limpa for t in ["dinheiro", "troco", "nota"])) or \
           (n_limpo == "pix" and "pix" in msg_limpa) or \
           ("credito" in n_limpo and "credito" in msg_limpa) or \
           ("debito" in n_limpo and "debito" in msg_limpa) or \
           (n_limpo in msg_limpa):
            if f["nome"] not in metodos: metodos.append(f["nome"])

    if not metodos:
        for i, f in enumerate(formas_db, 1):
            if str(i) in msg_limpa.split() or str(i) == msg_limpa.strip():
                metodos.append(f["nome"])
                break

    if not metodos:
        return create_response("⚠️ Opção inválida.\n\n" + "\n".join([f"{i+1}. *{f['nome']}*" for i, f in enumerate(formas_db)]))

    fluxo["pedido_info"]["forma_pagamento"] = " + ".join(metodos)

    if len(metodos) > 1:
        fluxo["pgto_lista_pendente"] = metodos
        fluxo["pgto_buffer_detalhes"] = []
        fluxo["pgto_metodo_atual"] = None
        fluxo["etapa"] = "finalizar_pgto_multiplo"
        return _avancar_fluxo_finalizacao(fluxo)

    pgto_final = metodos[0]
    forma_selecionada = next((f for f in formas_db if f["nome"] == pgto_final), None)

    if forma_selecionada and forma_selecionada["pede_detalhe"] == 1:
        fluxo["etapa"] = "finalizar_detalhe_pgto"
        return create_response(forma_selecionada.get("pergunta_detalhe") or f"Qual a observação para {pgto_final}?")
    else:
        fluxo["pedido_info"]["detalhe_pagamento_chat"] = "N/A"
        fluxo["etapa"] = "finalizar_obs_extra"
        return _avancar_fluxo_finalizacao(fluxo)


def gerar_recibo_final(fluxo, pedido_id, info, detalhe_chat, troco_msg):
    carrinho_txt = resumo_carrinho(fluxo)
    resumo_final = (
        f"✅ *PEDIDO #{pedido_id} CONFIRMADO!* 🎉\n"
        f"Já estamos preparando. Aguarde!\n\n"
        f"📄 *Resumo do Pedido # {pedido_id}:*\n"
        f"{carrinho_txt}\n--------------------\n"
        f"🛵 Tipo: *{info.get('tipo_entrega', 'Entrega')}*\n"
    )

    if info.get("tipo_entrega") in ["Retirada", "Comer no Local"]:
        resumo_final += f"⏰ Horário: {info.get('horario', 'Logo')}\n"
    else:
        resumo_final += "📍 Endereço confirmado\n"

    resumo_final += f"💲 Pagamento: {info.get('forma_pagamento', 'Dinheiro')}"
    if detalhe_chat: resumo_final += f"\n📋 Detalhes Pgt: {detalhe_chat}"
    if troco_msg: resumo_final += troco_msg

    if "Pix" in info.get("forma_pagamento", ""):
        pix_dados = get_chave_pix_ativa()
        if pix_dados: resumo_final += f"\n\n🔑 Chave PIX: *{pix_dados['chave']}*\n(Envie o comprovante aqui)"

    resumo_final += f"\n\n💰 *TOTAL: R$ {obter_total_geral(fluxo):.2f}*"
    return resumo_final


# ==============================================================================
# 3. ORQUESTRADOR PRINCIPAL (ROUTER)
# ==============================================================================

def _avancar_fluxo_finalizacao(fluxo):
    info = fluxo.setdefault("pedido_info", {})
    tipo_normalizado = info.get("tipo_entrega")
    cad = fluxo.get("cadastro", {})

    # Resgata as configurações do Modo de Envio escolhido
    modos_config = fluxo.get("modos_envio_cache", obter_modos_envio_wpp())
    modo_atual = next((m for m in modos_config if clean_text(m["nome"]) == clean_text(tipo_normalizado)), {})
    
    # 1. Gate de Endereço
    if modo_atual.get("pede_endereco") == 1 and not info.get("endereco_confirmado"):
        if not cad.get("rua"):
            fluxo["etapa"] = "finalizar_endereco_rua"
            return create_response("📍 Qual o nome da sua *Rua*?")
        if not cad.get("numero_casa"):
            fluxo["etapa"] = "finalizar_endereco_numero"
            return create_response("🏠 Qual o *Número* da casa?")
        if not cad.get("bairro"):
            fluxo["etapa"] = "finalizar_endereco_bairro"
            return create_response("🏘️ Qual o seu *Bairro*?")
        if not cad.get("ponto_referencia"):
            fluxo["etapa"] = "finalizar_endereco_referencia"
            return create_response("📍 Algum *Ponto de Referência*?")

        taxa = obter_taxa_entrega(cad.get("bairro"))
        info["taxa_entrega"] = taxa
        fluxo["etapa"] = "finalizar_confirma_endereco"
        
        endereco_resumo = f"{cad['rua']}, {cad['numero_casa']} - {cad['bairro']}\nRef: {cad['ponto_referencia']}"
        return create_response(f"📍 *Confirmando endereço:*\n\n{endereco_resumo}\n(Taxa: R$ {taxa:.2f})\n\nEstá correto? (Sim / Não)")

    # 2. Gate de Horário
    if modo_atual.get("pede_horario") == 1 and not info.get("horario"):
        fluxo["etapa"] = "finalizar_horario"
        pergunta = modo_atual.get("pergunta_horario") or "Para qual horário deseja agendar?"
        return create_response(pergunta)

    # 3. Gate de Pagamento (Com Bypass Inteligente)
    if not info.get("forma_pagamento"):
        if modo_atual.get("pede_pagamento") == 0:
            # Bypass! Lança pagamento oculto e avança
            info["forma_pagamento"] = "Dinheiro"
            info["detalhe_pagamento_chat"] = "sem troco"
        else:
            return lidar_exibir_formas_pagamento(fluxo)

    # 4. Gate de Detalhe de Pagamento
    if "detalhe_pagamento_chat" not in info:
        forma_atual = info.get("forma_pagamento", "")
        formas_db = obter_formas_pagamento_wpp()
        forma_config = next((f for f in formas_db if f["nome"] == forma_atual), None)
        
        if forma_config and forma_config.get("pede_detalhe") == 1:
            fluxo["etapa"] = "finalizar_detalhe_pgto"
            pergunta = forma_config.get("pergunta_detalhe") or f"Qual a observação para {forma_atual}?"
            return create_response(pergunta)
        else:
            info["detalhe_pagamento_chat"] = "N/A" # Ignora e avança direto

    # 5. Gate de Observação Extra (Com Bypass e Pergunta Dinâmica)
    if not fluxo.get("obs_extra_perguntada"):
        fluxo["obs_extra_perguntada"] = True
        if modo_atual.get("pede_obs_final") == 0:
            info["observacoes_gerais"] = ""
        else:
            fluxo["etapa"] = "finalizar_obs_extra"
            pergunta_obs = modo_atual.get("pergunta_obs_final") or "📝 Alguma observação geral para o pedido?\nDigite a observação ou 'não'."
            return create_response(pergunta_obs)

    # 6. Fim do Fluxo
    fluxo["telefone_cliente"] = fluxo.get("telefone_cliente", "")
    salvar_pedido_completo_db(fluxo["telefone_cliente"], fluxo)
    
    detalhe_chat = info.get("detalhe_pagamento_chat", "")
    if detalhe_chat == "N/A": detalhe_chat = ""
    troco_msg = ""
    
    total_final_calc = obter_total_geral(fluxo)
    forma_unica = info.get("forma_pagamento", "Dinheiro")
    
    # Esconde a forma de pagamento do painel se o Bypass estiver ativo
    if modo_atual.get("pede_pagamento") == 0:
        info["detalhe_pagamento"] = "A Combinar"
    else:
        info["detalhe_pagamento"] = f"{forma_unica}: R$ {total_final_calc:.2f}"
        if detalhe_chat and clean_text(detalhe_chat) not in ["sem troco", "nao", "n", "ok"]:
            info["detalhe_pagamento"] += f" ({detalhe_chat})"
            
        if "dinheiro" in clean_text(forma_unica) and "troco para" in clean_text(detalhe_chat):
            match = re.search(r"(\d+(\.\d+)?)", detalhe_chat.replace(",", "."))
            if match:
                val_entregue = float(match.group(1))
                if val_entregue > total_final_calc:
                    troco_msg = f"\n💵 *Troco: R$ {(val_entregue - total_final_calc):.2f}*"

    pedido_id = confirmar_pedido_db(fluxo["telefone_cliente"], fluxo)
    try: disparar_gatilho_site(pedido_id)
    except Exception: pass

    # Modifica o recibo para esconder informações de pagamento se o Bypass estiver ativo
    if modo_atual.get("pede_pagamento") == 0:
        info["forma_pagamento"] = "A Combinar" # Para não mostrar "Dinheiro" no recibo do cliente
    
    recibo_texto_final = gerar_recibo_final(fluxo, pedido_id, info, detalhe_chat if modo_atual.get("pede_pagamento") != 0 else "", troco_msg)

    for k in ["etapa", "obs_extra_perguntada", "em_finalizacao", "pgto_lista_pendente", "pgto_buffer_detalhes"]:
        fluxo.pop(k, None)
    fluxo["carrinho_atual"] = []
    fluxo["pedido_info"] = {}

    return create_response(recibo_texto_final)


def finalizar_pedido(fluxo, user_message, user_phone):
    fluxo["telefone_cliente"] = user_phone
    user_message = user_message or ""
    msg_limpa = clean_text(user_message)
    etapa = fluxo.get("etapa")

    if msg_limpa in ["finalizar", "fechar", "concluir", "encerrar", "cancelar"]:
        fluxo["etapa"] = None
        fluxo.setdefault("pedido_info", {})["endereco_confirmado"] = False
        etapa = None

    carrinho = fluxo.get("carrinho_atual", [])
    if not carrinho: return create_response("Seu carrinho está vazio.")

    total_prods = sum(float(i.get("preco", 0.0)) * int(i.get("quantidade", 1)) for i in carrinho)
    minimo = obter_config_valor_minimo()
    etapas_avancadas = ["finalizar_confirma_endereco", "finalizar_horario", "finalizar_pagamento", "finalizar_detalhe_pgto", "finalizar_obs_extra"]
    
    if total_prods < minimo and etapa not in etapas_avancadas:
        fluxo["etapa"] = None
        return create_response(f"🚫 *Pedido Mínimo não atingido!*\nMínimo: R$ {minimo:.2f}\nFaltam: R$ {(minimo - total_prods):.2f}\n\nPor favor, adicione mais itens.")

    # Roteador Inteligente: Se a IA já marcou o tipo de entrega, salta a pergunta.
    if not etapa or etapa == "finalizar_pedido":
        if fluxo.get("pedido_info", {}).get("tipo_entrega"):
            return _avancar_fluxo_finalizacao(fluxo)

        modos = obter_modos_envio_wpp()
        fluxo["modos_envio_cache"] = modos
        txt = "📦 *Como deseja receber seu pedido?*\n\n"
        for i, m in enumerate(modos): txt += f"*{i+1}* - {m['nome']}\n"
        fluxo["etapa"] = "finalizar_tipo_entrega" 
        return create_response(txt)

    if etapa == "finalizar_tipo_entrega": return lidar_escolha_tipo_entrega(fluxo, user_message)
    elif etapa in ["finalizar_endereco_rua", "finalizar_endereco_numero", "finalizar_endereco_bairro", "finalizar_endereco_referencia"]: return lidar_coleta_endereco_manual(fluxo, user_message, etapa)
    elif etapa == "finalizar_confirma_endereco": return lidar_confirmacao_endereco(fluxo, msg_limpa)
    elif etapa == "finalizar_horario":
        fluxo.setdefault("pedido_info", {})["horario"] = user_message.strip()
        fluxo["etapa"] = None
        return _avancar_fluxo_finalizacao(fluxo)
    elif etapa == "finalizar_pagamento": return lidar_escolha_pagamento(fluxo, msg_limpa)
    elif etapa == "finalizar_detalhe_pgto":
        fluxo.setdefault("pedido_info", {})["detalhe_pagamento_chat"] = user_message.strip()
        fluxo["etapa"] = None
        return _avancar_fluxo_finalizacao(fluxo)
    elif etapa == "finalizar_obs_extra":
        if msg_limpa not in ["nao", "n", "nop", "sem"]: fluxo.setdefault("pedido_info", {})["observacoes_gerais"] = user_message.strip()
        fluxo["etapa"] = None
        return _avancar_fluxo_finalizacao(fluxo)

    return _avancar_fluxo_finalizacao(fluxo)