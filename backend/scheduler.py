import asyncio
import sqlite3
import os
import requests
import logging
from datetime import datetime
from dotenv import load_dotenv

# Reutilizar a configuração de banco e API que você já tem
from storage import get_db_connection

load_dotenv()

EVOLUTION_BASE_URL = os.getenv("EVOLUTION_BASE_URL")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE")
EVOLUTION_APIKEY = os.getenv("EVOLUTION_APIKEY")

async def disparar_mensagem_evolution(telefone, texto, imagem_base64):
    """Função que envia a mensagem (com ou sem imagem) via Evolution API"""
    
    # --- CORREÇÃO DO NÚMERO ---
    tel_str = str(telefone).strip()
    # Remove qualquer caractere não numérico
    tel_str = ''.join(filter(str.isdigit, tel_str))
    
    # Se o número não começar com 55 e for do tamanho de um celular (10 ou 11 dígitos), coloca o 55.
    # Se já tiver 55 (que é o padrão salvo pelo bot), ignora e segue a vida.
    if not tel_str.startswith("55") and len(tel_str) <= 11:
        tel_str = f"55{tel_str}"
        
    numero_payload = f"{tel_str}@s.whatsapp.net"
    headers = {"apikey": EVOLUTION_APIKEY, "Content-Type": "application/json"}
    
    try:
        # Se tiver imagem, usa a rota de SendMedia
        if imagem_base64:
            url = f"{EVOLUTION_BASE_URL}/message/sendMedia/{EVOLUTION_INSTANCE}"
            
            mimetype = "image/jpeg"
            base64_data = imagem_base64
            
            if "base64," in imagem_base64:
                mimetype = imagem_base64.split(";")[0].replace("data:", "")
                base64_data = imagem_base64.split("base64,")[1]

            payload = {
                "number": numero_payload,
                "mediatype": "image",
                "mimetype": mimetype,
                "caption": texto,
                "media": base64_data
            }
        else:
            # Rota padrão de texto
            url = f"{EVOLUTION_BASE_URL}/message/sendText/{EVOLUTION_INSTANCE}"
            payload = {
                "number": numero_payload,
                "text": texto
            }

        # Envia para a API e captura a resposta
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        # Se a API der um erro (código diferente de 200/201), loga no console
        if response.status_code not in [200, 201]:
            logging.error(f"❌ Erro da Evolution API para o número {tel_str}: {response.text}")
            
        # Pequena pausa para evitar banimento do WhatsApp (Anti-Spam)
        await asyncio.sleep(1.5) 
    except Exception as e:
        logging.error(f"❌ Falha de comunicação/rede ao disparar para {tel_str}: {e}")

async def processar_agendamentos():
    """Roda a cada 60 segundos procurando disparos pendentes"""
    print("🤖 Iniciando robô de disparos agendados...")
    while True:
        try:
            agora = datetime.now().strftime('%Y-%m-%dT%H:%M')
            
            with get_db_connection() as conn:
                conn.row_factory = sqlite3.Row
                mensagens = conn.execute("""
                    SELECT * FROM mensagens_agendadas 
                    WHERE status = 'pendente' AND data_hora_envio <= ?
                """, (agora,)).fetchall()

                if mensagens:
                    clientes = conn.execute("SELECT telefone FROM cliente WHERE chat_ativo = 1").fetchall()
                    telefones = [c['telefone'] for c in clientes]

                    for msg in mensagens:
                        print(f"📢 Iniciando disparo #{msg['id']} para {len(telefones)} clientes...")
                        for telefone in telefones:
                            await disparar_mensagem_evolution(telefone, msg['texto'], msg['imagem_base64'])
                        
                        conn.execute("UPDATE mensagens_agendadas SET status = 'enviada' WHERE id = ?", (msg['id'],))
                        conn.commit()
                        print(f"✅ Disparo #{msg['id']} finalizado com sucesso.")
                        
        except Exception as e:
            logging.error(f"Erro no agendador principal: {e}")
        
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(processar_agendamentos())