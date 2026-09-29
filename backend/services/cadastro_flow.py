# services/cadastro_flow.py

import re
import difflib
import sqlite3
import logging
import traceback

from storage import (
    create_response,
    resumo_carrinho,
    salvar_cliente_no_banco,
    obter_taxa_entrega,
    remover_acentos,
    get_db_connection,
)
from storage.configuracoes import obter_lista_bairros_nomes
from core import (
    MSG_CADASTRO_FINALIZADO_CONTINUE,
    MSG_NOME_CURTO,
    MSG_ENDERECO_ATUALIZADO,
    MSG_CADASTRO_CONCLUIDO_HEADER,
)


# ==============================================================================
# 1. FUNÇÕES UTILITÁRIAS DE VALIDAÇÃO E TEXTO
# ==============================================================================

def validar_cpf_algoritmo(cpf_input):
    """Valida matematicamente um CPF brasileiro."""
    try:
        cpf = re.sub(r"\D", "", str(cpf_input))
        if len(cpf) != 11 or len(set(cpf)) == 1: return False
        soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
        resto = (soma * 10) % 11
        if (0 if resto == 10 else resto) != int(cpf[9]): return False
        soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
        resto = (soma * 10) % 11
        if (0 if resto == 10 else resto) != int(cpf[10]): return False
        return True
    except Exception:
        return False

def eh_apenas_complemento(texto):
    if not texto: return False
    palavras = texto.strip().split()
    if len(palavras) > 4: return False
    termos_complemento = ["apto", "apt", "bloco", "casa", "fundos", "frente", "lado", "loja", "sl", "sala", "terreo"]
    return any(t in texto.lower() for t in termos_complemento)

def validar_bairro(nome_informado):
    bairros_db = obter_lista_bairros_nomes() 
    if not bairros_db: return None
    matches = difflib.get_close_matches(nome_informado.title(), bairros_db, n=1, cutoff=0.7)
    return matches[0] if matches else None

def tentar_recuperar_bairro_perdido(texto):
    if not texto: return None
    if "," in texto:
        for p in texto.split(","):
            b = validar_bairro(p.strip())
            if b: return b
    for p in texto.split():
        if len(p) > 3:
            b = validar_bairro(p.strip())
            if b: return b
    return None

def extrair_complemento_para_referencia(msg_usuario):
    if not msg_usuario: return ""
    padrao = r"(?i)\b(?:apto|apt|apartamento|bloco|bl|sala|lj|loja|casa|unidade|qd|quadra|lt|lote|predio|prédio)\s*[a-zA-Z0-9]+"
    matches = re.findall(padrao, msg_usuario)
    return ", ".join(matches) if matches else ""

def processar_texto_endereco(msg, cad):
    """Tenta extrair Rua, Número, Bairro e Complemento de uma string única."""
    bairro_encontrado = tentar_recuperar_bairro_perdido(msg)
    msg_para_processar = msg
    
    if bairro_encontrado:
        cad["bairro"] = bairro_encontrado
        msg_para_processar = re.sub(rf'(?i)\b{re.escape(bairro_encontrado)}\b', '', msg_para_processar)

    complementos = extrair_complemento_para_referencia(msg_para_processar)
    if complementos:
        if cad.get("ponto_referencia"): cad["ponto_referencia"] += ", " + complementos
        else: cad["ponto_referencia"] = complementos
        padrao_comp = r"(?i)\b(?:apto|apt|apartamento|bloco|bl|sala|lj|loja|casa|unidade|qd|quadra|lt|lote|predio|prédio)\s*[a-zA-Z0-9]+"
        msg_para_processar = re.sub(padrao_comp, '', msg_para_processar)

    match_num = re.search(r'(?i)\b(?:numero|nº|n)?\s*(\d{1,5})\b', msg_para_processar)
    if match_num:
        cad["numero_casa"] = match_num.group(1)
        msg_para_processar = msg_para_processar.replace(match_num.group(0), '')
    else:
        nums = re.findall(r'\b\d{1,5}\b', msg_para_processar)
        if nums:
            cad["numero_casa"] = nums[-1]
            msg_para_processar = re.sub(rf'\b{nums[-1]}\b', '', msg_para_processar, count=1)

    rua_sobra = msg_para_processar.replace(',', '').strip()
    rua_sobra = re.sub(r'\s+', ' ', rua_sobra).strip()
    rua_sobra = re.sub(r'(?i)\b(?:numero|nº|n)\b', '', rua_sobra).strip(" -.")
    
    if len(rua_sobra) > 2: cad["rua"] = rua_sobra.title()
    elif not cad.get("rua"):
        partes = msg.split(",")
        cad["rua"] = partes[0].title() if partes else ""


