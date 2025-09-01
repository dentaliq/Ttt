import os
import requests
import json
import math
import qrcode
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from flask import Flask, request, jsonify
from flask_cors import CORS
from reportlab.lib.enums import TA_RIGHT, TA_CENTER

# دعم العربية
import arabic_reshaper
from bidi.algorithm import get_display

# إعداد تطبيق Flask
app = Flask(__name__)
CORS(app)

# بيانات بوت تيليجرام
BOT_TOKEN = '8256210377:AAH7ogEPTvIUo9hyY2p8uCkF-Yby13weXkk'
CHAT_ID = '7836619198'

# موقع المتجر لحساب المسافة
MARKET_LOCATION = {'lat': 32.6468089, 'lng': 43.9782430}

# تسجيل خطوط عربية
try:
    pdfmetrics.registerFont(TTFont('Tajawal', 'Tajawal-Regular.ttf'))
    pdfmetrics.registerFont(TTFont('Tajawal-Bold', 'Tajawal-Bold.ttf'))
    ARABIC_FONT = '1.ttf'
    ARABIC_FONT_BOLD = '2.ttf'
except Exception as e:
    print(f"Error loading Arabic font: {e}. Using Helvetica as fallback.")
    ARABIC_FONT = 'Helvetica'
    ARABIC_FONT_BOLD = 'Helvetica-Bold'

# دالة لمعالجة النص العربي (حروف متصلة + RTL)
def rtl(text):
    if not text:
        return ""
    reshaped_text = arabic_reshaper.reshape(text)   # توصيل الحروف
    bidi_text = get_display(reshaped_text)          # عكس الاتجاه RTL
    return bidi_text

# دالة لحساب المسافة
def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371e3
    φ1 = math.radians(lat1)
    φ2 = math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)
    a = math.sin(Δφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# إرسال رسالة نصية
def send_telegram_message(text, chat_id=CHAT_ID):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
    response = requests.post(url, json=payload)
    print(f"Telegram API response (message): {response.json()}")
    return response

# إرسال ملف PDF
def send_telegram_document(file_path, chat_id=CHAT_ID, caption=''):
    print(f"Attempting to send document from path: {file_path}")
    if not os.path.exists(file_path):
        print(f"Error: File not found at path: {file_path}")
        return None
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    try:
        with open(file_path, 'rb') as f:
            files = {'document': f}
            payload = {'chat_id': chat_id, 'caption': caption}
            response = requests.post(url, data=payload, files=files)
            print(f"Telegram API response (document): {response.json()}")
            return response
    except Exception as e:
        print(f"Error sending document to Telegram: {e}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"PDF file removed: {file_path}")

# إنشاء فاتورة PDF
def create_order_pdf(order_details, filename="order.pdf"):
    print(f"Attempting to create PDF: {filename}")
    try:
        doc = SimpleDocTemplate(filename, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        story = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontName=ARABIC_FONT_BOLD,
            alignment=TA_CENTER,
            spaceAfter=30,
            fontSize=18
        )

        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontName=ARABIC_FONT,
            alignment=TA_RIGHT,
            spaceAfter=12,
            fontSize=12
        )

        bold_style = ParagraphStyle(
            'CustomBold',
            parent=styles['Normal'],
            fontName=ARABIC_FONT_BOLD,
            alignment=TA_RIGHT,
            spaceAfter=12,
            fontSize=12
        )

        story.append(Paragraph(rtl("سوبر ماركت العراق"), title_style))
        story.append(Spacer(1, 0.2 * inch))

        story.append(Paragraph(rtl(f"تاريخ الطلب: {datetime.now().strftime('%Y-%m-%d %H:%M')}"), normal_style))
        story.append(Spacer(1, 0.3 * inch))

        story.append(Paragraph(rtl(f"الاسم: {order_details['customer']['name']}"), bold_style))
        story.append(Paragraph(rtl(f"الهاتف: {order_details['customer']['phone']}"), bold_style))
        story.append(Spacer(1, 0.3 * inch))

        table_data = [
            [
                Paragraph(rtl("المنتج"), bold_style),
                Paragraph(rtl("الكمية"), bold_style),
                Paragraph(rtl("السعر"), bold_style),
                Paragraph(rtl("الإجمالي"), bold_style),
            ]
        ]

        total_price_num = 0
        for item_name, item_data in order_details['items'].items():
            item_total = item_data['price'] * item_data['quantity']
            total_price_num += item_total
            table_data.append([
                Paragraph(rtl(item_name), normal_style),
                Paragraph(rtl(str(item_data['quantity'])), normal_style),
                Paragraph(rtl(f"{item_data['price']:,.0f} د.ع"), normal_style),
                Paragraph(rtl(f"{item_total:,.0f} د.ع"), normal_style)
            ])

        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1c212c')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), ARABIC_FONT),
            ('FONTNAME', (0, 0), (-1, 0), ARABIC_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#dee2e6')),
        ])

        order_table = Table(table_data, colWidths=[2.5*inch, 1*inch, 1.5*inch, 1.5*inch])
        order_table.setStyle(table_style)
        story.append(order_table)
        story.append(Spacer(1, 0.3 * inch))

        total_style = ParagraphStyle(
            'TotalStyle',
            parent=styles['Heading2'],
            fontName=ARABIC_FONT_BOLD,
            alignment=TA_RIGHT,
            spaceBefore=20,
            fontSize=14
        )
        story.append(Paragraph(rtl(f"المجموع الإجمالي: {total_price_num:,.0f} د.ع"), total_style))
        story.append(Spacer(1, 0.5 * inch))

        qr_img_path = None
        if order_details['customer']['location']:
            lat = order_details['customer']['location']['lat']
            lng = order_details['customer']['location']['lng']
            qr_data = f"https://www.google.com/maps/place/{lat},{lng}"
            qr_img = qrcode.make(qr_data)
            qr_img_path = "qr_code.png"
            qr_img.save(qr_img_path)

            story.append(Paragraph(rtl("امسح الباركود للوصول إلى موقع العميل:"), normal_style))
            story.append(Spacer(1, 0.2 * inch))

            img = Image(qr_img_path)
            img.drawHeight = 2*inch
            img.drawWidth = 2*inch
            img.hAlign = 'CENTER'
            story.append(img)

        doc.build(story)
        print(f"PDF created successfully: {filename}")
        return filename

    except Exception as e:
        print(f"Error creating PDF: {e}")
        return None
    finally:
        if 'qr_img_path' in locals() and qr_img_path and os.path.exists(qr_img_path):
            os.remove(qr_img_path)
            print(f"QR code image removed: {qr_img_path}")

