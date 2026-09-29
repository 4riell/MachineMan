import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from .utils import esperar, limpar_filtro
from .etapa_pedido import adicionar_pizza, adicionar_item_com_variacao
from .etapa_cliente import atualizar_dados_cliente
from .etapa_endereco import cadastrar_endereco
from .etapa_pagamento import selecionar_pagamento
from .etapa_finalizacao import finalizar_pedido

from storage import get_db_connection, buscar_itens_do_pedido

MODO_TESTE_LOJA_FECHADA = True


def lancar_pedido_no_site(pedido_id):
    print(f"Starting site automation for ORDER ID: {pedido_id}")

    # --- 1. Busca Dados no Banco ---
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT p.id, p.forma_pagamento, p.detalhe_pagamento, p.tipo_entrega,
               c.nome as cliente_nome, c.telefone, c.rua, c.numero_casa, c.bairro, c.ponto_referencia 
        FROM pedidos p 
        JOIN cliente c ON p.cliente_telefone = c.telefone 
        WHERE p.id = ?
    """,
        (pedido_id,),
    )
    pedido_row = cursor.fetchone()

    if not pedido_row:
        print(f"[ERROR] Order {pedido_id} not found.")
        conn.close()
        return False

    pedido = dict(pedido_row)
    pizzas, extras = buscar_itens_do_pedido(pedido_id)
    conn.close()

    # Preparar lista de itens unificada
    itens_do_pedido = []
    for p in pizzas:
        p["tipo"] = "pizza"
        itens_do_pedido.append(p)
    for e in extras:
        e["tipo"] = "bebida"
        itens_do_pedido.append(e)

    driver = None
    try:
        # --- 2. Inicializar Driver ---
        service = ChromeService(ChromeDriverManager().install())
        chrome_options = Options()
        caminho_perfil = os.path.join(os.getcwd(), "chrome_profile_bot")
        chrome_options.add_argument(f"user-data-dir={caminho_perfil}")
        chrome_options.add_argument("--start-maximized")

        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get("https://app.cooki.com.br/degusttopizzaria")

        # Verificar login
        try:
            esperar(driver, 8, EC.presence_of_element_located((By.ID, "divCardapio")))
        except Exception:
            print("[ALERTA] Bot não parece logado. Verifique o cookie/perfil.")

        print("[INFO] Site loaded.")

        # --- 3. Executar Etapas ---

        # Etapa A: Itens
        for item in itens_do_pedido:
            print(f"--- Adding: {item.get('nome') or item.get('sabores')} ---")
            if item.get("tipo") == "pizza":
                adicionar_pizza(driver, item, MODO_TESTE_LOJA_FECHADA)
            elif item.get("tipo") == "bebida":
                nome_lower = item.get("nome", "").lower()
                if "1,5l" in nome_lower:
                    item["categoria"] = "Refrigerante 1,5L"
                elif "long neck" in nome_lower:
                    item["categoria"] = "Cerveja Long Neck"
                elif "água" in nome_lower:
                    item["categoria"] = "Água Mineral"

                if item.get("categoria"):
                    adicionar_item_com_variacao(driver, item, MODO_TESTE_LOJA_FECHADA)

            limpar_filtro(driver)

        # Etapa B: Cliente
        atualizar_dados_cliente(driver, pedido)

        # Etapa C: Endereço (se entrega)
        if pedido.get("tipo_entrega") == "Entrega":
            endereco_info = {
                "rua": pedido.get("rua"),
                "bairro": pedido.get("bairro"),
                "numero": pedido.get("numero_casa"),
                "referencia": pedido.get("ponto_referencia"),
            }
            cadastrar_endereco(driver, endereco_info)

        # Etapa D: Pagamento e Finalização
        if not MODO_TESTE_LOJA_FECHADA:
            if selecionar_pagamento(driver, pedido):
                if not finalizar_pedido(driver):
                    raise Exception("Failed at final click.")
        else:
            print("[INFO] TEST MODE: Payment/Finalization skipped.")

        return True

    except Exception as e:
        print(f"\n[GENERAL ERROR] Automation failed: {e}")
        if driver:
            driver.save_screenshot(f"error_order_{pedido_id}.png")
        return False
    finally:
        if driver:
            driver.quit()
