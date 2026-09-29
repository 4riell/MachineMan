import os
import shutil
import sqlite3
import requests
from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.primitives import serialization

router = APIRouter(tags=["Configuração Fiscal ERP"])
templates = Jinja2Templates(directory="templates")

DB_PATH = 'database/pizzaria.db'
DIR_CERTIFICADOS = 'motor_fiscal/certificados_clientes'

if not os.path.exists(DIR_CERTIFICADOS):
    os.makedirs(DIR_CERTIFICADOS)

def init_db_config():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS erp_certificados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa_id INTEGER,
            ambiente INTEGER,
            cnpj VARCHAR(14),
            ultimo_nsu VARCHAR(15) DEFAULT '000000000000000',
            nome_arquivo VARCHAR(255),
            senha VARCHAR(255),
            caminho_pfx VARCHAR(255),
            caminho_cert_pem VARCHAR(255),
            caminho_chave_pem VARCHAR(255),
            data_upload DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Evita erros caso a tabela já exista de versões anteriores do código
    try: cursor.execute("ALTER TABLE erp_certificados ADD COLUMN cnpj VARCHAR(14)")
    except: pass
    try: cursor.execute("ALTER TABLE erp_certificados ADD COLUMN ultimo_nsu VARCHAR(15) DEFAULT '000000000000000'")
    except: pass
    
    conn.commit()
    conn.close()

init_db_config()

@router.get("/login-sefaz", response_class=HTMLResponse)
async def pagina_login_sefaz(request: Request):
    return templates.TemplateResponse("config_fiscal.html", {"request": request})

@router.post("/api/config/certificado")
async def upload_certificado(
    empresa_id: int = Form(1),
    ambiente: int = Form(...),
    cnpj: str = Form(...), # NOVO: Recebe o CNPJ limpo do form
    senha: str = Form(...),
    arquivo: UploadFile = File(...)
):
    if not arquivo.filename.lower().endswith(('.pfx', '.p12')):
        return JSONResponse(status_code=400, content={"sucesso": False, "erro": "Formato inválido. Envie um arquivo .pfx ou .p12"})

    caminho_pfx = os.path.join(DIR_CERTIFICADOS, f"emp_{empresa_id}_{arquivo.filename}")
    caminho_cert_pem = os.path.join(DIR_CERTIFICADOS, f"emp_{empresa_id}_cert.pem")
    caminho_chave_pem = os.path.join(DIR_CERTIFICADOS, f"emp_{empresa_id}_chave.pem")

    try:
        # 1. Salva o arquivo original
        with open(caminho_pfx, "wb") as buffer:
            shutil.copyfileobj(arquivo.file, buffer)

        # 2. Abre o cofre
        with open(caminho_pfx, "rb") as f:
            pfx_data = f.read()

        private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(
            pfx_data,
            senha.encode()
        )

        # 3. Salva a Chave Privada
        with open(caminho_chave_pem, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))

        # 4. Salva a Cadeia Pública
        with open(caminho_cert_pem, "wb") as f:
            f.write(certificate.public_bytes(serialization.Encoding.PEM))
            if additional_certificates:
                for cert in additional_certificates:
                    f.write(cert.public_bytes(serialization.Encoding.PEM))

        # 5. TESTE DE CONEXÃO REAL NA SEFAZ (SVRS)
        if ambiente == 1:
            url_sefaz = "https://nfce.svrs.rs.gov.br/ws/NfeStatusServico/NfeStatusServico2.asmx"
        else:
            url_sefaz = "https://nfce-homologacao.svrs.rs.gov.br/ws/NfeStatusServico/NfeStatusServico2.asmx"

        try:
            requests.get(f"{url_sefaz}?wsdl", cert=(caminho_cert_pem, caminho_chave_pem), timeout=10)
        except requests.exceptions.SSLError:
            if os.path.exists(caminho_pfx): os.remove(caminho_pfx)
            return JSONResponse(status_code=400, content={"sucesso": False, "erro": "Conexão rejeitada pela SEFAZ. O certificado pode estar expirado, revogado ou ser inválido."})
        except requests.exceptions.RequestException as e:
            if os.path.exists(caminho_pfx): os.remove(caminho_pfx)
            return JSONResponse(status_code=500, content={"sucesso": False, "erro": "A SEFAZ não está respondendo ou está instável no momento. Tente novamente."})

        # 6. Salva referências no Banco de Dados
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM erp_certificados WHERE empresa_id = ?", (empresa_id,))
        
        cursor.execute("""
            INSERT INTO erp_certificados 
            (empresa_id, ambiente, cnpj, nome_arquivo, senha, caminho_pfx, caminho_cert_pem, caminho_chave_pem, ultimo_nsu) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, '000000000000000')
        """, (empresa_id, ambiente, cnpj, arquivo.filename, senha, caminho_pfx, caminho_cert_pem, caminho_chave_pem))
        
        conn.commit()
        conn.close()

        return {"sucesso": True, "mensagem": "Certificado válido! Conexão com os servidores da SEFAZ estabelecida com sucesso."}

    except ValueError:
        if os.path.exists(caminho_pfx): os.remove(caminho_pfx)
        return JSONResponse(status_code=400, content={"sucesso": False, "erro": "Senha incorreta para este certificado digital."})
    except Exception as e:
        if os.path.exists(caminho_pfx): os.remove(caminho_pfx)
        return JSONResponse(status_code=500, content={"sucesso": False, "erro": f"Erro interno: {str(e)}"})