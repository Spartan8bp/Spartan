# 📦 IMPORTAÇÕES E CONFIGURAÇÕES INICIAIS
import os
import json
import random
import re
import datetime
import pytz
import time
import threading

from flask import Flask, request
import telebot

# 🛡️ --- CONFIGURAÇÕES DO BOT ---
TOKEN = '8307062095:AAE3RbmLV5p7brAPJNkDL-0nO79ejKib8Eg'  # ⚠️ Coloque seu token aqui com segurança, nunca compartilhe!
ID_GRUPO = -1002363575666  # ⚠️ ID do grupo Telegram
ID_DONO = 1481389775       # ⚠️ ID do dono (você)

# 🌍 Fuso horário de Brasília
FUSO_BRT = pytz.timezone('America/Sao_Paulo')

# 🚀 Inicialização do bot e Flask
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# 📂 --- ARQUIVOS JSON NA RAIZ DO PROJETO ---
ARQUIVOS_JSON = {
    "bem_vindas": "frases_regras_bemvindo.json",
    "cade_samuel": "frases_cade_samuel.json",
    "madrugada": "frases_madrugada.json",
    "motivacionais": "frases_motivacionais.json",
    "aniversarios_dia": "frases_aniversario_dia.json",
    "aniversarios_mes": "frases_aniversario_mes.json",
    "risadas": "frases_risada.json",
    "despedidas": "frases_despedida.json",
    "sem_perfil": "frases_advertencia_sem_perfil.json",
    "engajamento": "frases_mais_engajado.json",
    "dados_aniversarios": "aniversarios_dia.json",
    "dados_mes": "aniversarios_mes.json"
}

# 🔁 Dados de engajamento diário
contador_mensagens = {}

