# core/messages.py

# --- GERAIS ---
MSG_SISTEMA_REINICIADO = "🔄 *Sistema Reiniciado!*\n\n{menu}"
MSG_OPERACAO_CANCELADA = "❌ Operação cancelada.\n\n{menu}"
MSG_NAO_ENTENDI_GENERICO = "🤔 Não entendi. Escolha uma opção do menu:\n\n{menu}"
MSG_ENCERRAMENTO_NEUTRO = "Tudo bem! Se precisar de algo, é só chamar. 👋"
MSG_ROBO_PAUSADO_ATENDENTE = (
    "🔕 *Robô pausado.*\n\nUm atendente humano irá responder em breve."
)

# --- CARDÁPIO E SAUDAÇÃO ---
CARDAPIO_LINK = "https://seusite.com/cardapio"  # Configure seu link real aqui
MSG_CARDAPIO_SAUDACAO_NOME = (
    "Olá, *{nome}*! 👋\nBem-vindo de volta! Aqui está nosso cardápio:\n{link}"
)
MSG_CARDAPIO_SAUDACAO_PADRAO = (
    "Olá! 👋\nBem-vindo! Confira nosso cardápio digital:\n{link}"
)
MSG_VER_CARDAPIO_LINK = "🍔 *Acesse nosso Cardápio:*\n{link}"
MSG_MENU_O_QUE_DESEJA = "O que deseja fazer agora?"
MSG_AGRADECIMENTO_FINAL = "Nós que agradecemos! Volte sempre! 🍕🍔"

# --- CARRINHO E ITENS ---
MSG_CARRINHO_VAZIO = "🛒 Seu carrinho está vazio."
MSG_CARRINHO_LIMPO_SUCESSO = "🗑️ Carrinho limpo com sucesso!"

# --- EXTRAS / VARIAÇÕES (GENÉRICO) ---
MSG_DIGITE_APENAS_NUMERO = "🔢 Digite apenas o número."
MSG_NUMERO_INVALIDO_TENTE_NOVAMENTE = "⚠️ Número inválido. Tente novamente."
MSG_MENU_REMOVER = "🗑️ *Remover Item:*\nDigite o número do item para remover:\n\n{lista}"
MSG_ITEM_REMOVIDO_SUCESSO = (
    "✅ *{nome}* removido do carrinho!\n\n{carrinho}\n\n{opcoes}"
)

# --- CADASTRO ---
MSG_NOME_CURTO = "⚠️ O nome precisa ter pelo menos 3 letras."
MSG_SAUDACAO_NF = "Prazer, {nome}! 😃\nDeseja CPF na nota? (Digite o CPF ou 'não')"
MSG_PEDIR_CPF = "Deseja CPF na nota?"
MSG_CPF_INVALIDO = "⚠️ CPF inválido. Tente novamente ou digite 'não'."
MSG_PRAZER_NOTA_FALLBACK = "Ok, sem CPF na nota.\n\n{msg_rua}"
MSG_CPF_ANOTADO_PONTO = "CPF anotado! 👍\n\n{prox}"
MSG_PERGUNTA_RUA = "📍 Qual o nome da sua *Rua*?"
MSG_CADASTRO_NOME_SALVO_RUA = "Anotei seu nome!\nAgora, qual a sua *Rua*?"
MSG_CADASTRO_SALVO_NUMERO = "Rua: *{rua}*.\n🔢 Qual o *Número* da casa?"
MSG_PERGUNTA_NUMERO_CASA = "🔢 Qual o *Número* da casa?"
MSG_PERGUNTA_BAIRRO = "Qual o seu Bairro?"
MSG_CADASTRO_SALVO_BAIRRO = "Número: {numero}.\n🏘️ Qual o seu *Bairro*?"
MSG_DIGITE_PONTO_OBRIGATORIO = "📍 Por favor, digite um *Ponto de Referência* (ex: portão azul, ao lado da padaria):"
MSG_CADASTRO_CONCLUIDO_HEADER = "✅ Cadastro atualizado!"
MSG_CADASTRO_FINALIZADO_CONTINUE = "O que deseja fazer agora?"
MSG_ENDERECO_ATUALIZADO = "✅ Endereço em atualização."

# --- FINALIZAÇÃO ---

MSG_RESPOSTA_CHAVE_PIX = "💠 *Dados para Pagamento PIX:*\n\nChave: *{chave}*\nTitular: {titular}\nBanco: {banco}"
MSG_ERRO_CHAVE_PIX = "⚠️ Nenhuma chave PIX cadastrada no momento."
MSG_COMPROVANTE_RECEBIDO = "🧾 Comprovante recebido! Vamos verificar."
MSG_VINCULO_SUCESSO = "✅ Vínculo realizado com sucesso para {telefone}!"

# --- INFORMAÇÕES GERAIS ---
AUDIO_MSG = (
    "Desculpe, ainda não consigo ouvir áudios. Por favor, escreva sua mensagem. ✍️"
)
MSG_LOJA_FECHADA = "🚫 *Loja Fechada!*\n\nNosso horário de funcionamento é:\n"
MSG_FILA_ESTIMATIVA = (
    "⏳ Temos *{fila}* pedidos na frente.\nTempo estimado: {min}-{max} min."
)
MSG_FILA_VAZIA = "🚀 A cozinha está tranquila! Seu pedido será preparado rapidamente."
MSG_AREAS_ENTREGA_HEADER = "🛵 *Áreas de Entrega:*"
MSG_AREAS_ENTREGA_TAXA10 = "Taxa Fixa: {lista}"
MSG_AREAS_ENTREGA_DEMAIS = "Outros Bairros: {lista} (Consulte taxa)"
MSG_TEMPO_ENTREGA_RESP = "🕒 O tempo médio de entrega hoje é de *{tempo}*."
MSG_VERIFICAR_PEDIDO_EXTERNO = "🔍 Vou verificar seu pedido do app..."
MSG_PEDIR_MOTIVO_CANCELAMENTO = "Qual o motivo do cancelamento?"
MSG_REPETIR_PEDIDO_SUCESSO = (
    "✅ Pedido anterior carregado!\n\n{carrinho}\n\nDeseja finalizar?"
)
MSG_REPETIR_PEDIDO_ERRO = "⚠️ Não encontrei um pedido anterior válido para repetir."

# --- PLACEHOLDERS PARA EVITAR ERROS EM MÓDULOS ANTIGOS ---
