import sqlite3, datetime, random, time, os, threading, telebot
from telebot import types
from telebot.apihelper import ApiTelegramException
from http.server import HTTPServer, BaseHTTPRequestHandler

# ----------------- ВЕБ-СЕРВЕР ДЛЯ 24/7 (UPTIMEROBOT / RENDER) -----------------
class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("FamilyNest Bot is running 24/7!".encode("utf-8"))

def start_ping_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), PingHandler)
    server.serve_forever()

threading.Thread(target=start_ping_server, daemon=True).start()

# ----------------- НАЛАШТУВАННЯ ТЕЛЕГРАМ БОТА -----------------
TOKEN = "8842183639:AAEhvvR41dzyHZeh1bo-61a9kjsiXEFsia8"
bot = telebot.TeleBot(TOKEN)
DB = "baby_render.db"

def normalize_code(c):
    c = c.strip().upper().replace(" ", "").replace("—", "-").replace("–", "-").replace("_", "-")
    tr = str.maketrans("ВАУ", "BAY")
    c = c.translate(tr)
    if not c.startswith("BABY-") and len(c) == 4 and c.isdigit():
        c = f"BABY-{c}"
    elif not c.startswith("BABY-") and len(c) > 4:
        c = f"BABY-{c.replace('BABY', '')}"
    return c

def q(sql, p=(), one=False):
    with sqlite3.connect(DB, timeout=20.0) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(sql, p)
        conn.commit()
        return c.fetchone() if one else None

def init_db():
    q('''CREATE TABLE IF NOT EXISTS fam (
        id INTEGER PRIMARY KEY, code TEXT UNIQUE, p1_id INT, p1_name TEXT, p1_role TEXT,
        p2_id INT, p2_name TEXT, p2_role TEXT, baby TEXT, gender TEXT, born TEXT,
        hunger INT DEFAULT 80, happy INT DEFAULT 80, energy INT DEFAULT 80, hygiene INT DEFAULT 80,
        sleep INT DEFAULT 0, love INT DEFAULT 0, updated TEXT, last_act TEXT)''')
    q('CREATE TABLE IF NOT EXISTS state (uid INT PRIMARY KEY, st TEXT, d TEXT)')

def get_fam(u):
    return q("SELECT * FROM fam WHERE p1_id=? OR p2_id=?", (u, u), one=True)

def bar(v):
    v = max(0, min(100, int(v)))
    return f"[{'▰'*(v//10)}{'▱'*(10-(v//10))}] {v}%"

def decay(f):
    now = datetime.datetime.now()
    try: last = datetime.datetime.fromisoformat(f['updated'])
    except: last = now
    dt = (now - last).total_seconds() / 3600.0
    if dt > 0.05:
        h, hp, hy = max(0, int(f['hunger'] - dt*6)), max(0, int(f['happy'] - dt*5)), max(0, int(f['hygiene'] - dt*4))
        en = min(100, int(f['energy'] + dt*25)) if f['sleep'] else max(0, int(f['energy'] - dt*5))
        q("UPDATE fam SET hunger=?, happy=?, energy=?, hygiene=?, updated=? WHERE id=?",
          (h, hp, en, hy, now.isoformat(), f['id']))
        return q("SELECT * FROM fam WHERE id=?", (f['id'],), one=True)
    return f

def thoughts(f):
    if f['sleep']: return "😴 *солодко сопе у ліжечку... хрр-псс*"
    if f['hunger'] < 30: return "😭 *«Хочу молочка! Животик бурчить!»*"
    if f['hygiene'] < 30: return "🙈 *«Терміново змініть мені підгузок!»*"
    if f['happy'] < 35: return "🥺 *«Хочу обіймів або пограймося!»*"
    quotes = ["«Ви найкращі мама й тато у світі! ❤️»", "«А коли ми підемо гуляти в парк? 🌳»", "«Дивіться, як я вмію сміятися! 🧸»"]
    return random.choice(quotes)

