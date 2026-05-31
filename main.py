import logging
import asyncio
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage  # Xotira ombori qo'shildi
import sqlite3

# 1. SOZLAMALAR
BOT_TOKEN = "8973838260:AAGXiKqilXrXC9Ozux7uK4bWkqYOrwtKvwA"  # Tokeningizni yozing
ADMIN_ID = 8712872253  # ID raqamingiz

logging.basicConfig(level=logging.INFO)

# Bu yerda MemoryStorage majburiy biriktirildi, xatolik bermasligi uchun
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)
router = Router()

# 2. MA'LUMOTLAR BAZASI BILAN ISHLASH
def init_db():
    conn = sqlite3.connect("movie_bot.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            subscribed INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            code TEXT PRIMARY KEY,
            file_id TEXT,
            caption TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('insta_link', 'https://www.instagram.com/xamzayevich.o7?utm_source=qr')")
    conn.commit()
    conn.close()

def get_setting(key):
    conn = sqlite3.connect("movie_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else "https://instagram.com/"

def set_setting(key, value):
    conn = sqlite3.connect("movie_bot.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE settings SET value=? WHERE key=?", (value, key))
    conn.commit()
    conn.close()

# 3. FSM (STATE) HOLATLARI
class AdminStates(StatesGroup):
    waiting_for_insta_link = State()
    waiting_for_movie_code = State()
    waiting_for_movie_video = State()

# 4. KLAVIATURALAR
def get_sub_keyboard():
    insta_url = get_setting("insta_link")
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1. Instagramga obuna bo'lish 📝", url=insta_url)],
        [InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_sub")]
    ])
    return ikb

def get_admin_keyboard():
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 Kino qo'shish", callback_data="admin_add_movie")],
        [InlineKeyboardButton(text="🔗 Insta Linkni o'zgartirish", callback_data="admin_change_insta")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")]
    ])
    return ikb

# 5. FOYDALANUVCHI HANDLERLARI
@router.message(Command("start"))
async def start_cmd(message: Message, state: FSMContext):
    await state.clear()  # Start bosilganda har qanday chalkash holat o'chadi
    user_id = message.from_user.id
    
    conn = sqlite3.connect("movie_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()
    
    await message.answer(
        "👋 Salom! Kinolarni ko'rish uchun avval quyidagi tugma orqali Instagram sahifamizga obuna bo'ling va keyin 'Tekshirish' tugmasini bosing.",
        reply_markup=get_sub_keyboard()
    )

@router.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    conn = sqlite3.connect("movie_bot.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET subscribed = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    await callback.answer("✅ Obuna tasdiqlandi!")
    await callback.message.edit_text("🎉 Rahmat! Endi menga xohlagan kino kodingizni yuboring, men uni topib beraman.")

# 6. ADMIN HANDLERLARI
@router.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
    await state.clear()  # Har ehtimolga qarshi eski holatlarni tozalaymiz
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("🛠 Admin panelga xush kelibsiz. Quyidagi amallardan birini tanlang:", reply_markup=get_admin_keyboard())

@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect("movie_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM movies")
    total_movies = cursor.fetchone()[0]
    conn.close()
    await callback.message.answer(f"📊 *Bot statistikasi:*\n\n👥 Jami a'zolar: {total_users} ta\n🎬 Jami kinolar: {total_movies} ta", parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "admin_change_insta")
async def change_insta_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await state.set_state(AdminStates.waiting_for_insta_link)
    await callback.message.answer("📝 Yangi Instagram havola (link)ni yuboring:")
    await callback.answer()

@router.message(AdminStates.waiting_for_insta_link)
async def change_insta_save(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    new_link = message.text.strip()
    set_setting("insta_link", new_link)
    await message.answer(f"✅ Instagram link muvaffaqiyatli o'zgartirildi!")
    await state.clear()

@router.callback_query(F.data == "admin_add_movie")
async def add_movie_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    # Birinchi state o'rnatiladi, keyin xabar yuboriladi (Aniq ishlashi uchun)
    await state.set_state(AdminStates.waiting_for_movie_code)
    await callback.message.answer("🔢 Kino uchun kod kiriting (masalan: 155 yoki M7):")
    await callback.answer()

# ADMIN KOD KIRITGANDA SHU HANDLER IShLAYDI (FSM filtri tepadagi oddiy matndan ustun turadi)
@router.message(AdminStates.waiting_for_movie_code)
async def add_movie_code(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    code = message.text.strip()
    await state.update_data(movie_code=code)
    await state.set_state(AdminStates.waiting_for_movie_video)
    await message.answer("📹 Endi ushbu kinoning videosini (yoki kinosi bor kanaldan botingizga video faylni forward qilib) yuboring. Izohiga kino nomini yozishingiz mumkin:")

@router.message(AdminStates.waiting_for_movie_video, F.video)
async def add_movie_video(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    data = await state.get_data()
    movie_code = data['movie_code']
    file_id = message.video.file_id
    caption = message.caption if message.caption else "Kino nomi yozilmagan."
    
    conn = sqlite3.connect("movie_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO movies (code, file_id, caption) VALUES (?, ?, ?)", (movie_code, file_id, caption))
    conn.commit()
    conn.close()
    
    await message.answer(f"✅ Kino muvaffaqiyatli saqlandi!\n🔑 Kodi: {movie_code}")
    await state.clear()

# ODDIY MATN YOKI KINO QIDIRISH (ENG OXIRIDA TURISHI SHART)
@router.message(F.text & ~F.text.startswith('/'))
async def get_movie(message: Message):
    user_id = message.from_user.id
    conn = sqlite3.connect("movie_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT subscribed FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    
    if not res or res[0] == 0:
        await message.answer("⚠️ Kechirasiz, kino ko'rishdan oldin Instagram sahifamizga a'zo bo'lishingiz shart!", reply_markup=get_sub_keyboard())
        conn.close()
        return

    movie_code = message.text.strip()
    cursor.execute("SELECT file_id, caption FROM movies WHERE code = ?", (movie_code,))
    movie = cursor.fetchone()
    conn.close()
    
    if movie:
        file_id, caption = movie
        await message.answer_video(video=file_id, caption=caption)
    else:
        await message.answer("❌ Afsuski, bunday kodli kino topilmadi. Kodni to'g'ri kiritganingizni tekshiring.")

# 7. BOTNI ISHGA TUSHIRISH
async def main():
    init_db()
    dp.include_router(router)
    print("🤖 Bot muvaffaqiyatli ishga tushdi...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
