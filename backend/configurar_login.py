import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager


def configurar_login():
    # 1. Define o caminho ABSOLUTO para a pasta do perfil
    # Isso garante que o Python sempre ache a mesma pasta, não importa de onde rode
    caminho_atual = os.getcwd()
    caminho_perfil = os.path.join(caminho_atual, "chrome_profile_bot")

    print("--- CONFIGURAÇÃO DE LOGIN ---")
    print(f"Perfil será salvo em: {caminho_perfil}")

    # 2. Configura as opções do Chrome
    chrome_options = Options()
    chrome_options.add_argument(f"user-data-dir={caminho_perfil}")

    # Argumentos para evitar detecção e erros de perfil
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    # Inicializa o driver
    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # 3. Abre o site
        driver.get("https://app.cooki.com.br/degusttopizzaria")

        print("\n" + "=" * 50)
        print(" O NAVEGADOR FOI ABERTO.")
        print(" 1. Vá até o navegador aberto.")
        print(" 2. FAÇA O LOGIN manualmente com email e senha.")
        print(" 3. Marque a opção 'Lembrar-me' ou 'Manter conectado' se houver.")
        print(" 4. Verifique se você entrou na tela inicial do sistema.")
        print("=" * 50 + "\n")

        # 4. Trava o script aqui até você dar o comando
        input(
            ">>> DEPOIS DE LOGAR NO SITE, VOLTE AQUI E APERTE [ENTER] PARA SALVAR E SAIR..."
        )

    except Exception as e:
        print(f"Erro: {e}")
    finally:
        print("Fechando navegador e salvando perfil...")
        driver.quit()
        print("Pronto! Perfil salvo.")


if __name__ == "__main__":
    configurar_login()
