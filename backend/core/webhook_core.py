# core/webhook_core.py

import logging
import requests
import os
import re
import json
import time
import asyncio
import sqlite3
import inspect
from dotenv import load_dotenv

from .ia import analisar_intencao
from .messages import (
    MSG_CARDAPIO_SAUDACAO_NOME,
    MSG_CARDAPIO_SAUDACAO_PADRAO,
    CARDAPIO_LINK,
    AUDIO_MSG,
    MSG_FILA_ESTIMATIVA,
    MSG_LOJA_FECHADA,
    MSG_SISTEMA_REINICIADO,
    MSG_OPERACAO_CANCELADA,
    MSG_VINCULO_SUCESSO,
    MSG_CARRINHO_LIMPO_SUCESSO,
    MSG_RESPOSTA_CHAVE_PIX,
    MSG_ERRO_CHAVE_PIX,
    MSG_COMPROVANTE_RECEBIDO,
    MSG_ENCERRAMENTO_NEUTRO,
    MSG_ROBO_PAUSADO_ATENDENTE,
    MSG_PEDIR_MOTIVO_CANCELAMENTO,
    MSG_VERIFICAR_PEDIDO_EXTERNO,
    MSG_TEMPO_ENTREGA_RESP,
    MSG_FILA_VAZIA,
    MSG_VER_CARDAPIO_LINK,
    MSG_AGRADECIMENTO_FINAL,
    MSG_REPETIR_PEDIDO_SUCESSO,
    MSG_REPETIR_PEDIDO_ERRO,
    MSG_NAO_ENTENDI_GENERICO,
)
from storage import (
    carrinhos,
    obter_tempo_entrega_config,
    contar_pedidos_na_frente,
    copiar_ultimo_pedido,
    desativar_chat_e_notificar,
    BAIRROS_VALIDOS,
    buscar_cliente_completo,
    buscar_cliente_por_telefone,
    resumo_carrinho,
    verificar_chat_geral_ativo,
    verificar_chat_cliente_ativo,
    verificar_loja_aberta,
    create_response,
    remover_acentos,
    get_db_connection,
    get_chave_pix_ativa,
)
from storage.configuracoes import (
    obter_texto_horario_dinamico,
    verificar_restricao_cadastrados,
    obter_categorias_ativas,
    gerar_menu_opcoes,
    gerar_opcoes_carrinho,
    get_nome_tabela,
    obter_config_valor,
    obter_mensagem_bairros_formatada,
    criar_reserva_db,
    obter_todas_categorias_db,
)
from services import (
    processar_cadastro,
    iniciar_atualizacao_endereco,
    processar_remocao,
    iniciar_remocao,
    processar_extras,
    processar_pedido_complexo,
    finalizar_pedido,
    processar_tamanho_lote,
)
from services.reserva_flow import processar_reserva
from services.pedido_flow import (
    tratar_pedido_story,
    processar_resolucao_ambiguidade,
    processar_pizza,
)
from services.complex_flow import processar_sabor_restante
from services.cadastro_flow import validar_bairro
from storage.pedidos import abandonar_pedido_aberto

load_dotenv()

EVOLUTION_BASE_URL = os.getenv("EVOLUTION_BASE_URL")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE")
EVOLUTION_APIKEY = os.getenv("EVOLUTION_APIKEY")

HORA_INICIO_SISTEMA = int(time.time())
SYSTEM_NUMBER_CACHE = {}
message_buffers = {}
last_msg_timestamps = {}
BUFFER_DELAY = 2.0
MODO_PRODUCAO = False
PREFIXO_TESTE = "!"


# ==============================================================================
# 0. HELPER DE MIGRAÇÃO MULTI-TENANT E SINCRONIZAÇÃO
# ==============================================================================
def call_with_tenant(func, *args, **kwargs):
    tenant_id = kwargs.get('usuario_id')
    try:
        sig = inspect.signature(func)
        if 'loja_id' in sig.parameters or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
            kwargs['loja_id'] = tenant_id
            
        if 'usuario_id' not in sig.parameters and not any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
            kwargs.pop('usuario_id', None)
    except Exception:
        kwargs.pop('usuario_id', None)
    return func(*args, **kwargs)

def sincronizar_loja_id_pedido(user_phone, loja_id):
    try:
        with get_db_connection() as conn:
            conn.execute('''
                UPDATE pedidos 
                SET loja_id = ? 
                WHERE id = (SELECT id FROM pedidos WHERE cliente_telefone = ? ORDER BY id DESC LIMIT 1)
                AND status IN ('ABERTO', 'EM_PREPARO')
                AND (loja_id IS NULL OR loja_id != ?)
            ''', (loja_id, user_phone, loja_id))
            
            conn.execute('''
                UPDATE pedido_outros_itens 
                SET loja_id = ? 
                WHERE pedido_id = (SELECT id FROM pedidos WHERE cliente_telefone = ? ORDER BY id DESC LIMIT 1)
                AND (loja_id IS NULL OR loja_id != ?)
            ''', (loja_id, user_phone, loja_id))
            conn.commit()
    except Exception as e:
        logging.error(f"Erro ao sincronizar loja_id do pedido: {e}")

def descobrir_loja_por_instancia(instance_name):
    if not instance_name: return 1
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            try:
                r = conn.execute("SELECT id FROM lojas WHERE evolution_instance_name = ?", (instance_name,)).fetchone()
                if r: return r["id"]
            except Exception: pass
            
            try:
                r = conn.execute("SELECT loja_id FROM usuarios WHERE instance_name = ? OR evolution_instance = ?", (instance_name, instance_name)).fetchone()
                if r and r["loja_id"]: return r["loja_id"]
            except Exception: pass
            
            try:
                r = conn.execute("SELECT loja_id FROM configuracoes WHERE chave IN ('evolution_instance', 'instancia') AND valor = ?", (instance_name,)).fetchone()
                if r and r["loja_id"]: return r["loja_id"]
            except Exception: pass
            
            try:
                r = conn.execute("SELECT loja_id FROM usuarios WHERE loja_id IS NOT NULL ORDER BY id ASC LIMIT 1").fetchone()
                if r and r["loja_id"]: return r["loja_id"]
            except Exception: pass
    except Exception: pass
    return 1

# ==============================================================================
# 1. FUNÇÕES UTILITÁRIAS DE MENSAGENS (HELPERS)
# ==============================================================================

def find_context_info_recursively(data):
    if isinstance(data, dict):
        if "contextInfo" in data: return data["contextInfo"]
        for key, value in data.items():
            resultado = find_context_info_recursively(value)
            if resultado: return resultado
    elif isinstance(data, list):
        for item in data:
            resultado = find_context_info_recursively(item)
            if resultado: return resultado
    return None

def desembrulhar_mensagem(message_obj):
    if not isinstance(message_obj, dict): return {}
    # FIX: Removido 'messageContextInfo' da lista. Ele não é um wrapper de mensagem, e sim um metadado irmão.
    wrappers = ["ephemeralMessage", "viewOnceMessage", "documentWithCaptionMessage"]
    current_msg = message_obj
    for _ in range(4):
        found_wrapper = False
        for key in wrappers:
            if key in current_msg:
                content = current_msg[key]
                if isinstance(content, dict):
                    if "message" in content: current_msg = content["message"]
                    else: current_msg = content
                    found_wrapper = True
                break
        if not found_wrapper: break
    return current_msg

