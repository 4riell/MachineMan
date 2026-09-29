from fastapi import APIRouter, Request, HTTPException, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import sqlite3

router = APIRouter()
templates = Jinja2Templates(directory="templates")

class LoginDados(BaseModel):
    email: str
    senha: str

class CadastroDados(BaseModel):
    nome_estabelecimento: str
    email: str
    senha: str

import os

def get_db_connection():
    pasta_atual = os.path.dirname(os.path.abspath(__file__))
    raiz_projeto = os.path.dirname(pasta_atual)
    db_path = os.path.join(raiz_projeto, "database", "pizzaria.db")
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn

@router.get("/login", response_class=HTMLResponse)
async def tela_login(request: Request):
    # Se o cookie de sessão existir, o usuário já está logado, manda pro painel
    if request.cookies.get("session_user_id"):
        return RedirectResponse(url="/pedidos", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/api/auth/login")
async def processar_login(dados: LoginDados, response: Response):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Valida as credenciais (em produção, use senhas com hash como bcrypt)
    cursor.execute("SELECT id FROM usuarios WHERE email = ? AND senha_hash = ?", (dados.email, dados.senha))
    usuario = cursor.fetchone()
    conn.close()
    
    if usuario:
        # Injeta o cookie seguro de autenticação
        response.set_cookie(
            key="session_user_id",
            value=str(usuario["id"]),
            httponly=True,
            max_age=28800, # 8 horas
            samesite="lax"
        )
        return {"status": "sucesso"}
    
    raise HTTPException(status_code=401, detail="E-mail ou senha incorretos")

@router.post("/api/auth/cadastro")
async def processar_cadastro(dados: CadastroDados):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO usuarios (nome_estabelecimento, email, senha_hash) VALUES (?, ?, ?)",
            (dados.nome_estabelecimento, dados.email, dados.senha)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="E-mail já está em uso")
    finally:
        conn.close()
    
    return {"status": "sucesso"}

@router.get("/logout")
async def processar_logout():
    # 1. Cria a resposta de redirecionamento PRIMEIRO
    resposta = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    
    # 2. Deleta o cookie DIRETAMENTE na resposta que será enviada ao navegador
    resposta.delete_cookie("session_user_id")
    
    # 3. Retorna a resposta completa (redirecionamento + ordem de apagar cookie)
    return resposta