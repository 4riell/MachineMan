import sqlite3
import os

# Caminho para o seu banco de dados
pasta_atual = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(pasta_atual, "database", "pizzaria.db") # Ajuste se a pasta for diferente

def atualizar_instancia():
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE usuarios SET loja_id = '3' WHERE id = 4"
        )
        conn.commit()
        print("✅ Instância atualizada com sucesso para o usuário 4!")
    except Exception as e:
        print(f"❌ Erro ao atualizar: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    atualizar_instancia()