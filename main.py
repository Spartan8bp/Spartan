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
from collections import defaultdict

# 🛡️ --- CONFIGURAÇÕES DO BOT ---
TOKEN = '8307062095:AAE3RbmLV5p7brAPJNkDL-0nO79ejKib8Eg'
ID_GRUPO = -1002363575666
ID_DONO = 1481389775

# 🌍 Fuso horário de Brasília
FUSO_BRT = pytz.timezone('America/Sao_Paulo')

# 🚀 Inicialização do bot e Flask
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# 📂 --- ARQUIVOS JSON ---
ARQUIVOS_JSON = {
    "bem_vindas": "frases_regras_bemvindo.json",
    "cade_samuel": "frases_cade_samuel.json",
    "madrugada": "frases_madrugada.json",
    "motivacionais": "frases_motivacionais.json",
    "aniversarios_dia": "frases_aniversario_dia.json",
    "aniversarios_mes": "frases_aniversario_mes.json",
    "despedidas": "frases_despedida.json",
    "sem_perfil": "frases_advertencia_sem_perfil.json",
    "engajamento": "frases_mais_engajado.json",
    "dados_aniversarios": "aniversarios_dia.json",
    "dados_mes": "aniversarios_mes.json",
    "sticks_risadas": "sticks_risadas.json"
}

# garante que o arquivo de sticks exista
if not os.path.exists(ARQUIVOS_JSON["sticks_risadas"]):
    with open(ARQUIVOS_JSON["sticks_risadas"], "w", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False, indent=2)

# 🔁 Engajamento
contador_mensagens = {}
usuarios_sem_perfil_avisados = set()
historico_mensagens = defaultdict(list)

# ⚙️ Anti-flood para risadas
COOLDOWN_RISADA_SEG = int(os.getenv("COOLDOWN_RISADA_SEG", 300))  # 5 min padrão
PROB_RISADA = float(os.getenv("PROB_RISADA", 0.15))               # 15% de chance
ultimo_risada_por_chat = {}  # chat_id -> timestamp do último envio

# Compila o regex uma vez só (mais leve)
RISADA_RE = re.compile(r"(kkk+|ha(?:ha)+h*|rsrs+|hehe+)", re.IGNORECASE)

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
    return f"@{user.username}" if user.username else user.first_name or "Usuário"

def sem_usuario(user):
    return not bool(user.username)

# lock para escrita segura no arquivo de sticks
sticks_lock = threading.Lock()

def salvar_json_lista(caminho, dados):
    try:
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"❌ Erro ao salvar {caminho}: {e}")
        return False

# 🕒 Responder com atraso
def responder_com_atraso(funcao_envio, *args, delay=20, **kwargs):
    def enviar():
        time.sleep(delay)
        funcao_envio(*args, **kwargs)
    threading.Thread(target=enviar).start()

# 📢 --- HANDLERS ---
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

@bot.message_handler(func=lambda msg: True)
def monitorar_mensagens(msg):
    user = msg.from_user
    contador_mensagens[user.id] = contador_mensagens.get(user.id, 0) + 1

    if sem_usuario(user) and (user.id not in usuarios_sem_perfil_avisados):
        frases = carregar_json(ARQUIVOS_JSON["sem_perfil"])
        nome = nome_ou_mention(user)
        texto = escolher_frase(frases).replace("{nome}", nome)
        responder_com_atraso(bot.reply_to, msg, f"⚠️ {texto}")
        usuarios_sem_perfil_avisados.add(user.id)

    detectar_cade_samuel(msg)
    detectar_risadas(msg)
    detectar_madrugada(msg)

@bot.message_handler(commands=['addstick'])
def cmd_addstick(message):
    # só funciona no PRIVADO com o bot (silencioso fora do privado)
    if message.chat.type != 'private':
        return

    # só o DONO pode usar
    if message.from_user.id != ID_DONO:
        return

    # duas formas de uso:
    # a) responder a um sticker com /addstick  (preferida → usa file_id)
    # b) /addstick <link_ou_file_id>
    novo = None

    # a) se respondeu a um sticker
    if message.reply_to_message and message.reply_to_message.sticker:
        novo = message.reply_to_message.sticker.file_id

    # b) argumento de texto
    if not novo:
        partes = (message.text or "").split(maxsplit=1)
        if len(partes) > 1:
            novo = partes[1].strip()

    if not novo:
        bot.reply_to(
            message,
            "Como usar:\n"
            "• Responda a um sticker com: /addstick\n"
            "• Ou envie: /addstick <file_id ou link>\n\n"
            "Dica: responder a um sticker é o mais seguro (usa o file_id)."
        )
        return

    # carrega a lista, evita duplicado, salva
    with sticks_lock:
        lista = carregar_json(ARQUIVOS_JSON['sticks_risadas'])
        if not isinstance(lista, list):
            lista = []

        if novo in lista:
            bot.reply_to(message, "Esse sticker já está na lista ✅")
            return

        lista.append(novo)
        ok = salvar_json_lista(ARQUIVOS_JSON['sticks_risadas'], lista)

    if ok:
        bot.reply_to(message, f"Adicionado! Agora são {len(lista)} stickers na lista.")
    else:
        bot.reply_to(message, "❌ Não consegui salvar. Veja os logs do servidor.")

@bot.message_handler(commands=['countsticks'])
def cmd_countsticks(message):
    if message.chat.type != 'private' or message.from_user.id != ID_DONO:
        return
    lista = carregar_json(ARQUIVOS_JSON['sticks_risadas'])
    total = len(lista) if isinstance(lista, list) else 0
    bot.reply_to(message, f"Total de stickers cadastrados: {total}")

