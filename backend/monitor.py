import time
import traceback
from pathlib import Path
from filelock import FileLock
from storage import execute_with_retry, get_db_connection
from automate import lancar_pedido_no_site

BASE_DIR = Path(__file__).parent
PASTA_AUTOMATE = BASE_DIR / "automate"

ARQUIVO_GATILHO_PATH = PASTA_AUTOMATE / "automacao_gatilho.txt"
LOCK_GATILHO_PATH = PASTA_AUTOMATE / "automacao_gatilho.txt.lock"
INTERVALO_VERIFICACAO = 5


def monitorar():
    print("--- Automation Monitor Started ---")
    print(f"Watching trigger file: {ARQUIVO_GATILHO_PATH}")

    if not PASTA_AUTOMATE.exists():
        print(f"[ERROR] Pasta '{PASTA_AUTOMATE}' não encontrada.")
        return

    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(pedidos)")
            colunas = [info[1] for info in cursor.fetchall()]
            if "automacao_enviada" not in colunas:
                conn.execute(
                    "ALTER TABLE pedidos ADD COLUMN automacao_enviada INTEGER DEFAULT 0"
                )
                conn.commit()
                print("[INFO] Added column 'automacao_enviada' to table 'pedidos'.")
        except Exception as e:
            print(f"[WARNING] DB Schema check: {e}")
        finally:
            conn.close()
    except Exception as e:
        print(f"[ERROR] DB connection failed: {e}")

    while True:
        try:
            if ARQUIVO_GATILHO_PATH.exists():
                with FileLock(str(LOCK_GATILHO_PATH), timeout=5):
                    conteudo = ARQUIVO_GATILHO_PATH.read_text(encoding="utf-8").strip()
                    try:
                        ARQUIVO_GATILHO_PATH.unlink()
                    except Exception as e:
                        print(f"[WARNING] Could not remove trigger file: {e}")

                linhas = [l.strip() for l in conteudo.splitlines() if l.strip()]
                ids_validos = [int(l) for l in linhas if l.isdigit()]

                ids_validos = list(dict.fromkeys(ids_validos))

                for pedido_id in ids_validos:
                    print(f"\n[TRIGGER DETECTED] Order ID: {pedido_id}")
                    processar_pedido(pedido_id)

                if ids_validos:
                    print("[INFO] Batch processed. Waiting...")

            time.sleep(INTERVALO_VERIFICACAO)

        except KeyboardInterrupt:
            print("\n--- Monitor Stopped ---")
            break
        except Exception as e:
            print(f"[CRITICAL ERROR IN MONITOR] {e}")
            traceback.print_exc()
            time.sleep(10)


def processar_pedido(pedido_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT automacao_enviada FROM pedidos WHERE id=?", (pedido_id,))
    row = cursor.fetchone()
    conn.close()

    if row and (row["automacao_enviada"] == 0 or row["automacao_enviada"] is None):
        sucesso = lancar_pedido_no_site(pedido_id)
        if sucesso:
            conn = get_db_connection()
            cursor = conn.cursor()
            execute_with_retry(
                cursor,
                "UPDATE pedidos SET automacao_enviada=1 WHERE id=?",
                (pedido_id,),
            )
            conn.commit()
            conn.close()
            print(f"[INFO] Order {pedido_id} marked as sent.")
        else:
            print(f"[ERROR] Automation failed for order {pedido_id}.")
    else:
        print(f"[WARNING] Order {pedido_id} already processed or not found.")


if __name__ == "__main__":
    monitorar()
