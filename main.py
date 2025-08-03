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
    "dados_mes": "aniversarios_mes.json",
    "sticks_risadas": "sticks_risadas.json"
}

# 🔁 Dados de engajamento diário
contador_mensagens = {}
ultimo_risada_respondida = {}  # user_id: datetime

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

def sem_usuario(user):
    return not bool(user.username)

# 🕒 Enviar mensagens com atraso
def responder_com_atraso(funcao_envio, *args, delay=20):
    def enviar():
        time.sleep(delay)
        funcao_envio(*args)
    threading.Thread(target=enviar).start()

# 📢 --- HANDLERS DE EVENTOS ---
@bot.message_handler(content_types=["new_chat_members"])
def boas_vindas_handler(message):
    for membro in message.new_chat_members:
        nome = nome_ou_mention(membro)
        frases = carregar_json(ARQUIVOS_JSON["bem_vindas"])
        texto = escolher_frase(frases).replace("{nome}", nome)
        bot.reply_to(message, texto)

@bot.message_handler(content_types=['left_chat_member'])
def despedida_handler(message):
    nome = nome_ou_mention(message.left_chat_member)
    frases = carregar_json(ARQUIVOS_JSON["despedidas"])
    texto = escolher_frase(frases).replace("{nome}", nome)
    bot.reply_to(message, texto)

usuarios_sem_perfil_avisados = set()
from collections import defaultdict

# Dicionário para armazenar mensagens recentes por usuário
historico_mensagens = defaultdict(list)

@bot.message_handler(func=lambda msg: True)
def monitorar_mensagens(msg):
    #if msg.chat.id != ID_GRUPO:
    #    return

    user = msg.from_user
    contador_mensagens[user.id] = contador_mensagens.get(user.id, 0) + 1

        # Verifica mensagens repetidas
    historico = historico_mensagens[user.id]
    conteudo = None

    if msg.content_type == "text":
        conteudo = msg.text.strip()
    elif msg.content_type == "sticker":
        conteudo = msg.sticker.file_id
    elif msg.content_type == "emoji":
        conteudo = msg.text  # emojis geralmente vêm como texto

    if conteudo:
        agora = agora_brasilia()
        historico.append((conteudo, agora))

        # Remove mensagens antigas (mais de 1 min)
        historico = [m for m in historico if (agora - m[1]).total_seconds() < 60]
        historico_mensagens[user.id] = historico

        # Verifica se há 2 ou mais mensagens repetidas consecutivas
        if len(historico) >= 2 and all(m[0] == conteudo for m in historico[-2:]):
            enviar_alerta_repeticao(msg.chat.id)
            historico_mensagens[user.id] = []  # limpa para não repetir
            return

    if sem_usuario(user) and (user.id not in usuarios_sem_perfil_avisados):
        frases = carregar_json(ARQUIVOS_JSON["sem_perfil"])
        nome = nome_ou_mention(user)
        texto = escolher_frase(frases).replace("{nome}", nome)
        responder_com_atraso(bot.reply_to, msg, f"⚠️ {texto}")
        usuarios_sem_perfil_avisados.add(user.id)

    detectar_cade_samuel(msg)
    detectar_risadas(msg)
    detectar_madrugada(msg)

def detectar_cade_samuel(msg):
    texto = (msg.text or '').lower()
    padrao = r"\b(cad[eê]|onde|t[áa]|est[áa]|sumiu).*(samuel|samuca|samuka|chefe|dono)\b"
    if re.search(padrao, texto):
        frases = carregar_json(ARQUIVOS_JSON["cade_samuel"])
        nome = nome_ou_mention(msg.from_user)
        resposta = escolher_frase(frases).replace("{nome}", nome)
        responder_com_atraso(bot.reply_to, msg, resposta)

