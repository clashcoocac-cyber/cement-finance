# Cement Finance Bot

Telegram bot for customers to view their orders and outstanding debt reports.

## Features

✅ Customer search by phone number  
✅ PDF report generation  
✅ View total orders and outstanding debt  
✅ Order history tracking

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Get Telegram Bot Token

1. Message `@BotFather` on Telegram
2. Use `/newbot` command
3. Choose a name and username for your bot
4. Copy the token provided

### 3. Setup Environment Variables

Create `.env` file and add your `BOT_TOKEN`:

```bash
cp .env.example .env
# Edit .env and add your BOT_TOKEN
```

### 4. Run the Bot

```bash
python run_bot.py
```

or

```bash
python -m bot.main
```

## Project Structure

```
bot/
├── config/              # Configuration
│   └── settings.py     # Bot settings
├── handlers/            # Message handlers
│   ├── start.py        # /start command
│   └── phone.py        # Phone number handler
├── services/            # Business logic
│   ├── database.py     # Database service
│   └── pdf_generator.py # PDF generation
├── middlewares/         # Middleware
│   └── logging.py      # Logging middleware
└── main.py             # Main bot file
```

## Workflow

1. User sends `/start` command
2. Bot requests phone number
3. User shares their phone number
4. Bot searches database
5. Bot generates and sends PDF report

## Best Practices Applied

✅ **Separation of Concerns** - Services, Handlers, Middlewares separated  
✅ **Logging** - All operations logged  
✅ **Error Handling** - Comprehensive error handling  
✅ **Configuration** - Environment variables for config  
✅ **Documentation** - Docstrings for all functions  
✅ **Asynchronous** - Aiogram async/await pattern  
✅ **Django Integration** - Direct ORM usage  
✅ **Type Hints** - Python type hints for clarity

## PDF Report Format

```
CUSTOMER ORDERS AND DEBT REPORT

Customer Name: [Name]
Phone: [Number]
Address: [Address]
Time: [YYYY-MM-DD HH:MM]

Total Orders: [Amount] som
Total Paid: [Amount] som
Total Debt: [Amount] som
Default Debt: [Amount] som

ORDERS LIST
[Table with all orders]
```

## Debugging

View logs:

```bash
# INFO level and above
LOG_LEVEL=INFO python run_bot.py

# All logs including DEBUG
LOG_LEVEL=DEBUG python run_bot.py
```

## Troubleshooting

### Bot not receiving messages?

1. Verify BOT_TOKEN is correct
2. Send /start to @BotFather
3. Check if bot has permission for groups

### PDF not generating?

1. Check if `temp_pdfs` directory exists
2. Verify reportlab is installed: `pip install reportlab`
3. Check file permissions

### Database connection issues?

1. Verify Django settings are correct
2. Check if `db.sqlite3` exists
3. Ensure migrations are applied: `python manage.py migrate`

## Support

For issues or suggestions, contact the administrator.
