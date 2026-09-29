# route_perfil.py
from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import sqlite3
import os

router = APIRouter()
templates = Jinja2Templates(directory="templates")

class AtualizarSenhaRequest(BaseModel):
    senha_atual: str
    nova_senha: str

class CriarFuncionarioRequest(BaseModel):
    nome: str
    email: str
    senha: str

def get_db_connection():
    pasta_atual = os.path.dirname(os.path.abspath(__file__))
    raiz_projeto = os.path.dirname(pasta_atual)
    db_path = os.path.join(raiz_projeto, "database", "pizzaria.db")
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn

def obter_perfil_logado(request: Request) -> str:
    """Busca o perfil do usuário logado para renderização do template base"""
    usuario_id = request.cookies.get("session_user_id")
    if not usuario_id:
        usuario_id = getattr(request.state, "usuario_id", None)
    if not usuario_id: return "funcionario"
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT perfil FROM usuarios WHERE id = ?", (int(usuario_id),)).fetchone()
        if not row: return "dono"
        row_dict = dict(row)
        return row_dict.get("perfil", "dono")
    except Exception:
        return "dono"
    finally:
        conn.close()

def garantir_coluna_perfil(conn):
    try:
        cur = conn.execute("PRAGMA table_info(usuarios)")
        colunas = [c[1] for c in cur.fetchall()]
        if "perfil" not in colunas:
            conn.execute("ALTER TABLE usuarios ADD COLUMN perfil TEXT DEFAULT 'dono'")
            conn.commit()
    except Exception as e:
        print(f"Erro de estrutura em usuarios: {e}")

@router.get("/perfil", response_class=HTMLResponse)
async def pagina_perfil(request: Request):
    perfil_usuario = obter_perfil_logado(request) # <- ENVIADO PARA O TEMPLATE BASE.HTML
    return templates.TemplateResponse("perfil.html", {"request": request, "perfil": perfil_usuario})

@router.get("/api/usuario/me")
async def buscar_dados_usuario(request: Request):
    usuario_id = getattr(request.state, "usuario_id", None)
    if not usuario_id:
        raise HTTPException(status_code=401, detail="Não autorizado")
        
    conn = get_db_connection()
    garantir_coluna_perfil(conn)
    usuario = conn.execute("SELECT nome_estabelecimento, email, perfil FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
    conn.close()
    
    if usuario:
        return dict(usuario)
    raise HTTPException(status_code=404, detail="Usuário não encontrado")

@router.put("/api/usuario/senha")
async def atualizar_senha(dados: AtualizarSenhaRequest, request: Request):
    usuario_id = getattr(request.state, "usuario_id", None)
    if not usuario_id:
        raise HTTPException(status_code=401, detail="Não autorizado")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    usuario = cursor.execute("SELECT senha_hash FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
    if not usuario or usuario["senha_hash"] != dados.senha_atual:
        conn.close()
        raise HTTPException(status_code=400, detail="A senha atual está incorreta.")
        
    cursor.execute("UPDATE usuarios SET senha_hash = ? WHERE id = ?", (dados.nova_senha, usuario_id))
    conn.commit()
    conn.close()
    
    return {"status": "sucesso", "mensagem": "Senha atualizada com sucesso!"}

@router.post("/api/usuario/funcionario")
async def criar_funcionario(dados: CriarFuncionarioRequest, request: Request):
    usuario_id = getattr(request.state, "usuario_id", None)
    if not usuario_id:
        raise HTTPException(status_code=401, detail="Não autorizado")
        
    conn = get_db_connection()
    try:
        garantir_coluna_perfil(conn)
        
        # Verifica se quem está chamando é o dono
        user_logado = conn.execute("SELECT loja_id, perfil FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
        if not user_logado or user_logado["perfil"] not in ["dono", "admin"]:
            raise HTTPException(status_code=403, detail="Apenas donos podem cadastrar funcionários.")
            
        loja_id = user_logado["loja_id"]
        
        # Verifica se e-mail já existe
        existe = conn.execute("SELECT id FROM usuarios WHERE email = ?", (dados.email,)).fetchone()
        if existe:
            raise HTTPException(status_code=400, detail="Este e-mail já está cadastrado no sistema.")
            
        conn.execute(
            "INSERT INTO usuarios (nome_estabelecimento, email, senha_hash, loja_id, perfil) VALUES (?, ?, ?, ?, 'funcionario')",
            (dados.nome, dados.email, dados.senha, loja_id)
        )
        conn.commit()
        return {"status": "sucesso", "mensagem": "Funcionário criado com sucesso!"}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()