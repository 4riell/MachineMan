import logging
from pathlib import Path
from filelock import FileLock

BASE_DIR = Path(__file__).parent
ARQUIVO_GATILHO = BASE_DIR / "automacao_gatilho.txt"
LOCK_GATILHO = BASE_DIR / "automacao_gatilho.txt.lock"


def disparar_gatilho_site(pedido_id):
    """
    Escreve o ID do pedido no arquivo de fila para o monitor ler.
    Usa FileLock para evitar conflito se dois pedidos saírem ao mesmo tempo.
    """
    try:
        if not ARQUIVO_GATILHO.exists():
            ARQUIVO_GATILHO.touch()

        with FileLock(str(LOCK_GATILHO), timeout=5):
            with open(ARQUIVO_GATILHO, "a", encoding="utf-8") as f:
                f.write(f"{pedido_id}\n")

        logging.info(
            f"🚀 [GATILHO] Pedido #{pedido_id} enviado para fila de automação."
        )
        return True
    except Exception as e:
        logging.error(
            f"❌ [ERRO GATILHO] Falha ao disparar automação para pedido {pedido_id}: {e}"
        )
        return False
