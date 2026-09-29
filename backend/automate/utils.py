import time
import unicodedata
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait


def normalizar(txt: str) -> str:
    return (
        unicodedata.normalize("NFKD", (txt or "").lower())
        .encode("ascii", "ignore")
        .decode()
    )


def esperar(driver, timeout, cond):
    return WebDriverWait(driver, timeout).until(cond)


def limpar_filtro(driver):
    try:
        search_bar = driver.find_element(By.ID, "filtro")
        driver.execute_script(
            """
            const el = arguments[0];
            el.value = '';
            el.dispatchEvent(new Event('input', {bubbles: true}));
            el.dispatchEvent(new Event('change', {bubbles: true}));
        """,
            search_bar,
        )
        try:
            search_bar.clear()
        except Exception:
            pass
        search_bar.send_keys(Keys.ESCAPE)
        time.sleep(0.3)
    except Exception:
        pass
