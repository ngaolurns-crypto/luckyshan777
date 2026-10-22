import sqlite3
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime, timedelta, timezone
import os
from google import genai

# ============================================================================
# CONFIGURATION
# ============================================================================
BOT_TOKEN = "8872734998:AAGaLOgwSrw4vNgERziaCH1cTGFqnaJaNJ4"
GEMINI_API_KEY = "AQ.Ab8RN6JxVySBYSvVko8R_EeafKE_Hhli1zS2sok1YevqqrxREQ"
ADMIN_ID = 8065105992

bot = telebot.TeleBot(BOT_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# မြန်မာစံတော်ချိန် (MMT = UTC + 6:30)
MMT = timezone(timedelta(hours=6, minutes=30))

def get_mmt_now():
    return datetime.now(MMT)

# ============================================================================
# DATABASE SETUP (Packages, Links & Transactions)
# ============================================================================
def init_db():
    conn = sqlite3.connect('vip_bot.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # ဝင်ငွေ/ထွက်ငွေ စာရင်းဇယား
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            package_name TEXT,
            date TEXT
        )
    ''')
    
    # VIP Packages & Links ဇယား
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS packages (
            id TEXT PRIMARY KEY,
            name TEXT,
            price REAL,
            link TEXT
        )
    ''')
    
    # ပုံမှန် Package ၇ ခု ထည့်သွင်းခြင်း (မရှိသေးမှသာ)
    default_packages = [
        ('all_in', 'အကုန်ဝင် (All Access)', 50000, 'https://t.me/+n4-uKuYVkZY3YWFl'),
        ('shan', 'ရှမ်းကား', 30000, 'https://t.me/+3JPO0ZdkgHdmYjNl'),
        ('kalay', 'ကလေးကား', 10000, 'လင့်ခ်မရှိသေးပါ'),
        ('parking', 'ပါကင်', 10000, 'လင့်ခ်မရှိသေးပါ'),
        ('cele', 'မြန်မာဆယ်လီ', 10000, 'လင့်ခ်မရှိသေးပါ'),
        ('china', 'တရုတ်ကား/နိုင်ငံခြား', 10000, 'လင့်ခ်မရှိသေးပါ'),
        ('solo', 'Solo', 10000, 'လင့်ခ်မရှိသေးပါ')
    ]
    
    for pkg_id, name, price, link in default_packages:
        cursor.execute("INSERT OR IGNORE INTO packages (id, name, price, link) VALUES (?, ?, ?, ?)", 
                       (pkg_id, name, price, link))
        
    conn.commit()
    conn.close()

init_db()

# ယာယီအချက်အလက် သိမ်းဆည်းရန် (User ရွေးချယ်ထားသော Package မှတ်ရန်)
user_selected_pkg = {}
admin_states = {}

# ============================================================================
# CUSTOMER & ADMIN START / MENU
# ============================================================================
@bot.message_handler(commands=['start', 'menu'])
def handle_start(message):
    user_id = message.from_user.id

    if user_id == ADMIN_ID:
        # Admin Menu
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
        # Customer Menu (Packages လာပြခြင်း)
        send_packages_menu(message.chat.id)

