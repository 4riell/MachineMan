# flows/reserva_flow.py

import json
import sqlite3
from datetime import datetime
from storage import get_db_connection, create_response

# --- MENSAGENS DO FLUXO DE RESERVA ---
MSG_RESERVA_DATA = "📅 *Reserva de Mesa*\n\nPara qual dia você gostaria de reservar? (Digite no formato *Dia/Mês*, ex: 26/01)"
MSG_RESERVA_FECHADO = "🚫 Poxa, nesse dia da semana ({dia}) nós não abrimos.\n\nTemos vagas nestes dias: {dias_abertos}.\n\nEscolha outra data:"
MSG_RESERVA_CAPACIDADE_CHEIA = "🚫 Infelizmente já estamos lotados para o dia {data}. Temos {vagas} lugares restantes.\n\nPor favor, escolha outro dia ou diminua a quantidade."
MSG_RESERVA_PESSOAS = "👥 Para quantas pessoas é a mesa?"
MSG_RESERVA_HORARIO = "⏰ Qual horário você prefere? (Ex: 19:30)"
MSG_RESERVA_PRE_PEDIDO = "🍽️ Deseja deixar algum pedido adiantado para agilizar?\n(Digite o nome dos pratos ou 'não' para pular)"
MSG_RESERVA_CONFIRMADA = "✅ *Reserva Confirmada!*\n\n📅 Data: {data}\n⏰ Hora: {hora}\n👥 Pessoas: {pessoas}\n👤 Nome: {nome}\n🍽️ Pedido: {pedido}\n\nTe esperamos lá! 😉"
MSG_RESERVA_ERRO_DATA = (
    "⚠️ Data inválida. Digite no formato Dia/Mês (ex: 26/01) ou 'cancelar'."
)
MSG_RESERVA_ERRO_NUMERO = "⚠️ Por favor, digite apenas números."


def obter_config_reserva():
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT chave, valor FROM configuracoes").fetchall()
        config = {r["chave"]: r["valor"] for r in rows}

    horarios = {}
    if config.get("horario_json"):
        try:
            horarios = json.loads(config["horario_json"])
        except Exception:
            pass

    return {
        "max_pessoas": int(config.get("capacidade_maxima", 100)),
        "horarios": horarios,
    }


def verificar_lotacao(data_str, qtd_solicitada, max_pessoas):
    """Retorna True se couber, False se lotado"""
    with get_db_connection() as conn:
        res = conn.execute(
            "SELECT SUM(qtd_pessoas) FROM reservas WHERE data_reserva = ?", (data_str,)
        ).fetchone()
        ocupados = res[0] if res and res[0] else 0

    disponivel = max_pessoas - ocupados
    return (qtd_solicitada <= disponivel), disponivel


def converter_data(texto):
    """Converte '26/01' para '2026-01-26' (assume ano atual ou proximo)"""
    try:
        hoje = datetime.now()
        dia, mes = map(int, texto.split("/"))
        ano = hoje.year

        # Se a data ja passou este ano, assume ano que vem
        dt_obj = datetime(ano, mes, dia)
        if dt_obj.date() < hoje.date():
            ano += 1
            dt_obj = datetime(ano, mes, dia)

        return dt_obj, dt_obj.strftime("%Y-%m-%d")
    except Exception:
        return None, None


