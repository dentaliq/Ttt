import os
import requests
import json
import math
import qrcode
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from flask import Flask, request, jsonify

# Flask App setup
app = Flask(__name__)

# Telegram Bot API credentials
BOT_TOKEN = 'YOUR_BOT_TOKEN'
CHAT_ID = 'YOUR_CHAT_ID'

# Market location for distance calculation
MARKET_LOCATION = {'lat': 32.6468089, 'lng': 43.9782430}

# Register a font that supports Arabic script
try:
    pdfmetrics.registerFont(TTFont('Tajawal', 'Tajawal-Regular.ttf'))
    pdfmetrics.registerFont(TTFont('Tajawal-Bold', 'Tajawal-Bold.ttf'))
except Exception as e:
    print(f"Error loading Arabic font: {e}. Please ensure 'Tajawal-Regular.ttf' and 'Tajawal-Bold.ttf' are in the same directory.")
    # Fallback font
    pdfmetrics.registerFont(TTFont('Arabic', 'arial.ttf'))
    pdfmetrics.registerFont(TTFont('Arabic-Bold', 'arialbd.ttf'))

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371e3  # metres
    φ1 = math.radians(lat1)
    φ2 = math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)

    a = math.sin(Δφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

def send_telegram_message(text, chat_id=CHAT_ID):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML'
    }
    return requests.post(url, json=payload)

def send_telegram_document(file_path, chat_id=CHAT_ID, caption=''):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    files = {
        'document': open(file_path, 'rb')
    }
    payload = {
        'chat_id': chat_id,
        'caption': caption
    }
    return requests.post(url, data=payload, files=files)

def create_order_pdf(order_details, filename="order.pdf"):
    try:
        doc = SimpleDocTemplate(filename, pagesize=letter)
        story = []
        styles = getSampleStyleSheet()
        
        # Check if Arabic font is registered
        font_name = 'Tajawal' if 'Tajawal' in pdfmetrics.getFontNames() else 'Arabic'
        font_name_bold = 'Tajawal-Bold' if 'Tajawal-Bold' in pdfmetrics.getFontNames() else 'Arabic-Bold'

        # Title
        title_style = styles['Title']
        title_style.fontName = font_name_bold
        title_style.alignment = 1 # Center
        story.append(Paragraph("سوبر ماركت العراق", title_style))
        story.append(Spacer(1, 0.2 * inch))

        # Date
        date_style = styles['Normal']
        date_style.fontName = font_name
        date_style.alignment = 1
        story.append(Paragraph("تاريخ الطلب: 1-9-2025", date_style)) # Static date for now
        story.append(Spacer(1, 0.5 * inch))

        # Customer Info
        info_style = styles['Normal']
        info_style.fontName = font_name
        info_style.alignment = 2 # Right
        story.append(Paragraph(f"الاسم: {order_details['customer']['name']}", info_style))
        story.append(Paragraph(f"الهاتف: {order_details['customer']['phone']}", info_style))
        story.append(Spacer(1, 0.2 * inch))

        # Order table
        table_data = [
            [
                Paragraph("<b>الإجمالي</b>", styles['Normal']),
                Paragraph("<b>السعر</b>", styles['Normal']),
                Paragraph("<b>الكمية</b>", styles['Normal']),
                Paragraph("<b>المنتج</b>", styles['Normal'])
            ]
        ]
        
        table_style = styles['Normal']
        table_style.fontName = font_name
        
        total_price_num = 0
        for item_name, item_data in order_details['items'].items():
            item_total = item_data['price'] * item_data['quantity']
            total_price_num += item_total
            table_data.append([
                Paragraph(f"{item_total:,.0f} د.ع", table_style),
                Paragraph(f"{item_data['price']:,.0f} د.ع", table_style),
                Paragraph(str(item_data['quantity']), table_style),
                Paragraph(item_name, table_style)
            ])

        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1c212c')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTNAME', (0, 0), (-1, 0), font_name_bold),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#ffffff')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ])

        order_table = Table(table_data, colWidths=[2*inch, 1.5*inch, 1*inch, 2*inch])
        order_table.setStyle(table_style)
        story.append(order_table)
        story.append(Spacer(1, 0.2 * inch))

        # Total Price
        total_style = styles['Heading2']
        total_style.fontName = font_name_bold
        total_style.alignment = 0 # Left
        story.append(Paragraph(f"المجموع الإجمالي: {total_price_num:,.0f} د.ع", total_style))
        story.append(Spacer(1, 0.5 * inch))
        
        # QR Code for location
        if order_details['customer']['location']:
            qr_data = f"https://www.google.com/maps/place/{order_details['customer']['location']['lat']},{order_details['customer']['location']['lng']}"
            qr_img = qrcode.make(qr_data)
            qr_img_path = "qr_code.png"
            qr_img.save(qr_img_path)
            
            story.append(Paragraph("امسح الباركود للوصول إلى موقع العميل:", info_style))
            story.append(Spacer(1, 0.2 * inch))
            
            img = Image(qr_img_path)
            img.drawHeight = 2*inch
            img.drawWidth = 2*inch
            img.hAlign = 'CENTER'
            story.append(img)
            os.remove(qr_img_path)
            
        doc.build(story)
        return filename
        
    except Exception as e:
        print(f"Error creating PDF: {e}")
        return None

@app.route('/send-order', methods=['POST'])
def send_order():
    try:
        order_details = request.get_json()
        
        # Send text message to Telegram
        text_message = f"✅ طلب جديد من السوبر ماركت:\n\n"
        text_message += f"الاسم: {order_details['customer']['name']}\n"
        text_message += f"الهاتف: {order_details['customer']['phone']}\n"
        
        if 'location' in order_details['customer'] and order_details['customer']['location']:
            lat = order_details['customer']['location']['lat']
            lng = order_details['customer']['location']['lng']
            distance = haversine_distance(MARKET_LOCATION['lat'], MARKET_LOCATION['lng'], lat, lng)
            text_message += f"الإحداثيات: {lat}, {lng}\n"
            text_message += f"المسافة عن المتجر: {distance:,.2f} متر\n"
            text_message += f"الموقع الجغرافي: https://www.google.com/maps/place/{lat},{lng}\n"
        else:
            text_message += f"ملاحظة: لم يتمكن العميل من إرسال موقعه الجغرافي.\n"
        
        text_message += f"\nالمنتجات:\n"
        for item_name, item_data in order_details['items'].items():
            item_total = item_data['price'] * item_data['quantity']
            text_message += f"• {item_name} (الكمية: {item_data['quantity']}) - السعر: {item_total:,.0f} د.ع\n"
        
        text_message += f"\nالمجموع الإجمالي: {order_details['total']}"
        
        send_telegram_message(text_message)
        
        # Create and send PDF
        pdf_file = create_order_pdf(order_details)
        if pdf_file:
            send_telegram_document(pdf_file, caption=f"فاتورة طلب السيد {order_details['customer']['name']}")
            os.remove(pdf_file)
        
        return jsonify({'status': 'success', 'message': 'Order and PDF sent to Telegram successfully.'})

    except Exception as e:
        print(f"Error processing order: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(port=5000)
