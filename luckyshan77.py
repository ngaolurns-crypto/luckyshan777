import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import time
import threading
import json
import os
from datetime import datetime, timedelta

# ============================================================================
# CONFIGURATION
# ============================================================================
BOT_TOKEN = "8848906323:AAH1Al4Ln3S9s86JiNydo3ckH4O_sDeNVwo"
ADMIN_ID = 5948214334
AGENT_USERNAME = "bf11135656"
AGENT_PASSWORD = "Lmc@256422"
AGENT_ID = 1255657
BASE_URL = "https://ag.buffalo688.com"
POLL_INTERVAL = 5  # 5 seconds polling

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN)
polling_active = False

# Track notified IDs to avoid duplicate notifications
notified_deposits = set()
notified_withdraws = set()

# ============================================================================
# BUFFALO API CLIENT
# ============================================================================
class BuffaloAPI:
    def __init__(self):
        self.token = None
        self.lock = threading.Lock()
        self.login()

    def login(self):
        with self.lock:
            try:
                r = requests.post(f"{BASE_URL}/api/auth/login", json={
                    "name": AGENT_USERNAME,
                    "password": AGENT_PASSWORD,
                    "captcha": "",
                    "captcha_key": "",
                    "roles": "commissioner"
                }, headers={"Accept": "application/json"}, timeout=30)
                data = r.json()
                if data.get("status") == "success" and data.get("token"):
                    self.token = data["token"]
                    print("Login successful!")
                    return True
                else:
                    print(f"Login failed: {data}")
                    return False
            except Exception as e:
                print(f"Login error: {e}")
                return False

    def request(self, method, endpoint, **kwargs):
        if not self.token:
            self.login()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.token}"
        headers["Accept"] = "application/json"
        try:
            r = requests.request(method, f"{BASE_URL}{endpoint}", headers=headers, timeout=30, **kwargs)
            if r.status_code == 401:
                print("Token expired, re-login...")
                if self.login():
                    headers["Authorization"] = f"Bearer {self.token}"
                    r = requests.request(method, f"{BASE_URL}{endpoint}", headers=headers, timeout=30, **kwargs)
            try:
                return r.json()
            except:
                print(f"Non-JSON response from {endpoint}, re-login...")
                if self.login():
                    headers["Authorization"] = f"Bearer {self.token}"
                    r = requests.request(method, f"{BASE_URL}{endpoint}", headers=headers, timeout=30, **kwargs)
                    try:
                        return r.json()
                    except:
                        return None
                return None
        except Exception as e:
            print(f"Request error: {e}")
            return None

    def check_deposits(self):
        data = self.request("GET", "/api/check/deposits")
        if data and data.get("success"):
            return data.get("deposits", 0)
        return 0

    def check_withdraws(self):
        data = self.request("GET", "/api/check/withdraws")
        if data and data.get("success"):
            return data.get("withdraws", 0)
        return 0

    def list_pending_deposits(self):
        data = self.request("POST", "/api/admin/deposits", json={"type": "pending", "page": 1, "limit": 50})
        if data and data.get("success"):
            return data.get("data", [])
        return []

    def list_pending_withdraws(self):
        data = self.request("POST", "/api/admin/withdraws", json={"type": "pending", "page": 1, "limit": 50})
        if data and data.get("success"):
            return data.get("data", [])
        return []

    def confirm_deposit(self, deposit_id, user_id, amount):
        data = self.request("POST", "/api/admin/deposits/confirm", json={
            "userId": user_id,
            "amount": amount,
            "depositId": deposit_id,
            "promotion": None,
            "turn_over_amount": None
        })
        return data and data.get("success")

    def reject_deposit(self, deposit_id, amount):
        data = self.request("PUT", f"/api/deposits/{deposit_id}", json={
            "status": "fail",
            "type": "status update",
            "amount": amount
        })
        return data and data.get("success")

    def confirm_withdraw(self, withdraw_id, user_id, amount):
        data = self.request("POST", "/api/admin/withdraws/confirm", json={
            "userId": user_id,
            "amount": amount,
            "withdrawId": withdraw_id,
            "status": "confirm",
            "reason": ""
        })
        return data and data.get("success")

    def reject_withdraw(self, withdraw_id, user_id, amount, reason=""):
        data = self.request("POST", "/api/admin/withdraws/confirm", json={
            "userId": user_id,
            "amount": amount,
            "withdrawId": withdraw_id,
            "status": "fail",
            "reason": reason
        })
        return data and data.get("success")

    def get_balance(self):
        data = self.request("GET", "/api/auth/user")
        if data and data.get("data"):
            return float(data["data"].get("amount", 0))
        return 0

api = BuffaloAPI()

# ============================================================================
# BOT COMMAND HANDLERS
# ============================================================================
@bot.message_handler(commands=['start', 'help'])
def handle_start(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "⛔ Unauthorized Access.")
        return
    bot.send_message(message.chat.id, "🤖 **Buffalo688 Admin Bot Live**\n\n- /status : Check balance and bot status\n- /pending : List all pending transactions\n- /report : Get daily profit report manually")

