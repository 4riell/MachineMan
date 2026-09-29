# core/ia.py

import os
import re
import json
import logging
import sqlite3
import google.generativeai as genai
from dotenv import load_dotenv

from storage import get_db_connection
from storage.configuracoes import (
    obter_todas_categorias_db,
    obter_variacoes_pizza_db,
    obter_lista_bairros_nomes,
)

# Inicialização da API do Google Gemini
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))


# ==============================================================================
# 1. FUNÇÕES DE CONSTRUÇÃO DE CONTEXTO (DATABASE)
# ==============================================================================

def obter_formas_pagamento_wpp():
    """Busca as formas de pagamento ativas no banco de dados para o Prompt da IA."""
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT nome, pede_detalhe FROM formas_pagamento WHERE disponivel_wpp = 1").fetchall()
            if rows:
                return [{"nome": r["nome"], "pede_detalhe": r["pede_detalhe"]} for r in rows]
    except Exception as e:
        logging.error(f"Erro ao buscar pagamentos para IA: {e}")
        
    return [
        {"nome": "Dinheiro", "pede_detalhe": 1},
        {"nome": "Pix", "pede_detalhe": 0},
        {"nome": "Cartão de Crédito", "pede_detalhe": 0},
        {"nome": "Cartão de Débito", "pede_detalhe": 0}
    ]

def _construir_contexto_dinamico():
    """Coleta todos os dados do BD necessários para ensinar a IA sobre o cardápio atual."""
    contexto = {
        "categorias": '"pizza" | "lanche" | "bebida"',
        "tamanhos_pizza": '"Pequena", "Média", "Grande"',
        "bairros_regra": "NUNCA invente o bairro. Se não estiver escrito, use null.",
        "formas_pagamento": '"Dinheiro" | "Pix" | "Cartão"'
    }

    try:
        # 1. Categorias
        cats_db = obter_todas_categorias_db()
        if cats_db:
            lista_ids = [f'"{c["id"]}"' for c in cats_db]
            contexto["categorias"] = " | ".join(lista_ids)

        # 2. Tamanhos de Pizza
        vars_pizza = obter_variacoes_pizza_db()
        if vars_pizza:
            lista_tamanhos = []
            for v in vars_pizza:
                detalhes = []
                if v.get("fatias"): detalhes.append(f"{v['fatias']} fatias")
                if v.get("max_sabores"): detalhes.append(f"até {v['max_sabores']} sabores")
                str_det = f" ({', '.join(detalhes)})" if detalhes else ""
                lista_tamanhos.append(f"\"{v['nome']}{str_det}\"")
            contexto["tamanhos_pizza"] = ", ".join(lista_tamanhos)

        # 3. Bairros (REGRA ANTI-ALUCINAÇÃO MELHORADA)
        bairros_db = obter_lista_bairros_nomes()
        if bairros_db:
            contexto["bairros_regra"] = (
                "REGRA RESTRITA DE BAIRRO: NUNCA adivinhe ou invente um bairro. "
                "Se o cliente NÃO digitou explicitamente o nome do bairro na mensagem, o campo 'bairro' DEVE SER null. "
                f"Se ele digitou, tente classificar como um destes: {', '.join(bairros_db)}."
            )

        # 4. Formas de Pagamento
        formas_pgt = obter_formas_pagamento_wpp()
        if formas_pgt:
            contexto["formas_pagamento"] = " | ".join([f'"{f["nome"]}"' for f in formas_pgt])

    except Exception as e:
        logging.error(f"Erro ao construir contexto dinâmico para a IA: {e}")

    return contexto


# ==============================================================================
# 2. ENGENHARIA DO PROMPT (INSTRUÇÕES DA IA)
# ==============================================================================

