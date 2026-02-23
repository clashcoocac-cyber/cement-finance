"""
Phone number handler and callback queries
"""
import logging
import os
from datetime import datetime
from aiogram import Router, types, F
from aiogram.filters import Filter
from aiogram.types import ReplyKeyboardRemove

from bot.services import CustomerService, PDFGenerator
from bot.config.settings import get_settings


logger = logging.getLogger(__name__)

phone_router = Router()


class ContactFilter(Filter):
    """Filter for contact messages"""
    async def __call__(self, message: types.Message) -> bool:
        return message.contact is not None


@phone_router.message(ContactFilter())
async def handle_contact(message: types.Message):
    """
    Handle contact/phone number from user
    """
    try:
        phone = message.contact.phone_number if message.contact else None
        logger.info(phone)
        
        if not phone:
            await message.answer(
                "❌ Telefon raqamini olishda xatolik. Iltimos, qayta urinib ko'ring.",
                reply_markup=ReplyKeyboardRemove()
            )
            return
        
        # Format phone number
        
        logger.info(f"Processing phone number: {phone}")
        
        # Show processing message
        status_msg = await message.answer("⏳ Ma'lumot izlanmoqda...")
        
        # Get customer data (async call)
        customer = await CustomerService.get_customer_by_phone(phone)
        
        if not customer:
            await status_msg.delete()
            await message.answer(
                f"❌ Telefon raqami <b>{phone}</b> bizning bazada topilmadi.\n\n"
                "Iltimos, admin bilan bog'laning.",
                parse_mode="HTML",
                reply_markup=ReplyKeyboardRemove()
            )
            logger.warning(f"Customer not found for phone: {phone}")
            return
        
        # Get combined data with cumulative debt (async call)
        combined_data, _ = await CustomerService.get_customer_combined_data(customer['id'])
        summary = await CustomerService.get_customer_summary(customer['id'])
        
        # Generate PDF
        settings = get_settings()
        pdf_generator = PDFGenerator(settings.PDF_TEMP_DIR)
        pdf_path = pdf_generator.generate_customer_report(customer, combined_data, summary)
        
        # Send PDF
        await status_msg.delete()
        
        try:
            await message.answer_document(
                types.FSInputFile(pdf_path),
                caption=f"{customer['name']}\n{datetime.now().strftime('%Y-%m-%d')}",
                reply_markup=ReplyKeyboardRemove()
            )
        finally:
            # Delete temp PDF file
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
                logger.info(f"Deleted temp PDF: {pdf_path}")
        
        # Send debt message

        
        logger.info(f"Successfully processed customer: {customer['name']} ({phone})")
        
    except Exception as e:
        logger.error(f"Error processing contact: {e}", exc_info=True)
        await message.answer(
            "❌ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring yoki admin bilan bog'laning.",
            reply_markup=ReplyKeyboardRemove()
        )


def validate_phone(phone: str) -> bool:
    """
    Validate phone number format
    Accepts: 998934701803, +998934701803, 34701803, 9934701803
    """
    phone_clean = phone.strip().replace('+', '').replace(' ', '').replace('-', '')
    
    # Check if valid Uzbek phone number
    if len(phone_clean) == 12 and phone_clean.startswith('998'):
        return True
    if len(phone_clean) == 9 and phone_clean.isdigit():
        return True
    if len(phone_clean) == 10 and phone_clean.startswith('99'):
        return True
    
    return False


