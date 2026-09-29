import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from .utils import esperar


def cadastrar_endereco(driver, endereco_info):
    try:
        print("[INFO] Registering delivery address...")

        # Reabre modal perfil
        perfil_btn_xpath = "//a[@data-toggle='modal' and @data-target='#ModalPerfil']"
        perfil_btn = esperar(
            driver, 10, EC.element_to_be_clickable((By.XPATH, perfil_btn_xpath))
        )
        driver.execute_script("arguments[0].click();", perfil_btn)
        time.sleep(0.8)

        # Vai para Endereços
        enderecos_xpath = "//a[contains(@class,'a-perfil') and contains(@href,'ListarEnderecosCliente')]"
        btn_enderecos = esperar(
            driver, 10, EC.element_to_be_clickable((By.XPATH, enderecos_xpath))
        )
        driver.execute_script("arguments[0].click();", btn_enderecos)
        time.sleep(1.0)

        # Adicionar Novo Endereço
        novo_end_xpath = "//a[contains(@class,'btn-add-endereco')]"
        btn_add = esperar(
            driver, 10, EC.element_to_be_clickable((By.XPATH, novo_end_xpath))
        )
        driver.execute_script("arguments[0].click();", btn_add)

        # Preencher campos
        esperar(driver, 10, EC.presence_of_element_located((By.ID, "Rua")))
        driver.find_element(By.ID, "Rua").clear()
        driver.find_element(By.ID, "Rua").send_keys(endereco_info["rua"])

        try:
            Select(driver.find_element(By.ID, "SelectBairro")).select_by_visible_text(
                endereco_info["bairro"]
            )
        except Exception:
            print(
                f"[WARNING] Could not select neighborhood '{endereco_info['bairro']}'."
            )

        driver.find_element(By.ID, "Numero").clear()
        driver.find_element(By.ID, "Numero").send_keys(endereco_info["numero"])
        driver.find_element(By.ID, "PontoDeReferencia").clear()
        driver.find_element(By.ID, "PontoDeReferencia").send_keys(
            endereco_info["referencia"]
        )

        # Salvar
        salvar_end_xpath = "//button[contains(@class,'btn-add-endereco2')]"
        btn_salvar_end = esperar(
            driver, 10, EC.element_to_be_clickable((By.XPATH, salvar_end_xpath))
        )
        driver.execute_script("arguments[0].click();", btn_salvar_end)
        print("[INFO] Address saved.")
        time.sleep(1.5)

        try:
            fechar_btn_xpath = "//button[@type='button' and @data-dismiss='modal' and contains(normalize-space(.),'Fechar')]"
            driver.find_element(By.XPATH, fechar_btn_xpath).click()
        except Exception:
            pass

        return True
    except Exception as e:
        print(f"[ERROR] Failed to save address: {e}")
        return False