# ==============================================================================
# 2. CONFIGURAÇÕES E FLUXO PRINCIPAL
# ==============================================================================

def obter_perguntas_cadastro():
    """Obtém as perguntas ativas do fluxo de cadastro diretamente do DB."""
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM config_cadastro WHERE ativo_wpp = 1 ORDER BY ordem ASC").fetchall()
            if rows: return [dict(r) for r in rows]
    except Exception: pass
    
    return [
        {"coluna": "nome", "label": "Nome", "pergunta_wpp": "Qual é o seu *Nome*?", "obrigatorio": 1},
        {"coluna": "cpf", "label": "CPF", "pergunta_wpp": "Deseja incluir CPF na nota?", "obrigatorio": 0},
        {"coluna": "rua", "label": "Rua", "pergunta_wpp": "Qual a sua Rua?", "obrigatorio": 1},
        {"coluna": "numero_casa", "label": "Número", "pergunta_wpp": "Qual o Número?", "obrigatorio": 1},
        {"coluna": "bairro", "label": "Bairro", "pergunta_wpp": "Qual o Bairro?", "obrigatorio": 1},
        {"coluna": "ponto_referencia", "label": "Ref", "pergunta_wpp": "Algum Ponto de Referência?", "obrigatorio": 0}
    ]

def iniciar_fluxo_cadastro(fluxo, user_phone, msg_cabecalho=""):
    """Verifica qual é a próxima pergunta pendente e retorna a mensagem."""
    try:
        perguntas = obter_perguntas_cadastro()
        cad = fluxo.setdefault("cadastro", {})
        
        tipo_str = str(fluxo.get("pedido_info", {}).get("tipo_entrega") or "Entrega").lower()
        is_retirada = "retirada" in tipo_str or "local" in tipo_str or "mesa" in tipo_str
        
        for p in perguntas:
            col = p["coluna"]
            if is_retirada and col in ["rua", "numero_casa", "bairro", "ponto_referencia"]:
                continue
                
            if col not in cad or cad[col] is None:
                fluxo["etapa"] = "cadastro_dinamico"
                fluxo["cadastro_coluna_atual"] = col
                resp = p.get("pergunta_wpp") or f"Por favor, informe: {p.get('label')}"
                return f"{msg_cabecalho}\n\n{resp}" if msg_cabecalho else resp
                
        fluxo["etapa"] = None
        return None
    except Exception as e:
        logging.error(f"Erro ao iniciar fluxo: {e}")
        return None


# ==============================================================================
# 3. HANDLERS ESPECIALISTAS DO ROTEADOR
# ==============================================================================

def lidar_cadastro_nome(msg, msg_lower, cad, is_obrig):
    if len(msg) < 3: return create_response(MSG_NOME_CURTO)
    
    # Deteção Inteligente: Utilizador enviou a morada em vez do nome
    if any(t in msg_lower for t in ["rua ", "av ", "avenida", "bairro", "numero", "nº", "apto", "bloco", "casa ", "centro"]):
        cad["nome"] = "Cliente"
        processar_texto_endereco(msg, cad)
        return "SMART_JUMP" # Sinaliza que capturou endereço
        
    cad["nome"] = msg.title()
    return None

