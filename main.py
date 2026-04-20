import asyncio
import sqlite3
import requests
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

# --- 1. ASOSIY SOZLAMALAR ---
TOKEN = "8641910402:AAGJ-LsNN-_8ZhRXvrfXiVUxGQWUU0dqgjE"
ADMIN_ID = 8536944196  
ADMIN_USER = "@academyadminM"
KARTA_RAQAM = "9860 0000 0000 0000" 
KARTA_EGA = "Abdullayev Mirjalol"
DB_NAME = "admin.db"
REFERAL_BONUS = 500 

# SEENSMS.UZ API
API_URL = "https://seensms.uz/api/v1" 
API_KEY = "2TUMWpQz3Iq3rJHuqxpdD7o3BRYGG1Rg"

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- 2. TILLAR LUG'ATI ---
texts = {
    'uz': {
        'welcome': "Xush kelibsiz! Bot tilini tanlang:",
        'main_menu': "Asosiy menyu 🏠",
        'services': "📂 Xizmatlar",
        'orders': "🔍 Buyurtmalarim",
        'topup': "💳 Hisob to'ldirish",
        'balance': "💰 Mening hisobim",
        'referal': "👥 Referal",
        'support': "☎️ Qo'llab-quvvatlash",
        'lang_btn': "🌐 Tilni o'zgartirish",
        'reg_success': "✅ Ro'yxatdan muvaffaqiyatli o'tdingiz!",
        'send_phone': "Xush kelibsiz! Botdan foydalanish uchun telefon raqamingizni yuboring:",
        'insufficient': "❌ Mablag' yetarli emas!",
        'enter_qty': "Miqdorni kiriting (Masalan: 1000):",
        'enter_link': "🔗 Havolani (link) yuboring:"
    },
    'ru': {
        'welcome': "Добро пожаловать! Выберите язык бота:",
        'main_menu': "Главное меню 🏠",
        'services': "📂 Услуги",
        'orders': "🔍 Мои заказы",
        'topup': "💳 Пополнить баланс",
        'balance': "💰 Мой счет",
        'referal': "👥 Реферал",
        'support': "☎️ Поддержка",
        'lang_btn': "🌐 Смена языка",
        'reg_success': "✅ Вы успешно зарегистрировались!",
        'send_phone': "Добро пожаловать! Отправьте свой номер телефона для использования бота:",
        'insufficient': "❌ Недостаточно средств!",
        'enter_qty': "Введите количество (Например: 1000):",
        'enter_link': "🔗 Отправьте ссылку:"
    }
}

# --- 3. DATABASE ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, phone TEXT, balance INTEGER DEFAULT 0, invited_by INTEGER, lang TEXT DEFAULT 'uz')")
    cursor.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, service_name TEXT, api_order_id TEXT, qty INTEGER, price INTEGER, status TEXT DEFAULT 'Bajarilmoqda')")
    conn.commit()
    conn.close()

class BotState(StatesGroup):
    choosing_lang = State()
    waiting_phone = State()
    topup_amount = State()
    waiting_receipt = State()
    entering_qty = State()
    entering_link = State()

# --- 4. API FUNKSIYASI ---
def api_request(action, params):
    url_params = {'key': API_KEY, 'action': action}
    url_params.update(params)
    try:
        response = requests.get(API_URL, params=url_params, timeout=15)
        return response.json()
    except:
        return {"error": "Aloqa xatosi"}

# --- 5. KEYBOARDLAR ---
def lang_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🇺🇿 O'zbek tili"), KeyboardButton(text="🇷🇺 Русский")]
    ], resize_keyboard=True)

def main_menu_kb(lang, is_admin=False):
    builder = ReplyKeyboardBuilder()
    builder.button(text=texts[lang]['services']), builder.button(text=texts[lang]['orders'])
    builder.button(text=texts[lang]['topup']), builder.button(text=texts[lang]['balance'])
    builder.button(text=texts[lang]['referal']), builder.button(text=texts[lang]['support'])
    builder.button(text=texts[lang]['lang_btn'])
    if is_admin:
        builder.button(text="📊 Admin Statistika")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

# --- 6. START VA TILINGI TANLASH ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext, command: CommandObject):
    init_db()
    uid = message.from_user.id
    args = command.args
    
    conn = sqlite3.connect(DB_NAME)
    user = conn.execute("SELECT lang FROM users WHERE user_id = ?", (uid,)).fetchone()
    
    if not user:
        inviter = None
        if args and args.isdigit() and int(args) != uid:
            inviter = int(args)
        conn.execute("INSERT OR IGNORE INTO users (user_id, invited_by) VALUES (?, ?)", (uid, inviter))
        conn.commit()
        await state.set_state(BotState.choosing_lang)
        await message.answer("Assalomu alaykum! Bot tilini tanlang / Выберите язык бота:", reply_markup=lang_kb())
    else:
        lang = user[0]
        await message.answer(texts[lang]['main_menu'], reply_markup=main_menu_kb(lang, uid == ADMIN_ID))
    conn.close()