def card(f):
    f = decay(f)
    g = "👦" if f['gender'] == 'boy' else "👧"
    try: age = max(0, (datetime.datetime.now() - datetime.datetime.fromisoformat(f['born'])).days)
    except: age = 0
    p2 = f" & {f['p2_role']} {f['p2_name']}" if f['p2_name'] else f" (код: <code>{f['code']}</code>)"
    st = "😴 Спить" if f['sleep'] else "😊 Бадьорий"
    return (f"✨ <b>{f['baby']}</b> {g} ✨\n"
            f"👨‍👩‍👧 Батьки: {f['p1_role']} {f['p1_name']}{p2}\n"
            f"🎂 Вік: {age} дн. | Стан: <b>{st}</b> | 💖 Любов: {f['love']}\n\n"
            f"🍼 Ситість:  <code>{bar(f['hunger'])}</code>\n"
            f"🧸 Настрій:  <code>{bar(f['happy'])}</code>\n"
            f"⚡ Енергія:  <code>{bar(f['energy'])}</code>\n"
            f"🛁 Чистота:  <code>{bar(f['hygiene'])}</code>\n\n"
            f"💭 <i>{thoughts(f)}</i>\n"
            f"📝 <i>{f['last_act']}</i>")

def kb(f):
    k = types.InlineKeyboardMarkup(row_width=2)
    s = "☀️ Розбудити" if f['sleep'] else "💤 Спати"
    k.add(types.InlineKeyboardButton("🍼 Нагодувати (+25%)", callback_data="a_feed"),
          types.InlineKeyboardButton("🧸 Погратися (+25%)", callback_data="a_play"))
    k.add(types.InlineKeyboardButton("🛁 Викупати (+35%)", callback_data="a_bath"),
          types.InlineKeyboardButton(s, callback_data="a_sleep"))
    k.add(types.InlineKeyboardButton("💋 Надіслати цьом", callback_data="a_kiss"),
          types.InlineKeyboardButton("🎲 Кубик", callback_data="a_dice"))
    k.add(types.InlineKeyboardButton("💭 Правда/Дія", callback_data="a_truth"),
          types.InlineKeyboardButton("💌 Записка", callback_data="a_note"))
    k.add(types.InlineKeyboardButton("🔄 Оновити", callback_data="a_ref"))
    return k

def safe_edit(c, text, reply_markup=None):
    try: bot.edit_message_text(text, c.message.chat.id, c.message.message_id, parse_mode="HTML", reply_markup=reply_markup)
    except: pass

def notify(f, sender, msg):
    other = f['p2_id'] if sender == f['p1_id'] else f['p1_id']
    if other:
        try: bot.send_message(other, msg, parse_mode="HTML")
        except: pass

def show_welcome(u):
    k = types.InlineKeyboardMarkup()
    k.add(types.InlineKeyboardButton("🐣 Створити сім'ю та малюка", callback_data="c_baby"))
    k.add(types.InlineKeyboardButton("🔗 Приєднатися за кодом", callback_data="j_fam"))
    bot.send_message(u, "👋 <b>Ласкаво просимо до FamilyNest!</b>\n\nТут ви разом зі своєю половинкою можете доглядати за малюком та грати в ігри.\n\nОберіть дію:", parse_mode="HTML", reply_markup=k)

# ----------------- КОМАНДИ І ОБРОБНИКИ -----------------
@bot.message_handler(commands=['start'])
def start(m):
    u = m.from_user.id
    f = get_fam(u)
    if f:
        return bot.send_message(u, card(f), parse_mode="HTML", reply_markup=kb(f))
    
    args = m.text.split()
    if len(args) > 1:
        code = normalize_code(args)
        target = q("SELECT * FROM fam WHERE code=?", (code,), one=True)
        if target:
            if target['p2_id']:
                return bot.send_message(u, "⚠️ У цієї сім'ї вже є обоє батьків!")
            q("INSERT OR REPLACE INTO state VALUES (?, 'j_role', ?)", (u, str(target['id'])))
            k = types.InlineKeyboardMarkup()
            k.add(types.InlineKeyboardButton("👩 Мама", callback_data="jr_Мама"),
                  types.InlineKeyboardButton("👨 Тато", callback_data="jr_Тато"))
            return bot.send_message(u, f"🎉 Знайдено малюка <b>{target['baby']}</b>!\nХто ти для нього?", parse_mode="HTML", reply_markup=k)
    
    show_welcome(u)

