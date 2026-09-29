# storage/__init__.py

from .config import carrinhos, templates, BAIRROS_VALIDOS, BAIRROS_COM_TAXA_FIXA
from .connection import get_db_connection, get_db, execute_with_retry
from .utils import (
    remover_acentos,
    normalizar_tamanho,
    normalizar_tipo_entrega,
    enviar_msg_whatsapp,
    create_response,
)
from .produtos import buscar_produto_db, validar_sabores_db, listar_bordas_db
from .clientes import (
    buscar_cliente_completo,
    buscar_cliente_por_telefone,
    salvar_cliente_no_banco,
    get_endereco_formatado,
)
from .pedidos import (
    obter_id_pedido_aberto,
    buscar_itens_do_pedido,
    copiar_ultimo_pedido,
    salvar_pedido_completo_db,
    confirmar_pedido_db,
    cancelar_pedido_ativo_e_notificar,
    contar_pedidos_na_frente,
    resumo_carrinho,
    sincronizar_itens_pedido_db,
)
from .configuracoes import (
    criar_notificacao,
    listar_notificacoes,
    marcar_notificacao_lida,
    desativar_chat_e_notificar,
    get_chave_pix_ativa,
    obter_taxa_entrega,
    obter_tempo_entrega_config,
    verificar_chat_geral_ativo,
    verificar_chat_cliente_ativo,
    verificar_loja_aberta,
)
