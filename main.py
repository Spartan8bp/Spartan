from flask import Flask, request
import telebot
import os
import json
import datetime
import pytz
import random
import re

# ✅ CONFIGURAÇÕES GERAIS
TOKEN = '8307062095:AAE3RbmLV5p7brAPJNkDL-0nO79ejKib8Eg'
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
ID_GRUPO = -1002363575666
ID_DONO = 1481389775
fuso_brasilia = pytz.timezone('America/Sao_Paulo')

# ✅ CAMINHOS PARA JSON
CAMINHO_MENSAGENS = {
    "motivacionais": "frases_motivacionais.json",
    "madrugada": "frases_madrugada.json",
    "cadê_samuel": "frases_cade_samuel.json",
    "boas_vindas": "frases_regras_bemvindo.json",
}

# ✅ DADOS TEMPORÁRIOS
usuarios_sem_perfil = set()

# ✅ UTILS
def carregar_json(caminho):
    with open(caminho, 'r', encoding='utf-8') as f:
        return json.load(f)

def escolher_aleatoria(lista):
    return random.choice(lista)

def tem_usuario_sem_perfil(user):
    return not user.username or not user.photo

def horario_agora():
    return datetime.datetime.now(fuso_brasilia)

def nome_ou_mention(user):
    return user.first_name or f"@{user.username}"

# ✅ 1. ENTRADA NO GRUPO → BEM-VINDO + REGRAS
@bot.message_handler(content_types=['new_chat_members'])
def boas_vindas(message):
    for membro in message.new_chat_members:
        nome = membro.first_name
        texto = escolher_aleatoria(carregar_json(CAMINHO_MENSAGENS["boas_vindas"]))
        bot.reply_to(message, f"🎈 OIA, {nome}!\n\n{texto}")

# ✅ 2. SAÍDA DO GRUPO → DESPEDIDA
@bot.message_handler(content_types=['left_chat_member'])
def despedida(message):
    nome = message.left_chat_member.first_name
    bot.reply_to(message, f"👋 {nome} deixou o grupo. Boa sorte por aí, soldado.")

# ✅ 3. MONITORAR SEM FOTO OU NOME DE USUÁRIO (FALA QUALQUER COISA)
@bot.message_handler(func=lambda msg: True)
def detectar_sem_foto_ou_usuario(msg):
    user = msg.from_user
    agora = horario_agora()
    if tem_usuario_sem_perfil(user):
        if user.id not in usuarios_sem_perfil:
            nome = nome_ou_mention(user)
            bot.reply_to(msg, f"⚠️ {nome}, atualize seu perfil com nome de usuário e foto. Aqui é zona de disciplina. 🛡️")
            usuarios_sem_perfil.add(user)
    detectar_cade_samuel(msg)
    detectar_madrugada(msg)

# ✅ 4. "CADÊ SAMUEL?" / "CADE O DONO?" (VARIAÇÕES)
def detectar_cade_samuel(msg):
    texto = msg.text.lower()
    if re.search(r"(cad[eê]|onde|tá|está|sumiu).*(samuel|samuca|samuka|chefe|dono)", texto):
        resposta = escolher_aleatoria(carregar_json(CAMINHO_MENSAGENS["cadê_samuel"]))
        bot.reply_to(msg, resposta)

# ✅ 5. FRASE DE MADRUGADA (APÓS 1H)
def detectar_madrugada(msg):
    hora = horario_agora().hour
    if hora >= 1 and hora <= 5:
        nome = nome_ou_mention(msg.from_user)
        frases = carregar_json(CAMINHO_MENSAGENS["madrugada"])
        bot.reply_to(msg, f"{escolher_aleatoria(frases).replace('{nome}', nome)}")

# ✅ 6. FRASE MOTIVACIONAL DIÁRIA (às 07:00 BR)
@app.route("/motivacional")
def enviar_motivacional():
    agora = horario_agora()
    if agora.hour == 7:
        frases = carregar_json(CAMINHO_MENSAGENS["motivacionais"])
        bot.send_message(ID_GRUPO, f"💪 {escolher_aleatoria(frases)}")
    return "OK"

# ✅ 7. WEBHOOK PARA FUNCIONAR COM FLASK
@app.route(f"/{TOKEN}", methods=['POST'])
def receber_webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "OK", 200

# ✅ 8. INICIALIZAÇÃO DO WEBHOOK
@app.route("/")
def index():
    return "Spartan está no comando."

# ✅ INICIAR APP FLASK
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
