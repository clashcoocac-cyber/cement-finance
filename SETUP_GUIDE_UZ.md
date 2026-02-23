# 🤖 Cement Finance Bot - To'liq O'rnatish Qo'llanmasi

## O'rnatish Qadamlari

### 1️⃣ Telegram Bot Token olish

1. Telegram dasturida "@BotFather"ni qidiring
2. Uni ochib, `/start` komandasini yuboring
3. `/newbot` komandasini yuboring
4. Bot uchun nom kiriting (masalan: "Cement Finance Bot")
5. Bot uchun username kiriting (masalan: "cement_finance_bot")
6. BotFather tomonidan berilgan **TOKEN**ni nusxalang

### 2️⃣ Environment Setup

```bash
# Lotinasi loyahasiga o'ting
cd /home/komron/cement-finance

# .env faylini yarating
cp .env.example .env

# .env faylini tahrirlang (nano yoki boshqa editor bilan)
nano .env
```

`.env` fayliga quyidagini yozing:
```
BOT_TOKEN=YOUR_TOKEN_HERE
DB_NAME=db.sqlite3
DB_PATH=../db.sqlite3
LOG_LEVEL=INFO
```

### 3️⃣ Dependentsialarni O'rnatish

```bash
# Agar oldin o'rnatilmagan bo'lsa
python -m pip install --upgrade pip

# Barcha paketlarni o'rnatish
pip install -r requirements.txt
```

### 4️⃣ Bot Papkasini Yaratish

Papka strukturasi avtomatik yaratiladi, lekin `temp_pdfs` papkasini qo'l bilan yarating:

```bash
mkdir -p temp_pdfs
chmod 755 temp_pdfs
```

### 5️⃣ Botni Ishga Tushirish

```bash
# 1-usul: To'g'ridan-to'g'ri run
python run_bot.py

# 2-usul: Module sifatida
python -m bot.main
```

Agar muvaffaqiyatli bo'lsa, quyidagi xabar ko'rinadi:
```
INFO - Starting Cement Finance Bot...
INFO - Bot commands set successfully
INFO - Bot is running... (polling mode)
```

## Botni Tekshirish

### 1. Telegram da Bot Topish

1. Telegram dasturida bot usernamesini qidiring (masalan: @cement_finance_bot)
2. Bot bilan ochni
3. `/start` komandasini yuboring

### 2. Test qiling

Bot to'g'ri ishlashini tekshirish uchun:

1. `/start` komandasini yuboring
2. Bot "📞 Telefon raqamimni jo'natish" tugmasini ko'rsatadi
3. Tugmani bosing va telefon raqamingizni yuboring
4. Bot ma'lumotlarni qayta ishlashi kerak

## Muammolarni Hal Qilish

### Problem: "BOT_TOKEN is not set"

**Sababu**: .env vaylida BOT_TOKEN yoq

**Yechim**:
```bash
nano .env
# BOT_TOKEN=XXXXXXXXXXXX qo'shing
```

### Problem: "ModuleNotFoundError: No module named 'aiogram'"

**Sababu**: Paketlar o'rnatilmagan

**Yechim**:
```bash
pip install aiogram reportlab PyPDF2 python-dotenv
```

### Problem: Bot xabar olmayapti

**Sababu**: 
- Bot token noto'g'ri
- Tarmoq ulanmagan
- Firewall blokirovkasi

**Yechim**:
1. TOKEN-ni tekshiring (@BotFather da)
2. Internet ulanishini tekshiring
3. VPN yoqib ko'ring
4. Firewall sozlamalarini tekshiring

### Problem: "No such table: customers"

**Sababu**: Database migrations o'tkazilmagan

**Yechim**:
```bash
python manage.py migrate
```

### Problem: PDF yaratilmayapti

**Sababu**: temp_pdfs papkasi yoki reportlab xatosi

**Yechim**:
```bash
mkdir -p temp_pdfs
pip install --upgrade reportlab
```

## Best Practices - Loyaha Arxitekturasi