def extrair_mensagem_e_tipo(message_obj):
    if not isinstance(message_obj, dict): return "", "unknown"
    msg_real = desembrulhar_mensagem(message_obj)
    msg_text = ""
    msg_type = "text"

    if "conversation" in msg_real: 
        msg_text = msg_real["conversation"]
    elif "extendedTextMessage" in msg_real: 
        msg_text = msg_real["extendedTextMessage"].get("text", "")
    elif "imageMessage" in msg_real:
        msg_type = "image"
        msg_text = msg_real["imageMessage"].get("caption", "")
        if not msg_text: msg_text = "Foto enviada"
    elif "documentMessage" in msg_real:
        msg_type = "document"
        doc = msg_real["documentMessage"]
        filename = doc.get("fileName", "")
        title = doc.get("title", "")
        caption = doc.get("caption", "")
        parts = []
        if caption: parts.append(caption)
        if filename: parts.append(filename)
        if title and title != filename: parts.append(title)
        msg_text = " ".join(parts).strip()
        if not msg_text: msg_text = "Arquivo enviado"
    elif "audioMessage" in msg_real:
        msg_type = "audio"
        msg_text = "Audio enviado"
        
    if not msg_text:
        if "textMessage" in msg_real:
            msg_text = msg_real["textMessage"].get("text", "")
        elif "text" in msg_real:
            msg_text = msg_real["text"]
            
        if not msg_text and msg_type == "text":
            for chave, valor in msg_real.items():
                if isinstance(valor, str) and len(valor.strip()) > 0:
                    msg_text = valor
                    break

    if not msg_text and msg_type == "text":
        logging.warning(f"⚠️ MENSAGEM VAZIA! Estrutura do payload da Evolution: {json.dumps(message_obj)}")

    return str(msg_text), msg_type

def get_text_from_message(message_obj):
    t, _ = extrair_mensagem_e_tipo(message_obj)
    return t

def get_system_owner_jid_sync(instance_name):
    global SYSTEM_NUMBER_CACHE
    if not instance_name: return None
    if instance_name in SYSTEM_NUMBER_CACHE: return SYSTEM_NUMBER_CACHE[instance_name]
    try:
        url = f"{EVOLUTION_BASE_URL}/instance/fetchInstances"
        headers = {"apikey": EVOLUTION_APIKEY}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            instances = response.json()
            if isinstance(instances, dict): instances = [instances]
            
            for inst in instances:
                name = inst.get("instance", {}).get("instanceName") or inst.get("name")
                if name == instance_name:
                    owner = inst.get("owner") or inst.get("instance", {}).get("owner")
                    if owner:
                        SYSTEM_NUMBER_CACHE[instance_name] = owner
                        return owner
    except Exception as e:
        logging.error(f"Erro ao buscar número do sistema para {instance_name}: {e}")
    return None

async def enviar_evolution(jid, text, instance_name=None):
    if not text: return
    if hasattr(text, "body"):
        try: text = text.body.decode("utf-8")
        except Exception: text = str(text)

    text_str = str(text)
    if "<Message>" in text_str:
        match = re.search(r"<Message>(.*?)</Message>", text_str, re.DOTALL)
        if match: text_str = match.group(1).strip()

    inst = instance_name or EVOLUTION_INSTANCE
    url = f"{EVOLUTION_BASE_URL}/message/sendText/{inst}"
    numero_payload = jid
    if "@" not in jid:
        if len(jid) > 16: numero_payload = f"{jid}@lid"
        else: numero_payload = f"{jid}@s.whatsapp.net"

    headers = {"apikey": EVOLUTION_APIKEY, "Content-Type": "application/json"}
    payload = {"number": numero_payload, "text": text_str}

    try: requests.post(url, json=payload, headers=headers)
    except Exception as e: logging.error(f"❌ Erro Crítico no Envio: {e}")

# ==============================================================================
# 2. PIPELINE DE INTELIGÊNCIA E ROTEAMENTO
# ==============================================================================