@dp.message(BotState.choosing_lang)
async def set_language(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    if "O'zbek" in message.text: lang = 'uz'
    elif "Русский" in message.text: lang = 'ru'
    else: return

    conn = sqlite3.connect(DB_NAME)
    conn.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, uid))
    conn.commit()
    
    user_phone = conn.execute("SELECT phone FROM users WHERE user_id = ?", (uid,)).fetchone()
    conn.close()

    if not user_phone[0]:
        builder = ReplyKeyboardBuilder().button(text="📲 Raqamni yuborish" if lang == 'uz' else "📲 Отправить номер", request_contact=True)
        await message.answer(texts[lang]['send_phone'], reply_markup=builder.as_markup(resize_keyboard=True))
        await state.set_state(BotState.waiting_phone)
    else:
        await state.clear()
        await message.answer(texts[lang]['main_menu'], reply_markup=main_menu_kb(lang, uid == ADMIN_ID))

@dp.message(BotState.waiting_phone, F.contact)
async def get_phone(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    conn = sqlite3.connect(DB_NAME)
    conn.execute("UPDATE users SET phone = ? WHERE user_id = ?", (message.contact.phone_number, uid))
    lang = conn.execute("SELECT lang FROM users WHERE user_id = ?", (uid,)).fetchone()[0]
    
    inviter = conn.execute("SELECT invited_by FROM users WHERE user_id = ?", (uid,)).fetchone()
    if inviter and inviter[0]:
        conn.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (REFERAL_BONUS, inviter[0]))
        try: await bot.send_message(inviter[0], f"👥 Yangi do'st qo'shildi! Sizga {REFERAL_BONUS} so'm bonus berildi.")
        except: pass
    
    conn.commit()
    conn.close()
    await state.clear()
    await message.answer(texts[lang]['reg_success'], reply_markup=main_menu_kb(lang, uid == ADMIN_ID))

# --- 7. XIZMATLAR VA BUYURTMA ---
@dp.message(F.text.in_([texts['uz']['services'], texts['ru']['services']]))
async def services_handler(message: types.Message):
    uid = message.from_user.id
    conn = sqlite3.connect(DB_NAME)
    lang = conn.execute("SELECT lang FROM users WHERE user_id = ?", (uid,)).fetchone()[0]
    conn.close()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🟣 Insta Obunachi", callback_data="buy_100_15000_Instagram")
    builder.button(text="🔵 TG Obunachi", callback_data="buy_462_15000_Telegram")
    builder.adjust(1)
    await message.answer(texts[lang]['choose_service'], reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("buy_"))