### 📁 Papka Tuzilishi

```
bot/
├── config/              # 🔧 Konfiguratsiya
│   ├── __init__.py
│   └── settings.py     # Django settings o'qish
│
├── handlers/            # 📨 Xabar qayta ishlash
│   ├── __init__.py
│   ├── start.py        # /start komandasi
│   └── phone.py        # Telefon raqamini qabul qilish
│
├── services/            # 🛠️ Biznes logikasi
│   ├── __init__.py
│   ├── database.py     # Django ORM'dan o'qish
│   └── pdf_generator.py # PDF yaratish
│
├── middlewares/         # 🔀 O'rtacha dastur
│   ├── __init__.py
│   └── logging.py      # Loglarni yozish
│
├── main.py             # 🚀 Asosiy bot fayli
├── constants.py        # ⚙️ Konstantalar
├── README.md           # English qo'llanma
└── README_UZ.md        # Uzbek qo'llanma
```

### 🔑 Muhim Modullar

**settings.py**
- Environment variables o'qish
- Bot konfiguratsiyasi
- Django sozlama

**database.py**
- Django ORM'dan ma'lumot o'qish
- Customer qidirish
- Buyurtmalarni ro'yxat qilish

**pdf_generator.py**
- ReportLab kutubxonasidan foydalanish
- Professional PDF yaratish
- Jadvallar va yo'l yuning tasniflash

**handlers/start.py**
- /start komandasi
- Telefon raqamini so'rash
- Hisobotni berish

**handlers/phone.py**
- Telefon raqamini qabul qilish
- Ma'lumotlarni izlash
- PDF yaratish va yuborish

### 🛡️ Xavfsizlik

✅ Environment variables orqali konfidential ma'lumotlarni saqlash  
✅ Xatoli qayta ishlash  
✅ Loglarni tekshiriş  
✅ Input validatsiyasi

### 📊 Logging

Bot barcha faoliyatlarni logga yozadi:
```
INFO - Bot started
INFO - User X sent command
INFO - PDF generated
ERROR - Database error
```

Log darajalarini o'zgartirish:
```bash
LOG_LEVEL=DEBUG python run_bot.py  # Detallı log
LOG_LEVEL=WARNING python run_bot.py # Faqat ogohlantirish
```

## Kengaytirishni Davom Ettirish

### Buyurtmanyosh Ko'ppa Qilish

`handlers/phone.py` da callback button qo'shing:

```python
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Tugmalar
keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Qaytadan yuborish", callback_data="refresh")]
])
```

### E-pochtaga Yuborish

```python
import smtplib
# PDF ni e-pochtaga yuborish
```

### Statistika

Models da:
```python
class BotStatistics(models.Model):
    user_id = models.IntegerField()
    requests_count = models.IntegerField()
    last_request = models.DateTimeField()
```

## Mahalliy Ishga Tushirish (Development)

```bash
# Virtual environment yaratish
python -m venv env

# Activate qilish
source env/bin/activate  # Linux/Mac
# yoki
env\Scripts\activate  # Windows

# Paketlarni o'rnatish
pip install -r requirements.txt

# Bot-ni start qilish
python run_bot.py
```

## Production Sozlama

### Systemd Service Yaratish

`/etc/systemd/system/cement-bot.service` faylini yarating:

```ini
[Unit]
Description=Cement Finance Bot
After=network.target

[Service]
Type=simple
User=komron
WorkingDirectory=/home/komron/cement-finance
Environment="PATH=/home/komron/cement-finance/env/bin"
ExecStart=/home/komron/cement-finance/env/bin/python run_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Shundan keyin:
```bash
sudo systemctl daemon-reload
sudo systemctl enable cement-bot
sudo systemctl start cement-bot
sudo systemctl status cement-bot
```

## Kontakt va Qo'llab-quvvatlash

Savollar yoki muammolar bo'lsa, admin bilan bog'laning.

---

**Oxirgi yangilash**: 2024  
**Versiya**: 1.0.0  
**Til**: Uzbek / English
