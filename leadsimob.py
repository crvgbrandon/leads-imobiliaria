import os
import json
from datetime import datetime

import gspread
import requests
from flask import Flask, request, jsonify
from google.oauth2.service_account import Credentials

app = Flask(__name__)

TELEGRAM_TOKEN    = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID  = os.environ.get("TELEGRAM_CHAT_ID")
GOOGLE_SHEET_NAME = os.environ.get("GOOGLE_SHEET_NAME", "LeadsImobiliaria")
GOOGLE_CREDS_JSON = os.environ.get("GOOGLE_CREDS_JSON")  # JSON inteiro como string

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


# ── Google Sheets ─────────────────────────────────────────────
def conectar_planilha():
    escopos = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    info = json.loads(GOOGLE_CREDS_JSON)  # lê JSON da env var
    creds = Credentials.from_service_account_info(info, scopes=escopos)
    cliente = gspread.authorize(creds)
    return cliente.open(GOOGLE_SHEET_NAME).sheet1


def salvar_na_planilha(dados: dict):
    planilha = conectar_planilha()

    if planilha.cell(1, 1).value is None:
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


# ── Telegram ──────────────────────────────────────────────────
def enviar_telegram(dados: dict):
    renda    = RENDAS.get(dados.get("renda", ""),       dados.get("renda", "—"))
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
    resp = requests.post(url, json={
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       mensagem,
        "parse_mode": "Markdown",
    })
    return resp.ok


# ── Rotas Flask ───────────────────────────────────────────────
@app.route("/lead", methods=["POST", "OPTIONS"])
def receber_lead():
    if request.method == "OPTIONS":
        resp = app.make_default_options_response()
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return resp

    try:
        dados = request.get_json(force=True)

        if not dados or not dados.get("nome"):
            return jsonify({"status": "erro", "msg": "Dados inválidos"}), 400

        salvar_na_planilha(dados)
        telegram_ok = enviar_telegram(dados)

        print(f"[{datetime.now():%H:%M:%S}] Lead: {dados.get('nome')} | Telegram: {telegram_ok}")

        resp = jsonify({"status": "ok", "telegram": telegram_ok})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    except Exception as e:
        print(f"[ERRO] {e}")
        return jsonify({"status": "erro", "msg": str(e)}), 500


@app.route("/teste", methods=["GET"])
def teste():
    return jsonify({
        "status": "online",
        "hora":   datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "msg":    "Bot de leads funcionando!"
    })


@app.route("/teste-telegram", methods=["GET"])
def teste_telegram():
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    ok = requests.post(url, json={
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       "✅ Bot conectado! Os leads chegarão aqui.",
        "parse_mode": "Markdown",
    }).ok
    return jsonify({"telegram_ok": ok})


# ── Iniciar ───────────────────────────────────────────────────
if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=porta)