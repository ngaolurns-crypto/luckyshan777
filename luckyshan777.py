from datetime import datetime, timedelta, timezone
import json
import logging
import os
import threading
import time
import requests
import telebot
from telebot.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BASE_URL = "https://ag.buffalo688.com"
POLL_INTERVAL = 3

# ဝင်ရောက်ထားသော အချက်အလက်များ
BOT_TOKEN = "9024731744:AAFogr_WEnT9MRFK-5C9y2RA7E-YOKIx7FY"
ADMIN_ID = 8022481594
USERNAME = "bf11425225"
PASSWORD = "Sarmleng@1"
MAIN_ADMIN_ID = 5546899291
MM_TZ = timezone(timedelta(hours=6, minutes=30))


class BuffaloAPIInstance:

  def __init__(self, username, password):
    self.username = username
    self.password = password
    self.token = None
    self.lock = threading.Lock()
    self.login()

  def login(self):
    with self.lock:
      try:
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "name": self.username,
                "password": self.password,
                "captcha": "",
                "captcha_key": "",
                "roles": "commissioner",
            },
            headers={"Accept": "application/json"},
            timeout=30,
        )
        data = r.json()
        if data.get("status") == "success" and data.get("token"):
          self.token = data["token"]
          return True
        return False
      except Exception as e:
        print(f"Login error for {self.username}: {e}")
        return False

  def request(self, method, endpoint, **kwargs):
    if not self.token:
      self.login()
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {self.token}"
    headers["Accept"] = "application/json"
    try:
      r = requests.request(
          method, f"{BASE_URL}{endpoint}", headers=headers, timeout=30, **kwargs
      )
      if r.status_code == 401:
        if self.login():
          headers["Authorization"] = f"Bearer {self.token}"
          r = requests.request(
              method,
              f"{BASE_URL}{endpoint}",
              headers=headers,
              timeout=30,
              **kwargs,
          )
      try:
        return r.json()
      except:
        return None
    except Exception as e:
      print(f"Request error: {e}")
      return None

  def list_pending_deposits(self):
    data = self.request(
        "POST",
        "/api/admin/deposits",
        json={"type": "pending", "page": 1, "limit": 50},
    )
    if data and data.get("success"):
      return data.get("data", [])
    return []

  def list_pending_withdraws(self):
    data = self.request(
        "POST",
        "/api/admin/withdraws",
        json={"type": "pending", "page": 1, "limit": 50},
    )
    if data and data.get("success"):
      return data.get("data", [])
    return []

  def confirm_deposit(self, deposit_id, user_id, amount):
    data = self.request(
        "POST",
        "/api/admin/deposits/confirm",
        json={
            "userId": user_id,
            "amount": amount,
            "depositId": deposit_id,
            "promotion": None,
            "turn_over_amount": None,
        },
    )
    return data and data.get("success")

  def reject_deposit(self, deposit_id, amount):
    data = self.request(
        "PUT",
        f"/api/deposits/{deposit_id}",
        json={"status": "fail", "type": "status update", "amount": amount},
    )
    return data and data.get("success")

  def confirm_withdraw(self, withdraw_id, user_id, amount):
    data = self.request(
        "POST",
        "/api/admin/withdraws/confirm",
        json={
            "userId": user_id,
            "amount": amount,
            "withdrawId": withdraw_id,
            "status": "confirm",
            "reason": "",
        },
    )
    return data and data.get("success")

  def reject_withdraw(self, withdraw_id, user_id, amount, reason="Rejected"):
    data = self.request(
        "POST",
        "/api/admin/withdraws/confirm",
        json={
            "userId": user_id,
            "amount": amount,
            "withdrawId": withdraw_id,
            "status": "fail",
            "reason": reason,
        },
    )
    if not data or not data.get("success"):
      data = self.request(
          "PUT",
          f"/api/withdraws/{withdraw_id}",
          json={"status": "fail", "type": "status update", "amount": amount},
      )
    return data and data.get("success")

  def get_balance(self):
    data = self.request("GET", "/api/auth/user")
    return (
        float(data["data"].get("amount", 0))
        if data and data.get("data")
        else 0
    )


