import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from .utils import normalizar


def selecionar_pagamento(driver, pedido):
    try:
        print("[INFO] Selecting payment method...")
        wait = WebDriverWait(driver, 15)

        # Abrir menu de pagamentos
        xpath_abrir_pagamentos = "//span[normalize-space(.)='Selecionar forma de pagamento']/ancestor::div[contains(@class, 'card-formaPagamento-pagamento')]"
        botao_abrir_pagamentos = wait.until(
            EC.element_to_be_clickable((By.XPATH, xpath_abrir_pagamentos))
        )
        driver.execute_script("arguments[0].click();", botao_abrir_pagamentos)
        time.sleep(1)

        # Definir termo de busca
        forma = normalizar(pedido.get("forma_pagamento", ""))
        detalhe = normalizar(pedido.get("detalhe_pagamento", ""))
        termo_busca = ""

        if "dinheiro" in forma:
            termo_busca = "dinheiro"
        elif "pix" in forma:
            termo_busca = "pix"
        elif "cartao" in forma:
            termo_busca = "debito" if "debito" in detalhe else "credito"

        if not termo_busca:
            print(f"[ERROR] Unrecognized payment: '{forma}'")
            return False

        # Garantir aba Entrega (pagamento offline/na entrega)
        try:
            aba_off_xpath = "//a[contains(@class,'tabPagarEntrega')]"
            driver.find_element(By.XPATH, aba_off_xpath).click()
            time.sleep(0.5)
        except Exception:
            pass

        # Buscar opção na lista
        wait.until(EC.visibility_of_element_located((By.ID, "collapsePagarEntrega")))
        xpath_opcoes = "//div[contains(@class, 'tab-pane') and contains(@class, 'active')]//div[contains(@class, 'card-formaPagamento-pagamento')]"
        opcoes_pagamento = driver.find_elements(By.XPATH, xpath_opcoes)

        for opcao in opcoes_pagamento:
            if termo_busca in normalizar(opcao.text):
                print(f"[INFO] Found payment option: '{opcao.text}'. Clicking...")
                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", opcao
                )
                time.sleep(0.5)
                opcao.click()
                return True

        print(f"[ERROR] No payment option found for '{termo_busca}'.")
        return False

    except Exception as e:
        print(f"[ERROR] Payment selection failed: {e}")
        return False