async def interceptar_comandos_globais(fluxo, user_message, msg_lower, msg_clean, user_phone, usuario_id=1):
    if msg_lower == "reiniciar":
        call_with_tenant(abandonar_pedido_aberto, user_phone, usuario_id=usuario_id)
        fluxo.clear()
        fluxo.update({"etapa": None, "carrinho_atual": [], "item_em_construcao": {}, "itens_com_perguntas_pendentes": [], "itens_ambiguos_pendentes": [], "pedido_info": {}, "usuario_id": usuario_id, "loja_id": usuario_id})
        return create_response(MSG_SISTEMA_REINICIADO.format(menu=call_with_tenant(gerar_menu_opcoes, usuario_id=usuario_id)))

    if msg_lower in ["cancelar", "menu", "voltar", "sair", "inicio"]:
        fluxo["etapa"] = None
        fluxo["item_em_construcao"] = {}
        fluxo["itens_com_perguntas_pendentes"] = []
        fluxo["itens_ambiguos_pendentes"] = []
        msg_retorno = MSG_OPERACAO_CANCELADA.format(menu=call_with_tenant(gerar_menu_opcoes, usuario_id=usuario_id)) if fluxo.get("carrinho_atual") else call_with_tenant(gerar_menu_opcoes, usuario_id=usuario_id)
        return create_response(msg_retorno)

    if msg_lower == "vincular": return create_response(MSG_VINCULO_SUCESSO.format(telefone=user_phone))
    if msg_lower in ["carrinho", "ver carrinho", "resumo", "meu pedido", "ver meu pedido"]:
        carrinho_txt = resumo_carrinho(fluxo)
        return create_response(f"🛒 *SEU CARRINHO:*\n\n{carrinho_txt}\n\n{call_with_tenant(gerar_opcoes_carrinho, usuario_id=usuario_id)}")

    if msg_lower in ["limpar", "limpar carrinho", "esvaziar carrinho"]:
        fluxo["carrinho_atual"] = []
        fluxo["etapa"] = None
        return create_response(MSG_CARRINHO_LIMPO_SUCESSO)

    if msg_lower in ["remover item", "remover produto", "excluir item", "tirar item"] or (msg_lower.startswith("remover") and len(msg_lower) < 15):
        return iniciar_remocao(fluxo)

    termos_pedir_pix = ["chave pix", "qual o pix", "me manda o pix", "passa o pix", "conta para deposito", "dados bancarios", "qual a chave", "pagar no pix", "pagar pelo pix", "pagar via pix", "deixar pago", "pago de uma vez", "pagar agora", "tem pix", "aceita pix", "paga no pix"]
    quer_pagar_pix = any(t in msg_lower for t in termos_pedir_pix) or ("pix" in msg_lower and any(v in msg_lower for v in ["fazer", "mandar", "enviar", "pagar", "deixar"]))

    if quer_pagar_pix and len(user_message) < 350:
        termos_pedido_forte = ["pizza", "pitzza", "piza", "lanche", "burguer", "hamburguer", "sabor", "metade", "recheada", "borda", "coca", "fanta", "guarana", "refrigerante", "entrega", "reservar", "entregar"]
        contexto_passado = any(t in msg_lower for t in ["fiz", "fui", "pedi", "chegasse", "deixar"])
        possivel_novo_pedido = (any(t in msg_lower for t in termos_pedido_forte) and not contexto_passado)

        if possivel_novo_pedido:
            logging.info("⚠️ Detectado Pedido junto com Pix. Passando para IA processar...")
        else:
            dados_pix = call_with_tenant(get_chave_pix_ativa, usuario_id=usuario_id)
            msg_pix = MSG_RESPOSTA_CHAVE_PIX.format(chave=dados_pix["chave"], titular=dados_pix["titular"], banco=dados_pix["banco"]) if dados_pix else MSG_ERRO_CHAVE_PIX
            return create_response(msg_pix)

    termos_agradecimento = ["obrigado", "obg", "valeu", "agradecido", "tks", "thanks", "vlw"]
    termos_saudacao = ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "opa", "eai", "eae"]
    eh_agradecimento = any(re.search(rf"\b{t}\b", msg_lower) for t in termos_agradecimento)
    eh_saudacao = any(re.search(rf"\b{t}\b", msg_lower) for t in termos_saudacao)
    termos_pedido_no_inicio = ["quero", "gostaria", "vê", "ve ", "me vê", "manda", "pizza", "lanche", "hamburguer", "coca", "fanta", "sabor"]
    tem_pedido_junto = any(t in msg_lower for t in termos_pedido_no_inicio)

    if eh_agradecimento and len(user_message) < 50: 
        msg = call_with_tenant(obter_config_valor, "msg_agradecimento", usuario_id=usuario_id) or MSG_AGRADECIMENTO_FINAL
        return create_response(msg)

    if eh_saudacao and len(user_message) < 50 and not tem_pedido_junto:
        nome_cliente = call_with_tenant(buscar_cliente_por_telefone, user_phone, usuario_id=usuario_id)
        link = CARDAPIO_LINK
        db_saudacao_nome = call_with_tenant(obter_config_valor, "msg_saudacao_nome", usuario_id=usuario_id) or MSG_CARDAPIO_SAUDACAO_NOME
        db_saudacao_padrao = call_with_tenant(obter_config_valor, "msg_saudacao_padrao", usuario_id=usuario_id) or MSG_CARDAPIO_SAUDACAO_PADRAO
        msg = db_saudacao_nome.replace("{nome}", nome_cliente).replace("{link}", link) if nome_cliente else db_saudacao_padrao.replace("{link}", link)
        return create_response(msg)

    termos_neutros = ["vamos analisar", "e retorno", "te falo", "vejo e aviso", "analiso e retorno", "qualquer coisa chamo", "já retorno", "vou ver", "vou pensar"]
    if any(t in msg_lower for t in termos_neutros): return create_response(MSG_ENCERRAMENTO_NEUTRO)

    termos_atendente = ["pausar", "parar robo", "parar robô", "falar com atendente", "falar atendente", "humano", "atendente", "suporte", "fiz um pedido", "fiz o pedido", "já pedi", "acabei de pedir", "eu pedi", "meu pedido", "esqueci de", "esqueci do", "esqueci da", "esqueci o", "pode acrescentar", "acrescentar no pedido", "adicionar no pedido", "adicionar também", "coloca também", "manda também", "trocar o", "mudar o", "alterar", "interfone", "campainha", "avise quando", "me liga", "bater no portão", "não está funcionando"]
    eh_caso_atendente = any(t in msg_lower for t in termos_atendente)
    if eh_caso_atendente and not any(t in msg_lower for t in ["quanto tempo", "qual a demora", "previsao", "previsão", "pix", "reservar", "reserva"]):
        logging.info(f"🛑 Interceptado Pós-Pedido/Aviso: '{user_message}' -> Redirecionado para Humano.")
        call_with_tenant(desativar_chat_e_notificar, user_phone, user_message, usuario_id=usuario_id)
        return create_response(MSG_ROBO_PAUSADO_ATENDENTE)

    check_tempo = ["quanto tempo", "qual a demora", "previsao", "previsão", "quanto leva", "demora muito"]
    if ("tempo" in msg_lower and "entrega" in msg_lower) or any(t in msg_lower for t in check_tempo):
        msg = call_with_tenant(obter_config_valor, "msg_tempo_entrega", usuario_id=usuario_id) or MSG_TEMPO_ENTREGA_RESP
        return create_response(msg.replace("{tempo}", call_with_tenant(obter_tempo_entrega_config, usuario_id=usuario_id)))

    check_horario = ["que horas", "qual horario", "horario de funcionamento", "loja aberta", "esta aberto", "estao abertos", "abre que horas", "fecha que horas", "funcionamento"]
    if any(t in msg_clean for t in check_horario): return create_response(call_with_tenant(obter_texto_horario_dinamico, usuario_id=usuario_id))

    check_areas = ["taxa", "valor da entrega", "custo da entrega", "onde entrega", "faz entrega", "bairros atendidos", "quais bairros", "entregam em", "entrega em"]
    if any(t in msg_clean for t in check_areas): return create_response(call_with_tenant(obter_mensagem_bairros_formatada, usuario_id=usuario_id))

    return None

async def rotear_por_etapa(fluxo, user_message, msg_lower, msg_clean, user_phone, etapa_atual, usuario_id=1):
    if etapa_atual == "finalizar_endereco_manual":
        endereco_simulado = {}
        if "," in user_message:
            parts = [p.strip() for p in user_message.split(",")]
            if len(parts) >= 1: endereco_simulado["rua"] = parts[0]
            if len(parts) >= 2: endereco_simulado["numero"] = parts[1]
            if len(parts) >= 3: endereco_simulado["bairro"] = parts[2]
        else:
            analise_manual = analisar_intencao(user_message)
            end_ia = analise_manual.get("endereco_completo", {})
            bairro_match = next((b for b in BAIRROS_VALIDOS if b.lower() == msg_lower), None)

            if bairro_match:
                endereco_simulado["bairro"] = bairro_match
                if end_ia.get("rua", "").lower() == msg_lower: endereco_simulado["rua"] = None
            else:
                if end_ia.get("rua"): endereco_simulado["rua"] = end_ia["rua"]
                if end_ia.get("bairro"): endereco_simulado["bairro"] = end_ia["bairro"]

            if end_ia.get("numero"): endereco_simulado["numero"] = end_ia["numero"]
            if end_ia.get("ponto_referencia"): endereco_simulado["ponto_referencia"] = end_ia["ponto_referencia"]

            if not endereco_simulado.get("rua") and not endereco_simulado.get("bairro") and not endereco_simulado.get("numero"):
                endereco_simulado["rua"] = user_message

        analise_fake = {"endereco_completo": endereco_simulado}
        response_text = call_with_tenant(iniciar_atualizacao_endereco, fluxo, analise_fake, user_phone, user_message_raw=user_message, usuario_id=usuario_id)

        if "," in user_message:
            parts = [p.strip() for p in user_message.split(",")]
            if len(parts) < 3: fluxo["cadastro"]["bairro"] = fluxo["cadastro"].get("bairro")
            if len(parts) < 4: fluxo["cadastro"]["ponto_referencia"] = fluxo["cadastro"].get("ponto_referencia")

        if fluxo.get("em_finalizacao"):
            fluxo["etapa"] = "finalizar_confirma_endereco"
            response_text = call_with_tenant(finalizar_pedido, fluxo, "retomar", user_phone, usuario_id=usuario_id)
        return response_text

    if etapa_atual:
        ETAPAS_EXTRAS = ["selecionar_da_lista", "definir_quantidade_pre_adicionais", "definir_quantidade_extra", "processar_perguntas_db", "observacao_extra_final", "escolher_variacao_complexa", "processar_adicionais_complexos", "confirmar_corte_sabor", "escolher_borda_pizza_extra", "adicionar_sabores_extras", "perguntar_quantidade_final"]

        if etapa_atual == "escolher_tamanho_lote": return call_with_tenant(processar_tamanho_lote, fluxo, user_message, user_phone, usuario_id=usuario_id)
        elif etapa_atual == "pizza_flow": return call_with_tenant(processar_pizza, fluxo, user_message, {}, user_phone, "continuar_pizza", usuario_id=usuario_id)
        elif etapa_atual == "pedir_sabor_restante": return call_with_tenant(processar_sabor_restante, fluxo, user_message, user_phone, usuario_id=usuario_id)
        elif etapa_atual.startswith("escolher_") or etapa_atual in ETAPAS_EXTRAS: return call_with_tenant(processar_extras, fluxo, user_message, {}, user_phone, "continuar_extra", usuario_id=usuario_id)
        elif etapa_atual == "processar_resolucao_ambiguidade": return call_with_tenant(processar_resolucao_ambiguidade, fluxo, user_message, user_phone, usuario_id=usuario_id)
        elif etapa_atual == "cadastro_dinamico" or etapa_atual.startswith("cadastro_"): return call_with_tenant(processar_cadastro, fluxo, user_message, user_phone, usuario_id=usuario_id)
        elif etapa_atual.startswith("finalizar_"): return call_with_tenant(finalizar_pedido, fluxo, user_message, user_phone, usuario_id=usuario_id)
        elif etapa_atual == "remover_item": return call_with_tenant(processar_remocao, fluxo, user_message, user_phone, usuario_id=usuario_id)
        elif etapa_atual == "escolher_item_story": return call_with_tenant(tratar_pedido_story, fluxo, user_message, user_phone, usuario_id=usuario_id)
        elif etapa_atual.startswith("reserva_"):
            nome_cli = fluxo.get("cadastro", {}).get("nome") or "Cliente"
            return call_with_tenant(processar_reserva, fluxo, user_message, user_phone, nome_cli, usuario_id=usuario_id)

    eh_finalizacao = any(t == msg_lower for t in ["finalizar", "fechar", "encerrar"])
    if eh_finalizacao:
        from services.cadastro_flow import iniciar_fluxo_cadastro
        fluxo["em_finalizacao"] = True
        cad = fluxo.get("cadastro", {})
        msg_cabecalho = "👋 Para finalizar seu pedido, preciso de alguns dados." if not cad.get("nome") else "📋 Vamos confirmar alguns dados para a entrega."
        
        next_pergunta = call_with_tenant(iniciar_fluxo_cadastro, fluxo, user_phone, msg_cabecalho=msg_cabecalho, usuario_id=usuario_id)
        if next_pergunta: return create_response(next_pergunta)
        
        return call_with_tenant(finalizar_pedido, fluxo, user_message, user_phone, usuario_id=usuario_id)

    return None