@bot.message_handler(commands=['pending'])
def handle_pending(message):
    if message.from_user.id != ADMIN_ID:
        return
    deposits = api.list_pending_deposits()
    withdraws = api.list_pending_withdraws()
    text = ""
    if deposits:
        text += f"💰 Pending Deposits: {len(deposits)}\n"
        for d in deposits[:10]:
            text += f"  - {d.get('user_name')} | {d.get('amount'):,} MMK | slip: {d.get('remark')}\n"
    else:
        text += "💰 Pending Deposits: 0\n"
    text += "\n"
    if withdraws:
        text += f"💸 Pending Withdraws: {len(withdraws)}\n"
        for w in withdraws[:10]:
            text += f"  - {w.get('user_name')} | {w.get('amount'):,} MMK | {w.get('type')} {w.get('account_number')}\n"
    else:
        text += "💸 Pending Withdraws: 0\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['status'])
def handle_status(message):
    if message.from_user.id != ADMIN_ID:
        return
    balance = api.get_balance()
    status = "✅ Bot running 24/7" if polling_active else "🛑 Bot stopped"
    bot.send_message(message.chat.id, f"{status}\n💰 Agent Balance: {balance:,.0f} MMK")

@bot.message_handler(commands=['report'])
def handle_manual_report(message):
    if message.from_user.id != ADMIN_ID:
        return
    report = get_daily_report()
    bot.send_message(ADMIN_ID, report)

