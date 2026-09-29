from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def finalizar_pedido(driver):
    try:
        print("[INFO] Finalizing order...")
        wait = WebDriverWait(driver, 15)

        xpath_btn_finalizar = "//button[contains(@class, 'btnFinalizarPagamento')]"
        botao_finalizar = wait.until(
            EC.element_to_be_clickable((By.XPATH, xpath_btn_finalizar))
        )

        driver.execute_script("arguments[0].click();", botao_finalizar)

        wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//*[contains(text(), 'Pedido enviado com sucesso')]")
            )
        )
        print("[SUCCESS] Order finalized!")
        return True

    except Exception as e:
        print(f"[CRITICAL ERROR] Finalization failed: {e}")
        return False
