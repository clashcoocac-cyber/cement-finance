"""
Bot constants and utilities
"""

# Phone number formats
PHONE_FORMATS = [
    # Uzbekistan phone numbers
    r'^\+?998\d{9}$',
    r'^998\d{9}$',
    r'^\d{9}$',
    r'^0\d{9}$',
]

# Bot messages
BOT_MESSAGES = {
    'start': (
        "Assalomu alaikum! 👋\n\n"
        "Siz o'z buyurtmalar va qarzyligingizni ko'rish uchun telefon raqamingizni jo'nating."
    ),
    'help': (
        "📋 <b>Bot qo'llanma:</b>\n\n"
        "1️⃣ <b>/start</b> - Botni boshlab, raqamingizni jo'nating\n"
        "2️⃣ Telefon raqamingiz orqali o'z ma'lumotlaringizni oling\n"
        "3️⃣ Bot PDF fayl shaklida hisobotni yuboradi\n\n"
        "<i>Agar xatolik bo'lsa admin bilan bog'laning</i>"
    ),
    'processing': "⏳ Ma'lumot izlanmoqda...",
    'not_found': "❌ Telefon raqami <b>{phone}</b> bizning bazada topilmadi.\n\nIltimos, admin bilan bog'laning.",
    'error': "❌ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring yoki admin bilan bog'laning.",
    'text_fallback': "ℹ️ Iltimos, <b>📞 Telefon raqamimni jo'natish</b> tugmasini ishlating yoki /start komandasini yozing.",
}

# PDF settings
PDF_TITLE = "BUYURTMALAR VA QARZYLIK HISOBOTI"
PDF_TEMP_DIR = "temp_pdfs"

# Date format
DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M"
