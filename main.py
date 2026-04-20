import asyncio
import sqlite3
import requests
import google.generativeai as genai
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

# --- 1. ASOSIY SOZLAMALAR ---
TOKEN = "8641910402:AAGJ-LsNN-_8ZhRXvrfXiVUxGQWUU0dqgjE"
GEMINI_API_KEY = "AIzaSyBOIpeJwTjeWCPmfKKVg2rGk2BQ8kCeEmQ" 
ADMIN_ID = 8536944196  
ADMIN_USER = "@academyadminM"
KARTA_RAQAM = "9860 0000 0000 0000" 
KARTA_EGA = "Abdullayev Mirjalol"
DB_NAME = "admin.db"
REFERAL_BONUS = 500 

# SEENSMS.UZ API
API_URL = "https://seensms.uz/api/v1" 
API_KEY = "2TUMWpQz3Iq3rJHuqxpdD7o3BRYGG1Rg"

# Gemini AI Sozlamasi
genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash-latest')

# Bot va Dispatcher (Bular hamma handlerlardan tepada bo'lishi shart!)
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- 2. DATABASE ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, phone TEXT, balance INTEGER DEFAULT 0, invited_by INTEGER)")
    cursor.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, service_name TEXT, api_order_id TEXT, qty INTEGER, price INTEGER, status TEXT DEFAULT 'Bajarilmoqda')")
    conn.commit()
    conn.close()

class BotState(StatesGroup):
    waiting_phone = State()
    topup_amount = State()
    waiting_receipt = State()
    entering_qty = State()
    entering_link = State()
    chat_ai = State()

# --- 3. API FUNKSIYASI ---
def api_request(action, params):
    url_params = {'key': API_KEY, 'action': action}
    url_params.update(params)
    try:
        response = requests.get(API_URL, params=url_params, timeout=15)
        return response.json()
    except:
        return {"error": "Aloqa xatosi"}

# --- 4. KEYBOARDLAR ---
def main_menu_kb(is_admin=False):
    builder = ReplyKeyboardBuilder()
    builder.button(text="📂 Xizmatlar"), builder.button(text="🔍 Buyurtmalarim")
    builder.button(text="💳 Hisob to'ldirish"), builder.button(text="💰 Mening hisobim")
    builder.button(text="👥 Referal"), builder.button(text="🤖 AI Yordamchi")
    builder.button(text="☎️ Qo'llab-quvvatlash")
    if is_admin:
        builder.button(text="📊 Admin Statistika")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

# --- 5. START VA RO'YXATDAN O'TISH ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext, command: CommandObject):
    init_db()
    uid = message.from_user.id
    args = command.args
    conn = sqlite3.connect(DB_NAME)
    user = conn.execute("SELECT phone FROM users WHERE user_id = ?", (uid,)).fetchone()
    
    if not user:
        inviter = None
        if args and args.isdigit() and int(args) != uid:
            inviter = int(args)
        conn.execute("INSERT OR IGNORE INTO users (user_id, invited_by) VALUES (?, ?)", (uid, inviter))
        conn.commit()
        
        builder = ReplyKeyboardBuilder().button(text="📲 Raqamni yuborish", request_contact=True)
        await message.answer("Xush kelibsiz! Botdan foydalanish uchun telefon raqamingizni yuboring:", 
                             reply_markup=builder.as_markup(resize_keyboard=True))
        await state.set_state(BotState.waiting_phone)
    else:
        await message.answer("✅ Xush kelibsiz!", reply_markup=main_menu_kb(uid == ADMIN_ID))
    conn.close()

@dp.message(BotState.waiting_phone, F.contact)
async def get_phone(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    conn = sqlite3.connect(DB_NAME)
    conn.execute("UPDATE users SET phone = ? WHERE user_id = ?", (message.contact.phone_number, uid))
    
    inviter = conn.execute("SELECT invited_by FROM users WHERE user_id = ?", (uid,)).fetchone()
    if inviter and inviter[0]:
        conn.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (REFERAL_BONUS, inviter[0]))
        try: await bot.send_message(inviter[0], f"👥 Yangi do'st qo'shildi! Sizga {REFERAL_BONUS} so'm bonus berildi.")
        except: pass
    
    conn.commit()
    conn.close()
    await state.clear()
    await message.answer("✅ Ro'yxatdan o'tdingiz!", reply_markup=main_menu_kb(uid == ADMIN_ID))