async def roteador_de_intencoes(fluxo, intencao, analise, user_message, msg_lower, msg_clean, user_phone, usuario_id=1):
    if intencao == "status_pedido": intencao = "ver_status_pedido"

    if intencao in ["ver_cardapio", "fazer_pedido", "produto_generico", "nao_entendi"] and not analise.get("itens"):
        msg_clean_core = remover_acentos(msg_lower)
        from storage.produtos import buscar_produto_db
        prods_db = call_with_tenant(buscar_produto_db, msg_clean_core, usuario_id=usuario_id)
        produto_alvo = None

        if prods_db:
            candidatos = prods_db if isinstance(prods_db, list) else [prods_db]
            for p in candidatos:
                n_p = remover_acentos(p["nome"].lower())
                if n_p == msg_clean_core or (msg_clean_core in n_p and len(msg_clean_core) > 3):
                    produto_alvo = p
                    break

        if produto_alvo:
            logging.info(f"✨ Auto-Correção: '{user_message}' -> 1x {produto_alvo['nome']}")
            intencao = "fazer_pedido"
            analise["itens"] = [{
                "nome": produto_alvo["nome"],
                "quantidade": 1,
                "observacao": "",
                "categoria": produto_alvo.get("categoria") or "diversos",
            }]
        else:
            from services.extras_flow import get_keywords_categoria
            import difflib
            keywords = call_with_tenant(get_keywords_categoria, usuario_id=usuario_id)
            cat_match_key = None

            if msg_clean_core in keywords: cat_match_key = keywords[msg_clean_core]

            if not cat_match_key:
                palavras = msg_clean_core.split()
                if len(palavras) <= 5:
                    for p in palavras:
                        if len(p) < 3: continue
                        if p in keywords:
                            cat_match_key = keywords[p]
                            break
                        matches = difflib.get_close_matches(p, list(keywords.keys()), n=1, cutoff=0.85)
                        if matches:
                            cat_match_key = keywords[matches[0]]
                            break

            if cat_match_key:
                intencao = cat_match_key
                logging.info(f"🔄 Sobrescrita de Intenção (Categoria Detectada): '{user_message}' -> {intencao}")

    if "cancelar pedido" in msg_lower: intencao = "cancelar_pedido"
    elif any(t in msg_lower for t in ["marcar mesa", "agendar mesa", "reservar mesa", "reserva de mesa", "quero uma mesa", "reserva para", "reservar para", "lugares para"]): intencao = "fazer_reserva"
    elif ("reserva" in msg_lower or "agendar" in msg_lower) and re.search(r"\d+\s*(pessoas|gente|lugares)", msg_lower): intencao = "fazer_reserva"
    elif ("reservar" in msg_lower or "reserva" in msg_lower) and not any(t in msg_lower for t in ["entregar", "entrega", "motoboy", "delivery"]): intencao = "fazer_reserva"
    elif msg_lower in ["reiniciar", "inicio", "menu"]: intencao = "reiniciar_sistema"
    elif not intencao and not (re.match(r"^\s*\d+\s+\w+", msg_lower) or re.search(r"\n\s*\d+\s+\w+", msg_lower)):
        try:
            msg_clean_core = remover_acentos(msg_lower)
            from services.extras_flow import get_keywords_categoria
            keywords = call_with_tenant(get_keywords_categoria, usuario_id=usuario_id)
            sorted_keywords = sorted(keywords.keys(), key=len, reverse=True)
            for kw in sorted_keywords:
                is_explicit = (f"ver {kw}" in msg_clean_core or f"cardapio {kw}" in msg_clean_core or f"lista {kw}" in msg_clean_core or f"quero {kw}" == msg_clean_core)
                is_exact = kw == msg_clean_core
                if is_exact or is_explicit:
                    intencao = keywords[kw]
                    break

            if not intencao:
                cats_db = call_with_tenant(obter_todas_categorias_db, usuario_id=usuario_id)
                candidatos = []
                for cat in cats_db:
                    if not cat.get("nome"): continue
                    nome_norm = remover_acentos(cat["nome"].lower())
                    id_str = str(cat["id"]).lower()

                    if msg_clean == nome_norm or msg_clean == id_str:
                        intencao = f"listar_{cat['id']}"
                        break

                    palavras_nome = nome_norm.replace("/", " ").split()
                    termos_ver = [f"ver {nome_norm}", f"cardapio {nome_norm}", f"lista de {nome_norm}"]

                    if msg_clean in palavras_nome or any(t in msg_clean for t in termos_ver):
                        if len(msg_clean) > 3: candidatos.append(cat)

                if not intencao and candidatos:
                    candidatos.sort(key=lambda x: (0 if "/" in x["nome"] else 1, 0 if remover_acentos(x["nome"].lower()).startswith(msg_clean) else 1, len(x["nome"])))
                    intencao = f"listar_{candidatos[0]['id']}"
        except Exception as e: logging.error(f"Erro na busca de categorias: {e}")

    if not intencao:
        if (any(t in msg_lower for t in ["ver bebidas", "lista de bebidas", "cardapio bebidas"]) or msg_lower == "bebidas"): intencao = "listar_bebidas"
        ultimo = fluxo.get("ultimo_item_pesquisado")
        if ultimo and len(user_message) < 15:
            user_message = f"{ultimo} {user_message}"
            fluxo.pop("ultimo_item_pesquisado", None)
            analise = analisar_intencao(user_message)
            intencao = analise.get("intencao")

    if not intencao: intencao = "nao_entendi"
    logging.info(f"🧠 Intenção Final Resolvida: {intencao} | JSON: {analise}")

    termos_pedir_pix = ["chave pix", "qual o pix", "me manda o pix", "passa o pix", "conta para deposito", "dados bancarios", "qual a chave", "pagar no pix", "pagar pelo pix", "pagar via pix", "deixar pago", "pago de uma vez", "pagar agora", "tem pix", "aceita pix", "paga no pix"]
    quer_pagar_pix = any(t in msg_lower for t in termos_pedir_pix) or ("pix" in msg_lower and any(v in msg_lower for v in ["fazer", "mandar", "enviar", "pagar", "deixar"]))

    if quer_pagar_pix:
        keywords_payment = ["pagar", "deixar pago", "fazer o pix", "manda o pix", "chave"]
        is_payment_intent = any(k in msg_lower for k in keywords_payment)

        if is_payment_intent and not analise.get("itens"): intencao = "perguntar_pix"
        elif (intencao in ["nao_entendi", "produto_generico", "ver_status_pedido", "falar_atendente"] or 
             (intencao == "pedido_complexo" and not analise.get("itens")) or 
             (intencao == "fazer_pedido" and not analise.get("itens"))):
            intencao = "perguntar_pix"

    cats_ativas = call_with_tenant(obter_categorias_ativas, usuario_id=usuario_id)
    if intencao == "pedir_pizza": intencao = "listar_pizza"

    if intencao.startswith("listar_"):
        cat_alvo = intencao.replace("listar_", "")
        if not cats_ativas.get(cat_alvo, True): intencao = "ignorar_categoria_desativada"

    response_text = None

    if intencao == "reiniciar_sistema":
        call_with_tenant(abandonar_pedido_aberto, user_phone, usuario_id=usuario_id)
        fluxo.clear()
        fluxo.update({"etapa": None, "carrinho_atual": [], "usuario_id": usuario_id, "loja_id": usuario_id})
        response_text = create_response(MSG_SISTEMA_REINICIADO.format(menu=call_with_tenant(gerar_menu_opcoes, usuario_id=usuario_id)))

    elif intencao == "fazer_reserva":
        modo = call_with_tenant(obter_config_valor, "modo_reserva", "humano", usuario_id=usuario_id)
        if modo == "humano":
            call_with_tenant(desativar_chat_e_notificar, user_phone, f"Solicitação de Reserva: {user_message}", usuario_id=usuario_id)
            response_text = create_response(MSG_ROBO_PAUSADO_ATENDENTE)
        else:
            dados = analise.get("dados_reserva", {})
            data_res = dados.get("data")
            hora_res = dados.get("hora")
            pessoas = dados.get("pessoas", 0)

            if not data_res or not hora_res:
                match_data = re.search(r"(\d{1,2}/\d{1,2})", user_message)
                if match_data: data_res = match_data.group(1)
                match_hora = re.search(r"(\d{1,2}[:h]\d{0,2})", user_message)
                if match_hora: hora_res = match_hora.group(1)
                if not pessoas:
                    msg_temp = re.sub(r"\d{1,2}/\d{1,2}", "", user_message)
                    msg_temp = re.sub(r"\d{1,2}[:h]\d{0,2}", "", msg_temp)
                    match_pessoas = re.search(r"\b(\d{1,2})\b", msg_temp)
                    if match_pessoas:
                        try: pessoas = int(match_pessoas.group(1))
                        except Exception: pass

            if data_res and hora_res and pessoas:
                nome_cli = call_with_tenant(buscar_cliente_por_telefone, user_phone, usuario_id=usuario_id) or "Cliente"
                sucesso = call_with_tenant(criar_reserva_db, data_res, hora_res, pessoas, nome_cli, user_phone, user_message, usuario_id=usuario_id)
                if sucesso:
                    try:
                        with get_db_connection() as conn:
                            msg_notif = f"📅 NOVA RESERVA AUTO:\n{data_res} às {hora_res} ({pessoas}p)\nMsg: {user_message}"
                            conn.execute("""INSERT INTO notificacoes (cliente_telefone, mensagem, lida, data_hora, tipo, loja_id) VALUES (?, ?, 0, datetime('now', 'localtime'), 'RESERVA', ?)""", (user_phone, usuario_id))
                            conn.commit()
                    except Exception as e: logging.error(f"Erro ao notificar reserva: {e}")
                    response_text = create_response(f"✅ Reserva PRÉ-AGENDADA!\n\n📅 {data_res} às {hora_res}\n👥 {pessoas} pessoas\n\nAguarde a confirmação.")
                else:
                    call_with_tenant(desativar_chat_e_notificar, user_phone, "Erro reserva auto", usuario_id=usuario_id)
                    response_text = create_response("❌ Erro no sistema ao agendar. Um atendente irá confirmar.")
            else:
                fluxo["etapa"] = "reserva_inicio"
                nome_cli = fluxo.get("cadastro", {}).get("nome") or "Cliente"
                response_text = call_with_tenant(processar_reserva, fluxo, "", user_phone, nome_cli, usuario_id=usuario_id)

    elif intencao == "ignorar_categoria_desativada":
        response_text = create_response("Desculpe, não estamos trabalhando com essa categoria no momento.")

    termos_story = ["quero esse", "quero um desse", "me vê esse", "me ve esse", "quero o da foto", "quero a da foto", "quero a pizza da foto", "quero o lanche da foto", "tem esse", "tem desse", "quero este", "gostei desse", "da foto", "na foto"]
    eh_pedido_story = (any(t in msg_lower for t in termos_story) or (intencao == "pedir_pizza_da_foto"))

    if eh_pedido_story and not response_text:
        response_text = call_with_tenant(tratar_pedido_story, fluxo, user_message, user_phone, usuario_id=usuario_id)

    if not response_text:
        if intencao == "verificar_pedido_externo":
            call_with_tenant(desativar_chat_e_notificar, user_phone, f"Consulta pedido externo: {user_message}", usuario_id=usuario_id)
            response_text = create_response(MSG_VERIFICAR_PEDIDO_EXTERNO)
        elif intencao == "falar_atendente":
            call_with_tenant(desativar_chat_e_notificar, user_phone, user_message, usuario_id=usuario_id)
            response_text = create_response(MSG_ROBO_PAUSADO_ATENDENTE)
        elif intencao == "perguntar_pix":
            dados_pix = call_with_tenant(get_chave_pix_ativa, usuario_id=usuario_id)
            if dados_pix: msg_pix = MSG_RESPOSTA_CHAVE_PIX.format(chave=dados_pix["chave"], titular=dados_pix["titular"], banco=dados_pix["banco"])
            else: msg_pix = MSG_ERRO_CHAVE_PIX
            response_text = create_response(msg_pix)
        elif intencao == "agradecimento":
            msg = call_with_tenant(obter_config_valor, "msg_agradecimento", usuario_id=usuario_id) or MSG_AGRADECIMENTO_FINAL
            response_text = create_response(msg)
        elif intencao == "cancelar_pedido":
            fluxo["etapa"] = "aguardando_motivo_cancelamento"
            response_text = create_response(MSG_PEDIR_MOTIVO_CANCELAMENTO)
        
        elif intencao == "pedido_complexo" or (analise.get("itens") and len(analise["itens"]) > 0):
            end_ia = analise.get("endereco_completo", {})
            if end_ia:
                info = fluxo.setdefault("pedido_info", {})
                if end_ia.get("tipo_entrega"): info["tipo_entrega"] = end_ia["tipo_entrega"]
                if end_ia.get("horario"): info["horario"] = end_ia["horario"]
                
                cad = fluxo.setdefault("cadastro", {})
                
                if end_ia.get("rua"):
                    cad["rua"] = end_ia["rua"]
                    cad["numero_casa"] = end_ia.get("numero")
                    
                    if end_ia.get("bairro"):
                        b_val = call_with_tenant(validar_bairro, end_ia["bairro"], usuario_id=usuario_id)
                        cad["bairro"] = b_val if b_val else None
                    else:
                        cad["bairro"] = None  
                        
                    cad["ponto_referencia"] = "" 
                
                ref_parts = []
                if end_ia.get("apartamento"): ref_parts.append(f"Apto {end_ia['apartamento']}")
                if end_ia.get("bloco"): ref_parts.append(f"Bloco {end_ia['bloco']}")
                if end_ia.get("ponto_referencia"): ref_parts.append(end_ia["ponto_referencia"])
                
                if ref_parts:
                    nova_ref = ", ".join(ref_parts)
                    if not end_ia.get("rua") and cad.get("ponto_referencia"):
                        if nova_ref not in cad["ponto_referencia"]:
                            cad["ponto_referencia"] += f", {nova_ref}"
                    else:
                        cad["ponto_referencia"] = nova_ref

            pag_ia = analise.get("dados_pagamento", {})
            if pag_ia and pag_ia.get("forma_pagamento"):
                fluxo.setdefault("pedido_info", {})["forma_pagamento"] = pag_ia["forma_pagamento"]
                if pag_ia.get("detalhe_pagamento"):
                    fluxo.setdefault("pedido_info", {})["detalhe_pagamento_chat"] = pag_ia["detalhe_pagamento"]

            if not analise.get("itens"):
                response_text = create_response(f"✅ Opção de Entrega/Retirada e Pagamento atualizada.\n\n{call_with_tenant(gerar_menu_opcoes, usuario_id=usuario_id)}")
            else:
                response_text = call_with_tenant(processar_pedido_complexo, fluxo, analise, user_phone, user_message=user_message, usuario_id=usuario_id)

        elif intencao.startswith("listar_") or intencao == "pedir_pizza":
            response_text = call_with_tenant(processar_extras, fluxo, user_message, analise, user_phone, intencao, usuario_id=usuario_id)
        elif intencao == "perguntar_tempo":
            msg = call_with_tenant(obter_config_valor, "msg_tempo_entrega", usuario_id=usuario_id) or MSG_TEMPO_ENTREGA_RESP
            response_text = create_response(msg.replace("{tempo}", call_with_tenant(obter_tempo_entrega_config, usuario_id=usuario_id)))
        elif intencao == "perguntar_areas_entrega":
            response_text = create_response(call_with_tenant(obter_mensagem_bairros_formatada, usuario_id=usuario_id))
        elif intencao == "perguntar_horario":
            response_text = create_response(call_with_tenant(obter_texto_horario_dinamico, usuario_id=usuario_id))
        elif intencao == "fazer_pedido":
            response_text = create_response(call_with_tenant(gerar_menu_opcoes, usuario_id=usuario_id))
        elif intencao.startswith("pedir_"):
            if analise.get("itens"): response_text = call_with_tenant(processar_pedido_complexo, fluxo, analise, user_phone, user_message=user_message, usuario_id=usuario_id)
            else: response_text = call_with_tenant(processar_extras, fluxo, user_message, analise, user_phone, intencao, usuario_id=usuario_id)
        elif intencao == "saudacao":
            nome = fluxo.get("cadastro", {}).get("nome") or call_with_tenant(buscar_cliente_por_telefone, user_phone, usuario_id=usuario_id)
            link = CARDAPIO_LINK
            db_saudacao_nome = call_with_tenant(obter_config_valor, "msg_saudacao_nome", usuario_id=usuario_id) or MSG_CARDAPIO_SAUDACAO_NOME
            db_saudacao_padrao = call_with_tenant(obter_config_valor, "msg_saudacao_padrao", usuario_id=usuario_id) or MSG_CARDAPIO_SAUDACAO_PADRAO
            if nome: response_text = create_response(db_saudacao_nome.replace("{nome}", nome).replace("{link}", link))
            else: response_text = create_response(db_saudacao_padrao.replace("{link}", link))
        elif intencao == "perguntar_fila":
            qtd = call_with_tenant(contar_pedidos_na_frente, user_phone, usuario_id=usuario_id)
            if qtd == 0:
                msg = call_with_tenant(obter_config_valor, "msg_fila_vazia", usuario_id=usuario_id) or MSG_FILA_VAZIA
                response_text = create_response(msg)
            else:
                tempo_min = qtd * 20
                tempo_max = tempo_min + 10  
                msg = call_with_tenant(obter_config_valor, "msg_fila_estimativa", usuario_id=usuario_id) or MSG_FILA_ESTIMATIVA
                msg_pronta = (msg.replace("{fila}", str(qtd))
                                 .replace("{min}", str(tempo_min))
                                 .replace("{max}", str(tempo_max)))
                
                response_text = create_response(msg_pronta)
        elif intencao == "perguntar_precos" or intencao == "ver_cardapio":
            template_link = call_with_tenant(obter_config_valor, "msg_texto_cardapio", usuario_id=usuario_id) or MSG_VER_CARDAPIO_LINK
            response_text = create_response(template_link.format(link=CARDAPIO_LINK))
        elif intencao == "repetir_pedido":
            novo_carrinho = call_with_tenant(copiar_ultimo_pedido, user_phone, usuario_id=usuario_id)
            if novo_carrinho:
                fluxo["carrinho_atual"] = novo_carrinho
                fluxo["etapa"] = None
                response_text = create_response(MSG_REPETIR_PEDIDO_SUCESSO.format(carrinho=resumo_carrinho(fluxo)))
            else:
                response_text = create_response(MSG_REPETIR_PEDIDO_ERRO)
        elif intencao == "ver_status_pedido":
            from storage import listar_pedidos_ativos_cliente
            pedidos = call_with_tenant(listar_pedidos_ativos_cliente, user_phone, usuario_id=usuario_id)
            if not pedidos: response_text = create_response("Você não tem pedidos abertos no momento.")
            else:
                txt = "📋 *Seus Pedidos:*\\n"
                for p in pedidos: txt += f"- Pedido #{p['id']}: *{p['status'].upper()}*\\n"
                response_text = create_response(txt)
        else:
            response_text = create_response(MSG_NAO_ENTENDI_GENERICO.format(menu=call_with_tenant(gerar_menu_opcoes, usuario_id=usuario_id)))

    return response_text