def detectar_risadas(msg):
    texto = (msg.text or '').lower()
    user_id = msg.from_user.id
    agora = agora_brasilia()

    # Verifica se é risada
    if re.search(r"(kkk+|haha+h+|rsrs+|hehe+)", texto):
        ultima_resposta = ultimo_risada_respondida.get(user_id)
        intervalo = (agora - ultima_resposta).total_seconds() if ultima_resposta else None
        if intervalo and intervalo < random.randint(15, 60):
            return

        qtde_k = texto.count('k')

        if qtde_k >= 6:
            sticks = carregar_json(ARQUIVOS_JSON["sticks_risadas"])
            if sticks:
                responder_com_atraso(bot.reply_to, msg, random.choice(sticks))
        else:
            frases = carregar_json(ARQUIVOS_JSON["risadas"])
            nome = msg.from_user.first_name or "Espartano"
            resposta = escolher_frase(frases).replace("{nome}", nome)
            responder_com_atraso(bot.send_message, msg.chat.id, resposta)

        ultimo_risada_respondida[user_id] = agora
def enviar_alerta_repeticao(chat_id):
    linha_sirene = "🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨"
    linha1 = "💀REPETIR É COISA DE VASSALO💀"
    linha2 = "⚔️ESPARTANOS ESCREVEM COM HONRA⚔️"
    mensagem_base = f"{linha_sirene}\n{linha1}\n{linha2}\n{linha_sirene}"

    ids_msgs = []

    def enviar_e_apagar():
        for _ in range(10):  # 10 balões
            bloco = "\n".join([mensagem_base] * 5)  # 5x4 = 20 linhas por balão
            msg = bot.send_message(chat_id, bloco)
            ids_msgs.append(msg.message_id)
            time.sleep(0.5)
        time.sleep(60)
        for msg_id in ids_msgs:
            try:
                bot.delete_message(chat_id, msg_id)
            except:
                pass

    threading.Thread(target=enviar_e_apagar).start()

def detectar_madrugada(msg):
    hora = agora_brasilia().hour
    if 1 <= hora <= 5:
        frases = carregar_json(ARQUIVOS_JSON["madrugada"])
        texto = escolher_frase(frases).replace("{nome}", nome_ou_mention(msg.from_user))
        responder_com_atraso(bot.reply_to, msg, texto)

# 🎉 --- AÇÕES AGENDADAS ---
def enviar_motivacional():
    frases = carregar_json(ARQUIVOS_JSON["motivacionais"])
    frase = escolher_frase(frases).replace("{nome}", nome)
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
        frase = escolher_frase(frases).replace("{nome}", nome)
        lista_nomes = "\n".join(aniversariantes)
        bot.send_message(ID_GRUPO, f"🎉 Aniversariantes de {agora.strftime('%B')}:\n{lista_nomes}\n\n{frase}")

def relatorio_engajamento():
    if not contador_mensagens:
        return

    top3 = sorted(contador_mensagens.items(), key=lambda x: x[1], reverse=True)[:3]
    frases = carregar_json(ARQUIVOS_JSON["engajamento"])
    texto = "📊 ENGAJAMENTO DIÁRIO 🏆🏆🏆\n\n"

    if top3:
        # 🥇 Primeiro lugar
        uid1, qtd1 = top3[0]
        user1 = bot.get_chat_member(ID_GRUPO, uid1).user
        nome1 = user1.first_name
        frase_destaque = escolher_frase(frases).replace("{nome}", nome1)
        texto += f"🥇 {nome1} — 🗣️ {frase_destaque}\n\n"
        texto += f"🥇 1º lugar: {nome1} — {qtd1} msg\n"

        # 🥈 Segundo lugar
        if len(top3) > 1:
            uid2, qtd2 = top3[1]
            nome2 = bot.get_chat_member(ID_GRUPO, uid2).user.first_name
            texto += f"🥈 2º lugar: {nome2} — {qtd2} msg\n"

        # 🥉 Terceiro lugar
        if len(top3) > 2:
            uid3, qtd3 = top3[2]
            nome3 = bot.get_chat_member(ID_GRUPO, uid3).user.first_name
            texto += f"🥉 3º lugar: {nome3} — {qtd3} msg"

    # 🖼️ Enviar a imagem do troféu primeiro
    try:
        with open("trofeu_espartano.png", "rb") as img:
            bot.send_photo(ID_GRUPO, photo=img, caption="🏆")
    except Exception as e:
        print(f"❌ Erro ao enviar imagem do troféu: {e}")

    # 📊 Enviar o relatório após a imagem
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
