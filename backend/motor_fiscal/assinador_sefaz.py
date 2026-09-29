import os
from lxml import etree
from signxml import XMLSigner, methods

def assinar_xml_sefaz(xml_string, caminho_chave_privada, caminho_certificado):
    """
    Recebe uma string XML e os caminhos para as chaves .pem.
    Retorna o XML assinado no padrão XMLDSig exigido pela SEFAZ.
    """
    if not os.path.exists(caminho_chave_privada) or not os.path.exists(caminho_certificado):
        raise FileNotFoundError("Chaves .pem não encontradas na base de dados.")

    with open(caminho_chave_privada, "rb") as f:
        chave_privada = f.read()
    with open(caminho_certificado, "rb") as f:
        certificado = f.read()

    # Canonicalização (remover espaços e quebras de linha inúteis)
    parser = etree.XMLParser(remove_blank_text=True)
    root = etree.fromstring(xml_string.encode('utf-8'), parser)

    # Configuração do assinador (padrão ICP-Brasil)
    signer = XMLSigner(
        method=methods.enveloped,
        signature_algorithm="rsa-sha1",
        digest_algorithm="sha1",
        c14n_algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
    )

    # Assinar fisicamente o nó raiz do XML
    root_assinado = signer.sign(root, key=chave_privada, cert=certificado)

    # Converter de volta para string limpa
    xml_final = etree.tostring(root_assinado, encoding="utf-8", xml_declaration=False).decode('utf-8')
    
    return xml_final