def run_single_buffalo_bot():
  bot = telebot.TeleBot(BOT_TOKEN)
  api = BuffaloAPIInstance(USERNAME, PASSWORD)
  notified_deposits = set()
  notified_withdraws = set()
  polling_active = True

  def get_main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(
        KeyboardButton("💰 Pending စစ်ရန်"), KeyboardButton("📊 လက်ကျန်စစ်ရန်")
    )
    markup.row(KeyboardButton("📈 နေ့စဉ်စာရင်းထုတ်ရန်"))
    return markup

  @bot.message_handler(commands=["start", "help"])
  def handle_start(message):
    if message.from_user.id not in [ADMIN_ID, MAIN_ADMIN_ID]:
      return
    bot.send_message(
        message.chat.id,
        (
            "🤖 **Buffalo688 Admin Bot (Single)**\nUsername:"
            " `{username}`\n\nအောက်ပါခလုတ်များကို အသုံးပြု၍ စစ်ဆေးနိုင်ပါသည် -"
        ).format(username=USERNAME),
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown",
    )

  @bot.message_handler(
      func=lambda msg: msg.text in [
          "💰 Pending စစ်ရန်",
          "📊 လက်ကျန်စစ်ရန်",
          "📈 နေ့စဉ်စာရင်းထုတ်ရန်",
      ]
      or msg.text in ["/pending", "/status", "/report"]
  )
  def handle_pending(message):
    if message.from_user.id not in [ADMIN_ID, MAIN_ADMIN_ID]:
      return

    text = message.text
    if text in ["💰 Pending စစ်ရန်", "/pending"]:
      deposits = api.list_pending_deposits()
      withdraws = api.list_pending_withdraws()
      res_text = f"🔄 **Bot ({USERNAME}) ၏ လက်ရှိ Pending စာရင်းများ**\n━━━━━━━━━━━━━━━\n"
      if deposits:
        res_text += f"💰 **Pending Deposits ({len(deposits)}):**\n"
        for d in deposits[:10]:
          res_text += (
              f"  • {d.get('user_name')} | `{d.get('amount'):,}` MMK | Slip:"
              f" `{d.get('remark', 'N/A')}`\n"
          )
      else:
        res_text += "💰 Pending Deposits: 0\n"

      res_text += "\n"
      if withdraws:
        res_text += f"💸 **Pending Withdraws ({len(withdraws)}):**\n"
        for w in withdraws[:10]:
          res_text += (
              f"  • {w.get('user_name')} | `{w.get('amount'):,}` MMK |"
              f" {w.get('type')}\n"
          )
      else:
        res_text += "💸 Pending Withdraws: 0\n"
      bot.send_message(
          message.chat.id, res_text, reply_markup=get_main_keyboard(), parse_mode="Markdown"
      )
    elif text in ["📊 လက်ကျန်စစ်ရန်", "/status"]:
      balance = api.get_balance()
      bot.send_message(
          message.chat.id,
          f"✅ Bot Active (`{USERNAME}`)\n💰 လက်ကျန် Unit: `{balance:,.0f}` MMK",
          reply_markup=get_main_keyboard(),
          parse_mode="Markdown",
      )
    elif text in ["📈 နေ့စဉ်စာရင်းထုတ်ရန်", "/report"]:
      try:
        now = datetime.now(MM_TZ)
        yesterday = now - timedelta(days=1)
        target_str1 = (
            f"{yesterday.strftime('%b')} {yesterday.day},"
            f" {yesterday.strftime('%Y')}"
        )
        target_str2 = (
            f"{yesterday.strftime('%b')} {yesterday.strftime('%d')},"
            f" {yesterday.strftime('%Y')}"
        )
        target_str3 = yesterday.strftime("%Y-%m-%d")
        target_date_display = yesterday.strftime("%Y-%m-%d")

        total_deposit = 0
        page = 1
        while True:
          data = api.request(
              "POST",
              "/api/admin/deposits",
              json={"type": "all", "page": page, "limit": 100},
          )
          if not data or not data.get("data"):
            break
          for item in data["data"]:
            item_date = str(item.get("date", "")) + str(
                item.get("created_at", "")
            )
            if (
                target_str1 in item_date
                or target_str2 in item_date
                or target_str3 in item_date
            ) and item.get("status") == "confirm":
              amt = item.get("no_format_amount")
              if amt is None:
                amt = item.get("amount", 0)
              total_deposit += float(amt)
          page += 1

        total_withdraw = 0
        page = 1
        while True:
          data = api.request(
              "POST",
              "/api/admin/withdraws",
              json={"type": "all", "page": page, "limit": 100},
          )
          if not data or not data.get("data"):
            break
          for item in data["data"]:
            item_date = str(item.get("date", "")) + str(
                item.get("created_at", "")
            )
            status = str(item.get("status", "")).lower()
            if (
                target_str1 in item_date
                or target_str2 in item_date
                or target_str3 in item_date
            ) and (
                status == "confirm"
                or status == "approved"
                or status == "success"
            ):
              amt = item.get("no_format_amount")
              if amt is None:
                amt = item.get("amount", 0)
              total_withdraw += float(amt)
          page += 1

        profit_before = total_deposit - total_withdraw
        if profit_before >= 0:
          cost_28 = int(profit_before * 0.28)
          net_profit = profit_before - cost_28
          status_text = f"✅ **အမြတ် = {net_profit:,.0f} MMK**"
        else:
          status_text = f"❌ **အရှုံး = {abs(profit_before):,.0f} MMK**"

        report = (
            f"📊 **Daily Report - {target_date_display}** (`{USERNAME}`)\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💰 ထည့်ငွေ (Deposit): `{total_deposit:,.0f}` MMK\n"
            f"💸 ထုတ်ငွေ (Withdraw): `{total_withdraw:,.0f}` MMK\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📊 Net (ထည့် - ထုတ်): `{profit_before:,.0f}` MMK\n"
            f"{status_text}"
        )
        bot.send_message(
            message.chat.id,
            report,
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown",
        )
      except Exception as e:
        bot.send_message(
            message.chat.id,
            f"❌ Report error: {e}",
            reply_markup=get_main_keyboard(),
        )

  def polling_task():
    while polling_active:
      try:
        deposits = api.list_pending_deposits()
        for dep in deposits:
          dep_id = dep.get("id")
          if dep_id and dep_id not in notified_deposits:
            notified_deposits.add(dep_id)
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton(
                    "✅ Confirm",
                    callback_data=(
                        f"dep_confirm_{dep_id}_{dep.get('user_id')}_{dep.get('amount')}"
                    ),
                ),
                InlineKeyboardButton(
                    "❌ Reject",
                    callback_data=f"dep_reject_{dep_id}_{dep.get('amount')}",
                ),
            )
            dep_text = (
                f"💰 **ငွေသွင်းတောင်းဆိုမှု အသစ်** (`{USERNAME}`)\n"
                f"━━━━━━━━━━━━━━━\n"
                f"👤 User: {dep.get('user_name')}\n"
                f"💵 ပမာဏ: `{dep.get('amount'):,}` MMK\n"
                f"🧾 Slip နံပါတ်/Remark: `{dep.get('remark', 'N/A')}`\n"
                f"🏦 ဘဏ်အကောင့်: {dep.get('account', 'N/A')}\n"
                f"📅 အချိန်: {dep.get('date', 'N/A')}\n"
                f"━━━━━━━━━━━━━━━"
            )
            bot.send_message(
                ADMIN_ID,
                dep_text,
                reply_markup=markup,
                parse_mode="Markdown",
            )

        withdraws = api.list_pending_withdraws()
        for wd in withdraws:
          wd_id = wd.get("id")
          if wd_id and wd_id not in notified_withdraws:
            notified_withdraws.add(wd_id)
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton(
                    "✅ Confirm",
                    callback_data=(
                        f"wd_confirm_{wd_id}_{wd.get('user_id')}_{wd.get('amount')}"
                    ),
                ),
                InlineKeyboardButton(
                    "❌ Reject",
                    callback_data=(
                        f"wd_reject_{wd_id}_{wd.get('user_id')}_{wd.get('amount')}"
                    ),
                ),
            )
            wd_text = (
                f"💸 **ငွေထုတ်တောင်းဆိုမှု အသစ်** (`{USERNAME}`)\n"
                f"━━━━━━━━━━━━━━━\n"
                f"👤 User: {wd.get('user_name')}\n"
                f"💵 ပမာဏ: `{wd.get('amount'):,}` MMK\n"
                f"🏦 ဘဏ်အမျိုးအစား: {wd.get('type', 'N/A')}\n"
                f"📱 အကောင့်နံပါတ်: `{wd.get('account_number', 'N/A')}`\n"
                f"👤 အကောင့်အမည်: {wd.get('account_name', 'N/A')}\n"
                f"📅 အချိန်: {wd.get('date', 'N/A')}\n"
                f"━━━━━━━━━━━━━━━"
            )
            bot.send_message(
                ADMIN_ID,
                wd_text,
                reply_markup=markup,
                parse_mode="Markdown",
            )
      except Exception as e:
        print(f"Polling error for {USERNAME}: {e}")
      time.sleep(POLL_INTERVAL)

  @bot.callback_query_handler(
      func=lambda call: call.data.startswith("dep_")
      or call.data.startswith("wd_")
  )
  def handle_deposit_withdraw_action(call):
    if call.from_user.id not in [ADMIN_ID, MAIN_ADMIN_ID]:
      return
    parts = call.data.split("_")
    action_type = parts[0]
    action = parts[1]

    if action_type == "dep":
      dep_id = int(parts[2])
      if action == "confirm":
        user_id = int(parts[3])
        amount = float(parts[4])
        if api.confirm_deposit(dep_id, user_id, amount):
          bot.edit_message_text(
              call.message.text
              + f"\n\n✅ **Approved (ငွေသွင်းအတည်ပြုပြီး)**",
              call.message.chat.id,
              call.message.message_id,
              parse_mode="Markdown",
          )
      else:
        amount = float(parts[3])
        if api.reject_deposit(dep_id, amount):
          bot.edit_message_text(
              call.message.text + f"\n\n❌ **Rejected (ငွေသွင်းပယ်ချပြီး)**",
              call.message.chat.id,
              call.message.message_id,
              parse_mode="Markdown",
          )
    elif action_type == "wd":
      wd_id = int(parts[2])
      if action == "confirm":
        user_id = int(parts[3])
        amount = float(parts[4])
        if api.confirm_withdraw(wd_id, user_id, amount):
          bot.edit_message_text(
              call.message.text
              + f"\n\n✅ **Approved (ငွေထုတ်အတည်ပြုပြီး)**",
              call.message.chat.id,
              call.message.message_id,
              parse_mode="Markdown",
          )
      else:
        user_id = int(parts[3])
        amount = float(parts[4])
        if api.reject_withdraw(wd_id, user_id, amount):
          bot.edit_message_text(
              call.message.text + f"\n\n❌ **Rejected (ငွေထုတ်ပယ်ချပြီး)**",
              call.message.chat.id,
              call.message.message_id,
              parse_mode="Markdown",
          )

  threading.Thread(target=polling_task, daemon=True).start()
  print(f"Starting Single Buffalo Bot for {USERNAME}...")
  bot.infinity_polling(timeout=60, long_polling_timeout=60)


if __name__ == "__main__":
  run_single_buffalo_bot()