# 📌 --- FUNÇÕES UTILITÁRIAS ---
def carregar_json(nome_arquivo):
    try:
        with open(nome_arquivo, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Erro ao carregar {nome_arquivo}: {e}")
        return []

def escolher_frase(lista):
    if lista:
        return random.choice(lista)
    return ""

def agora_brasilia():
    return datetime.datetime.now(FUSO_BRT)

def nome_ou_mention(user):
    if user.username:
        return f"@{user.username}"
    return user.first_name or "Usuário"

def sem_usuario_ou_foto(user, bot_instance):
    sem_usu = not bool(user.username)
    try:
        fotos = bot_instance.get_user_profile_photos(user.id, limit=1)
        sem_foto = not fotos or fotos.total_count == 0
    except Exception as e:
        print(f"Erro ao buscar foto de perfil: {e}")
        sem_foto = False  # <-- Evita falsos positivos
    return sem_usu, sem_foto

# 📢 --- HANDLERS DE EVENTOS ---
@bot.message_handler(content_types=["new_chat_members"])
def boas_vindas_handler(message):
    for membro in message.new_chat_members:
        nome = nome_ou_mention(membro)
        frases = carregar_json(ARQUIVOS_JSON["bem_vindas"])
        texto = escolher_frase(frases)
        bot.reply_to(message, f"""🎈 Olá, {nome}!
{texto}""")

@bot.message_handler(content_types=['left_chat_member'])
def despedida_handler(message):
    nome = nome_ou_mention(message.left_chat_member)
    frases = carregar_json(ARQUIVOS_JSON["despedidas"])
    texto = escolher_frase(frases)
    bot.reply_to(message, f"👋 {nome} {texto}")

usuarios_sem_perfil_avisados = set()

@bot.message_handler(func=lambda msg: True)
def monitorar_mensagens(msg):
    if msg.chat.id != ID_GRUPO:
        return

    user = msg.from_user
    contador_mensagens[user.id] = contador_mensagens.get(user.id, 0) + 1

    sem_usu, sem_foto = sem_usuario_ou_foto(user, bot)
    if (sem_usu or sem_foto) and (user.id not in usuarios_sem_perfil_avisados):
        frases = carregar_json(ARQUIVOS_JSON["sem_perfil"])
        nome = nome_ou_mention(user)
        texto = escolher_frase(frases).replace("{nome}", nome)
        bot.reply_to(msg, f"⚠️ {texto}")
        usuarios_sem_perfil_avisados.add(user.id)

    detectar_cade_samuel(msg)
    detectar_risadas(msg)
    detectar_madrugada(msg)

def detectar_cade_samuel(msg):
    texto = (msg.text or '').lower()
    padrao = r"\b(cad[eê]|onde|t[áa]|est[áa]|sumiu).*(samuel|samuca|samuka|chefe|dono)\b"
    if re.search(padrao, texto):
        frases = carregar_json(ARQUIVOS_JSON["cade_samuel"])
        resposta = escolher_frase(frases)
        bot.reply_to(msg, resposta)

def detectar_risadas(msg):
    texto = (msg.text or '').lower()
    if re.search(r"(kkk+|haha+h+|rsrs+|hehe+)", texto):
        frases = carregar_json(ARQUIVOS_JSON["risadas"])
        nome = nome_ou_mention(msg.from_user)
        resposta = escolher_frase(frases).replace("{nome}", nome)
        bot.reply_to(msg, f"😂 Rindo de nervoso, {nome}.\n{resposta}")

def detectar_madrugada(msg):
    hora = agora_brasilia().hour
    if 1 <= hora <= 5:
        frases = carregar_json(ARQUIVOS_JSON["madrugada"])
        texto = escolher_frase(frases).replace("{nome}", nome_ou_mention(msg.from_user))
        bot.reply_to(msg, texto)

# 🎉 --- AÇÕES AGENDADAS ---
def enviar_motivacional():
    frases = carregar_json(ARQUIVOS_JSON["motivacionais"])
    frase = escolher_frase(frases)
    bot.send_message(ID_GRUPO, f"💪 {frase}")

def parabens_aniversariantes():
    hoje = agora_brasilia().strftime('%d/%m')
    aniversarios = carregar_json(ARQUIVOS_JSON["dados_aniversarios"])
    frases = carregar_json(ARQUIVOS_JSON["aniversarios_dia"])
    for usuario, data in aniversarios.items():
        if data == hoje:
            mensagem = escolher_frase(frases).replace("{usuario}", usuario)
            bot.send_message(ID_GRUPO, f"🎈 Feliz aniversário, {usuario}! 🎉\n{mensagem}")

def parabens_do_mes():
    agora = agora_brasilia()
    ultimo_dia = (agora + datetime.timedelta(days=1)).day == 1
    if ultimo_dia:
        mes = agora.strftime('%m')
        aniversariantes = carregar_json(ARQUIVOS_JSON["dados_mes"]).get(mes, [])
        frases = carregar_json(ARQUIVOS_JSON["aniversarios_mes"])
        frase = escolher_frase(frases)
        lista_nomes = "\n".join(aniversariantes)
        bot.send_message(ID_GRUPO, f"🎉 Aniversariantes de {agora.strftime('%B')}:\n{lista_nomes}\n\n{frase}")

def relatorio_engajamento():
    if not contador_mensagens:
        return
    top3 = sorted(contador_mensagens.items(), key=lambda x: x[1], reverse=True)[:3]
    frases = carregar_json(ARQUIVOS_JSON["engajamento"])
    texto = f"📊 Relatório de Engajamento:\n"
    if top3:
        top_nome = nome_ou_mention(bot.get_chat_member(ID_GRUPO, top3[0][0]).user)
        texto += f"🥇 {top_nome} — {escolher_frase(frases)}\n"
    for i, (uid, _) in enumerate(top3[1:], start=2):
        nome = nome_ou_mention(bot.get_chat_member(ID_GRUPO, uid).user)
        medalha = "🥈" if i == 2 else "🥉"
        texto += f"{medalha} {nome}\n"
    bot.send_message(ID_GRUPO, texto)
    contador_mensagens.clear()

# 🔁 --- AGENDADOR EM THREAD SEPARADA ---
def agendador():
    while True:
        agora = agora_brasilia()
        hora = agora.strftime('%H:%M')

        if hora == "07:00":
            enviar_motivacional()
        if hora == "00:30" or hora == "08:00":
            parabens_aniversariantes()
        if hora == "11:00":
            parabens_do_mes()
        if hora == "12:00" or hora == "23:00":
            relatorio_engajamento()

        time.sleep(60)

threading.Thread(target=agendador).start()

# 🌐 --- FLASK WEBHOOK ---
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def home():
    return "🤖 Spartan Bot está ativo e rodando!"

# ▶️ --- INICIAR APP ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
