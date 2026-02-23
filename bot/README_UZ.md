# Cement Finance Bot

Telegram bot asosida qurilgan mijozlar uchun buyurtmalar va qarzylik hisobot tizimi.

## Xususiyatlari

✅ Telefon raqami orqali mijoz qidirish  
✅ PDF formatida hisobotlar yuborish  
✅ Jami buyurtma summasi va qarzylik ko'rish  
✅ Xarid tarixi ko'rish

## O'rnatish

### 1. Dependentsialarni o'rnatish

```bash
pip install -r requirements.txt
```

### 2. Telegram Bot Token olish

1. Telegram da `@BotFather` ga xabar yuboring
2. `/newbot` komandasini ishlating
3. Bot uchun nom va username tanlang
4. Token-ni nusxalang

### 3. Environment variables sozlash

`.env` faylini yarating va `BOT_TOKEN` ni qo'shing:

```bash
cp .env.example .env
# .env faylini tahrirlang va BOT_TOKEN ni o'rnating
```

### 4. Botni ishga tushirish

```bash
python run_bot.py
```

yoki

```bash
python -m bot.main
```

## Loyaha tuzilishi

```
bot/
├── config/              # Konfiguratsiya
│   └── settings.py     # Bot sozlamalari
├── handlers/            # Xabar qayta ishlash
│   ├── start.py        # /start komandasi
│   └── phone.py        # Telefon raqamini qabul qilish
├── services/            # Biznes logikasi
│   ├── database.py     # Ma'lumot bazasi xizmati
│   └── pdf_generator.py # PDF yaratish
├── middlewares/         # O'rtacha dastur
│   └── logging.py      # Loglarni yozish
└── main.py             # Asosiy bot fayli
```

## Ishlash jarayoni

1. Foydalanuvchi `/start` komandasini yubor(adi)
2. Bot telefon raqamini so'raydi
3. Foydalanuvchi telefon raqamini jo'natadi
4. Bot ma'lumot bazasida qidiradi
5. PDF hisobotini yaratadi va yuboradi

## Best Practices

✅ **Separation of Concerns** - Services, Handlers, Middleware ajratilgan  
✅ **Logging** - Barcha operatsiyalar logga yoziladi  
✅ **Error Handling** - Xatoliklar yaxshi qayta ishlash  
✅ **Configuration** - Environment variables orqali  
✅ **Documentation** - Docstrings va sharhlar  
✅ **Asynchronous** - Aiogram async/await ishlatadi  

## Admin Uchun To'lqin Shartlari

### PDF Hisobotda ko'rinishi:

```
BUYURTMALAR VA QARZYLIK HISOBOTI

Mijoz nomi: [Ism]
Telefon: [Raqam]
Manzil: [Manzil]
Vaqt: [YYYY-MM-DD HH:MM]

Jami buyurtma summasi: [Summa] so'm
Jami to'langan: [Summa] so'm
Jami qarzylik: [Summa] so'm
Standart qarzylik: [Summa] so'm

BUYURTMALAR RO'YXATI
[Jadval]
```

## Debugging

Loglarni ko'rish uchun:

```bash
# INFO va undan yuqori darajasi
LOG_LEVEL=INFO python run_bot.py

# Barcha loglar, shu jumladan DEBUG
LOG_LEVEL=DEBUG python run_bot.py
```

## Muammolar

### Bot xabar olmayapti?

1. BOT_TOKEN to'g'ri ekanligini tekshiring
2. Bot @BotFather ga /start yuboring
3. Bot guruhlarga qo'shilishga ruxsat berganligini tekshiring

### PDF yaratilmayapti?

1. `temp_pdfs` papkasi yaratilganligini tekshiring
2. Reportlab o'rnatilganligini tekshiring: `pip install reportlab`

### Ma'lumot bazasi bilan aloqa?

1. Django sozlamalari to'g'ri ekanligini tekshiring
2. `db.sqlite3` mavjud ekanligini tekshiring
3. Database migrations o'tkazilganligini tekshiring

## Kontakt

Muammolar yoki takliflar uchun admin bilan bog'laning.
