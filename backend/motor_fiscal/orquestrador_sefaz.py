import sqlite3
import json
import base64
import zlib
import xmltodict
from datetime import datetime
import xml.etree.ElementTree as ET

# Importa o transmissor para comunicar com a SEFAZ
from transmissor_sefaz import enviar_soap_sefaz

DB_PATH = 'database/pizzaria.db'

def garantir_estrutura_db():
    """Garante que as tabelas necessárias existem e têm as colunas corretas."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Adicionar colunas de controlo à tabela de certificados (se não existirem)
    cursor.execute("PRAGMA table_info(erp_certificados)")
    colunas_cert = [col[1] for col in cursor.fetchall()]
    
    if 'ultimo_nsu' not in colunas_cert:
        cursor.execute("ALTER TABLE erp_certificados ADD COLUMN ultimo_nsu VARCHAR(15) DEFAULT '000000000000000'")
    if 'cnpj' not in colunas_cert:
        cursor.execute("ALTER TABLE erp_certificados ADD COLUMN cnpj VARCHAR(14) DEFAULT '00000000000000'")
        
    # 2. Criar tabela de Notas Fiscais (onde o frontend vai ler)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS erp_nfe (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero VARCHAR(50),
            serie VARCHAR(10),
            data_emissao DATE,
            chave_acesso VARCHAR(50),
            fornecedor_nome VARCHAR(150),
            vlr_total REAL,
            status VARCHAR(50),
            xml_completo TEXT,
            tipo_nota VARCHAR(10) DEFAULT 'NF-e'
        )
    """)
    conn.commit()
    conn.close()

def extrair_dados_e_salvar_nfe(xml_descompactado):
    """Transforma o XML num dicionário e guarda na tabela erp_nfe."""
    try:
        dicionario_nfe = xmltodict.parse(xml_descompactado)
        
        # Lidar com XML Completo vs Resumo de NFe
        if 'nfeProc' in dicionario_nfe:
            infNFe = dicionario_nfe['nfeProc']['NFe']['infNFe']
            chave = infNFe['@Id'].replace('NFe', '')
        elif 'resNFe' in dicionario_nfe:
            infNFe = dicionario_nfe['resNFe']
            chave = infNFe.get('chNFe', '')
        else:
            return False # Documento não é uma NF-e útil
            
        numero = infNFe.get('ide', {}).get('nNF') or infNFe.get('nNF', '')
        serie = infNFe.get('ide', {}).get('serie') or infNFe.get('serie', '')
        
        data_emissao_crua = infNFe.get('ide', {}).get('dhEmi') or infNFe.get('dhEmi', '')
        data_emissao = data_emissao_crua[:10] if data_emissao_crua else ''
        
        # Fornecedor
        if 'emit' in infNFe:
            fornecedor = infNFe['emit'].get('xNome', 'Fornecedor Desconhecido')
        else:
            fornecedor = infNFe.get('xNome', 'Fornecedor Desconhecido')
            
        # Total
        vlr_total = 0.0
        if 'total' in infNFe:
            vlr_total = float(infNFe['total']['ICMSTot'].get('vNF', 0.0))
        elif 'vNF' in infNFe:
            vlr_total = float(infNFe['vNF'])

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Verifica se a nota já existe para evitar duplicados
        cursor.execute("SELECT id FROM erp_nfe WHERE chave_acesso = ?", (chave,))
        if cursor.fetchone():
            conn.close()
            return True # Já existe, não fazemos nada
            
        cursor.execute("""
            INSERT INTO erp_nfe 
            (numero, serie, data_emissao, chave_acesso, fornecedor_nome, vlr_total, status, xml_completo) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (numero, serie, data_emissao, chave, fornecedor, vlr_total, "Sem Manifestação", xml_descompactado))
        
        conn.commit()
        conn.close()
        print(f"✅ NF-e {numero} ({fornecedor}) importada com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao ler XML da NFe: {e}")
        return False

def consultar_documentos_sefaz():
    """
    Função principal: Lê as configurações, envia o SOAP, processa o retorno e guarda o NSU.
    """
    garantir_estrutura_db()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT ambiente, cnpj, ultimo_nsu, caminho_cert_pem, caminho_chave_pem FROM erp_certificados LIMIT 1")
    config = cursor.fetchone()
    
    if not config:
        print("❌ Nenhum certificado configurado. Vá ao painel de configurações fiscais.")
        return
        
    ambiente, cnpj, ultimo_nsu, cert_pem, chave_pem = config
    
    # 1. Preparar Pedido MD-e (Distribuição DFe)
    xml_pedido = f"""<distDFeInt versao="1.01" xmlns="http://www.portalfiscal.inf.br/nfe">
        <tpAmb>{ambiente}</tpAmb>
        <cUFAutor>32</cUFAutor>
        <CNPJ>{cnpj}</CNPJ>
        <distNSU><ultNSU>{ultimo_nsu}</ultNSU></distNSU>
    </distDFeInt>"""
    
    url = "https://www1.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx" if ambiente == 1 else "https://hom1.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx"
    namespace = "http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe"
    soap_action = "http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe/nfeDistDFeInteresse"

    print(f"🔄 A consultar SEFAZ (NSU Atual: {ultimo_nsu})...")
    
    # 2. Enviar para a SEFAZ
    resposta_soap = enviar_soap_sefaz(xml_pedido, url, cert_pem, chave_pem, namespace, soap_action)
    
    if not resposta_soap:
        return
        
    # 3. Processar Retorno
    try:
        root = ET.fromstring(resposta_soap)
        # Limpar namespaces para facilitar a leitura
        for elem in root.iter():
            if '}' in elem.tag: elem.tag = elem.tag.split('}', 1)[1]
            
        ret_dist = root.find('.//retDistDFeInt')
        if ret_dist is None:
            print("❌ Estrutura de retorno inválida.")
            return
            
        c_stat = ret_dist.find('cStat').text
        novo_nsu = ret_dist.find('ultNSU').text
        
        if c_stat == '138' or c_stat == '137':
            docs = ret_dist.findall('.//docZip')
            print(f"📦 Foram encontrados {len(docs)} novos documentos.")
            
            for doc in docs:
                zipado = base64.b64decode(doc.text)
                xml_descompactado = zlib.decompress(zipado, 16 + zlib.MAX_WBITS).decode('utf-8')
                extrair_dados_e_salvar_nfe(xml_descompactado)
            
            # Atualizar o NSU na base de dados (MUITO IMPORTANTE)
            cursor.execute("UPDATE erp_certificados SET ultimo_nsu = ?", (novo_nsu,))
            conn.commit()
            print(f"💾 NSU atualizado para: {novo_nsu}")
            
        else:
            motivo = ret_dist.find('xMotivo').text
            print(f"⚠️ Resposta da SEFAZ: {motivo} (Código: {c_stat})")

    except Exception as e:
        print(f"❌ Erro ao analisar retorno: {e}")
        
    conn.close()

if __name__ == "__main__":
    consultar_documentos_sefaz()