@bot.callback_query_handler(func=lambda c: c.data in ["c_baby", "j_fam"])
def on_init(c):
    u = c.from_user.id
    bot.answer_callback_query(c.id)
    if c.data == "c_baby":
        q("INSERT OR REPLACE INTO state VALUES (?, 'name', '')", (u,))
        safe_edit(c, "🍼 <b>Як назвемо малюка?</b>\nНапишіть ім'я у відповідь повідомленням:")
    else:
        q("INSERT OR REPLACE INTO state VALUES (?, 'code', '')", (u,))
        safe_edit(c, "🔗 <b>Введіть сімейний код</b> (наприклад, <code>BABY-1234</code> або 4 цифри):")

@bot.message_handler(content_types=['text'])
def on_text(m):
    u = m.from_user.id
    text = m.text.strip()
    row = q("SELECT * FROM state WHERE uid=?", (u,), one=True)
    f = get_fam(u)

    norm_code = normalize_code(text)
    if not f and norm_code.startswith("BABY-"):
        target = q("SELECT * FROM fam WHERE code=?", (norm_code,), one=True)
        if target:
            if target['p2_id']:
                return bot.send_message(u, "⚠️ У цієї сім'ї вже є обоє батьків!")
            q("INSERT OR REPLACE INTO state VALUES (?, 'j_role', ?)", (u, str(target['id'])))
            k = types.InlineKeyboardMarkup()
            k.add(types.InlineKeyboardButton("👩 Мама", callback_data="jr_Мама"),
                  types.InlineKeyboardButton("👨 Тато", callback_data="jr_Тато"))
            return bot.send_message(u, f"🎉 Знайдено малюка <b>{target['baby']}</b>!\nХто ти для нього?", parse_mode="HTML", reply_markup=k)

    if not row:
        if f: return bot.send_message(u, card(f), parse_mode="HTML", reply_markup=kb(f))
        else: return show_welcome(u)

    st, d = row['st'], row['d']
    if st == 'name':
        q("INSERT OR REPLACE INTO state VALUES (?, 'gender', ?)", (u, text))
        k = types.InlineKeyboardMarkup()
        k.add(types.InlineKeyboardButton("👦 Хлопчик", callback_data="g_boy"),
              types.InlineKeyboardButton("👧 Дівчинка", callback_data="g_girl"))
        bot.send_message(u, f"Малюк <b>{text}</b>! ✨ Хто це буде?", parse_mode="HTML", reply_markup=k)
    elif st == 'code':
        target = q("SELECT * FROM fam WHERE code=?", (norm_code,), one=True)
        if not target:
            return bot.send_message(u, f"❌ Сім'ю з кодом <b>{norm_code}</b> не знайдено.\nПеревірте правильність коду:")
        if target['p2_id']:
            q("DELETE FROM state WHERE uid=?", (u,))
            return bot.send_message(u, "⚠️ У цієї сім'ї вже є обоє батьків!")
        q("INSERT OR REPLACE INTO state VALUES (?, 'j_role', ?)", (u, str(target['id'])))
        k = types.InlineKeyboardMarkup()
        k.add(types.InlineKeyboardButton("👩 Мама", callback_data="jr_Мама"),
              types.InlineKeyboardButton("👨 Тато", callback_data="jr_Тато"))
        bot.send_message(u, f"Знайдено малюка <b>{target['baby']}</b>! 🎉 Хто ти для нього?", parse_mode="HTML", reply_markup=k)
    elif st == 'note':
        q("DELETE FROM state WHERE uid=?", (u,))
        if not f: return
        r = f['p1_role'] if u == f['p1_id'] else f['p2_role']
        n = f['p1_name'] if u == f['p1_id'] else f['p2_name']
        notify(f, u, f"💌 <b>Тобі записка від {r} ({n}):</b>\n\n«<i>{text}</i>»\n\n<i>З любов'ю біля ліжечка ❤️</i>")
        bot.send_message(u, "✅ Записку передано твоїй половинці!")

