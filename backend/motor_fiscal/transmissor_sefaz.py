import requests
import xml.etree.ElementTree as ET

def enviar_soap_sefaz(xml_dados, url_webservice, caminho_cert, caminho_chave, namespace, soap_action=None):
    """
    Empacota o XML num Envelope SOAP dinâmico e envia para a SEFAZ usando mTLS.
    Agora aceita o namespace e soap_action dinamicamente para servir tanto para 
    MD-e (Distribuição), como para Emissão ou Manifestação.
    """
    
    envelope_soap = f"""<?xml version="1.0" encoding="utf-8"?>
    <soapenv:Envelope xmlns:soapenv="http://www.w3.org/2003/05/soap-envelope">
       <soapenv:Body>
          <nfeDadosMsg xmlns="{namespace}">
             {xml_dados}
          </nfeDadosMsg>
       </soapenv:Body>
    </soapenv:Envelope>"""

    headers = {'Content-Type': 'application/soap+xml; charset=utf-8;'}
    if soap_action:
        headers['SOAPAction'] = soap_action

    print(f"📡 A ligar ao Web Service: {url_webservice}...")

    try:
        # O Envio (Post) com TLS Mútuo
        response = requests.post(
            url_webservice,
            data=envelope_soap.encode('utf-8'),
            headers=headers,
            cert=(caminho_cert, caminho_chave),
            timeout=30
        )

        if response.status_code == 200:
            print("✅ Resposta recebida da SEFAZ com sucesso!")
            return response.text
        else:
            print(f"❌ Erro HTTP {response.status_code} na comunicação com a SEFAZ.")
            print(f"Detalhes: {response.text}")
            return None

    except requests.exceptions.SSLError as e:
        print(f"🔒 Erro de Certificado SSL/TLS. Verifique os seus ficheiros .pem: {e}")
    except requests.exceptions.ConnectionError as e:
        print(f"🌐 Erro de Ligação. A SEFAZ pode estar em baixo: {e}")
    except Exception as e:
        print(f"⚠️ Erro inesperado: {e}")
        
    return None