def lidar_cadastro_cpf(msg, cad, is_obrig):
    cpf_limpo = re.sub(r"\D", "", msg)
    if not validar_cpf_algoritmo(cpf_limpo):
        return create_response("❌ *CPF Inválido!*\n\nPor favor, digite um CPF válido contendo 11 números.\n_(Se não quiser incluir na nota, responda *não*)_")
    cad["cpf"] = cpf_limpo
    return None

def lidar_cadastro_rua(msg, msg_lower, cad, is_obrig):
    # Deteção Inteligente: Enviou a morada completa na etapa da rua
    if "," in msg or re.search(r'\d+', msg):
        processar_texto_endereco(msg, cad)
        return "SMART_JUMP"
    
    if len(msg) < 4: return create_response("🤔 Nome da rua muito curto. Por favor, digite novamente.")
    cad["rua"] = msg.title()
    return None

def lidar_cadastro_numero(msg, msg_lower, cad, is_obrig):
    # Adicionadas as variações "n tem", "nao tem", "nao possui"
    msg_limpa_num = remover_acentos(msg_lower).strip()
    termos_sem_numero = ["sem numero", "s/n", "sn", "sem", "n tem", "nao tem", "nao possui"]
    
    if any(t in msg_limpa_num for t in termos_sem_numero):
        cad["numero_casa"] = "S/N"
        return None
        
    complementos = extrair_complemento_para_referencia(msg)
    if complementos:
        if cad.get("ponto_referencia"): cad["ponto_referencia"] += ", " + complementos
        else: cad["ponto_referencia"] = complementos
        
        msg_num_limpo = re.sub(r"(?i)\b(?:apto|apt|apartamento|bloco|bl|sala|lj|loja|casa|unidade|qd|quadra|lt|lote|predio|prédio)\s*[a-zA-Z0-9]+", '', msg).strip()
        match_num = re.search(r'(?i)\b(?:numero|nº|n)?\s*(\d{1,5})\b', msg_num_limpo)
        cad["numero_casa"] = match_num.group(1) if match_num else msg_num_limpo.upper()
    else:
        nums = re.findall(r"\d+", msg)
        if not nums and not eh_apenas_complemento(msg): 
            return create_response("🔢 Por favor, digite o número da casa (ou 'S/N').")
            
        match_num = re.search(r'(?i)\b(?:numero|nº|n)?\s*(\d{1,5})\b', msg)
        cad["numero_casa"] = match_num.group(1) if match_num else msg.upper()
    return None

def lidar_cadastro_bairro(msg, cad, is_obrig):
    bairro_valido = validar_bairro(msg)
    if not bairro_valido:
        bairros_reais = obter_lista_bairros_nomes()
        lista_bairros = "\n".join([f"- {b}" for b in bairros_reais])
        return create_response(f"🚫 Não entregamos no bairro *{msg}* ou não entendi.\n\n*Atendemos nestes bairros:*\n{lista_bairros}\n\nDigite o nome do bairro novamente:")
    
    cad["bairro"] = bairro_valido
    return None

def lidar_cadastro_referencia(msg, cad, is_obrig):
    if len(msg) < 3 and is_obrig == 1: 
        return create_response("📍 O ponto de referência é importante. Digite algo que ajude o entregador.")
    cad["ponto_referencia"] = msg
    return None


# ==============================================================================
# 4. ORQUESTRADOR DE CADASTRO (ROUTER)
# ==============================================================================

ROTEADOR_CADASTRO = {
    "nome": lidar_cadastro_nome,
    "cpf": lidar_cadastro_cpf,
    "rua": lidar_cadastro_rua,
    "numero_casa": lidar_cadastro_numero,
    "bairro": lidar_cadastro_bairro,
    "ponto_referencia": lidar_cadastro_referencia
}

