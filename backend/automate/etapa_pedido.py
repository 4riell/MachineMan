import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from .utils import esperar, limpar_filtro, normalizar


def _clicar_card_categoria(driver, nome_categoria):
    try:
        limpar_filtro(driver)
        titulo_esperado = nome_categoria.upper()
        xpath_categoria = (
            f"//div[contains(@class, 'cardProduto')]//h5[@title='{titulo_esperado}']"
        )
        card = esperar(
            driver, 10, EC.element_to_be_clickable((By.XPATH, xpath_categoria))
        )
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
        time.sleep(0.5)
        card.click()
        return True
    except Exception as e:
        print(f"[WARNING] Category '{nome_categoria}' not found. Error: {e}")
        return False


def _clicar_produto_pizza(driver, nome_produto):
    search_bar_id = "filtro"
    titulo_esperado = f"PIZZA {nome_produto.upper()}"
    xpath_produto = (
        f"//div[contains(@class, 'cardProduto')]//h5[@title='{titulo_esperado}']"
    )
    try:
        search_bar = esperar(
            driver, 10, EC.presence_of_element_located((By.ID, search_bar_id))
        )
        search_bar.clear()
        search_bar.send_keys(nome_produto)
        search_bar.send_keys(Keys.RETURN)
        time.sleep(1.5)

        elemento_card = esperar(
            driver,
            10,
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    f"{xpath_produto}/ancestor::div[contains(@class, 'cardProduto')]",
                )
            ),
        )

        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', inline: 'center'});",
            elemento_card,
        )
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", elemento_card)
        print(f"[INFO] Clicked on '{nome_produto}'.")
        time.sleep(1)
        return True
    except Exception as e:
        print(f"[WARNING] Product '{nome_produto}' not found. Error: {e}")
        return False


def adicionar_item_com_variacao(driver, item, modo_teste=False):
    nome_item = item.get("nome")
    categoria = item.get("categoria")

    limpar_filtro(driver)
    if not _clicar_card_categoria(driver, categoria):
        return

    modal_selector = (By.ID, "modalProduto")
    try:
        esperar(driver, 10, EC.visibility_of_element_located(modal_selector))
        nome_curto = nome_item.replace(" 1,5l", "").replace(" long neck", "").strip()
        alvo = normalizar(nome_curto)

        xpath_opcao = (
            f"//p[contains(translate(normalize-space(.),'ÁÉÍÓÚÂÊÎÔÛÀÈÌÒÙÃÕÇ','AEIOUAEIOUAEIOUAOC'), '{alvo}')]"
            "/ancestor::div[contains(@class, 'btnSelecionarFilho')]"
        )
        esperar(driver, 5, EC.element_to_be_clickable((By.XPATH, xpath_opcao))).click()
        time.sleep(0.5)

        if not modo_teste:
            esperar(
                driver,
                5,
                EC.element_to_be_clickable((By.ID, "addProdutoComFilhoCarrinho")),
            ).click()
            print(f"[INFO] Item '{nome_item}' added to cart.")
    except Exception as e:
        print(f"[ERROR MODAL] Failed to select variation '{nome_item}'. Error: {e}")
    finally:
        _fechar_modal_se_aberto(driver, modo_teste, modal_selector)


