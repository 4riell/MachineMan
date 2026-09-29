import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi.templating import Jinja2Templates

load_dotenv()

# Caminhos
ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.environ.get("DB_FILE") or str(ROOT_DIR / "database" / "pizzaria.db")
templates = Jinja2Templates(directory=str(ROOT_DIR / "templates"))

# Estado Global
carrinhos = {}

# Constantes de Negócio
# MAPA_TAMANHOS removido para usar busca dinâmica no banco (ver storage/utils.py)

BAIRROS_VALIDOS = [
    "Alto Capelinha",
    "Alto da Serra",
    "Café",
    "Caixa D' Água",
    "Campo de Aviação",
    "Celina",
    "Centro",
    "Chácara",
    "Córrego da Prata",
    "Estância Bela Vista",
    "Faisqueira",
    "Jardim das Palmeiras",
    "Jardim Esperança",
    "João XXIII",
    "Loteamento",
    "Mata do Macuco",
    "Monte Verde",
    "Morada do Sol",
    "Niterói",
    "Nova Suíça",
    "Piteiras",
    "Pito Aceso",
    "Populares",
    "Recanto Verde",
    "Santa Edwiges",
    "Santa Rosa",
    "São Vicente",
    "Varginha",
    "Vila Esperança",
    "Vila Gomes",
    "Vila Nova",
    "Vila Reis",
]

BAIRROS_COM_TAXA_FIXA = [
    "Alto Capelinha",
    "Café",
    "Caixa D' Água",
    "Mata do Macuco",
    "Monte Verde",
    "Pito Aceso",
    "Santa Rosa",
    "Vila Reis",
]
