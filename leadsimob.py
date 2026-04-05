
import os
from datetime import datetime

import gspread
import requests
from flask import Flask, request, jsonify
from google.oauth2.service_account import Credentials

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

GOOGLE_CREDS_FILE    = "credentials.json"
GOOGLE_SHEET_NAME    = "Leads Imobiliária"
# ============================================================

RENDAS = {
    "ate3k":    "Até R$ 3.000",
    "3k5k":     "R$ 3.000 – R$ 5.000",
    "5k10k":    "R$ 5.000 – R$ 10.000",
    "10k20k":   "R$ 10.000 – R$ 20.000",
    "acima20k": "Acima de R$ 20.000",
}

URGENCIAS = {
    "imediato":    "🔥 Imediato (até 30 dias)",
    "curto":       "⏳ Curto prazo (1–3 meses)",
    "medio":       "📅 Médio prazo (3–6 meses)",
    "pesquisando": "👀 Ainda pesquisando",
}


# ── Google Sheets ────────────────────────────────────────────
def conectar_planilha():
    escopos = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(GOOGLE_CREDS_FILE, scopes=escopos)
    cliente = gspread.authorize(creds)
    planilha = cliente.open(GOOGLE_SHEET_NAME).sheet1
    return planilha


def salvar_na_planilha(dados: dict):
    planilha = conectar_planilha()

    # Cria cabeçalhos se a planilha estiver vazia
    if planilha.row_count == 0 or planilha.cell(1, 1).value is None:
        planilha.append_row(
            ["Data", "Nome", "Renda", "Profissão", "Zona", "Tipo", "Prazo"],
            value_input_option="RAW"
        )

    planilha.append_row([
        datetime.now().strftime("%d/%m/%Y %H:%M"),
        dados.get("nome", ""),
        RENDAS.get(dados.get("renda", ""), dados.get("renda", "")),
        dados.get("profissao", ""),
        dados.get("zona", ""),
        dados.get("tipo", ""),
        URGENCIAS.get(dados.get("urgencia", ""), dados.get("urgencia", "")),
    ])


# ── Telegram ─────────────────────────────────────────────────
def enviar_telegram(dados: dict):
    renda    = RENDAS.get(dados.get("renda", ""),    dados.get("renda", "—"))
    urgencia = URGENCIAS.get(dados.get("urgencia", ""), dados.get("urgencia", "—"))

    mensagem = (
        f"🏠 *Novo Lead Imobiliário!*\n\n"
        f"👤 *Nome:* {dados.get('nome', '—')}\n"
        f"💰 *Renda:* {renda}\n"
        f"💼 *Profissão:* {dados.get('profissao', '—')}\n"
        f"📍 *Zona:* {dados.get('zona', '—')}\n"
        f"🏡 *Tipo:* {dados.get('tipo', '—')}\n"
        f"⏱️ *Prazo:* {urgencia}\n\n"
        f"🕐 Recebido em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resposta = requests.post(url, json={
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       mensagem,
        "parse_mode": "Markdown",
    })
    return resposta.ok


# ── Rotas Flask ───────────────────────────────────────────────
@app.route("/lead", methods=["POST"])
def receber_lead():
    """Endpoint chamado pela landing page."""
    try:
        dados = request.get_json(force=True)

        if not dados or not dados.get("nome"):
            return jsonify({"status": "erro", "msg": "Dados inválidos"}), 400

        # Salva na planilha
        salvar_na_planilha(dados)

        # Envia no Telegram
        telegram_ok = enviar_telegram(dados)

        print(f"[{datetime.now():%H:%M:%S}] Lead recebido: {dados.get('nome')} | Telegram: {telegram_ok}")

        return jsonify({"status": "ok", "telegram": telegram_ok})

    except Exception as e:
        print(f"[ERRO] {e}")
        return jsonify({"status": "erro", "msg": str(e)}), 500


@app.route("/teste", methods=["GET"])
def teste():
    """Acesse /teste no navegador para verificar se o servidor está online."""
    return jsonify({
        "status": "online",
        "hora":   datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "msg":    "Bot de leads funcionando!"
    })


@app.route("/teste-telegram", methods=["GET"])
def teste_telegram():
    """Acesse /teste-telegram para enviar uma mensagem de teste no Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    ok = requests.post(url, json={
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       "✅ Bot conectado! Os leads da landing page chegarão aqui.",
        "parse_mode": "Markdown",
    }).ok
    return jsonify({"telegram_ok": ok})


# ── Iniciar servidor ──────────────────────────────────────────
if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 5000))
    print(f"🚀 Servidor rodando na porta {porta}")
    print(f"   Teste local: http://localhost:{porta}/teste")
    app.run(host="0.0.0.0", port=porta, debug=False)