def adicionar_pizza(driver, item_pizza, modo_teste=False):
    sabores_raw = item_pizza.get("sabores", "")
    sabores = (
        [s.strip() for s in sabores_raw.split(",")]
        if isinstance(sabores_raw, str)
        else sabores_raw
    )

    if not sabores:
        return

    sabor_principal = sabores[0].replace("pizza ", "").strip()
    print(f"[MODAL] Opening pizza: {sabor_principal}")

    if not _clicar_produto_pizza(driver, sabor_principal):
        return

    modal_selector = (By.ID, "modalProduto")
    try:
        esperar(driver, 10, EC.visibility_of_element_located(modal_selector))

        # Seleção de Tamanho
        tamanho_db = item_pizza.get("tamanho")
        mapa_tamanho = {"P": "pequena", "M": "média", "G": "grande", "F": "família"}
        tamanho_site = mapa_tamanho.get(tamanho_db, "grande")

        if tamanho_site:
            xpath_tamanho = f"//p[contains(translate(normalize-space(.),'ÁÉÍÓÚÂÊÎÔÛÀÈÌÒÙÃÕÇ','AEIOUAEIOUAEIOUAOC'), '{normalizar(tamanho_site)}')]/ancestor::div[contains(@class, 'btnSelecionarFilho')]"
            esperar(
                driver, 5, EC.element_to_be_clickable((By.XPATH, xpath_tamanho))
            ).click()
            time.sleep(0.5)

        # Habilitar segundo sabor
        try:
            xpath_segundo_sabor = "//div[@id='modalProduto']//*[self::p or self::span][contains(translate(normalize-space(.), 'ÁÉÍÓÚÂÊÎÔÛÀÈÌÒÙÃÕÇ','AEIOUAEIOUAEIOUAOC'), '+ sabor')]/ancestor::*[contains(@class,'btnSelecionarFilho') or contains(@class,'card')][1]"
            btn_segundo_sabor = esperar(
                driver, 2, EC.element_to_be_clickable((By.XPATH, xpath_segundo_sabor))
            )
            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", btn_segundo_sabor
            )
            driver.execute_script("arguments[0].click();", btn_segundo_sabor)
            time.sleep(0.4)
        except Exception:
            pass

        # Selecionar sabores extras
        if len(sabores) > 1:
            for sabor_extra in sabores[1:]:
                _selecionar_sabor_extra(driver, sabor_extra)

        # Borda
        borda_desejada = item_pizza.get("borda")
        if borda_desejada and "sem borda" not in borda_desejada.lower():
            _selecionar_borda(driver, borda_desejada)

        # Observação
        obs = item_pizza.get("observacao")
        if obs:
            campo_obs = esperar(
                driver, 8, EC.visibility_of_element_located((By.ID, "txtObs"))
            )
            campo_obs.clear()
            campo_obs.send_keys(str(obs))

        if not modo_teste:
            esperar(
                driver, 5, EC.element_to_be_clickable((By.ID, "addPizzaCarrinho"))
            ).click()
            print("[INFO] Pizza added to cart.")

    except Exception as e:
        print(f"[ERROR MODAL] Error configuring pizza: {e}")
    finally:
        _fechar_modal_se_aberto(driver, modo_teste, modal_selector)
        limpar_filtro(driver)


def _selecionar_sabor_extra(driver, sabor_extra):
    sabor_extra_nome = sabor_extra.replace("pizza ", "").strip()
    alvo1 = normalizar(sabor_extra_nome)
    xpath_sabor_opcao = f"//div[@id='modalProduto']//div[contains(@class,'ingrediente')][.//p[contains(translate(normalize-space(.),'ÁÉÍÓÚÂÊÎÔÛÀÈÌÒÙÃÕÇ','AEIOUAEIOUAEIOUAOC'), '{alvo1}')]]//input[@type='checkbox' or @type='radio']"
    try:
        checkbox = esperar(
            driver, 5, EC.presence_of_element_located((By.XPATH, xpath_sabor_opcao))
        )
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", checkbox
        )
        driver.execute_script("arguments[0].click();", checkbox)
    except Exception:
        pass


def _selecionar_borda(driver, borda_desejada):
    borda_site = (
        f"borda de {borda_desejada.lower()}"
        if "borda" not in borda_desejada.lower()
        else borda_desejada.lower()
    )
    xpath_input = f"//p[contains(translate(normalize-space(.),'ÁÉÍÓÚÂÊÎÔÛÀÈÌÒÙÃÕÇ','AEIOUAEIOUAEIOUAO'), '{normalizar(borda_site)}')]/ancestor::div[contains(@class, 'card-produto-ingrediente')]//input[@type='radio']"
    try:
        input_borda = esperar(
            driver, 5, EC.presence_of_element_located((By.XPATH, xpath_input))
        )
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", input_borda
        )
        driver.execute_script("arguments[0].click();", input_borda)
    except Exception:
        pass


def _fechar_modal_se_aberto(driver, modo_teste, modal_selector):
    try:
        if modo_teste:
            xpath_close = "//div[contains(@class, 'cabecalho-icon-detalhes') and @data-dismiss='modal']"
            esperar(
                driver, 5, EC.element_to_be_clickable((By.XPATH, xpath_close))
            ).click()
        esperar(driver, 5, EC.invisibility_of_element_located(modal_selector))
    except Exception:
        pass
