import sqlite3
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta, timezone
import os
from google import genai

# ============================================================================
# CONFIGURATION (Updated with New Bot Token)
# ============================================================================
BOT_TOKEN = "8674828979:AAHktLPCEnsxSH6ypBy_8q6Ie5b_FIFFw1U"
GEMINI_API_KEY = "AQ.Ab8RN6JxVySBYSvVko8R_EeafKE_Hhli1zS2sok1YevqqrxREQ"
ADMIN_ID = 8065105992

PAYMENT_LINK = "https://t.me/payment3444"

bot = telebot.TeleBot(BOT_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# မြန်မာစံတော်ချိန် (MMT = UTC + 6:30)
MMT = timezone(timedelta(hours=6, minutes=30))

def get_mmt_now():
    return datetime.now(MMT)

# ============================================================================
# DATABASE SETUP (Packages & Prices in MMK / THB)
# ============================================================================
def init_db():
    conn = sqlite3.connect('vip_bot.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            package_name TEXT,
            date TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS packages (
            id TEXT PRIMARY KEY,
            name TEXT,
            price_mmk REAL,
            price_thb REAL,
            link TEXT
        )
    ''')
    
    # VIP Packages ၇ ခုနှင့် ဈေးနှုန်းများ (MMK / THB)
    default_packages = [
        ('all_in', 'အကုန်ဝင် (All Access)', 50000, 300, 'https://t.me/+n4-uKuYVkZY3YWFl'),
        ('shan', 'ရှမ်းကား', 30000, 250, 'https://t.me/+3JPO0ZdkgHdmYjNl'),
        ('kalay', 'ကလေးကား', 10000, 100, 'လင့်ခ်မရှိသေးပါ'),
        ('parking', 'ပါကင်', 10000, 100, 'လင့်ခ်မရှိသေးပါ'),
        ('cele', 'မြန်မာဆယ်လီ', 10000, 100, 'လင့်ခ်မရှိသေးပါ'),
        ('china', 'တရုတ်ကား/နိုင်ငံခြား', 10000, 100, 'လင့်ခ်မရှိသေးပါ'),
        ('solo', 'Solo', 10000, 100, 'လင့်ခ်မရှိသေးပါ')
    ]
    
    for pkg_id, name, price_mmk, price_thb, link in default_packages:
        cursor.execute("INSERT OR IGNORE INTO packages (id, name, price_mmk, price_thb, link) VALUES (?, ?, ?, ?, ?)", 
                       (pkg_id, name, price_mmk, price_thb, link))
        
    conn.commit()
    conn.close()

init_db()

user_selected_pkg = {}
admin_states = {}

# ============================================================================
# START / MENU
# ============================================================================
@bot.message_handler(commands=['start', 'menu'])
def handle_start(message):
    user_id = message.from_user.id

    if user_id == ADMIN_ID:
        text = (
            "👑 **Admin စီမံခန့်ခွဲမှု ပန်နယ်** 👑\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "ချန်နယ်လင့်ခ်များနှင့် ဈေးနှုန်းများကို ဤနေရာတွင် ပြင်ဆင်နိုင်ပါသည်။"
        )
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("⚙️ VIP Packages & Links များကို ပြင်ဆင်ရန်", callback_data="admin_edit_pkgs"))
        markup.row(InlineKeyboardButton("📊 ရောင်းအားစာရင်း ကြည့်ရန်", callback_data="admin_view_sales"))
        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")
    else:
        send_packages_menu(message.chat.id)

def send_packages_menu(chat_id):
    conn = sqlite3.connect('vip_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price_mmk, price_thb FROM packages")
    pkgs = cursor.fetchall()
    conn.close()

    text = (
        "🌟 **VIP Member Store** 🌟\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "ဝယ်ယူလိုသော Package ကို အောက်ပါခလုတ်များမှ ရွေးချယ်ပါ -\n"
    )
    
    markup = InlineKeyboardMarkup()
    for pkg_id, name, p_mmk, p_thb in pkgs:
        btn_text = f"📌 {name} - {p_mmk:,.0f} MMK / {p_thb} THB"
        markup.row(InlineKeyboardButton(btn_text, callback_data=f"buy_{pkg_id}"))

    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

# ============================================================================
# PACKAGE SELECTION
# ============================================================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def handle_buy_package(call):
    user_id = call.from_user.id
    pkg_id = call.data.split("_", 1)[1]

    conn = sqlite3.connect('vip_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name, price_mmk, price_thb, link FROM packages WHERE id = ?", (pkg_id,))
    pkg = cursor.fetchone()
    conn.close()

    if not pkg:
        bot.answer_callback_query(call.id, "Package မရှိတော့ပါ။")
        return

    name, p_mmk, p_thb, link = pkg
    user_selected_pkg[user_id] = pkg_id

    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("💳 ငွေလွှဲရန် အကောင့်/လင့်ခ် ကြည့်ရန်", url=PAYMENT_LINK))

    text = (
        f"✅ သင်ရွေးချယ်ထားသည် - **{name}**\n"
        f"💰 ကျသင့်ငွေ - **{p_mmk:,.0f} MMK** (သို့မဟုတ်) **{p_thb} THB**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"🏦 **ငွေလွှဲရန် အကောင့်များကြည့်ရန် အောက်ပါ ခလုတ်ကို နှိပ်ပါ:**\n"
        f"👉 {PAYMENT_LINK}\n\n"
        "📥 ငွေလွှဲပြီးပါက **ငွေလွှဲစလစ် (Slip) ပုံကို ဤချတ်ထဲသို့ တိုက်ရိုက် ပို့ပေးပါ**။ "
        "AI မှ စလစ်စစ်ဆေးပြီး Group လင့်ခ် အလိုအလျောက် ပို့ပေးပါမည်ရှင်။ ✨"
    )
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

# ============================================================================
# MULTILINGUAL AI CHATBOT HANDLER (မြန်မာ၊ ရှမ်း၊ ထိုင်း၊ တရုတ်၊ အင်္ဂလိပ်)
# ============================================================================
@bot.message_handler(func=lambda msg: msg.from_user.id != ADMIN_ID, content_types=['text'])
def handle_customer_chat(message):
    user_text = message.text.strip()

    if user_text.lower() in ['/start', '/menu']:
        handle_start(message)
        return

    conn = sqlite3.connect('vip_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name, price_mmk, price_thb FROM packages")
    pkgs = cursor.fetchall()
    conn.close()

    pkg_info_str = "\n".join([f"- {name}: {p_mmk:,.0f} MMK ({p_thb} THB)" for name, p_mmk, p_thb in pkgs])

    system_prompt = (
        "You are a friendly, polite, and intelligent Customer Service AI Assistant for a Telegram VIP Channel Sales Bot.\n"
        "MULTILINGUAL SUPPORT REQUIREMENT:\n"
        "Detect the language used by the user in their message and RESPOND IN THE EXACT SAME LANGUAGE.\n"
        "Supported primary languages: Myanmar (မြန်မာ), Shan (တႆး), Thai (ไทย), Chinese (中文), and English.\n\n"
        f"CURRENT VIP PACKAGES & PRICES:\n{pkg_info_str}\n\n"
        f"PAYMENT DETAILS LINK: {PAYMENT_LINK}\n\n"
        "INSTRUCTIONS FOR YOU:\n"
        "1. Detect the user's language and respond naturally, warmly, and politely in that same language.\n"
        "2. Answer questions about prices (both MMK and THB), available VIP packages, and payment methods accurately.\n"
        "3. Explain that they can start buying by clicking /start or selecting a package, then pay using the payment link and send the payment slip image right here in the chat.\n"
        "4. Keep the output helpful, concise, well-formatted, and human-like."
    )

    try:
        bot.send_chat_action(message.chat.id, 'typing')
        
        response = ai_client.models.generate_content(
            model='gemini-1.5-flash',
            contents=[system_prompt, f"Customer Message: {user_text}"]
        )
        
        reply_text = response.text.strip()
        bot.send_message(message.chat.id, reply_text)

    except Exception as e:
        print(f"Chat AI Error: {e}")
        bot.send_message(message.chat.id, "မင်္ဂလာပါရှင်! VIP Member ဝယ်ယူရန် /start ကို နှိပ်၍ Package ရွေးချယ်နိုင်ပါတယ်ရှင်။ ✨")

# ============================================================================
# MULTILINGUAL AI SLIP VERIFICATION (MMK & THB Rules)
# ============================================================================
@bot.message_handler(content_types=['photo'])
def handle_slip_photo(message):
    user_id = message.from_user.id

    if user_id == ADMIN_ID:
        bot.send_message(message.chat.id, "ℹ️ Admin ပို့သော ပုံဖြစ်သဖြင့် စလစ်စစ်ဆေးခြင်း မပြုလုပ်ပါ။")
        return

    pkg_id = user_selected_pkg.get(user_id)
    if not pkg_id:
        bot.send_message(message.chat.id, "❌ ကျေးဇူးပြု၍ ပထမဦးစွာ ဝယ်ယူမည့် Package ကို ရွေးချယ်ပေးပါရှင်။ /start ကို နှိပ်ပါ။")
        return

    conn = sqlite3.connect('vip_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name, price_mmk, price_thb, link FROM packages WHERE id = ?", (pkg_id,))
    pkg = cursor.fetchone()
    conn.close()

    pkg_name, exp_mmk, exp_thb, group_link = pkg
    current_time_str = get_mmt_now().strftime('%Y-%m-%d %H:%M:%S')

    bot.send_message(message.chat.id, "⏳ ငွေလွှဲစလစ်ကို AI ဖြင့် စစ်ဆေးနေပါပြီ ခဏစောင့်ပါ...")

    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        temp_slip_path = f"slip_{user_id}.jpg"
        with open(temp_slip_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        gemini_file = ai_client.files.upload(file=temp_slip_path)

        prompt = (
            f"You are a strict payment slip verification AI for a business.\n"
            f"Current Myanmar Standard Time (MMT) right now: {current_time_str}.\n"
            f"Expected package price: {exp_mmk} MMK OR {exp_thb} THB.\n\n"
            "RULES FOR VERIFICATION:\n"
            "1. Currency / Payment Type Check:\n"
            "   - IF MMK Slip (KBZPay, Wave, Bank): Receiver Name MUST contain 'Mg Nyein Chan' or 'Nyein Chan'. Time on slip must be within 5 minutes of current MMT time. Amount must match or exceed expected MMK price ({exp_mmk} MMK).\n"
            "   - IF Thai Baht (THB) Slip: Receiver Name MUST contain 'Aung Kyaw Myint' or 'nan noon inter'. Time difference can be up to 30 minutes from MMT time. Amount must match or exceed expected THB price ({exp_thb} THB).\n"
            "   - IF Receiver Name does NOT match these exact names, REJECT the slip.\n"
            "2. Output strictly in this format:\n"
            "Valid: YES (or NO)\n"
            "Reason: [Short polite explanation matching the slip's native language context or Myanmar/English]"
        )

        response = ai_client.models.generate_content(
            model='gemini-1.5-flash',
            contents=[gemini_file, prompt]
        )

        ai_result = response.text.strip()

        if os.path.exists(temp_slip_path):
            os.remove(temp_slip_path)

        if "Valid: YES" in ai_result:
            now_str = get_mmt_now().strftime('%Y-%m-%d %H:%M:%S')
            conn = sqlite3.connect('vip_bot.db')
            cursor = conn.cursor()
            cursor.execute("INSERT INTO transactions (user_id, amount, package_name, date) VALUES (?, ?, ?, ?)",
                           (user_id, exp_mmk, pkg_name, now_str))
            conn.commit()
            conn.close()

            user_selected_pkg.pop(user_id, None)

            success_text = (
                f"✅ **စလစ် စစ်ဆေးမှု အောင်မြင်ပါသည်!** 🎉\n"
                f"📌 ဝယ်ယူသည့် Package: **{pkg_name}**\n\n"
                f"🔗 **သင့်အတွက် VIP Group ဖိတ်ကြားချက် လင့်ခ်:**\n"
                f"👉 {group_link}\n\n"
                "ကျေးဇူးတင်ပါသည်ရှင်! ✨"
            )
            bot.send_message(message.chat.id, success_text, parse_mode="Markdown")
        else:
            fail_text = (
                "❌ **စလစ် စစ်ဆေးမှု မအောင်မြင်ပါ။**\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                f"💡 **အကြောင်းအရင်း -**\n{ai_result}\n\n"
                f"ကျေးဇူးပြု၍ စလစ်ပုံ မှန်ကန်မှု ရှိမရှိ ပြန်လည်စစ်ဆေးပြီး ပို့ပေးပါရှင်။ သို့မဟုတ် {PAYMENT_LINK} တွင် စစ်ဆေးနိုင်ပါသည်။ 🙏"
            )
            bot.send_message(message.chat.id, fail_text, parse_mode="Markdown")

    except Exception as e:
        print(f"Error: {e}")
        bot.send_message(message.chat.id, "❌ စလစ် စစ်ဆေးရာတွင် အမှားအယွင်း ရှိသွားပါသည်။ ခဏနေမှ ထပ်ကြိုးစားပေးပါ။")

# ============================================================================
# ADMIN SETTING / LINK & PRICE EDITING
# ============================================================================
@bot.callback_query_handler(func=lambda call: call.data == "admin_edit_pkgs")
def admin_edit_pkgs(call):
    if call.from_user.id != ADMIN_ID:
        return

    conn = sqlite3.connect('vip_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM packages")
    pkgs = cursor.fetchall()
    conn.close()

    markup = InlineKeyboardMarkup()
    for pkg_id, name in pkgs:
        markup.row(InlineKeyboardButton(f"✏️ {name} ကို ပြင်ရန်", callback_data=f"edit_pkg_{pkg_id}"))
    markup.row(InlineKeyboardButton("🔙 ပင်မမီနူးသို့", callback_data="admin_back_main"))

    bot.edit_message_text("⚙️ ပြင်ဆင်လိုသော Package ကို ရွေးပါ -", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("edit_pkg_"))
def edit_specific_pkg(call):
    if call.from_user.id != ADMIN_ID:
        return
    pkg_id = call.data.split("_", 2)[2]

    conn = sqlite3.connect('vip_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name, price_mmk, price_thb, link FROM packages WHERE id = ?", (pkg_id,))
    pkg = cursor.fetchone()
    conn.close()

    name, p_mmk, p_thb, link = pkg
    admin_states[ADMIN_ID] = {"action": "editing_pkg", "pkg_id": pkg_id}

    text = (
        f"📦 **Package:** {name}\n"
        f"💰 **လက်ရှိ ဈေးနှုန်း:** {p_mmk:,.0f} MMK / {p_thb} THB\n"
        f"🔗 **လက်ရှိ လင့်ခ်:** {link}\n\n"
        "✍️ **အသစ်ပြောင်းလဲရန် ပုံစံအတိုင်း ရိုက်ပို့ပေးပါ:**\n"
        "`[MMK ဈေးနှုန်း] [THB ဈေးနှုန်း] [လင့်ခ်]`\n"
        "ဥပမာ: `35000 250 https://t.me/+xyz123`"
    )
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("🔙 မီးနူးသို့", callback_data="admin_edit_pkgs"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.from_user.id == ADMIN_ID, content_types=['text'])
def handle_admin_text(message):
    state = admin_states.get(ADMIN_ID)
    if state and state.get("action") == "editing_pkg":
        pkg_id = state.get("pkg_id")
        parts = message.text.strip().split(maxsplit=2)
        
        if len(parts) >= 3:
            try:
                new_mmk = float(parts[0].replace(",", ""))
                new_thb = float(parts[1].replace(",", ""))
                new_link = parts[2].strip()

                conn = sqlite3.connect('vip_bot.db')
                cursor = conn.cursor()
                cursor.execute("UPDATE packages SET price_mmk = ?, price_thb = ?, link = ? WHERE id = ?", (new_mmk, new_thb, new_link, pkg_id))
                conn.commit()
                conn.close()

                admin_states.pop(ADMIN_ID, None)
                bot.send_message(message.chat.id, f"✅ Package ဈေးနှုန်းနှင့် လင့်ခ် အောင်မြင်စွာ ပြောင်းလဲပြီးပါပြီရှင်! ✨")
                send_packages_menu(message.chat.id)
                return
            except ValueError:
                pass
        
        bot.send_message(message.chat.id, "❌ ပုံစံ မှားယွင်းနေပါသည်။ ဥပမာ - `35000 250 https://t.me/+xyz123` ဟု ရိုက်ထည့်ပေးပါ။")

@bot.callback_query_handler(func=lambda call: call.data == "admin_view_sales")
def admin_view_sales(call):
    if call.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('vip_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT amount, package_name, date FROM transactions ORDER BY id DESC LIMIT 10")
    rows = cursor.fetchall()
    conn.close()

    text = "📊 **နောက်ဆုံးရောင်းအား မှတ်တမ်း (၁၀ ခု)**\n━━━━━━━━━━━━━━━━━━━\n"
    if not rows:
        text += "ရောင်းအား မှတ်တမ်း မရှိသေးပါ။\n"
    else:
        for r in rows:
            text += f"• {r[2][:16]} | {r[1]} | {r[0]:,.0f} MMK\n"
    
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("🔙 ပင်မမီနူးသို့", callback_data="admin_back_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "admin_back_main")
def admin_back_main(call):
    if call.from_user.id != ADMIN_ID:
        return
    admin_states.pop(ADMIN_ID, None)
    text = "👑 **Admin စီမံခန့်ခွဲမှု ပန်နယ်** 👑"
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("⚙️ VIP Packages & Links များကို ပြင်ဆင်ရန်", callback_data="admin_edit_pkgs"))
    markup.row(InlineKeyboardButton("📊 ရောင်းအားစာရင်း ကြည့်ရန်", callback_data="admin_view_sales"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    print("Multilingual VIP Bot is running successfully with New Token...")
    bot.infinity_polling(skip_pending=True)
