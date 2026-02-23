"""
Start command handler
"""
import logging
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup

from bot.services import CustomerService


logger = logging.getLogger(__name__)

start_router = Router()


@start_router.message(Command("start"))
async def cmd_start(message: types.Message):
    """
    Start command handler
    Asks user to share phone number or type it
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(
                text="📞 Telefon raqamimni jo'natish",
                request_contact=True
            )]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    
    await message.answer(
        "Assalomu alaykum! 👋\n\n"
        "Siz o'z buyurtma va qarzlaringizni ko'rish uchun telefon raqamingizni jo'nating.\n\n"
        "Tugmani bosing yoki raqamni to'g'ridan-to'g'ri yozing",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    logger.info(f"User {message.from_user.id} started the bot")


@start_router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Help command"""
    await message.answer(
        "📋 <b>Bot qo'llanma:</b>\n\n"
        "1️⃣ <b>/start</b> - Botni boshlab, raqamingizni jo'nating\n"
        "2️⃣ Telefon raqamingiz orqali o'z ma'lumotlaringizni oling\n"
        "3️⃣ Bot PDF fayl shaklida hisobotni yuboradi\n"
        "4️⃣ <b>/customers</b> - Barcha mijozlarni ko'rish (Admin)\n\n"
        "<i>Agar xatolik bo'lsa admin bilan bog'laning</i>",
        parse_mode="HTML"
    )


@start_router.message(Command("customers"))
async def cmd_customers(message: types.Message):
    """
    Show all customers - Admin command
    """
    try:
        await message.answer("⏳ Mijozlar ro'yxati yuklanmoqda...")
        
        # Get all customers
        customers = await CustomerService.get_all_customers()
        
        if not customers:
            await message.answer(
                "❌ Bazada hech qanday mijoz topilmadi.",
                parse_mode="HTML"
            )
            return
        
        # Create inline buttons for customers
        buttons = []
        for customer in customers:
            buttons.append([
                InlineKeyboardButton(
                    text=f"👤 {customer['name']} ({customer['phone']})",
                    callback_data=f"customer_{customer['id']}"
                )
            ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await message.answer(
            f"📋 <b>Barcha mijozlar ({len(customers)} ta):</b>\n\n"
            "Birini tanlang:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error getting customers: {e}", exc_info=True)
        await message.answer(
            "❌ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring."
        )