# ==============================================================================
# 3. FUNÇÃO PRINCIPAL (HOOK RECEIVER - PIPELINE)
# ==============================================================================

async def whatsapp_webhook_core(data: dict):
    user_message = ""
    user_phone = ""
    media_type = ""
    context_info = None

    # EXTRAÇÃO DA INSTÂNCIA MULTI-TENANT
    instance_name = data.get("instance")
    if not instance_name and "instance" in data.get("data", {}):
        instance_name = data["data"]["instance"]

    await asyncio.to_thread(get_system_owner_jid_sync, instance_name)

    # Identifica corretamente qual Loja/Usuario deve processar o pedido
    usuario_id = descobrir_loja_por_instancia(instance_name)

    try:
        msg_data = data.get("data", {})
        
        # FIX 1: Verificação de mensagem antiga agora possui tolerância e envia log.
        try:
            message_timestamp = msg_data.get("messageTimestamp") or data.get("messageTimestamp")
            if message_timestamp:
                # Se o timestamp do WhatsApp for 5 minutos mais antigo que a hora em que a aplicação subiu
                if int(message_timestamp) < (HORA_INICIO_SISTEMA - 300):
                    logging.warning(f"⚠️ Ignorado (Msg Antiga). MsgTS: {message_timestamp}, Início: {HORA_INICIO_SISTEMA}")
                    return {"status": "ignored", "reason": "old_message"}
        except Exception as e: 
            pass

        key = msg_data.get("key", {})
        candidatos = [key.get("remoteJid"), key.get("remoteJidAlt"), key.get("participant"), msg_data.get("sender"), data.get("sender")]

        raw_msg = msg_data.get("message", {})
        if "extendedTextMessage" in raw_msg: context_info = raw_msg["extendedTextMessage"].get("contextInfo")
        if not context_info: context_info = find_context_info_recursively(msg_data)
        if context_info: candidatos.append(context_info.get("participant"))

        phone_candidato = next((c for c in candidatos if c and ("@s.whatsapp.net" in c or (c.isdigit() and 10 <= len(c) <= 15))), None)
        final_jid = phone_candidato if phone_candidato else key.get("remoteJid", "")
        
        user_message_raw, media_type = extrair_mensagem_e_tipo(raw_msg)
        
        # FIX 2: Adicionados logs nos descartes precoces 
        if not user_message_raw and media_type == "unknown": 
            logging.warning("⚠️ Ignorado: Mensagem vazia ou tipo desconhecido.")
            return {"status": "ignored"}
            
        if not final_jid: 
            logging.warning("⚠️ Ignorado: JID não encontrado.")
            return {"status": "ignored"}

        user_phone = final_jid.split("@")[0].split(":")[0]
        user_send_jid = final_jid
        should_process = False

        if key.get("fromMe", False):
            msg_raw_limpa = user_message_raw.strip()
            if msg_raw_limpa.startswith(PREFIXO_TESTE):
                should_process = True
                raw_command = msg_raw_limpa[len(PREFIXO_TESTE):].strip()
                match_impersonate = re.match(r"^(\d{10,15})\s+(.+)$", raw_command) 
                if match_impersonate:
                    user_phone, user_message = match_impersonate.group(1), match_impersonate.group(2)
                    user_send_jid = f"{user_phone}@s.whatsapp.net"
                else:
                    bot_jid = SYSTEM_NUMBER_CACHE.get(instance_name)
                    if bot_jid and final_jid != bot_jid:
                        logging.warning("⚠️ Ignorado (fromMe): Teste enviado em chat de cliente ao invés do próprio chat.")
                        return {"status": "ignored", "reason": "teste_sem_alvo_no_chat_do_cliente"}
                    user_message = raw_command
            else: 
                # Não logamos avisos intensos aqui, é apenas o uso normal de envio seu pelo WhatsApp web 
                return {"status": "ignored"}
        else:
            msg_raw_limpa = user_message_raw.strip()
            # FIX 3: Avisando exatamente por que bloqueamos clientes
            if MODO_PRODUCAO:
                should_process = True
                user_message = msg_raw_limpa if not msg_raw_limpa.startswith(PREFIXO_TESTE) else msg_raw_limpa[len(PREFIXO_TESTE):].strip()
            else:
                if msg_raw_limpa.startswith(PREFIXO_TESTE):
                    should_process = True
                    user_message = msg_raw_limpa[len(PREFIXO_TESTE):].strip()
                else: 
                    logging.warning(f"⚠️ Cliente Bloqueado: MODO_PRODUCAO é 'False' e msg veio sem prefixo ('{msg_raw_limpa}').")
                    return {"status": "ignored", "reason": "cliente_sem_prefixo_em_desenvolvimento"}

        if not should_process: 
            logging.warning("⚠️ Ignorado: should_process finalizou como False.")
            return {"status": "ignored"}

    except Exception as e:
        logging.error(f"❌ Erro crítico no payload: {e}")
        return {"status": "error"}

    # SEPARAÇÃO DE SESSÃO MULTI-TENANT (ID_TELEFONE)
    session_key = f"{usuario_id}_{user_phone}"

    if user_message and media_type == "text":
        if session_key not in message_buffers: message_buffers[session_key] = []
        message_buffers[session_key].append(user_message)
        current_ts = time.time()
        last_msg_timestamps[session_key] = current_ts
        await asyncio.sleep(BUFFER_DELAY)
        if last_msg_timestamps.get(session_key) != current_ts: 
            return {"status": "buffered"}

        user_message = " ".join([str(m) for m in message_buffers[session_key] if m is not None])
        message_buffers[session_key] = []

    user_message = user_message.replace("💯", "100").replace("💵", " dinheiro ").replace("💰", " dinheiro ").replace("💳", " cartão ")
    msg_lower = user_message.lower().strip()
    msg_clean = remover_acentos(msg_lower)

    logging.info(f"✅ Processando ID: {user_phone} (Loja {usuario_id}) | Msg: {user_message} | Tipo: {media_type}")

    termos_comprovante = ["comprovante", "pagamento", "pix", "transferencia", "doc", "pdf", "ta ai", "tá aí", "segue", "enviei", "pago"]
    eh_comprovante = False

    if media_type in ["document", "image"] and any(t in msg_lower for t in termos_comprovante): eh_comprovante = True
    elif media_type == "text" and context_info:
        quoted_real = desembrulhar_mensagem(context_info.get("quotedMessage", {}))
        if ("documentMessage" in quoted_real or "imageMessage" in quoted_real) and (any(t in msg_lower for t in termos_comprovante) or len(msg_lower) < 30):
            eh_comprovante = True
            user_message += " [Comprovante em Anexo Respondido]"

    if eh_comprovante:
        try:
            with get_db_connection() as conn:
                conn.execute("INSERT INTO notificacoes (tipo, mensagem, cliente_telefone, lida, data_hora, loja_id) VALUES ('COMPROVANTE', ?, ?, 0, datetime('now', 'localtime'), ?)", (f"🧾 COMPROVANTE: {user_message}", user_phone, usuario_id))
                conn.commit()
        except Exception: pass
        await enviar_evolution(user_send_jid, create_response(MSG_COMPROVANTE_RECEBIDO), instance_name)
        return {"status": "success"}

    if media_type == "image":
        call_with_tenant(desativar_chat_e_notificar, user_phone, "Foto recebida (sem identificação de comprovante)", usuario_id=usuario_id)
        await enviar_evolution(user_send_jid, create_response(MSG_ROBO_PAUSADO_ATENDENTE), instance_name)
        return {"status": "success"}
    elif media_type == "audio":
        await enviar_evolution(user_send_jid, create_response(AUDIO_MSG), instance_name)
        return {"status": "success"}

    if call_with_tenant(verificar_restricao_cadastrados, usuario_id=usuario_id) and not call_with_tenant(buscar_cliente_completo, user_phone, usuario_id=usuario_id):
        if call_with_tenant(obter_config_valor, "notif_restritos", "1", usuario_id=usuario_id) == "1":
            try:
                with get_db_connection() as conn:
                    conn.execute("INSERT INTO notificacoes (tipo, mensagem, cliente_telefone, lida, data_hora, loja_id) VALUES ('SUPORTE', ?, ?, 0, datetime('now', 'localtime'), ?)", (f"🔒 Não cadastrado: {user_message}", user_phone, usuario_id))
                    conn.commit()
            except Exception: pass
        return {"status": "ignored"}

    if not call_with_tenant(verificar_chat_geral_ativo, usuario_id=usuario_id): return {"status": "ignored"}

    chat_esta_ativo = call_with_tenant(verificar_chat_cliente_ativo, user_phone, usuario_id=usuario_id)
    if not chat_esta_ativo:
        if call_with_tenant(obter_config_valor, "notif_inativos", "1", usuario_id=usuario_id) == "1":
            try:
                with get_db_connection() as conn:
                    conn.execute("INSERT INTO notificacoes (cliente_telefone, mensagem, lida, data_hora, tipo, loja_id) VALUES (?, ?, 0, datetime('now', 'localtime'), 'SUPORTE', ?)", (user_phone, f"⚠️ INATIVO: {user_message}", usuario_id))
                    conn.commit()
            except Exception: pass
        return {"status": "ignored"}

    if not call_with_tenant(verificar_loja_aberta, usuario_id=usuario_id) and user_message.lower() != "abrir loja":
        await enviar_evolution(user_send_jid, create_response(MSG_LOJA_FECHADA.format(horario=call_with_tenant(obter_texto_horario_dinamico, usuario_id=usuario_id))), instance_name)
        return {"status": "success"}

    fluxo = carrinhos.get(session_key)
    if not fluxo:
        fluxo = {"etapa": None, "cadastro": {}, "carrinho_atual": [], "item_em_construcao": {}, "pedido_info": {}, "itens_com_perguntas_pendentes": [], "usuario_id": usuario_id, "loja_id": usuario_id, "instance_name": instance_name}
        try:
            with get_db_connection() as conn:
                conn.row_factory = sqlite3.Row
                conn.execute("CREATE TABLE IF NOT EXISTS sessoes_usuario (telefone TEXT, dados TEXT, updated_at DATETIME, loja_id INTEGER DEFAULT 1, PRIMARY KEY(telefone, loja_id))")
                row_sessao = conn.execute("SELECT dados FROM sessoes_usuario WHERE telefone = ? AND loja_id = ?", (user_phone, usuario_id)).fetchone()
                if row_sessao and row_sessao["dados"]:
                    sessao_db = json.loads(row_sessao["dados"])
                    if isinstance(sessao_db, dict): 
                        fluxo = sessao_db
                        fluxo["usuario_id"] = usuario_id
                        fluxo["loja_id"] = usuario_id
                        fluxo["instance_name"] = instance_name
                
                if not fluxo.get("carrinho_atual"):
                    row_pedido = conn.execute("SELECT id, tipo_entrega, forma_pagamento FROM pedidos WHERE cliente_telefone = ? AND status = 'ABERTO' AND loja_id = ? ORDER BY id DESC LIMIT 1", (user_phone, usuario_id)).fetchone()
                    if row_pedido:
                        fluxo["pedido_info"]["tipo_entrega"] = row_pedido["tipo_entrega"]
                        fluxo["pedido_info"]["forma_pagamento"] = row_pedido["forma_pagamento"]
                        itens_db = conn.execute("SELECT * FROM pedido_outros_itens WHERE pedido_id = ?", (row_pedido["id"],)).fetchall()
                        for e in itens_db:
                            nome_item = "Item"
                            obs_db = e["observacao"] or ""
                            match_nome = re.search(r"\[NM:(.*?)\]", obs_db)
                            if match_nome:
                                nome_item = match_nome.group(1)
                                obs_db = obs_db.replace(match_nome.group(0), "").strip()
                            fluxo["carrinho_atual"].append({"tipo": e["tipo"], "nome": nome_item, "preco": e["preco_vendido"], "quantidade": e["quantidade"], "observacao": obs_db, "adicionais": e["adicionais"] or ""})
        except Exception: pass
        carrinhos[session_key] = fluxo

    etapa_atual = fluxo.get("etapa") or ""

    if context_info and not eh_comprovante:
        quoted_text = get_text_from_message(context_info.get("quotedMessage", {}))
        if not quoted_text and "conversation" in context_info.get("quotedMessage", {}): quoted_text = context_info["quotedMessage"]["conversation"]
        if quoted_text:
            quoted_lower = quoted_text.lower()
            nova_etapa = None
            if any(t in quoted_lower for t in ["qual é a sua rua", "nome da rua"]): nova_etapa = "cadastro_rua"
            elif "número da casa" in quoted_lower: nova_etapa = "cadastro_numero"
            elif "qual é o bairro" in quoted_lower: nova_etapa = "cadastro_bairro"
            elif any(t in quoted_lower for t in ["ponto de referência", "qual o ponto"]): nova_etapa = "cadastro_ponto"
            elif "qual é o seu nome" in quoted_lower: nova_etapa = "cadastro_nome"
            elif "opção" in quoted_lower or "escolha" in quoted_lower: nova_etapa = "processar_perguntas_db"

            if nova_etapa: fluxo["etapa"] = nova_etapa
            if not nova_etapa:
                user_message = user_message.strip()
                if not (etapa_atual == "cadastro_dinamico" or etapa_atual.startswith("cadastro_")):
                    user_message = f"{quoted_text} {user_message}" if user_message else quoted_text
                    msg_lower = user_message.lower()
                    msg_clean = remover_acentos(msg_lower)

    if not etapa_atual.startswith("cadastro_"):
        cliente_db = call_with_tenant(buscar_cliente_completo, user_phone, usuario_id=usuario_id)
        if cliente_db:
            cad_atual = fluxo.setdefault("cadastro", {})
            for k, v in cliente_db.items():
                if k not in cad_atual: 
                    cad_atual[k] = v

    # PIPELINE 1: Comandos Globais
    resposta_global = await interceptar_comandos_globais(fluxo, user_message, msg_lower, msg_clean, user_phone, usuario_id)
    if resposta_global:
        carrinhos[session_key] = fluxo
        await enviar_evolution(user_send_jid, resposta_global, instance_name)
        sincronizar_loja_id_pedido(user_phone, usuario_id)
        return {"status": "success"}

    # PIPELINE 2: Roteador de Etapas
    resposta_etapa = await rotear_por_etapa(fluxo, user_message, msg_lower, msg_clean, user_phone, etapa_atual, usuario_id)
    if resposta_etapa:
        carrinhos[session_key] = fluxo
        await enviar_evolution(user_send_jid, resposta_etapa, instance_name)
        sincronizar_loja_id_pedido(user_phone, usuario_id)
        return {"status": "success"}

    # PIPELINE 3: Bypass e IA
    intencao_bypass = None
    try:
        from services.extras_flow import get_keywords_categoria
        keywords_cat = call_with_tenant(get_keywords_categoria, usuario_id=usuario_id)
        msg_clean_check = remover_acentos(msg_lower).strip()

        if msg_clean_check in keywords_cat:
            intencao_bypass = keywords_cat[msg_clean_check]
        else:
            prefixos_menu = ["ver ", "cardapio ", "lista ", "me ve ", "acessar ", "menu ", "quero ver "]
            if any(msg_clean_check.startswith(p) for p in prefixos_menu):
                for kw, action in keywords_cat.items():
                    if re.search(rf"\b{re.escape(kw)}\b", msg_clean_check):
                        intencao_bypass = action
                        break
    except Exception as e: logging.error(f"Erro Bypass Categoria: {e}")

    if intencao_bypass:
        resultado_ia = {"intencao": intencao_bypass, "itens": [], "confianca": 1.0, "bypass_local": True}
    else:
        resultado_ia = analisar_intencao(user_message)

    resposta_ia = await roteador_de_intencoes(
        fluxo, resultado_ia.get("intencao"), resultado_ia, user_message, msg_lower, msg_clean, user_phone, usuario_id
    )

    if resposta_ia:
        carrinhos[session_key] = fluxo
        await enviar_evolution(user_send_jid, resposta_ia, instance_name)
        sincronizar_loja_id_pedido(user_phone, usuario_id)
    
    return {"status": "success"}