"""
PDF Generator service for creating customer reports
"""
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from reportlab.lib.pagesizes import letter, A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os


def register_fonts():
    """Register fonts that support Cyrillic characters"""
    # Try to register DejaVu fonts which support Cyrillic
    font_paths = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',  # Linux
        '/System/Library/Fonts/Arial.ttf',  # macOS
        'C:\\Windows\\Fonts\\arial.ttf',  # Windows
    ]
    
    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont('Arial', font_path))
                return True
            except Exception:
                continue
    
    return False


# Register fonts at module load
register_fonts()


class PDFGenerator:
    """Generate PDF reports for customers"""
    
    def __init__(self, temp_dir: Path):
        """
        Initialize PDF generator
        
        Args:
            temp_dir: Directory to store temporary PDF files
        """
        self.temp_dir = temp_dir
        self.temp_dir.mkdir(exist_ok=True)
    
    def generate_customer_report(
        self,
        customer_data: Dict,
        combined_data: List[Dict] = None,
        summary: Dict = None
    ) -> Path:
        """
        Generate customer report PDF with combined orders and payments
        
        Args:
            customer_data: Customer information
            combined_data: Combined orders and payments list with cumulative debt
            summary: Summary information (optional)
            
        Returns:
            Path to generated PDF file
        """
        if combined_data is None:
            combined_data = []
        if summary is None:
            summary = {}
        
        filename = f"report_{customer_data['phone']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = self.temp_dir / filename
        
        # Create PDF (Landscape orientation)
        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=landscape(A4),
            rightMargin=0.4*inch,
            leftMargin=0.4*inch,
            topMargin=0.4*inch,
            bottomMargin=0.4*inch
        )
        
        elements = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=6,
            alignment=1,  # center
            fontName='Arial'
        )
        elements.append(Paragraph("BUYURTMALAR VA QARZYLIK HISOBOTI", title_style))
        elements.append(Spacer(1, 0.2*inch))
        
        # Customer Info
        customer_info_style = ParagraphStyle(
            'CustomerInfo',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.black,
            spaceAfter=3,
            fontName='Arial'
        )
        customer_info = f"""
        <b>Mijoz nomi:</b> {customer_data['name']}<br/>
        <b>Telefon:</b> {customer_data['phone']}<br/>
        <b>Manzil:</b> {customer_data['address']}<br/>
        <b>Vaqt:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}
        """
        elements.append(Paragraph(customer_info, customer_info_style))
        elements.append(Spacer(1, 0.15*inch))
        
        # Calculate starting and current debt
        if combined_data:
            first_transaction = combined_data[0]
            last_transaction = combined_data[-1]
            
            # Starting debt (before first transaction)
            if first_transaction['type'] == 'order':
                eski_qarzdorlik = first_transaction['cumulative_debt'] - first_transaction['remaining_debt']
            else:  # payment
                eski_qarzdorlik = first_transaction['cumulative_debt'] + first_transaction['paid_amount']
            
            # Current debt (after last transaction)
            hozirgi_qarz = last_transaction['cumulative_debt']
        else:
            eski_qarzdorlik = summary.get('total_debt', 0)
            hozirgi_qarz = summary.get('total_debt', 0)
        
        # Display starting and current debt
        debt_info_style = ParagraphStyle(
            'DebtInfo',
            parent=styles['Normal'],
            fontSize=11,
            textColor=colors.black,
            spaceAfter=3,
            fontName='Arial'
        )
        elements.append(Paragraph(f"<b>Eski qarzdorlik:</b> {eski_qarzdorlik:,} so'm", debt_info_style))
        elements.append(Paragraph(f"<b>Hozirgi qarz:</b> {hozirgi_qarz:,} so'm", debt_info_style))
        elements.append(Spacer(1, 0.12*inch))
        
        # Combined Transaction History with Cumulative Debt (Web App format)
        if combined_data:
            heading_style = ParagraphStyle(
                'Heading2Custom',
                parent=styles['Heading2'],
                fontName='Arial'
            )
            elements.append(Paragraph("<b>BUYURTMALAR RO'YXATI</b>", heading_style))
            elements.append(Spacer(1, 0.1*inch))
            
            # Header row matching web app: Sana | Turi | Mashina | Miqdori | Narxi | Yo'l Harajati | Jami | Olingan | Qarz
            transactions_data = [
                ['Sana', 'Turi', 'Mashina', 'Miqdori\n(kg)', 'Narxi\n(so\'m/kg)', 'Yo\'l\nHarajati', 'Jami', 'Olingan', 'Qarz'],
            ]
            
            # Add each transaction
            for transaction in combined_data:
                if transaction['type'] == 'order':
                    # Order transaction row
                    cement_type = transaction['cement_type']
                    car_number = transaction['car_number'] if transaction['car_number'] else '-'
                    quantity = f"{transaction['quantity']:,}"
                    price = f"{transaction['price_per_kg']:,}"
                    road_cost = f"{transaction['road_cost']:,}" if transaction['road_cost'] > 0 else '0'
                    total = f"{transaction['total_sum']:,}"
                    paid = f"{transaction['paid_amount']:,}"
                    debt = f"{transaction['cumulative_debt']:,}"
                    
                    transactions_data.append([
                        transaction['date'],
                        cement_type,
                        car_number,
                        quantity,
                        price,
                        road_cost,
                        total,
                        paid,
                        debt,
                    ])
                else:
                    # Payment transaction row
                    payment_type = transaction['payment_type']
                    transactions_data.append([
                        transaction['date'],
                        payment_type,
                        '-',  # Mashina
                        '-',  # Miqdori
                        '-',  # Narxi
                        '-',  # Road cost
                        '-',  # Jami
                        f"{transaction['paid_amount']:,}",  # Olingan (payment amount)
                        f"{transaction['cumulative_debt']:,}",  # Qarz
                    ])
            
            # Create table with landscape widths
            transactions_table = Table(transactions_data, colWidths=[0.65*inch, 1.1*inch, 0.9*inch, 0.75*inch, 0.85*inch, 0.75*inch, 1*inch, 1*inch, 1*inch])
            
            # Build table style
            table_style_commands = [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8eff5')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Arial'),
                ('FONTSIZE', (0, 0), (-1, 0), 7),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('TOPPADDING', (0, 0), (-1, 0), 6),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('FONTNAME', (0, 1), (-1, -1), 'Arial'),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),    # Date - center
                ('ALIGN', (1, 1), (1, -1), 'LEFT'),      # Type - left
                ('ALIGN', (2, 1), (2, -1), 'CENTER'),    # Vehicle - center
                ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),    # Numeric columns - right
            ]
            
            # Color rows: light blue for orders, light green for payments
            for idx, transaction in enumerate(combined_data, start=1):
                if transaction['type'] == 'order':
                    # Light blue for orders
                    bg_color = colors.HexColor('#e3f2fd')
                else:
                    # Light green for payments
                    bg_color = colors.HexColor('#e8f5e9')
                
                table_style_commands.append(('BACKGROUND', (0, idx), (-1, idx), bg_color))
            
            transactions_table.setStyle(TableStyle(table_style_commands))
            elements.append(transactions_table)
        else:
            elements.append(Paragraph("Buyurtmalar topilmadi", styles['Normal']))
        
        # Build PDF
        doc.build(elements)
        
        return filepath