@bot.callback_query_handler(func=lambda c: c.data.startswith("g_"))
def on_g(c):
    u = c.from_user.id
    bot.answer_callback_query(c.id)
    r = q("SELECT d FROM state WHERE uid=?", (u,), one=True)
    if not r: return
    gen = "boy" if c.data == "g_boy" else "girl"
    q("INSERT OR REPLACE INTO state VALUES (?, 'role', ?)", (u, f"{r['d']}::{gen}"))
    k = types.InlineKeyboardMarkup()
    k.add(types.InlineKeyboardButton("👨 Тато", callback_data="r_Тато"),
          types.InlineKeyboardButton("👩 Мама", callback_data="r_Мама"))
    safe_edit(c, "Хто ти для малюка?", k)

@bot.callback_query_handler(func=lambda c: c.data.startswith("r_"))
def on_r(c):
    u = c.from_user.id
    bot.answer_callback_query(c.id)
    r = q("SELECT d FROM state WHERE uid=?", (u,), one=True)
    if not r: return
    baby, gen = r['d'].split("::")
    role = c.data.replace("r_", "")
    name = c.from_user.first_name or "Батько"
    code = f"BABY-{random.randint(1000, 9999)}"
    now = datetime.datetime.now().isoformat()
    q("INSERT INTO fam (code, p1_id, p1_name, p1_role, baby, gender, born, updated, last_act) VALUES (?,?,?,?,?,?,?,?,?)",
      (code, u, name, role, baby, gen, now, now, f"{role} дав(-ла) життя малюку ✨"))
    q("DELETE FROM state WHERE uid=?", (u,))
    f = get_fam(u)
    bot_info = bot.get_me()
    invite_link = f"https://t.me/{bot_info.username}?start={code}"
    safe_edit(c, f"🎉 <b>Сім'ю успішно створено!</b>\n\n"
                 f"Код сім'ї: <code>{code}</code>\n\n"
                 f"👉 <b>Посилання для дівчини:</b>\n{invite_link}\n\n" + card(f), kb(f))

@bot.callback_query_handler(func=lambda c: c.data.startswith("jr_"))
def on_jr(c):
    u = c.from_user.id
    bot.answer_callback_query(c.id)
    r = q("SELECT d FROM state WHERE uid=?", (u,), one=True)
    if not r: return
    fid, role, name = int(r['d']), c.data.replace("jr_", ""), c.from_user.first_name or "Половинка"
    q("UPDATE fam SET p2_id=?, p2_name=?, p2_role=? WHERE id=?", (u, name, role, fid))
    q("DELETE FROM state WHERE uid=?", (u,))
    f = q("SELECT * FROM fam WHERE id=?", (fid,), one=True)
    notify(f, u, f"💖 <b>Чудова новина!</b> До сім'ї приєднався(-лася) {role} {name}!")
    safe_edit(c, "💖 <b>Ви успішно приєдналися до сім'ї!</b>\n\n" + card(f), kb(f))