def processar_reserva(fluxo, user_message, user_phone, user_name):
    msg = user_message.lower().strip()

    if msg in ["cancelar", "sair", "voltar", "menu"]:
        fluxo["etapa"] = None
        fluxo.pop("reserva_temp", None)
        from storage.configuracoes import gerar_menu_opcoes

        return create_response(gerar_menu_opcoes())

    etapa = fluxo.get("etapa")
    config = obter_config_reserva()

    # --- INÍCIO: PEDIR DATA ---
    if etapa == "reserva_inicio":
        fluxo["reserva_temp"] = {}
        fluxo["etapa"] = "reserva_data"
        return create_response(MSG_RESERVA_DATA)

    # --- VALIDAR DATA ---
    if etapa == "reserva_data":
        dt_obj, data_db = converter_data(user_message)

        if not dt_obj:
            return create_response(MSG_RESERVA_ERRO_DATA)

        # Valida Dia da Semana (0=Seg, 6=Dom)
        dias_sigla = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]
        sigla_dia = dias_sigla[dt_obj.weekday()]

        info_dia = config["horarios"].get(sigla_dia, {})
        if info_dia.get("fechado"):
            dias_abertos = [
                d for d, v in config["horarios"].items() if not v.get("fechado")
            ]
            # Traduz siglas
            mapa_dias = {
                "seg": "Seg",
                "ter": "Ter",
                "qua": "Qua",
                "qui": "Qui",
                "sex": "Sex",
                "sab": "Sáb",
                "dom": "Dom",
            }
            lista_dias = ", ".join([mapa_dias.get(d, d) for d in dias_abertos])
            return create_response(
                MSG_RESERVA_FECHADO.format(
                    dia=mapa_dias.get(sigla_dia), dias_abertos=lista_dias
                )
            )

        fluxo["reserva_temp"]["data_formatada"] = dt_obj.strftime("%d/%m")
        fluxo["reserva_temp"]["data_db"] = data_db
        fluxo["etapa"] = "reserva_pessoas"
        return create_response(MSG_RESERVA_PESSOAS)

    # --- VALIDAR PESSOAS E CAPACIDADE ---
    if etapa == "reserva_pessoas":
        if not msg.isdigit():
            return create_response(MSG_RESERVA_ERRO_NUMERO)

        qtd = int(msg)
        data_db = fluxo["reserva_temp"]["data_db"]
        max_cap = config["max_pessoas"]

        cabe, vagas = verificar_lotacao(data_db, qtd, max_cap)

        if not cabe:
            return create_response(
                MSG_RESERVA_CAPACIDADE_CHEIA.format(
                    data=fluxo["reserva_temp"]["data_formatada"], vagas=vagas
                )
            )

        fluxo["reserva_temp"]["pessoas"] = qtd
        fluxo["etapa"] = "reserva_horario"
        return create_response(MSG_RESERVA_HORARIO)

    # --- PEDIR HORÁRIO ---
    if etapa == "reserva_horario":
        # Validação simples de horário
        if ":" not in user_message and len(user_message) < 3:
            return create_response("⚠️ Digite um horário válido (ex: 19:30).")

        fluxo["reserva_temp"]["horario"] = user_message
        fluxo["etapa"] = "reserva_pre_pedido"
        return create_response(MSG_RESERVA_PRE_PEDIDO)

    # --- FINALIZAR E SALVAR ---
    if etapa == "reserva_pre_pedido":
        pre_pedido = ""
        if msg not in ["nao", "não", "n", "nop", "sem"]:
            pre_pedido = user_message

        dados = fluxo["reserva_temp"]

        # Salva no Banco
        with get_db_connection() as conn:
            # 1. Salva a Reserva
            conn.execute(
                """
                INSERT INTO reservas (data_reserva, horario, qtd_pessoas, nome_cliente, telefone_cliente, pre_pedido)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    dados["data_db"],
                    dados["horario"],
                    dados["pessoas"],
                    user_name,
                    user_phone,
                    pre_pedido,
                ),
            )

            # 2. NOVA PARTE: Cria a Notificação para o Painel
            msg_notif = f"📅 NOVA RESERVA (Fluxo):\n{dados['data_formatada']} às {dados['horario']} ({dados['pessoas']}p)\nCliente: {user_name}\nPedido: {pre_pedido or 'Nenhum'}"
            conn.execute(
                """
                INSERT INTO notificacoes (cliente_telefone, mensagem, lida, data_hora, tipo) 
                VALUES (?, ?, 0, datetime('now', 'localtime'), 'RESERVA')
            """,
                (user_phone, msg_notif),
            )

            conn.commit()

        resumo = MSG_RESERVA_CONFIRMADA.format(
            data=dados["data_formatada"],
            hora=dados["horario"],
            pessoas=dados["pessoas"],
            nome=user_name,
            pedido=pre_pedido or "Nenhum",
        )

        fluxo["etapa"] = None
        fluxo.pop("reserva_temp", None)
        from storage.configuracoes import gerar_menu_opcoes

        return create_response(resumo)

    return create_response("Erro no fluxo de reserva.")
