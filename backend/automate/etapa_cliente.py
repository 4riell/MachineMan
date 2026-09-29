import time
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .utils import esperar


def atualizar_dados_cliente(driver, pedido):
    try:
        print("[INFO] Updating customer data...")

        # Abrir modal perfil
        perfil_btn_xpath = "//a[@data-toggle='modal' and @data-target='#ModalPerfil']"
        perfil_btn = esperar(
            driver, 10, EC.element_to_be_clickable((By.XPATH, perfil_btn_xpath))
        )
        driver.execute_script("arguments[0].click();", perfil_btn)
        time.sleep(0.8)

        # Clicar em Meus Dados
        meus_dados_xpath = (
            "//a[contains(@class,'a-perfil') and contains(@href,'AdminCliente/Index')]"
        )
        meus_dados = esperar(
            driver, 10, EC.element_to_be_clickable((By.XPATH, meus_dados_xpath))
        )
        driver.execute_script("arguments[0].click();", meus_dados)
        time.sleep(1.2)

        # Preencher formulário
        campo_nome = esperar(
            driver, 10, EC.presence_of_element_located((By.ID, "Nome"))
        )
        campo_nome.clear()
        campo_nome.send_keys(pedido["cliente_nome"])

        campo_sobrenome = driver.find_element(By.ID, "Sobrenome")
        campo_sobrenome.clear()
        campo_sobrenome.send_keys("Whatsapp")

        # Formatar Telefone
        tel_raw = pedido.get("telefone", "")
        tel_norm = re.sub(r"\D", "", tel_raw).replace("55", "", 1)
        telefone_formatado = (
            f"({tel_norm[:2]}) {tel_norm[2:7]}-{tel_norm[7:11]}"
            if len(tel_norm) >= 11
            else tel_norm
        )

        campo_tel = driver.find_element(By.ID, "Telefone")
        campo_tel.clear()
        campo_tel.send_keys(telefone_formatado)

        # Salvar
        btn_alterar_xpath = "//button[contains(@class,'btn-padrao-full') and contains(normalize-space(.),'Alterar dados')]"
        btn_alterar = esperar(
            driver, 10, EC.element_to_be_clickable((By.XPATH, btn_alterar_xpath))
        )
        driver.execute_script("arguments[0].click();", btn_alterar)
        time.sleep(1.2)

        # Fechar modal se não fechou sozinho
        try:
            fechar_btn_xpath = "//button[@type='button' and @data-dismiss='modal' and contains(normalize-space(.),'Fechar')]"
            driver.find_element(By.XPATH, fechar_btn_xpath).click()
            time.sleep(0.6)
        except Exception:
            pass

        return True

    except Exception as e:
        print(f"[ERROR] Failed to update customer data: {e}")
        return False
