import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse # <-- ADICIONADO PARA SEGURANÇA
from core.webhook_core import whatsapp_webhook_core
from routes import (
    route_pedidos,
    route_cardapio,
    route_clientes,
    route_configuracoes,
    route_notificacoes,
    route_mesas,
    route_gestao,
    route_fiscal,
    route_cadastros,
    route_financeiro,
    route_doc_fiscais,
    route_operacional,
    route_comercial,
    route_suprimentos,
    route_servicos,
    route_controladoria,
    route_producao,
    route_delivery,
    route_dashboard,
    route_pdv,
    route_config_fiscal,
    route_login,
    route_perfil,
    route_publico
)
from storage import get_db_connection
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

# --- IMPORTAÇÃO DO ROBÔ DE DISPAROS ---
from scheduler import processar_agendamentos

# Configuração de Logs para aparecer no terminal
logging.basicConfig(level=logging.INFO, format="%(message)s")


# --- OTIMIZAÇÃO DE BANCO DE DADOS & TAREFAS DE FUNDO (LIFESPAN) ---
# Isso roda uma vez quando o servidor liga.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Configurações de Banco de Dados
    try:
        conn = get_db_connection()
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.commit()
        conn.close()
        logging.info("🚀 Banco de dados otimizado: Modo WAL ativado.")
    except Exception as e:
        logging.error(f"⚠️ Erro ao otimizar banco de dados: {e}")

    # 2. Inicia o robô de disparos agendados em segundo plano
    task_disparos = asyncio.create_task(processar_agendamentos())
    logging.info("⏰ Robô de disparos agendados iniciado.")

    yield  # O sistema roda aqui

    # 3. Limpeza ao desligar o servidor
    task_disparos.cancel()


# Inicia o App com o lifespan injetado
app = FastAPI(lifespan=lifespan)

# <-- ADICIONE ESTA LINHA PARA RESOLVER O CLOUDFLARE -->
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*") 

# =====================================================================
# MIDDLEWARE DE AUTENTICAÇÃO (TRAVA GLOBAL DO SISTEMA MULTI-USUÁRIO)
# =====================================================================
# Lista de rotas que a API/usuário pode acessar sem estar logado
ROTAS_LIVRES = ["/login", "/api/auth/login", "/api/auth/cadastro", "/logout", "/webhook", "/menu"]

@app.middleware("http")
async def trava_de_seguranca(request: Request, call_next):
    path = request.url.path
    
    # 1. Libera o acesso a arquivos CSS/JS e às rotas públicas configuradas acima
    if path.startswith("/static") or path in ROTAS_LIVRES or path.startswith("/menu"):
        return await call_next(request)
        
    # 2. Verifica se o usuário tem o cookie de sessão válido no navegador
    usuario_id = request.cookies.get("session_user_id")
    
    if not usuario_id:
        # Se for uma requisição interna de API (dados do painel), devolve erro 401
        if path.startswith("/api/"):
            return JSONResponse(status_code=401, content={"detail": "Sessão expirada. Faça login novamente."})
        # Se for tentativa de acessar uma página HTML (ex: /pedidos), bloqueia e redireciona pro login
        return RedirectResponse(url="/login", status_code=303)
        
    # 3. Se estiver logado, salva o ID na requisição para que os routers possam usá-lo depois
    request.state.usuario_id = int(usuario_id)
    return await call_next(request)
# =====================================================================

# Rotas do Painel
app.include_router(route_pedidos.router)
app.include_router(route_cardapio.router)
app.include_router(route_clientes.router)
app.include_router(route_configuracoes.router)
app.include_router(route_notificacoes.router)
app.include_router(route_mesas.router)
app.include_router(route_gestao.router)
app.include_router(route_fiscal.router)
app.include_router(route_cadastros.router)
app.include_router(route_financeiro.router)
app.include_router(route_doc_fiscais.router)
app.include_router(route_operacional.router)
app.include_router(route_comercial.router)
app.include_router(route_suprimentos.router)
app.include_router(route_servicos.router)
app.include_router(route_controladoria.router)
app.include_router(route_producao.router)
app.include_router(route_delivery.router)
app.include_router(route_dashboard.router)
app.include_router(route_pdv.router)
app.include_router(route_config_fiscal.router)
app.include_router(route_login.router)
app.include_router(route_perfil.router)
app.include_router(route_publico.router)
app.mount("/static", StaticFiles(directory="templates/static"), name="static")

# --- ROTA PARA EVOLUTION ---
@app.post("/webhook")
async def evolution_webhook(request: Request):
    try:
        # 1. PEGAR O JSON
        data = await request.json()

        # 2. DEBUG (Opcional, pode comentar em produção se quiser limpar o terminal)
        # print(f"DEBUG: Payload recebido: {str(data)[:100]}...")

        # 3. CHAMAR O NÚCLEO
        return await whatsapp_webhook_core(data)
    except Exception as e:
        print(f"ERRO CRÍTICO NO PAINEL: {e}")
        return {"status": "error"}


if __name__ == "__main__":
    import uvicorn

    # Rodar na porta 8000 (Painel)
    uvicorn.run(app, host="0.0.0.0", port=8000)