def send_packages_menu(chat_id):
    conn = sqlite3.connect('vip_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price FROM packages")
    pkgs = cursor.fetchall()
    conn.close()

    text = (
        "🌟 **VIP Member Store မှ ကြိုဆိုပါတယ်ရှင်** 🌟\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "ဝယ်ယူလိုသော Package ကို အောက်ပါခလုတ်များမှ ရွေးချယ်ပါ -\n"
    )
    
    markup = InlineKeyboardMarkup()
    for pkg_id, name, price in pkgs:
        markup.row(InlineKeyboardButton(f"📌 {name} - {price:,.0f} MMK", callback_data=f"buy_{pkg_id}"))

    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

# ============================================================================
# CUSTOMER PACKAGE SELECTION & SLIP UPLOAD
# ============================================================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def handle_buy_package(call):
    user_id = call.from_user.id
    pkg_id = call.data.split("_", 1)[1]

    conn = sqlite3.connect('vip_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name, price, link FROM packages WHERE id = ?", (pkg_id,))
    pkg = cursor.fetchone()
    conn.close()

    if not pkg:
        bot.answer_callback_query(call.id, "Package မရှိတော့ပါ။")
        return

    name, price, link = pkg
    user_selected_pkg[user_id] = pkg_id

    text = (
        f"✅ သင်ရွေးချယ်ထားသည် - **{name}**\n"
        f"💰 ကျသင့်ငွေ - **{price:,.0f} MMK**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🏦 **ငွေလွှဲရန် အကောင့်များ:**\n"
        "• KBZ Pay: 09XXXXXXXXX (အမည် - ထည့်ရန်)\n"
        "• Wave Money: 09XXXXXXXXX (အမည် - ထည့်ရန်)\n\n"
        "📥 ငွေလွှဲပြီးပါက **ငွေလွှဲစလစ် (Slip) ပုံကို ဤချတ်ထဲသို့ တိုက်ရိုက် ပို့ပေးပါ**။ "
        "AI မှ စစ်ဆေးပြီး Group လင့်ခ် အလိုအလျောက် ပို့ပေးပါမည်ရှင်။ ✨"
    )
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

# ============================================================================
# AI SLIP VERIFICATION & AUTO INVITE LINK
# ============================================================================
@bot.message_handler(content_types=['photo'])
def handle_slip_photo(message):
    user_id = message.from_user.id

    if user_id == ADMIN_ID:
        # Admin ပို့သော ပုံဖြစ်ပါက ကျော်မည်
        return

    pkg_id = user_selected_pkg.get(user_id)
    if not pkg_id:
        bot.send_message(message.chat.id, "❌ ကျေးဇူးပြု၍ ပထမဦးစွာ ဝယ်ယူမည့် Package ကို အရင်ရွေးချယ်ပေးပါရှင်။ /start ကို နှိပ်ပါ။")
        return

    conn = sqlite3.connect('vip_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name, price, link FROM packages WHERE id = ?", (pkg_id,))
    pkg = cursor.fetchone()
    conn.close()

    pkg_name, expected_price, group_link = pkg

    bot.send_message(message.chat.id, "⏳ ငွေလွှဲစလစ်ကို AI ဖြင့် စစ်ဆေးနေပါပြီ ခဏစောင့်ပါ...")

    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        temp_slip_path = f"slip_{user_id}.jpg"
        with open(temp_slip_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        gemini_file = ai_client.files.upload(file=temp_slip_path)

        prompt = (
            f"Analyze this payment slip image carefully. "
            f"Check if it's a valid transfer slip and if the amount is at least {expected_price} MMK.\n"
            "Answer strictly in this format:\n"
            "Valid: YES or NO\n"
            "Amount: [extracted number only or 0]\n"
            "Note: [short reason]"
        )

        response = ai_client.models.generate_content(
            model='gemini-1.5-flash',
            contents=[gemini_file, prompt]
        )

        ai_result = response.text.strip()
        print(f"AI Slip Result: {ai_result}")

        if os.path.exists(temp_slip_path):
            os.remove(temp_slip_path)

        if "Valid: YES" in ai_result:
            # Database ထဲသို့ ရောင်းအား မှတ်တမ်းတင်မည်
            now_str = get_mmt_now().strftime('%Y-%m-%d %H:%M:%S')
            conn = sqlite3.connect('vip_bot.db')
            cursor = conn.cursor()
            cursor.execute("INSERT INTO transactions (user_id, amount, package_name, date) VALUES (?, ?, ?, ?)",
                           (user_id, expected_price, pkg_name, now_str))
            conn.commit()
            conn.close()

            # State ရှင်းမည်
            user_selected_pkg.pop(user_id, None)

            success_text = (
                f"✅ **စလစ် စစ်ဆေးမှု အောင်မြင်ပါသည်!** 🎉\n"
                f"📌 ဝယ်ယူသည့် Package: **{pkg_name}**\n\n"
                f"🔗 **သင့်အတွက် Group ဖိတ်ကြားချက် လင့်ခ်:**\n"
                f"👉 {group_link}\n\n"
                "အဆင်ပြေပါစေရှင်! ✨"
            )
            bot.send_message(message.chat.id, success_text, parse_mode="Markdown")
        else:
            fail_text = (
                "❌ **စလစ် စစ်ဆေး၍ မရပါ သို့မဟုတ် ပမာဏ မမှန်ကန်ပါ။**\n"
                "ကျေးဇူးပြု၍ စလစ်ပုံ မှန်ကန်မှု ရှိမရှိ စစ်ဆေးပြီး ပြန်လည် ပို့ပေးပါရှင်။ 🙏"
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
    cursor.execute("SELECT name, price, link FROM packages WHERE id = ?", (pkg_id,))
    pkg = cursor.fetchone()
    conn.close()

    name, price, link = pkg
    admin_states[ADMIN_ID] = {"action": "editing_pkg", "pkg_id": pkg_id}

    text = (
        f"📦 **Package:** {name}\n"
        f"💰 **လက်ရှိ ဈေးနှုန်း:** {price:,.0f} MMK\n"
        f"🔗 **လက်ရှိ လင့်ခ်:** {link}\n\n"
        "✍️ **အသစ်ပြောင်းလဲရန် ပုံစံအတိုင်း ရိုက်ပို့ပေးပါ:**\n"
        "`[ဈေးနှုန်း] [လင့်ခ်]`\n"
        "ဥပမာ: `35000 https://t.me/+xyz123`"
    )
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("🔙 ကာရန် / უკან", callback_data="admin_edit_pkgs"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.from_user.id == ADMIN_ID, content_types=['text'])
def handle_admin_text(message):
    state = admin_states.get(ADMIN_ID)
    if state and state.get("action") == "editing_pkg":
        pkg_id = state.get("pkg_id")
        parts = message.text.strip().split(maxsplit=1)
        
        if len(parts) == 2:
            try:
                new_price = float(parts[0].replace(",", ""))
                new_link = parts[1].strip()

                conn = sqlite3.connect('vip_bot.db')
                cursor = conn.cursor()
                cursor.execute("UPDATE packages SET price = ?, link = ? WHERE id = ?", (new_price, new_link, pkg_id))
                conn.commit()
                conn.close()

                admin_states.pop(ADMIN_ID, None)
                bot.send_message(message.chat.id, f"✅ Package အချက်အလက် အောင်မြင်စွာ ပြောင်းလဲပြီးပါပြီရှင်! ✨")
                send_packages_menu(message.chat.id)
                return
            except ValueError:
                pass
        
        bot.send_message(message.chat.id, "❌ ပုံစံ မှားယွင်းနေပါသည်။ ဥပမာ - `35000 https://t.me/+xyz123` ဟု ပုံစံမှန် ရိုက်ထည့်ပေးပါ။")

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
    total_sales = sum(r[0] for r in rows) if rows else 0
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
    print("VIP Member Bot with Admin Link/Price Control is running...")
    bot.infinity_polling(skip_pending=True)