async def start_order(callback: types.CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    conn = sqlite3.connect(DB_NAME)
    lang = conn.execute("SELECT lang FROM users WHERE user_id = ?", (uid,)).fetchone()[0]
    conn.close()
    
    _, sid, price, name = callback.data.split("_")
    await state.update_data(s_id=sid, s_price=int(price), s_name=name, lang=lang)
    await state.set_state(BotState.entering_qty)
    await callback.message.answer(f"🚀 {name}. {texts[lang]['enter_qty']}")
    await callback.answer()

@dp.message(BotState.entering_qty)
async def process_qty(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return
    qty = int(message.text)
    data = await state.get_data()
    lang = data['lang']
    total = int((data['s_price'] / 1000) * qty)
    await state.update_data(qty=qty, total=total)
    
    confirm_text = "✅ Tasdiqlash" if lang == 'uz' else "✅ Подтвердить"
    builder = InlineKeyboardBuilder().button(text=confirm_text, callback_data="confirm_order")
    msg = f"💰 Jami: {total:,} so'm. Tasdiqlaysizmi?" if lang == 'uz' else f"💰 Итого: {total:,} сум. Подтверждаете?"
    await message.answer(msg, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "confirm_order")
async def ask_link(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data['lang']
    await state.set_state(BotState.entering_link)
    await callback.message.edit_text(texts[lang]['enter_link'])
    await callback.answer()

@dp.message(BotState.entering_link)
async def finish_order(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data['lang']
    uid = message.from_user.id
    conn = sqlite3.connect(DB_NAME)
    user_bal = conn.execute("SELECT balance FROM users WHERE user_id = ?", (uid,)).fetchone()[0]
    
    if user_bal < data['total']:
        await message.answer(texts[lang]['insufficient'])
    else:
        res = api_request('add', {'service': data['s_id'], 'link': message.text, 'quantity': data['qty']})
        if 'order' in res:
            conn.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (data['total'], uid))
            conn.execute("INSERT INTO orders (user_id, service_name, api_order_id, qty, price) VALUES (?, ?, ?, ?, ?)", 
                         (uid, data['s_name'], res['order'], data['qty'], data['total']))
            conn.commit()
            await message.answer(f"✅ OK! ID: {res['order']}")
        else:
            await message.answer(f"❌ Error: {res.get('error')}")
    conn.close()
    await state.clear()

# --- 8. TILNI O'ZGARTIRISH ---
@dp.message(F.text.in_([texts['uz']['lang_btn'], texts['ru']['lang_btn']]))
async def change_language_cmd(message: types.Message, state: FSMContext):
    await state.set_state(BotState.choosing_lang)
    await message.answer("Yangi tilni tanlang / Выберите новый язык:", reply_markup=lang_kb())

# --- 9. HISOB, ADMIN VA REFERAL ---
@dp.message(F.text.in_([texts['uz']['balance'], texts['ru']['balance']]))
async def balance_handler(message: types.Message):
    conn = sqlite3.connect(DB_NAME)
    res = conn.execute("SELECT balance FROM users WHERE user_id = ?", (message.from_user.id,)).fetchone()
    conn.close()
    await message.answer(f"🆔 ID: `{message.from_user.id}`\n💰 Balans: {res[0] if res else 0:,} so'm", parse_mode="Markdown")

@dp.message(F.text.in_([texts['uz']['orders'], texts['ru']['orders']]))
async def orders_handler(message: types.Message):
    conn = sqlite3.connect(DB_NAME)
    rows = conn.execute("SELECT service_name, api_order_id, status FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 5", (message.from_user.id,)).fetchall()
    conn.close()
    if not rows: return await message.answer("Hali buyurtmalar yo'q.")
    text = "📦 Buyurtmalar:\n\n"
    for r in rows: text += f"🔹 {r[0]}\nID: `{r[1]}` | {r[2]}\n\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text.in_([texts['uz']['referal'], texts['ru']['referal']]))
async def referal_handler(message: types.Message):
    bot_me = await bot.get_me()
    ref_link = f"https://t.me/{bot_me.username}?start={message.from_user.id}"
    conn = sqlite3.connect(DB_NAME)
    count = conn.execute("SELECT COUNT(*) FROM users WHERE invited_by = ?", (message.from_user.id,)).fetchone()[0]
    conn.close()
    await message.answer(f"👥 **Referal**\nLink: `{ref_link}`\nBonus: {REFERAL_BONUS}\nDo'stlar: {count}", parse_mode="Markdown")

@dp.message(F.text.in_([texts['uz']['support'], texts['ru']['support']]))
async def support_handler(message: types.Message):
    await message.answer(f"Admin: {ADMIN_USER}")

@dp.message(F.text == "📊 Admin Statistika", F.from_user.id == ADMIN_ID)
async def admin_stat(message: types.Message):
    conn = sqlite3.connect(DB_NAME)
    u = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    o = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    conn.close()
    await message.answer(f"📊 Stats:\nAzolar: {u}\nOrders: {o}")

@dp.message(F.text.in_([texts['uz']['topup'], texts['ru']['topup']]))
async def topup_handler(message: types.Message, state: FSMContext):
    await state.set_state(BotState.topup_amount)
    await message.answer("💰 Summani kiriting / Введите сумму:")

@dp.message(BotState.topup_amount)
async def topup_amt(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return
    await state.update_data(amt=int(message.text))
    btn_text = "✅ To'ladim / Оплатил"
    builder = InlineKeyboardBuilder().button(text=btn_text, callback_data="sent_receipt")
    await message.answer(f"💵 Karta: `{KARTA_RAQAM}`\nEga: {KARTA_EGA}\nSumma: {message.text} so'm", 
                         reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data == "sent_receipt")
async def receipt_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(BotState.waiting_receipt)
    await callback.message.answer("📸 Chek rasmini yuboring / Отправьте фото чека:")
    await callback.answer()

@dp.message(BotState.waiting_receipt, F.photo)
async def process_receipt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    uid = message.from_user.id
    amt = data['amt']
    caption = f"💰 *Yangi to'lov!*\nID: `{uid}`\nSumma: {amt:,} so'm\n\nNusxalash:\n`/plus {uid} {amt}`"
    await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=caption, parse_mode="Markdown")
    await message.answer("✅ Yuborildi! Admin tasdiqlashi kutilmoqda.")
    await state.clear()

@dp.message(Command("plus"), F.from_user.id == ADMIN_ID)
async def admin_plus(message: types.Message):
    try:
        parts = message.text.split()
        uid, amt = int(parts[1]), int(parts[2])
        conn = sqlite3.connect(DB_NAME)
        conn.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amt, uid))
        conn.commit()
        conn.close()
        await bot.send_message(uid, f"💰 Hisobingiz {amt:,} so'mga to'ldirildi!")
        await message.answer(f"✅ ID {uid} ga {amt:,} so'm qo'shildi.")
    except: pass

async def main():
    init_db()
    print("Bot ishga tushdi! 🚀")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())