def _gerar_prompt_extracao(mensagem_usuario, contexto):
    """Monta o texto exato que será enviado ao Gemini, blindado contra alucinações."""
    return f"""
Você é o assistente virtual da pizzaria 'Cook Degustto'. 
Sua tarefa é converter a mensagem do cliente EXCLUSIVAMENTE em um objeto JSON estruturado.

REGRAS DE EXTRAÇÃO DE ENDEREÇO E RECEBIMENTO:
1. Identifique Rua, Número, Bairro, Apartamento, Bloco e Referência.
2. NUNCA adivinhe dados. Se não estiver escrito na frase, coloque o valor como null.
3. O campo 'numero' DEVE conter apenas a numeração informada. Nomes de edifícios, empresas ou praças DEVEM ir para 'ponto_referencia' ou 'rua'. NUNCA preencha com "s/n" ou "sem número" por conta própria; se o cliente não digitou o número na mensagem, o valor DEVE ser null obrigatoriamente.
4. Se o cliente informar 'apto', 'apartamento', 'bloco', 'sala', EXTRAIA isso nos campos 'apartamento' ou 'bloco'.
5. {contexto['bairros_regra']}
6. Se o cliente disser "comer aí", "comer no local" ou "mesa", o 'tipo_entrega' DEVE ser "Retirada". Se informar horário, extraia em 'horario'. NUNCA coloque modo de entrega ou horário na 'observacao'.

REGRAS DE PAGAMENTO:
1. Formas de pagamento permitidas: {contexto['formas_pagamento']}.
2. Se o cliente disser apenas "cartão" e as opções tiverem "Cartão de Crédito" e "Cartão de Débito" separados, DEIXE O CAMPO 'forma_pagamento' COMO null. NUNCA adivinhe.
3. Pedidos como "trazer maquininha" ou "preciso de troco" devem ir para o campo 'detalhe_pagamento'.

REGRAS DE ITENS E CARDÁPIO:
1. Categorias permitidas: {contexto['categorias']}.
2. Pizza: O tamanho DEVE ser null se não for mencionado explicitamente. Opções: {contexto['tamanhos_pizza']}.
3. OBSERVAÇÕES ESPECÍFICAS: Mantenha as palavras EXATAS que o cliente usou para descrever alterações (ex: se o cliente disse "A de calabresa poderia tirar a cebola?", escreva "tirar a cebola"). NÃO invente termos robóticos como "na banda de".
4. BEBIDAS E TAMANHOS: Se o cliente pedir bebida informando o recipiente ou tamanho (ex: "2L", "1.5 litros", "1,5L", "Lata", "600ml"), coloque essa informação EXCLUSIVAMENTE no campo 'tamanho', deixando o 'nome' limpo.
5. ATENÇÃO - A REGRA DO "X-": Lanches que começam com "X" (ex: "X tudo") SÃO NOMES DE PRODUTOS. Não confunda com sinal de multiplicação.
6. ITENS FALSOS: NUNCA crie itens genéricos (como "Bebidas", "Sucos") se o cliente não especificar a marca ou sabor exato. Simplesmente ignore.

OBSERVAÇÕES GERAIS E INSTRUÇÕES DE COMANDA:
Se o cliente enviar detalhes sobre o grupo (ex: "somos 47 pessoas"), pedir coisas de logística ("abrir comanda separada para bebidas") ou recados gerais, coloque EXCLUSIVAMENTE no campo 'observacao_geral'.

FORMATO DE SAÍDA (Apenas JSON puro, sem markdown, sem explicações):
{{
  "intencao": "fazer_pedido"|"confirmar_pedido"|"pedir_cardapio"|"perguntar_fila"|"perguntar_tempo"|"outros",
  "observacao_geral": "..."|null,
  "itens": [
      {{ "tipo": "pizza", "tamanho": "Média", "sabores": ["Calabresa", "Frango"], "quantidade": 1, "observacao": "Sem cebola" }},
      {{ "tipo": "bebida", "nome": "Coca Cola", "tamanho": "1.5L", "quantidade": 1 }}
  ],
  "endereco_completo": {{
      "tipo_entrega": "Entrega"|"Retirada"|null,
      "horario": "..."|null,
      "rua": "...",
      "numero": "...",
      "bairro": "...",
      "apartamento": "...",
      "bloco": "...",
      "ponto_referencia": "..."
  }},
  "dados_pagamento": {{ 
      "forma_pagamento": {contexto['formas_pagamento']} ou null, 
      "detalhe_pagamento": "..." 
  }}
}}

Mensagem do Cliente: "{mensagem_usuario}"
"""


# ==============================================================================
# 3. EXECUTOR PRINCIPAL (CHAMADA E PARSER)
# ==============================================================================

def analisar_intencao(mensagem_usuario):
    """
    Função principal. Analisa a mensagem do usuário usando o modelo Gemini 
    para extrair a intenção e os dados estruturados do pedido.
    """
    modelos = ["gemini-2.5-pro", "gemini-1.5-flash"] 
    contexto = _construir_contexto_dinamico()
    prompt = _gerar_prompt_extracao(mensagem_usuario, contexto)

    for nome_modelo in modelos:
        try:
            model = genai.GenerativeModel(nome_modelo)
            response = model.generate_content(prompt)
            texto = response.text.strip()

            # --- PARSER DE LIMPEZA ESTRITA DE JSON ---
            if "```json" in texto:
                texto = texto.replace("```json", "").replace("```", "")
            elif "```" in texto:
                texto = texto.replace("```", "")
                
            # Garante que só pega o que está entre chaves {}
            match = re.search(r"\{.*\}", texto, re.DOTALL)
            if match: 
                texto = match.group()

            dados = json.loads(texto)

            # --- PÓS-PROCESSAMENTO (Adaptação do JSON para o formato do Bot) ---
            if "itens" in dados:
                for item in dados["itens"]:
                    adicionais = item.get("adicionais", [])
                    if adicionais:
                        obs_atual = item.get("observacao") or ""
                        texto_add = ", ".join([f"Com {a}" for a in adicionais])
                        item["observacao"] = f"{obs_atual} | {texto_add}" if obs_atual else texto_add
                        item["adicionais"] = [] # Limpa para não conflitar com o extras_flow

            return dados

        except json.JSONDecodeError as e:
            logging.error(f"Erro de Parse JSON com o modelo {nome_modelo}: {e}. Resposta crua: {texto}")
            continue # Tenta o próximo modelo
        except Exception as e:
            logging.error(f"Erro geral com o modelo {nome_modelo}: {e}")
            continue

    # Fallback seguro caso todos os modelos falhem
    logging.warning("Todos os modelos falharam. Retornando intenção genérica.")
    return {"intencao": "outros"}