def processar_cadastro(fluxo, user_message, user_phone):
    """Roteia a mensagem do utilizador para a função responsável pelo campo atual."""
    try:
        msg = user_message.strip()
        msg_lower = msg.lower()
        cad = fluxo.setdefault("cadastro", {})
        etapa = fluxo.get("etapa")
        coluna_atual = fluxo.get("cadastro_coluna_atual")

        # Fallback de segurança para recuperar o passo se ele se perder no fluxo
        if not coluna_atual and etapa and etapa.startswith("cadastro_"):
            coluna_atual = etapa.replace("cadastro_", "").replace("numero", "numero_casa").replace("ponto", "ponto_referencia")
            fluxo["cadastro_coluna_atual"] = coluna_atual
            fluxo["etapa"] = "cadastro_dinamico"

        perguntas = obter_perguntas_cadastro()
        pergunta_config = next((p for p in perguntas if p["coluna"] == coluna_atual), None)
# Verificação Universal de Pulo ("Não", "Sem", etc)
        msg_sem_acento = remover_acentos(msg_lower).strip()
        msg_limpa = re.sub(r"[^\w\s/]", "", msg_sem_acento).strip()
        
        # O pulo agora só acontece se for a palavra exata, evitando falsos positivos (como "Washington" ou "sn")
        termos_pular = ["nao", "n", "nop", "sem", "passo", "depois", "nada"]
        eh_pulo = msg_limpa in termos_pular
        
        is_obrig = int(pergunta_config.get("obrigatorio", 0))

        # EXCEÇÃO DE OURO: Na pergunta do NÚMERO, se o cliente disser "sem" ou "n", isso não é pulo, é a resposta "Sem Número"!
        if coluna_atual == "numero_casa" and msg_limpa in ["sem", "n"]:
            eh_pulo = False

        if eh_pulo and is_obrig == 0:
            cad[coluna_atual] = "" 
        elif eh_pulo and is_obrig == 1:
            return create_response(f"⚠️ Esta informação é obrigatória.\n\n{pergunta_config['pergunta_wpp']}")
        else:
            # DELEGAR PARA O HANDLER ESPECÍFICO
            handler = ROTEADOR_CADASTRO.get(coluna_atual)
            
            if handler:
                # O handler pode precisar de parâmetros diferentes
                if coluna_atual in ["nome", "rua", "numero_casa"]:
                    resultado = handler(msg, msg_lower, cad, is_obrig)
                else:
                    resultado = handler(msg, cad, is_obrig)
                
                # Se o handler devolver um dicionário, é uma mensagem de erro/re-pergunta
                if isinstance(resultado, dict): return resultado
                
                # Se o handler ativar o Smart Jump (Deteção de morada inteira)
                if resultado == "SMART_JUMP":
                    msg_aviso = "📍 *Endereço completo identificado e salvo!*"
                    next_pergunta = iniciar_fluxo_cadastro(fluxo, user_phone, msg_cabecalho=msg_aviso)
                    if next_pergunta: return create_response(next_pergunta)
                    return finalizar_cadastro_interno(fluxo, user_phone)
            else:
                cad[coluna_atual] = msg

        # Tenta obter a próxima pergunta do fluxo
        next_pergunta = iniciar_fluxo_cadastro(fluxo, user_phone)
        if next_pergunta: return create_response(next_pergunta)
        
        # Se não há mais perguntas, finaliza o cadastro
        return finalizar_cadastro_interno(fluxo, user_phone)

    except Exception as e:
        err_detalhado = traceback.format_exc()
        logging.error(f"Erro no processar_cadastro:\n{err_detalhado}")
        return create_response(f"⚠️ *Erro no Sistema* ao processar o seu cadastro.\nErro: {str(e)}\n\nDigite *finalizar* para tentar novamente.")


# ==============================================================================
# 5. FINALIZAÇÃO E REDIRECIONAMENTO
# ==============================================================================