@phone_router.message()
async def handle_text(message: types.Message):
    """
    Handle text input - phone number entered manually
    """
    if not message.text:
        return
    
    phone = message.text.strip()
    
    # Check if it looks like a phone number
    if not phone.replace('+', '').replace(' ', '').replace('-', '').isdigit():
        await message.answer(
            "ℹ️ Iltimos, telefon raqamini to'g'ri kiriting.\n"
            "Masallar: 998934701803, +998934701803, 34701803",
            parse_mode="HTML"
        )
        return
    
    # Validate phone format
    if not validate_phone(phone):
        await message.answer(
            "❌ Telefon raqami noto'g'ri format.\n\n"
            "<b>To'g'ri formatlar:</b>\n"
            "• 998934701803\n"
            "• +998934701803\n"
            "• 34701803",
            parse_mode="HTML"
        )
        return
    
    # Format phone number to standard
    phone_clean = phone.replace('-', '').replace(' ', '').replace('(', '').replace(')', '')

    logger.info(f"Processing phone number from text: {phone_clean}")
    
    # Show processing message
    status_msg = await message.answer("⏳ Ma'lumot izlanmoqda...")
    
    try:
        # Get customer data (async call)
        customer = await CustomerService.get_customer_by_phone(phone_clean)
        
        if not customer:
            await status_msg.delete()
            await message.answer(
                f"❌ Telefon raqami <b>{phone_clean}</b> bizning bazada topilmadi.\n\n"
                "Iltimos, admin bilan bog'laning.",
                parse_mode="HTML"
            )
            logger.warning(f"Customer not found for phone: {phone_clean}")
            return
        
        # Get combined data with cumulative debt (async call)
        combined_data, _ = await CustomerService.get_customer_combined_data(customer['id'])
        summary = await CustomerService.get_customer_summary(customer['id'])
        
        # Generate PDF
        settings = get_settings()
        pdf_generator = PDFGenerator(settings.PDF_TEMP_DIR)
        pdf_path = pdf_generator.generate_customer_report(customer, combined_data, summary)
        
        # Send PDF
        await status_msg.delete()
        
        try:
            await message.answer_document(
                types.FSInputFile(pdf_path),
                caption=f"{customer['name']}\n{datetime.now().strftime('%Y-%m-%d')}"
            )
        finally:
            # Delete temp PDF file
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
                logger.info(f"Deleted temp PDF: {pdf_path}")
                
        logger.info(f"Successfully processed customer: {customer['name']} ({phone_clean})")
        
    except Exception as e:
        logger.error(f"Error processing phone: {e}", exc_info=True)
        await message.answer(
            "❌ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring yoki admin bilan bog'laning."
        )


@phone_router.callback_query(F.data.startswith("customer_"))
async def handle_customer_callback(query: types.CallbackQuery):
    """
    Handle customer selection from list
    """
    try:
        customer_id = int(query.data.split("_")[1])
        
        await query.answer("⏳ Ma'lumot yuklanmoqda...")
        
        # Get customer data
        customers = await CustomerService.get_all_customers()
        customer = None
        for c in customers:
            if c['id'] == customer_id:
                customer = c
                break
        
        if not customer:
            await query.message.edit_text("❌ Mijoz topilmadi")
            return
        
        # Get combined data with cumulative debt (async call)
        combined_data, _ = await CustomerService.get_customer_combined_data(customer['id'])
        summary = await CustomerService.get_customer_summary(customer['id'])
        
        # Generate PDF
        settings = get_settings()
        pdf_generator = PDFGenerator(settings.PDF_TEMP_DIR)
        pdf_path = pdf_generator.generate_customer_report(customer, combined_data, summary)
        
        # Edit message
        await query.message.edit_text(
            f"📄 {customer['name']} ning hisoboti tayyorlanmoqda..."
        )
        
        # Send PDF
        try:
            await query.message.answer_document(
                types.FSInputFile(pdf_path),
                caption=f"{customer['name']}\n{datetime.now().strftime('%Y-%m-%d')}"
            )
        finally:
            # Delete temp PDF file
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
                logger.info(f"Deleted temp PDF: {pdf_path}")
        
        # Send debt message
        try:
            total_debt = summary.get('total_debt', 0) if summary else 0
            if total_debt == 0:
                debt_status = "✅"
                debt_message = "Qarz yo'q"
            else:
                debt_status = "⚠️"
                debt_message = f"{total_debt:,} so'm"
            
            summary_text = f"{debt_status} <b>Qarzdorlik:</b> {debt_message}"
            await query.message.answer(summary_text, parse_mode="HTML")
            logger.info(f"Debt message sent successfully: {debt_message}")
        except Exception as debt_error:
            logger.error(f"Error sending debt message: {debt_error}")
            await query.message.answer("Qarzylik ma'lumoti yuborildi.")
        
        logger.info(f"Successfully processed customer from list: {customer['name']}")
        
    except Exception as e:
        logger.error(f"Error processing callback: {e}", exc_info=True)
        await query.message.edit_text(
            "❌ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring."
        )
