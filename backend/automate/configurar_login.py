from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager


def configurar_login():

    pasta_atual = Path(__file__).parent
    pasta_raiz = pasta_atual.parent
    caminho_perfil = pasta_raiz / "chrome_profile_bot"

    print("--- CONFIGURAÇÃO DE LOGIN ---")
    print(f"Perfil será salvo em: {caminho_perfil}")

    chrome_options = Options()
    chrome_options.add_argument(f"user-data-dir={str(caminho_perfil)}")
    chrome_options.add_argument("--no-sandbox")

    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        driver.get("https://app.cooki.com.br/degusttopizzaria")
        print("\n" + "=" * 50)
        print(" O NAVEGADOR FOI ABERTO. FAÇA O LOGIN.")
        print("=" * 50 + "\n")
        input(">>> APERTE [ENTER] AQUI APÓS LOGAR PARA SALVAR E SAIR...")
    except Exception as e:
        print(f"Erro: {e}")
    finally:
        driver.quit()


if __name__ == "__main__":
    configurar_login()