@bot.callback_query_handler(func=lambda c: c.data.startswith("a_"))
def on_a(c):
    u = c.from_user.id
    f = get_fam(u)

    if not f:
        bot.answer_callback_query(c.id, "Ви ще не в сім'ї! Натисніть /start", show_alert=True)
        return show_welcome(u)

    act = c.data
    role = f['p1_role'] if u == f['p1_id'] else f['p2_role']
    name = f['p1_name'] if u == f['p1_id'] else f['p2_name']
    now_str = datetime.datetime.now().strftime("%H:%M")
    now_iso = datetime.datetime.now().isoformat()
    
    if act == "a_ref":
        bot.answer_callback_query(c.id, "Оновлено! 🔄")
        return safe_edit(c, card(f), kb(f))
    if act == "a_note":
        q("INSERT OR REPLACE INTO state VALUES (?, 'note', '')", (u,))
        bot.send_message(u, "💌 <b>Напишіть текст записки</b> для вашої половинки у відповідь:")
        return bot.answer_callback_query(c.id)
    if act == "a_kiss":
        q("UPDATE fam SET love=love+1, happy=min(100, happy+10), updated=?, last_act=? WHERE id=?",
          (now_iso, f"{role} надіслав(-ла) ніжний цьомчик 💋 ({now_str})", f['id']))
        bot.answer_callback_query(c.id, "Цьомчик надіслано! 🥰")
        notify(f, u, f"💋 <b>Ніжний цьомчик!</b>\n{role} {name} надсилає тобі поцілунок та обійми! ❤️")
        return safe_edit(c, card(get_fam(u)), kb(f))
    if act == "a_dice":
        roll = random.randint(1, 6)
        msg = f"🎲 {role} {name} вибив {roll}! Хід половинки!"
        bot.answer_callback_query(c.id, f"Випало {roll}!")
        notify(f, u, msg)
        return safe_edit(c, f"🎲 <b>Битва кубиків</b>\n\n{role} вибив(-ла): <b>{roll}</b>!\nХід за половинкою 😉\n\n" + card(f), kb(f))
    if act == "a_truth":
        items = [
            "Який наш наймиліший або найсмішніший спогад ти пам'ятаєш найяскравіше?",
            "Яка моя звичка найбільше розчулює тебе або змушує посміхатися?",
            "Якби ми прямо зараз могли опинитися в будь-якому місці — куди б поїхали?",
            "Запиши 10-секундне ніжне голосове повідомлення своїй половинці прямо зараз ❤️",
            "Скинь у ваш спільний чат найулюбленіше спільне фото 📸",
            "Назви 3 причини, чому ти любиш свою половинку прямо зараз 🥰"
        ]
        chosen = random.choice(items)
        bot.answer_callback_query(c.id, "Завдання витягнуто! 🎯")
        notify(f, u, f"💭 Завдання для пари від {role}: «{chosen}»")
        return safe_edit(c, f"🎯 <b>Завдання/питання для пари:</b>\n\n👉 <b>«{chosen}»</b>\n\n" + card(f), kb(f))
    if act == "a_sleep":
        ns = 0 if f['sleep'] else 1
        t = f"{role} вклав(-ла) спати 🌙 ({now_str})" if ns else f"{role} лагідно розбудив(-ла) ☀️ ({now_str})"
        q("UPDATE fam SET sleep=?, updated=?, last_act=? WHERE id=?", (ns, now_iso, t, f['id']))
        bot.answer_callback_query(c.id, "Спить... 💤" if ns else "Прокинувся! ☀️")
        notify(f, u, f"🔔 {t}")
        return safe_edit(c, card(get_fam(u)), kb(f))

    if f['sleep']:
        return bot.answer_callback_query(c.id, "Малюк спить! Спершу розбудіть кнопкою «Розбудити» 😴", show_alert=True)
    
    h, hp, hy, en = f['hunger'], f['happy'], f['hygiene'], f['energy']
    desc = ""
    if act == "a_feed":
        h = min(100, h + 25)
        desc = f"{role} нагодував(-ла) малюка 🍼 ({now_str})"
        bot.answer_callback_query(c.id, "Малюк поїв! (+25% ситість) 🍼")
    elif act == "a_play":
        hp, en = min(100, hp + 25), max(0, en - 10)
        desc = f"{role} погрався(-лася) з малюком 🧸 ({now_str})"
        bot.answer_callback_query(c.id, "Весело погралися! (+25% настрій) 🧸")
    elif act == "a_bath":
        hy, hp = min(100, hy + 35), min(100, hp + 5)
        desc = f"{role} викупав(-ла) малюка 🛁 ({now_str})"
        bot.answer_callback_query(c.id, "Малюк чистенький! (+35% чистота) 🛁")

    q("UPDATE fam SET hunger=?, happy=?, energy=?, hygiene=?, updated=?, last_act=? WHERE id=?",
      (h, hp, en, hy, now_iso, desc, f['id']))
    notify(f, u, f"🔔 {desc}")
    safe_edit(c, card(get_fam(u)), kb(f))

# ----------------- СТАРТ -----------------
init_db()
print("Бот FamilyNest запущений на Render і готовий до роботи 24/7!")
while True:
    try:
        bot.infinity_polling(skip_pending=True, timeout=20)
    except Exception as e:
        time.sleep(3)
             