# ============================================================================
# CALLBACK HANDLERS (Admin Actions)
# ============================================================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("dep_confirm_"))
def handle_dep_confirm(call):
    if call.from_user.id != ADMIN_ID:
        return
    parts = call.data.split("_")
    dep_id = int(parts[2])
    game_user_id = int(parts[3])
    amount = int(parts[4])

    if api.confirm_deposit(dep_id, game_user_id, amount):
        result_text = call.message.text + "\n\n✅ CONFIRMED!"
        bot.edit_message_text(result_text, call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "Confirmed!")
    else:
        bot.answer_callback_query(call.id, "Error confirming deposit.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("dep_reject_"))
def handle_dep_reject(call):
    if call.from_user.id != ADMIN_ID:
        return
    parts = call.data.split("_")
    dep_id = int(parts[2])
    amount = int(parts[3])
    if api.reject_deposit(dep_id, amount):
        bot.edit_message_text(call.message.text + "\n\n❌ REJECTED!", call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "Rejected!")
    else:
        bot.answer_callback_query(call.id, "Error rejecting deposit.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("wd_confirm_"))
def handle_wd_confirm(call):
    if call.from_user.id != ADMIN_ID:
        return
    parts = call.data.split("_")
    wd_id = int(parts[2])
    user_id = int(parts[3])
    amount = int(parts[4])
    if api.confirm_withdraw(wd_id, user_id, amount):
        bot.edit_message_text(call.message.text + "\n\n✅ CONFIRMED!", call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "Confirmed!")
    else:
        bot.answer_callback_query(call.id, "Error confirming withdraw.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("wd_reject_"))
def handle_wd_reject(call):
    if call.from_user.id != ADMIN_ID:
        return
    parts = call.data.split("_")
    wd_id = int(parts[2])
    user_id = int(parts[3])
    amount = int(parts[4])
    if api.reject_withdraw(wd_id, user_id, amount):
        bot.edit_message_text(call.message.text + "\n\n❌ REJECTED!", call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "Rejected!")
    else:
        bot.answer_callback_query(call.id, "Error rejecting withdraw.")

# ============================================================================
# NOTIFICATIONS & REPORTS
# ============================================================================
def notify_deposit(dep):
    dep_id = dep.get("id")
    if dep_id in notified_deposits:
        return
    notified_deposits.add(dep_id)

    game_user_id = dep.get("user_id")
    text = (
        "💰 **ငွေသွင်းတောင်းဆိုမှု (Deposit)**\n"
        "━━━━━━━━━━━━━━━\n"
        f"👤 User: {dep.get('user_name')}\n"
        f"💵 ပမာဏ: {dep.get('amount'):,} MMK\n"
        f"🧾 Slip: {dep.get('remark')}\n"
        f"🏦 Account: {dep.get('account', 'N/A')}\n"
        f"📅 Date: {dep.get('date')}\n"
        "━━━━━━━━━━━━━━━"
    )

    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("✅ Confirm", callback_data=f"dep_confirm_{dep_id}_{game_user_id}_{dep.get('amount')}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"dep_reject_{dep_id}_{dep.get('amount')}")
    )
    try:
        bot.send_message(ADMIN_ID, text, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        print(f"Error notifying deposit: {e}")

def notify_withdraw(wd):
    wd_id = wd.get("id")
    if wd_id in notified_withdraws:
        return
    notified_withdraws.add(wd_id)
    text = (
        "💸 **ငွေထုတ်တောင်းဆိုမှု (Withdraw)**\n"
        "━━━━━━━━━━━━━━━\n"
        f"👤 User: {wd.get('user_name')}\n"
        f"💵 ပမာဏ: {wd.get('amount'):,} MMK\n"
        f"🏦 Type: {wd.get('type')}\n"
        f"📱 Account: {wd.get('account_number')}\n"
        f"👤 Name: {wd.get('account_name')}\n"
        f"📅 Date: {wd.get('date')}\n"
        "━━━━━━━━━━━━━━━"
    )
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("✅ Confirm", callback_data=f"wd_confirm_{wd_id}_{wd.get('user_id')}_{wd.get('amount')}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"wd_reject_{wd_id}_{wd.get('user_id')}_{wd.get('amount')}")
    )
    try:
        bot.send_message(ADMIN_ID, text, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        print(f"Error notifying withdraw: {e}")

def get_daily_report():
    try:
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        target_str = yesterday.strftime('%b ') + str(yesterday.day) + yesterday.strftime(', %Y')
        target_date_display = yesterday.strftime('%Y-%m-%d')

        total_deposit = 0
        page = 1
        while True:
            data = api.request("POST", "/api/admin/deposits", json={"type": "all", "page": page, "limit": 100})
            if not data or not data.get("data"):
                break
            found_old = False
            for item in data["data"]:
                if target_str in item.get("date", ""):
                    if item.get("status") == "confirm":
                        total_deposit += item.get("no_format_amount", 0)
                elif item.get("date", "") and target_str not in item.get("date", ""):
                    try:
                        item_date = datetime.strptime(item['date'], '%b %d, %Y %I:%M:%S %p')
                        if item_date.date() < yesterday.date():
                            found_old = True
                            break
                    except:
                        pass
            if found_old:
                break
            page += 1

        total_withdraw = 0
        page = 1
        while True:
            data = api.request("POST", "/api/admin/withdraws", json={"type": "all", "page": page, "limit": 100})
            if not data or not data.get("data"):
                break
            found_old = False
            for item in data["data"]:
                if target_str in item.get("date", ""):
                    if item.get("status") == "confirm":
                        total_withdraw += item.get("no_format_amount", item.get("amount", 0))
                elif item.get("date", "") and target_str not in item.get("date", ""):
                    try:
                        item_date = datetime.strptime(item['date'], '%b %d, %Y %I:%M:%S %p')
                        if item_date.date() < yesterday.date():
                            found_old = True
                            break
                    except:
                        pass
            if found_old:
                break
            page += 1

        profit_before = total_deposit - total_withdraw

        if profit_before >= 0:
            cost_28 = int(profit_before * 0.28)
            net_profit = profit_before - cost_28
            report = (
                f"📊 **Daily Report - {target_date_display}**\n"
                f"━━━━━━━━━━━━━━━\n"
                f"💰 ထည့်ငွေ (Deposit): {total_deposit:,} MMK\n"
                f"💸 ထုတ်ငွေ (Withdraw): {total_withdraw:,} MMK\n"
                f"━━━━━━━━━━━━━━━\n"
                f"📈 Deposit - Withdraw = {profit_before:,} MMK\n"
                f"📉 အရင်း 28% = {cost_28:,} MMK\n"
                f"━━━━━━━━━━━━━━━\n"
                f"✅ အမြတ် (Profit) = {net_profit:,} MMK"
            )
        else:
            loss = abs(profit_before)
            report = (
                f"📊 **Daily Report - {target_date_display}**\n"
                f"━━━━━━━━━━━━━━━\n"
                f"💰 ထည့်ငွေ (Deposit): {total_deposit:,} MMK\n"
                f"💸 ထုတ်ငွေ (Withdraw): {total_withdraw:,} MMK\n"
                f"━━━━━━━━━━━━━━━\n"
                f"📊 Deposit - Withdraw = -{loss:,} MMK\n"
                f"━━━━━━━━━━━━━━━\n"
                f"❌ အရှုံး (Loss) = -{loss:,} MMK"
            )
        return report
    except Exception as e:
        return f"❌ Daily report error: {e}"

# ============================================================================
# POLLING TASK
# ============================================================================
def polling_task():
    global polling_active
    polling_active = True
    print("Polling started...")
    last_report_date = None
    while polling_active:
        try:
            dep_count = api.check_deposits()
            if dep_count > 0:
                deposits = api.list_pending_deposits()
                for dep in deposits:
                    notify_deposit(dep)

            wd_count = api.check_withdraws()
            if wd_count > 0:
                withdraws = api.list_pending_withdraws()
                for wd in withdraws:
                    notify_withdraw(wd)

            now = datetime.now()
            today_date = now.strftime('%Y-%m-%d')
            if now.hour == 0 and now.minute < 1 and last_report_date != today_date:
                last_report_date = today_date
                report = get_daily_report()
                bot.send_message(ADMIN_ID, report)

        except Exception as e:
            print(f"Polling error: {e}")

        time.sleep(POLL_INTERVAL)

# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    print("Buffalo688 Admin Bot starting...")
    t = threading.Thread(target=polling_task, daemon=True)
    t.start()

    try:
        bot.infinity_polling()
    except KeyboardInterrupt:
        polling_active = False