# API: استقبال الطلب
@app.route('/send-order', methods=['POST'])
def send_order():
    try:
        order_details = request.get_json()
        
        text_message = f"<b>✅ طلب جديد من السوبر ماركت:</b>\n\n"
        text_message += f"<b>- الاسم:</b> {order_details['customer']['name']}\n"
        text_message += f"<b>- الهاتف:</b> {order_details['customer']['phone']}\n"
        
        if 'location' in order_details['customer'] and order_details['customer']['location']:
            lat = order_details['customer']['location']['lat']
            lng = order_details['customer']['location']['lng']
            distance = haversine_distance(MARKET_LOCATION['lat'], MARKET_LOCATION['lng'], lat, lng)
            text_message += f"<b>- الإحداثيات:</b> <a href='https://www.google.com/maps/place/{lat},{lng}'>الموقع الجغرافي</a>\n"
            text_message += f"<b>- المسافة عن المتجر:</b> {distance:,.2f} متر\n"
        else:
            text_message += f"<b>- ملاحظة:</b> لم يتمكن العميل من إرسال موقعه الجغرافي.\n"
        
        text_message += f"\n<b><u>المنتجات:</u></b>\n"
        for item_name, item_data in order_details['items'].items():
            item_total = item_data['price'] * item_data['quantity']
            text_message += f"• {item_name} (الكمية: {item_data['quantity']}) - السعر: {item_total:,.0f} د.ع\n"
        
        total_price = sum(item['price'] * item['quantity'] for item in order_details['items'].values())
        text_message += f"\n<b>المجموع الإجمالي: {total_price:,.0f} د.ع</b>"
        
        # إرسال الرسالة
        send_telegram_message(text_message)
        
        # إنشاء وإرسال PDF
        pdf_file = create_order_pdf(order_details)
        if pdf_file:
            send_telegram_document(
                pdf_file, 
                caption=f"فاتورة طلب السيد {order_details['customer']['name']} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
        
        return jsonify({'status': 'success', 'message': 'Order and PDF sent to Telegram successfully.'})

    except Exception as e:
        print(f"Error processing order: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# API: إرسال صورة
@app.route('/send-photo', methods=['POST'])
def send_photo():
    try:
        photo_file = request.files.get('photo')
        if not photo_file:
            return jsonify({'status': 'error', 'message': 'No photo file provided.'}), 400
        
        caption = request.form.get('caption', 'صورة مرفقة بالطلب.')
        
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        files = {'photo': photo_file}
        payload = {'chat_id': CHAT_ID, 'caption': caption}
        response = requests.post(url, data=payload, files=files)
        print(f"Telegram API response (photo): {response.json()}")

        return jsonify({'status': 'success', 'message': 'Photo sent successfully.'})

    except Exception as e:
        print(f"Error sending photo to Telegram: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))
