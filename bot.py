import re, json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CallbackQueryHandler, filters, ContextTypes

TOKEN = "TOKEN"
FILE = "data.json"

user_state = {}

staff = {
    "早班": [
        ("奇奇", "组长"), ("贝果", "副组长"), ("艾娃", ""),
        ("卡比", ""), ("路奇", ""), ("果冻", "")
    ],
    "中班": [
        ("百川", "主管"), ("沙西米", "组长"), ("小玥", "副组长"),
        ("卡姆利", ""), ("鱼丸", ""), ("翅膀", ""), ("霄霄", "")
    ],
    "夜班": [
        ("轩轩", "组长"), ("小邱", "副组长"), ("大雄", ""),
        ("咖啡", ""), ("九节狼", ""), ("当肯", ""), ("小江", "")
    ]
}

def load():
    try:
        with open(FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except:
        return {}

def save(d):
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

def clear_old_month(data, new_month):
    new_data = {}
    for k, v in data.items():
        if v["date"].startswith(new_month):
            new_data[k] = v
    return new_data

def calc(text):
    prices = re.findall(r"\$(\d+)", text)
    total = sum(map(int, prices))
    extra = max(0, total - 500)
    items = text.split("\n")
    return items, total, extra

def format_output(x):
    msg = f"日期] {x['date']}\n"
    msg += "[公司] 悅達\n"
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
        [InlineKeyboardButton("新增團建", callback_data="add")],
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

    # 日期
    if step == "date":
        user_state[user_id]["date"] = text
        user_state[user_id]["step"] = "shift"

        month = text.split("/")[0]
        data = clear_old_month(data, month)
        save(data)

        keyboard = [
            [InlineKeyboardButton("早班", callback_data="早班")],
            [InlineKeyboardButton("中班", callback_data="中班")],
            [InlineKeyboardButton("夜班", callback_data="夜班")]
        ]

        await update.message.reply_text("選擇班別", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # 餐點
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

        await update.message.reply_text(format_output(x))
        user_state[user_id]["step"] = "done"

# ===== 按鍵 =====
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    db = load()

    # 👉 新增
    if data == "add":
        user_state[user_id] = {"step": "date"}
        await query.message.reply_text("請輸入日期（例如 4/16）")
        return

    # 👉 查詢入口
    if data == "query":
        keyboard = [
            [InlineKeyboardButton("早班", callback_data="查_早班")],
            [InlineKeyboardButton("中班", callback_data="查_中班")],
            [InlineKeyboardButton("夜班", callback_data="查_夜班")]
        ]
        await query.message.reply_text("選擇班別", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # 👉 查詢結果
    if data.startswith("查_"):
        shift = data.replace("查_", "")
        result = ""

        for x in db.values():
            if x["shift"] == shift:
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

        names = staff[data]
        keyboard = []

        for name, role in names:
            text = f"{name}【{role}】" if role else name
            keyboard.append([InlineKeyboardButton(text, callback_data=name)])

        await query.message.reply_text("選擇花名", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # 花名
    if step == "name":
        user_state[user_id]["name"] = data
        user_state[user_id]["step"] = "food"

        await query.message.reply_text("請輸入餐點（例如：奶茶 $50）")

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(MessageHandler(filters.COMMAND, start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
app.add_handler(CallbackQueryHandler(handle_button))

print("🔥 團建機器人（入口按鍵版）啟動")
app.run_polling()