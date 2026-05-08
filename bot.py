import re, json, requests
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CallbackQueryHandler, filters, ContextTypes

TOKEN = "你的TOKEN"
SHEET_URL = "你的Apps Script網址"
FILE = "data.json"

user_state = {}

staff = {
    "早班": ["贝果","路奇","卡比","奇奇","艾娃","果冻"],
    "中班": ["百川","沙西米","小玥","卡姆利","鱼丸","翅膀","霄霄"],
    "夜班": ["轩轩","小邱","大雄","咖啡","九节狼","当肯","小江"]
}

# ===== 主選單 =====
def main_menu():
    keyboard = [
        ["新增/修改"],
        ["查詢資料"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ===== 返回鍵 =====
def back_btn():
    return ReplyKeyboardMarkup([["🔙 返回主選單"]], resize_keyboard=True)

# ===== 工具 =====
def load():
    try:
        with open(FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        return {}

    now = datetime.now().strftime("%Y-%m")
    return {k:v for k,v in data.items() if v["date"].startswith(now)}

def save(d):
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

def calc(text):
    prices = re.findall(r"\d+", text)
    total = sum(map(int, prices))
    extra = max(0, total - 500)
    return text.split("\n"), total, extra

def format_output(x):
    msg = f"日期] {x['date']}\n[班別] {x['shift']}\n[花名] {x['name']}\n[餐點]\n"
    for i in x["items"]:
        if i.strip():
            msg += f"- {i}\n"
    msg += f"\n小計 {x['total']} / 補款 {x['extra']}\n────────\n"
    return msg

# ===== 啟動 =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("請選擇功能👇", reply_markup=main_menu())

# ===== 文字 =====
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    data = load()

    # 🔙 返回
    if text == "🔙 返回主選單":
        user_state[user_id] = {}
        await update.message.reply_text("已返回主選單👇", reply_markup=main_menu())
        return

    # 主選單
    if text == "新增/修改":
        user_state[user_id] = {"step": "date"}
        await update.message.reply_text("請輸入日期（2026-05-07）", reply_markup=back_btn())
        return

    if text == "查詢資料":
        user_state[user_id] = {"step": "query_date"}
        await update.message.reply_text("請輸入查詢日期（2026-05-07）", reply_markup=back_btn())
        return

    if user_id not in user_state:
        return

    step = user_state[user_id]["step"]

    # 🛑 防呆：日期格式
    if step in ["date","query_date"]:
        if not re.match(r"\d{4}-\d{2}-\d{2}", text):
            await update.message.reply_text("❌ 日期格式錯誤（例：2026-05-07）", reply_markup=back_btn())
            return

    # ===== 新增 =====
    if step == "date":
        user_state[user_id]["date"] = text
        user_state[user_id]["step"] = "shift"

        kb = [[InlineKeyboardButton(x, callback_data=x)] for x in ["早班","中班","夜班"]]
        await update.message.reply_text("選班別", reply_markup=InlineKeyboardMarkup(kb))
        return

    # ===== 查詢 =====
    if step == "query_date":
        user_state[user_id]["date"] = text
        user_state[user_id]["step"] = "query_shift"

        kb = [[InlineKeyboardButton(x, callback_data="查_"+x)] for x in ["早班","中班","夜班"]]
        await update.message.reply_text("選班別", reply_markup=InlineKeyboardMarkup(kb))
        return

    # ===== 餐點 =====
    if step == "food":

        # 🛑 防呆：沒輸入金額
        if not re.search(r"\d+", text):
            await update.message.reply_text("❌ 請輸入金額（例如：雞腿便當 120）", reply_markup=back_btn())
            return

        items, total, extra = calc(text)

        x = {
            "date": user_state[user_id]["date"],
            "shift": user_state[user_id]["shift"],
            "name": user_state[user_id]["name"],
            "items": items,
            "total": total,
            "extra": extra
        }

        key = f"{x['date']}_{x['shift']}_{x['name']}"
        data[key] = x
        save(data)

        try:
            requests.post(SHEET_URL, json={
                "date": x["date"],
                "shift": x["shift"],
                "name": x["name"],
                "food": "\n".join(items),
                "total": total,
                "extra": extra
            })
        except:
            print("雲端錯誤")

        await update.message.reply_text("✅ 已更新\n\n"+format_output(x), reply_markup=main_menu())
        user_state[user_id] = {}

# ===== 按鈕 =====
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data
    db = load()

    if data.startswith("查_"):
        shift = data.replace("查_","")
        date = user_state[user_id]["date"]

        result = ""
        for x in db.values():
            if x["date"]==date and x["shift"]==shift:
                result += format_output(x)

        await query.message.reply_text(result if result else "查無資料", reply_markup=main_menu())
        return

    step = user_state[user_id]["step"]

    if step == "shift":
        user_state[user_id]["shift"] = data
        user_state[user_id]["step"] = "name"

        kb = [[InlineKeyboardButton(n, callback_data=n)] for n in staff[data]]
        await query.message.reply_text("選人", reply_markup=InlineKeyboardMarkup(kb))

    elif step == "name":
        user_state[user_id]["name"] = data
        user_state[user_id]["step"] = "food"
        await query.message.reply_text("輸入餐點（例：雞腿 120）", reply_markup=back_btn())

# ===== 啟動 =====
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.COMMAND, start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
app.add_handler(CallbackQueryHandler(handle_button))

print("🔥 完整穩定版啟動")
app.run_polling()
