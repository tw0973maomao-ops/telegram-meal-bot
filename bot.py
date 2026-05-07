import re, json, requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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

# ===== 工具 =====
def load():
    try:
        with open(FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        return {}

    # 只保留當月
    now_month = datetime.now().strftime("%Y-%m")
    new_data = {}

    for k, v in data.items():
        if v["date"].startswith(now_month):
            new_data[k] = v

    return new_data

def save(d):
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

def calc(text):
    prices = re.findall(r"(\d+)", text)
    total = sum(map(int, prices))
    extra = max(0, total - 500)
    items = text.split("\n")
    return items, total, extra

def format_output(x):
    msg = f"日期] {x['date']}\n"
    msg += f"[班別] {x['shift']}\n"
    msg += f"[花名] {x['name']}\n"
    msg += "[餐點]\n"
    for item in x["items"]:
        if item.strip():
            msg += f"- {item}\n"
    msg += f"\n小計 {x['total']} / 補款 {x['extra']}\n────────────\n"
    return msg

# ===== 主選單 =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("新增/修改", callback_data="add")],
        [InlineKeyboardButton("查詢資料", callback_data="query")]
    ]
    await update.message.reply_text("請選擇功能", reply_markup=InlineKeyboardMarkup(keyboard))

# ===== 文字 =====
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    data = load()

    if user_id not in user_state:
        return

    step = user_state[user_id]["step"]

    # 新增流程
    if step == "date":
        user_state[user_id]["date"] = text
        user_state[user_id]["step"] = "shift"

        keyboard = [
            [InlineKeyboardButton("早班", callback_data="早班")],
            [InlineKeyboardButton("中班", callback_data="中班")],
            [InlineKeyboardButton("夜班", callback_data="夜班")]
        ]

        await update.message.reply_text("選擇班別", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # 查詢日期
    if step == "query_date":
        user_state[user_id]["date"] = text
        user_state[user_id]["step"] = "query_shift"

        keyboard = [
            [InlineKeyboardButton("早班", callback_data="查_早班")],
            [InlineKeyboardButton("中班", callback_data="查_中班")],
            [InlineKeyboardButton("夜班", callback_data="查_夜班")]
        ]

        await update.message.reply_text("選擇班別", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # 餐點（新增 or 修改）
    if step == "food":
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

        # 寫入雲端
        try:
            requests.post(SHEET_URL, json={
                "date": x["date"],
                "shift": x["shift"],
                "name": x["name"],
                "food": "\n".join(x["items"]),
                "total": x["total"],
                "extra": x["extra"]
            })
        except:
            print("雲端失敗")

        await update.message.reply_text("✅ 已更新\n\n" + format_output(x))
        user_state[user_id]["step"] = "done"

# ===== 按鍵 =====
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass

    user_id = query.from_user.id
    data = query.data
    db = load()

    # 新增
    if data == "add":
        user_state[user_id] = {"step": "date"}
        await query.message.reply_text("請輸入日期（例如 2026-05-07）")
        return

    # 查詢入口
    if data == "query":
        user_state[user_id] = {"step": "query_date"}
        await query.message.reply_text("請輸入查詢日期（例如 2026-05-07）")
        return

    # 查詢結果
    if data.startswith("查_"):
        shift = data.replace("查_", "")
        date = user_state[user_id]["date"]

        result = ""
        for x in db.values():
            if x["date"] == date and x["shift"] == shift:
                result += format_output(x)

        await query.message.reply_text(result if result else "查無資料")
        return

    if user_id not in user_state:
        return

    step = user_state[user_id]["step"]

    # 班別
    if step == "shift":
        user_state[user_id]["shift"] = data
        user_state[user_id]["step"] = "name"

        keyboard = []
        for name in staff[data]:
            keyboard.append([InlineKeyboardButton(name, callback_data=name)])

        await query.message.reply_text("選擇花名", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # 花名
    if step == "name":
        user_state[user_id]["name"] = data
        user_state[user_id]["step"] = "food"
        await query.message.reply_text("請輸入餐點（例如：雞腿便當 120）")

# ===== 啟動 =====
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(MessageHandler(filters.COMMAND, start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
app.add_handler(CallbackQueryHandler(handle_button))

print("🔥 團建機器人（最終版）啟動")
app.run_polling()
