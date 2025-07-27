import os
import json
import random
import re
import datetime
import pytz

from flask import Flask, request
import telebot

# 🛡️ — CONFIGURAÇÕES DO BOT

TOKEN = '8307062095:AAE3RbmLV5p7brAPJNkDL-0nO79ejKib8Eg'  # ⚠️ Coloque seu token aqui!
bot = telebot.TeleBot(TOKEN)

ID_GRUPO = -1002363575666  # ID do seu grupo Telegram
ID_DONO = 1481389775       # Seu ID (Samuel)

# Fuso horário de Brasília
FUSO_BRT = pytz.timezone('America/Sao_Paulo')

# Flask app para webhook
app = Flask(__name__)

# 📂 — CAMINHOS DOS ARQUIVOS JSON NA RAIZ DO PROJETO

ARQUIVOS_JSON = {
    "bem_vindas": "frases_regras_bemvindo.json",
    "cade_samuel": "frases_cade_samuel.json",
    "madrugada": "frases_madrugada.json",
    "motivacionais": "frases_motivacionais.json",
    "aniversarios_dia": "frases_aniversario_dia.json",
    "aniversarios_mes": "frases_aniversario_mes.json",
    "risadas": "frases_risada.json",
    "despedidas": "frases_despedida.json",
    "sem_perfil": "frases_advertencia_sem_perfil.json"
}

# 📝 — Função para carregar JSON e retornar lista de frases
def carregar_json(nome_arquivo):
    try:
        with open(nome_arquivo, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Erro ao carregar {nome_arquivo}: {e}")
        return []

# 🎲 — Escolher frase aleatória de uma lista
def escolher_frase(lista):
    if lista:
        return random.choice(lista)
    return ""

# ⏰ — Função para obter horário atual em Brasília
def agora_brasilia():
    return datetime.datetime.now(FUSO_BRT)

# 👤 — Função para pegar nome ou nome de usuário de um usuário Telegram
def nome_ou_mention(user):
    if user.first_name:
        return user.first_name
    if user.username:
        return "@" + user.username
    return "Usuário"

# 🛑 — Verifica se o usuário está sem nome de usuário ou foto
def sem_usuario_ou_foto(user, bot_instance):
    sem_usu = not user.username
    # Para foto, precisamos buscar via API
    try:
        fotos = bot_instance.get_user_profile_photos(user.id, limit=1)
        sem_foto = fotos.total_count == 0
    except:
        sem_foto = True
    return sem_usu, sem_foto

# -----------------------------------------------
# 🌟 HANDLERS DO BOT
# -----------------------------------------------

# 1️⃣ — Boas-vindas quando alguém entra no grupo
@bot.message_handler(content_types=['new_chat_members'])
def boas_vindas_handler(message):
    for membro in message.new_chat_members:
        nome = nome_ou_mention(membro)
        frases = carregar_json(ARQUIVOS_JSON["bem_vindas"])
        texto = escolher_frase(frases)
        resposta = f"🎈 Olá, {nome}!\n\n{texto}"
        bot.reply_to(message, resposta)

# 2️⃣ — Mensagem de despedida quando alguém sai ou é removido
@bot.message_handler(content_types=['left_chat_member'])
def despedida_handler(message):
    nome = nome_ou_mention(message.left_chat_member)
    frases = carregar_json(ARQUIVOS_JSON["despedidas"])
    texto = escolher_frase(frases)
    resposta = f"👋 {nome} {texto}"
    bot.reply_to(message, resposta)

# 3️⃣ — Monitorar mensagens para avisar quem está sem perfil completo (nome de usuário e foto)
usuarios_sem_perfil_avisados = set()

@bot.message_handler(func=lambda msg: True)
def monitorar_sem_perfil(msg):
    user = msg.from_user

    # Verificar nome de usuário e foto
    sem_usu, sem_foto = sem_usuario_ou_foto(user, bot)

    if (sem_usu or sem_foto) and (user.id not in usuarios_sem_perfil_avisados):
        frases = carregar_json(ARQUIVOS_JSON["sem_perfil"])
        nome = nome_ou_mention(user)
        texto = escolher_frase(frases)
        resposta = f"⚠️ {nome}, {texto}"
        bot.reply_to(msg, resposta)
        usuarios_sem_perfil_avisados.add(user.id)

    # Detectar gatilhos específicos
    detectar_cade_samuel(msg)
    detectar_risadas(msg)
    detectar_madrugada(msg)

# 4️⃣ — Detectar frases tipo "Cadê Samuel?"
def detectar_cade_samuel(msg):
    texto = (msg.text or "").lower()
    padrao = r"\b(cad[eê]|onde|tá|está|sumiu).*(samuel|samuca|samuka|chefe|dono)\b"
    if re.search(padrao, texto):
        frases = carregar_json(ARQUIVOS_JSON["cade_samuel"])
        resposta = escolher_frase(frases)
        bot.reply_to(msg, resposta)

# 5️⃣ — Detector de risadas (kkk, hahaha, rsrs etc)
def detectar_risadas(msg):
    texto = (msg.text or "").lower()
    padrao_risadas = r"(kkk+|haha+h+|rsrs+|kkkk+|hehe+)"
    if re.search(padrao_risadas, texto):
        frases = carregar_json(ARQUIVOS_JSON["risadas"])
        nome = nome_ou_mention(msg.from_user)
        resposta = escolher_frase(frases)
        resposta_formatada = f"😂 Rindo de nervoso, {nome}.\n{resposta}"
        bot.reply_to(msg, resposta_formatada)
        # Aqui você pode implementar envio de figurinha (sticker) se desejar

# 6️⃣ — Mensagem para quem fala no grupo entre 1h e 5h da manhã (vigia noturna)
def detectar_madrugada(msg):
    hora = agora_brasilia().hour
    if 1 <= hora <= 5:
        frases = carregar_json(ARQUIVOS_JSON["madrugada"])
        nome = nome_ou_mention(msg.from_user)
        texto = escolher_frase(frases)
        texto = texto.replace("{nome}", nome)
        bot.reply_to(msg, texto)

# 7️⃣ — Frase motivacional diária às 07:00 horário Brasília
def enviar_motivacional_diario():
    agora = agora_brasilia()
    if agora.hour == 7 and agora.minute == 0:
        frases = carregar_json(ARQUIVOS_JSON["motivacionais"])
        frase = escolher_frase(frases)
        bot.send_message(ID_GRUPO, f"💪 {frase}")

# -----------------------------------------------
# 🔥 FLASK WEBHOOK
# -----------------------------------------------

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    json_str = request.stream.read().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def home():
    return "🤖 Spartan Bot está ativo e no comando! 🛡️"

# -----------------------------------------------
# ⏳ LOOP PARA AÇÕES AGENDADAS (exemplo: motivacional diário)
# -----------------------------------------------

# Você pode usar algum scheduler externo ou rodar script separado para chamadas periódicas.
# Aqui, deixamos um exemplo comentado de como fazer com while + sleep (não recomendado para produção).

"""
import time
import threading

def agendador():
    while True:
        enviar_motivacional_diario()
        time.sleep(60)  # Checa a cada minuto

threading.Thread(target=agendador).start()
"""

# -----------------------------------------------
# 🚀 INICIAR APP FLASK
# -----------------------------------------------

if __name__ == "__main__":
    # Para produção: Render ou outro serviço Flask irá rodar o app automaticamente
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
