# storage/utils.py
import os
import logging
import unicodedata
import httpx  # <--- NECESSÁRIO INSTALAR (pip install httpx)
from dotenv import load_dotenv
from .connection import get_db_connection

load_dotenv()

EVOLUTION_BASE_URL = os.getenv("EVOLUTION_BASE_URL")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE")
EVOLUTION_APIKEY = os.getenv("EVOLUTION_APIKEY")


def remover_acentos(texto):
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(texto))
    return "".join([c for c in nfkd if not unicodedata.combining(c)])


def normalizar_tamanho(entrada):
    # Mantive a lógica original, apenas removi comentários excessivos para brevidade
    if not entrada:
        return None
    texto_raw = str(entrada).replace(",", "").replace(".", "").replace("!", "").strip()
    texto_clean = remover_acentos(texto_raw).upper()

    conn = get_db_connection()
    tamanhos_db = []
    try:
        rows = conn.execute(
            "SELECT nome FROM produto_variacoes ORDER BY nome"
        ).fetchall()
        tamanhos_db = [r["nome"] for r in rows if r["nome"]]
    except Exception as e:
        logging.error(f"Erro ao buscar tamanhos no DB: {e}")
        return None
    finally:
        conn.close()

    if not tamanhos_db:
        return None

    for tam_real in tamanhos_db:
        tam_clean = remover_acentos(tam_real).upper()
        if texto_clean == tam_clean:
            return tam_real
        if tam_clean in texto_clean or texto_clean in tam_clean:
            if len(texto_clean) > 2 and len(tam_clean) > 2:
                return tam_real

    mapa_apelidos = {
        "P": ["P", "PEQUENA", "BROTO", "4 FATIAS", "INDIVIDUAL"],
        "M": ["M", "MEDIA", "MED", "6 FATIAS"],
        "G": ["G", "GRANDE", "PADRAO", "8 FATIAS", "NORMAL"],
        "F": ["F", "FAMILIA", "GIGANTE", "12 FATIAS", "BIG"],
    }

    apelido_detectado = None
    if texto_clean in ["P", "M", "G", "F", "GG"]:
        apelido_detectado = texto_clean[0]
    else:
        for chave, keywords in mapa_apelidos.items():
            if any(kw in texto_clean for kw in keywords):
                apelido_detectado = chave
                break

    if apelido_detectado:
        for tam_real in tamanhos_db:
            tam_clean = remover_acentos(tam_real).upper()
            if apelido_detectado == "P" and any(
                k in tam_clean for k in ["PEQ", "BROT", "INDI", "4 FAT"]
            ):
                return tam_real
            if apelido_detectado == "M" and any(
                k in tam_clean for k in ["MED", "6 FAT"]
            ):
                return tam_real
            if apelido_detectado == "G" and any(
                k in tam_clean for k in ["GRA", "PADR", "8 FAT"]
            ):
                return tam_real
            if apelido_detectado == "F" and any(
                k in tam_clean for k in ["FAM", "GIG", "BIG", "12 FAT"]
            ):
                return tam_real

    return None


def normalizar_tipo_entrega(entrada):
    if not entrada:
        return None
    texto = str(entrada).lower()
    if any(t in texto for t in ["entreg", "lev", "motoboy", "casa", "delivery"]):
        return "Entrega"
    if any(t in texto for t in ["retir", "busc", "peg", "balc", "loja", "aqui"]):
        return "Retirada"
    return None


# --- CORREÇÃO ASYNC AQUI ---
async def enviar_msg_whatsapp(telefone, mensagem):
    """
    Envia mensagem ativa de forma ASSÍNCRONA para não travar o bot.
    """
    try:
        numero_limpo = telefone.replace("+", "").replace("-", "").replace(" ", "")
        url = f"{EVOLUTION_BASE_URL}/message/sendText/{EVOLUTION_INSTANCE}"
        headers = {"apikey": EVOLUTION_APIKEY, "Content-Type": "application/json"}
        payload = {"number": numero_limpo, "text": str(mensagem)}

        logging.info(f"📤 Notificando {numero_limpo}...")

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=headers, timeout=10)

        if resp.status_code in [200, 201]:
            logging.info("✅ Notificação enviada.")
        else:
            logging.error(f"❌ Falha notificação: {resp.status_code} - {resp.text}")

    except Exception as e:
        logging.error(f"Erro ao enviar notificação WPP: {e}")


def create_response(text):
    logging.info(f"--- RESPOSTA GERADA ---\n{text}")
    return text