# --- 6. XIZMATLAR VA BUYURTMA ---
@dp.message(F.text == "📂 Xizmatlar")
async def services_handler(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="🟣 Insta Obunachi", callback_data="buy_100_15000_Instagram")
    builder.button(text="🔵 TG Obunachi", callback_data="buy_462_15000_Telegram")
    builder.adjust(1)
    await message.answer("Xizmatni tanlang:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("buy_"))
async def start_order(callback: types.CallbackQuery, state: FSMContext):
    _, sid, price, name = callback.data.split("_")
    await state.update_data(s_id=sid, s_price=int(price), s_name=name)
    await state.set_state(BotState.entering_qty)
    await callback.message.answer(f"🚀 {name} tanlandi. Miqdorni kiriting (Masalan: 1000):")
    await callback.answer()

@dp.message(BotState.entering_qty)
async def process_qty(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return
    qty = int(message.text)
    data = await state.get_data()
    total = int((data['s_price'] / 1000) * qty)
    await state.update_data(qty=qty, total=total)
    builder = InlineKeyboardBuilder().button(text="✅ Tasdiqlash", callback_data="confirm_order")
    await message.answer(f"💰 Jami narx: {total:,} so'm. Tasdiqlaysizmi?", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "confirm_order")
async def ask_link(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(BotState.entering_link)
    await callback.message.edit_text("🔗 Havolani (link) yuboring:")
    await callback.answer()

@dp.message(BotState.entering_link)
async def finish_order(message: types.Message, state: FSMContext):
    data = await state.get_data()
    uid = message.from_user.id
    conn = sqlite3.connect(DB_NAME)
    user_bal = conn.execute("SELECT balance FROM users WHERE user_id = ?", (uid,)).fetchone()[0]
    
    if user_bal < data['total']:
        await message.answer("❌ Mablag' yetarli emas!")
    else:
        res = api_request('add', {'service': data['s_id'], 'link': message.text, 'quantity': data['qty']})
        if 'order' in res:
            conn.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (data['total'], uid))
            conn.execute("INSERT INTO orders (user_id, service_name, api_order_id, qty, price) VALUES (?, ?, ?, ?, ?)", 
                         (uid, data['s_name'], res['order'], data['qty'], data['total']))
            conn.commit()
            await message.answer(f"✅ Buyurtma berildi! ID: {res['order']}")
        else:
            await message.answer(f"❌ API Xatosi: {res.get('error', 'Noma`lum')}")
    conn.close()
    await state.clear()

# --- 7. AI YORDAMCHI (CHAT AI) ---
@dp.message(F.text == "🤖 AI Yordamchi")
async def ai_start(message: types.Message, state: FSMContext):
    kb = ReplyKeyboardBuilder().button(text="❌ Chiqish").as_markup(resize_keyboard=True)
    await message.answer("SMM Botimiz haqida nimalarni bilmoqchisiz? Savolingizni yozing:", reply_markup=kb)
    await state.set_state(BotState.chat_ai)

@dp.message(BotState.chat_ai)
async def ai_chat_handler(message: types.Message, state: FSMContext):
    if message.text == "❌ Chiqish":
        await state.clear()
        return await message.answer("Asosiy menyu", reply_markup=main_menu_kb(message.from_user.id == ADMIN_ID))
    
    wait_msg = await message.answer("⏳ O'ylayapman...")
    
    instruction = (
        f"Siz Abdulning SMM botida yordamchisiz. Bot xizmatlari: Instagram, Telegram obunachilari. "
        f"Botda balansni 'Hisob to'ldirish' tugmasi orqali to'ldirish mumkin. Admin {ADMIN_USER} tasdiqlashi kerak. "
        f"Referal tizimi: har bir do'st uchun {REFERAL_BONUS} so'm bonus beriladi. "
        "Faqat shu bot va SMM bo'yicha juda qisqa va aniq javob bering."
    )
    
    try:
        safety = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        
        response = ai_model.generate_content(
            f"{instruction}\n\nMijoz savoli: {message.text}",
            safety_settings=safety
        )
        await wait_msg.edit_text(response.text if response.text else "AI javob bera olmadi.")
    except Exception as e:
        print(f"AI Xatosi: {e}")
        await wait_msg.edit_text("⚠️ AI tizimi hozircha band yoki hududiy cheklov bor. Birozdan so'ng urinib ko'ring.")

# --- 8. HISOB, ADMIN VA REFERAL ---
@dp.message(F.text == "💰 Mening hisobim")
async def balance_handler(message: types.Message):
    conn = sqlite3.connect(DB_NAME)
    res = conn.execute("SELECT balance FROM users WHERE user_id = ?", (message.from_user.id,)).fetchone()
    conn.close()
    await message.answer(f"🆔 ID: `{message.from_user.id}`\n💰 Balans: {res[0] if res else 0:,} so'm", parse_mode="Markdown")

@dp.message(F.text == "🔍 Buyurtmalarim")
async def orders_handler(message: types.Message):
    conn = sqlite3.connect(DB_NAME)
    rows = conn.execute("SELECT service_name, api_order_id, status FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 5", (message.from_user.id,)).fetchall()
    conn.close()
    if not rows: return await message.answer("Sizda hali buyurtmalar yo'q.")
    text = "📦 Oxirgi buyurtmalar:\n\n"
    for r in rows: text += f"🔹 {r[0]}\nID: `{r[1]}` | {r[2]}\n\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "👥 Referal")
async def referal_handler(message: types.Message):
    bot_me = await bot.get_me()
    ref_link = f"https://t.me/{bot_me.username}?start={message.from_user.id}"
    conn = sqlite3.connect(DB_NAME)
    count = conn.execute("SELECT COUNT(*) FROM users WHERE invited_by = ?", (message.from_user.id,)).fetchone()[0]
    conn.close()
    await message.answer(f"👥 **Referal tizimi**\n\nLink: `{ref_link}`\nBonus: {REFERAL_BONUS} so'm\nDo'stlar: {count} ta", parse_mode="Markdown")

@dp.message(F.text == "☎️ Qo'llab-quvvatlash")
async def support_handler(message: types.Message):
    await message.answer(f"Savollar bo'yicha adminga yozing: {ADMIN_USER}")

@dp.message(F.text == "📊 Admin Statistika", F.from_user.id == ADMIN_ID)
async def admin_stat(message: types.Message):
    conn = sqlite3.connect(DB_NAME)
    u = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    o = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    conn.close()
    await message.answer(f"📊 Statistika:\n\nAzolar: {u}\nBuyurtmalar: {o}")

@dp.message(F.text == "💳 Hisob to'ldirish")
async def topup_handler(message: types.Message, state: FSMContext):
    await state.set_state(BotState.topup_amount)
    await message.answer("💰 Summani kiriting (Faqat raqam):")

@dp.message(BotState.topup_amount)
async def topup_amt(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return
    await state.update_data(amt=int(message.text))
    builder = InlineKeyboardBuilder().button(text="✅ To'ladim", callback_data="sent_receipt")
    await message.answer(f"💵 Karta: `{KARTA_RAQAM}`\nEga: {KARTA_EGA}\nSumma: {message.text} so'm", 
                         reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data == "sent_receipt")
async def receipt_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(BotState.waiting_receipt)
    await callback.message.answer("📸 Chek rasmini yuboring:")
    await callback.answer()

@dp.message(BotState.waiting_receipt, F.photo)
async def process_receipt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    uid = message.from_user.id
    amt = data['amt']
    caption = f"💰 *Yangi to'lov!*\nID: `{uid}`\nSumma: {amt:,} so'm\n\nNusxalash uchun:\n`/plus {uid} {amt}`"
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