def finalizar_cadastro_interno(fluxo, user_phone):
    """Guarda o cliente no BD e decide para onde ele deve ser enviado a seguir."""
    try:
        cad = fluxo.get("cadastro", {})
        try: salvar_cliente_no_banco(user_phone, cad)
        except Exception as e: logging.error(f"Erro DB salvar cliente: {e}")

        # Atribui taxa de entrega se o bairro existir
        if fluxo.get("pedido_info", {}).get("tipo_entrega") == "Entrega" and cad.get("bairro"):
            try: fluxo["pedido_info"]["taxa_entrega"] = obter_taxa_entrega(cad["bairro"])
            except Exception: pass

        fluxo["etapa"] = None
        msgs_pendentes = fluxo.pop("msgs_pendentes", [])
        msg_retorno = MSG_CADASTRO_CONCLUIDO_HEADER

        # Retoma o fluxo que foi interrompido pelo cadastro
        if fluxo.get("itens_com_perguntas_pendentes"):
            from services.extras_flow import iniciar_fluxo_completo
            next_item = fluxo["itens_com_perguntas_pendentes"].pop(0)
            msg_intro = f"{msg_retorno}\n✅ Cadastro salvo! Voltando para personalizar: *{next_item['nome']}*"
            return iniciar_fluxo_completo(fluxo, next_item, user_phone, msg_intro=msg_intro)

        if fluxo.get("itens_ambiguos_pendentes"):
            from services.pedido_flow import resolver_pendencia_item
            header_list = [msg_retorno]
            if msgs_pendentes: header_list.extend(msgs_pendentes)
            return resolver_pendencia_item(fluxo, "", user_phone, header_list)

        if fluxo.get("em_finalizacao"):
            from services.finalizacao_flow import finalizar_pedido 
            return finalizar_pedido(fluxo, "retomar", user_phone)

        if fluxo.get("carrinho_atual"):
            carrinho_txt = resumo_carrinho(fluxo)
            txt_aviso = "\n\n".join(msgs_pendentes) + "\n\n" if msgs_pendentes else ""
            msg_endereco = f"📍 Entregar em: {cad.get('rua', '')}, {cad.get('numero_casa', '')} - {cad.get('bairro', '')}\n(Ref: {cad.get('ponto_referencia', '')})"
            return create_response(f"{msg_retorno}\n{txt_aviso}{msg_endereco}\n\n🛒 *Seu Pedido:*\n{carrinho_txt}\n\n{MSG_CADASTRO_FINALIZADO_CONTINUE}")

        return create_response(f"{msg_retorno}\n\nO que deseja pedir agora?")
        
    except Exception as e:
        err_detalhado = traceback.format_exc()
        logging.error(f"Erro CRÍTICO no finalizar_cadastro_interno:\n{err_detalhado}")
        return create_response(f"⚠️ Erro ao finalizar cadastro: {str(e)}\n\nDigite *finalizar* para tentar de novo.")


def iniciar_atualizacao_endereco(fluxo, analise, user_phone, user_message_raw=""):
    """Acionado quando a IA descobre que o cliente quer alterar a morada a meio do processo."""
    novo_end = analise.get("endereco_completo", {})
    cad = fluxo.get("cadastro", {})

    if novo_end.get("rua"): cad["rua"] = novo_end["rua"]
    if novo_end.get("numero"): cad["numero_casa"] = novo_end["numero"]
    if novo_end.get("bairro"):
        b = validar_bairro(novo_end["bairro"])
        if b: cad["bairro"] = b

    ref_ia = novo_end.get("ponto_referencia") or ""
    complementos_msg = extrair_complemento_para_referencia(user_message_raw)
    
    partes_ref = []
    if ref_ia: partes_ref.append(ref_ia)
    if complementos_msg and complementos_msg.lower() not in ref_ia.lower(): partes_ref.append(complementos_msg)
    if partes_ref: cad["ponto_referencia"] = ", ".join(partes_ref)

    fluxo["cadastro"] = cad
    
    next_pergunta = iniciar_fluxo_cadastro(fluxo, user_phone)
    if next_pergunta: return create_response(MSG_ENDERECO_ATUALIZADO + "\n\n" + next_pergunta)
    
    return finalizar_cadastro_interno(fluxo, user_phone)