def detectar_cade_samuel(msg):
    texto = (msg.text or '').lower()
    padrao = r"\b(cad[eê]|onde|t[áa]|est[áa]|sumiu).*(samuel|samuca|samuka|chefe|dono)\b"
    if re.search(padrao, texto):
        frases = carregar_json(ARQUIVOS_JSON["cade_samuel"])
        nome = nome_ou_mention(msg.from_user)
        resposta = escolher_frase(frases).replace("{nome}", nome)
        responder_com_atraso(bot.reply_to, msg, resposta)

def detectar_risadas(msg):
    texto = (msg.text or '')
    if not texto:
        return

    # Bate com "kkk", "hahaha", "rsrs", "hehe" etc.
    if not RISADA_RE.search(texto):
        return

    chat_id = msg.chat.id
    agora = time.time()

    # Respeita cooldown por chat
    ultimo = ultimo_risada_por_chat.get(chat_id, 0)
    if agora - ultimo < COOLDOWN_RISADA_SEG:
        return

    # Chance de responder (quanto menor, menos respostas)
    if random.random() > PROB_RISADA:
        return

    sticks = carregar_json(ARQUIVOS_JSON["sticks_risadas"])
    if sticks:
        ultimo_risada_por_chat[chat_id] = agora
        responder_com_atraso(bot.send_sticker, chat_id, random.choice(sticks), delay=5)

def detectar_madrugada(msg):
    hora = agora_brasilia().hour
    if 1 <= hora <= 5:
        frases = carregar_json(ARQUIVOS_JSON["madrugada"])
        texto = escolher_frase(frases).replace("{nome}", nome_ou_mention(msg.from_user))
        responder_com_atraso(bot.reply_to, msg, texto)

# 🎉 --- AÇÕES AGENDADAS ---
def enviar_motivacional():
    frases = carregar_json(ARQUIVOS_JSON["motivacionais"])
    frase = escolher_frase(frases).replace("{nome}", "Espartanos")
    bot.send_message(ID_GRUPO, f"💪 {frase}")

def parabens_aniversariantes():
    hoje_dia = agora_brasilia().day
    hoje_mes = agora_brasilia().month
    aniversarios = carregar_json(ARQUIVOS_JSON["dados_aniversarios"])
    frases = carregar_json(ARQUIVOS_JSON["aniversarios_dia"])
    for usuario, data in aniversarios.items():
        if isinstance(data, dict) and data.get("dia") == hoje_dia and data.get("mes") == hoje_mes:
            mensagem = escolher_frase(frases).replace("{usuario}", usuario)
            bot.send_message(ID_GRUPO, f"🎈 Feliz aniversário, {usuario}! 🎉\n{mensagem}")

def parabens_do_mes():
    agora = agora_brasilia()
    ultimo_dia = (agora + datetime.timedelta(days=1)).day == 1
    if ultimo_dia:
        mes = agora.month
        aniversariantes = carregar_json(ARQUIVOS_JSON["dados_mes"]).get(str(mes), [])
        frases = carregar_json(ARQUIVOS_JSON["aniversarios_mes"])
        frase = escolher_frase(frases).replace("{nome}", "Espartanos")
        lista_nomes = "\n".join(aniversariantes)
        bot.send_message(ID_GRUPO, f"🎉 Aniversariantes de {agora.strftime('%B')}:\n{lista_nomes}\n\n{frase}")

def relatorio_engajamento():
    if not contador_mensagens:
        return
    top3 = sorted(contador_mensagens.items(), key=lambda x: x[1], reverse=True)[:3]
    frases = carregar_json(ARQUIVOS_JSON["engajamento"])
    texto = "📊 ENGAJAMENTO DIÁRIO 🏆🏆🏆\n\n"
    if top3:
        uid1, qtd1 = top3[0]
        user1 = bot.get_chat_member(ID_GRUPO, uid1).user
        nome1 = user1.first_name
        frase_destaque = escolher_frase(frases).replace("{nome}", nome1)
        texto += f"🥇 {nome1} — 🗣️ {frase_destaque}\n\n"
        texto += f"🥇 1º lugar: {nome1} — {qtd1} msg\n"
        if len(top3) > 1:
            uid2, qtd2 = top3[1]
            nome2 = bot.get_chat_member(ID_GRUPO, uid2).user.first_name
            texto += f"🥈 2º lugar: {nome2} — {qtd2} msg\n"
        if len(top3) > 2:
            uid3, qtd3 = top3[2]
            nome3 = bot.get_chat_member(ID_GRUPO, uid3).user.first_name
            texto += f"🥉 3º lugar: {nome3} — {qtd3} msg"
    try:
        with open("trofeu_espartano.png", "rb") as img:
            bot.send_photo(ID_GRUPO, photo=img, caption="🏆")
    except Exception as e:
        print(f"❌ Erro ao enviar imagem do troféu: {e}")
    bot.send_message(ID_GRUPO, texto)
    contador_mensagens.clear()

# 🔁 --- AGENDADOR ---
def agendador():
    while True:
        agora = agora_brasilia()
        hora_minuto = agora.strftime('%H:%M')
        if hora_minuto == "07:00":
            enviar_motivacional()
        if "21:39" <= hora_minuto <= "21:40":
            parabens_aniversariantes()
        if hora_minuto == "11:00":
            parabens_do_mes()
        if hora_minuto == "23:50":
            relatorio_engajamento()
        time.sleep(60)

threading.Thread(target=agendador).start()

# 🌐 --- FLASK WEBHOOK ---
@app.route("/", methods=["POST"])
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
