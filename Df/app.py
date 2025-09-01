import os
import requests
import json
import math
import qrcode
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from flask import Flask, request, jsonify
from flask_cors import CORS
from reportlab.lib.enums import TA_RIGHT

# إعداد تطبيق Flask
app = Flask(__name__)
CORS(app)

# بيانات بوت تيليجرام
# يجب استبدال هذه القيم بقيمك الحقيقية
BOT_TOKEN = 'YOUR_BOT_TOKEN'
CHAT_ID = 'YOUR_CHAT_ID'

# موقع المتجر لحساب المسافة
MARKET_LOCATION = {'lat': 32.6468089, 'lng': 43.9782430}

# تسجيل خطوط عربية لإنشاء ملف PDF
try:
    pdfmetrics.registerFont(TTFont('Tajawal', 'Tajawal-Regular.ttf'))
    pdfmetrics.registerFont(TTFont('Tajawal-Bold', 'Tajawal-Bold.ttf'))
    ARABIC_FONT = 'Tajawal'
    ARABIC_FONT_BOLD = 'Tajawal-Bold'
except Exception as e:
    print(f"Error loading Arabic font: {e}. Please ensure font files are present.")
    ARABIC_FONT = 'Helvetica'
    ARABIC_FONT_BOLD = 'Helvetica-Bold'


# دالة لحساب المسافة بين نقطتين جغرافيتين
def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371e3  # نصف قطر الأرض بالأمتار
    φ1 = math.radians(lat1)
    φ2 = math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)

    a = math.sin(Δφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

# دالة لإرسال رسالة نصية إلى تيليجرام
def send_telegram_message(text, chat_id=CHAT_ID):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML'
    }
    response = requests.post(url, json=payload)
    print(f"Telegram API response (message): {response.json()}")
    return response

# دالة لإرسال ملف PDF إلى تيليجرام
def send_telegram_document(file_path, chat_id=CHAT_ID, caption=''):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    try:
        with open(file_path, 'rb') as f:
            files = {'document': f}
            payload = {
                'chat_id': chat_id,
                'caption': caption
            }
            response = requests.post(url, data=payload, files=files)
            print(f"Telegram API response (document): {response.json()}")
            return response
    except Exception as e:
        print(f"Error sending document to Telegram: {e}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

# دالة لإنشاء فاتورة PDF
def create_order_pdf(order_details, filename="order.pdf"):
    try:
        doc = SimpleDocTemplate(filename, pagesize=letter)
        story = []
        styles = getSampleStyleSheet()

        # العنوان
        title_style = styles['Title']
        title_style.fontName = ARABIC_FONT_BOLD
        title_style.alignment = 1
        story.append(Paragraph("سوبر ماركت العراق", title_style))
        story.append(Spacer(1, 0.2 * inch))

        # التاريخ
        date_style = styles['Normal']
        date_style.fontName = ARABIC_FONT
        date_style.alignment = 1
        story.append(Paragraph(f"تاريخ الطلب: {datetime.now().strftime('%Y-%m-%d %H:%M')}", date_style))
        story.append(Spacer(1, 0.5 * inch))

        # معلومات العميل
        info_style = styles['Normal']
        info_style.fontName = ARABIC_FONT
        info_style.alignment = 2
        story.append(Paragraph(f"الاسم: {order_details['customer']['name']}", info_style))
        story.append(Paragraph(f"الهاتف: {order_details['customer']['phone']}", info_style))
        story.append(Spacer(1, 0.2 * inch))

        # جدول الطلبات
        table_data = [
            [
                Paragraph("<b>المنتج</b>", styles['Normal']),
                Paragraph("<b>الكمية</b>", styles['Normal']),
                Paragraph("<b>السعر</b>", styles['Normal']),
                Paragraph("<b>الإجمالي</b>", styles['Normal']),
            ]
        ]
        
        table_style = styles['Normal']
        table_style.fontName = ARABIC_FONT
        table_style.alignment = TA_RIGHT

        total_price_num = 0
        for item_name, item_data in order_details['items'].items():
            item_total = item_data['price'] * item_data['quantity']
            total_price_num += item_total
            table_data.append([
                Paragraph(item_name, table_style),
                Paragraph(str(item_data['quantity']), table_style),
                Paragraph(f"{item_data['price']:,.0f} د.ع", table_style),
                Paragraph(f"{item_total:,.0f} د.ع", table_style)
            ])

        pdf_table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1c212c')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
            ('FONTNAME', (0, 0), (-1, -1), ARABIC_FONT),
            ('FONTNAME', (0, 0), (-1, 0), ARABIC_FONT_BOLD),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#ffffff')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('RIGHTPADDING', (0,0), (-1,-1), 12),
            ('LEFTPADDING', (0,0), (-1,-1), 12),
        ])

        order_table = Table(table_data, colWidths=[2.5*inch, 1*inch, 1.5*inch, 1.5*inch])
        order_table.setStyle(pdf_table_style)
        story.append(order_table)
        story.append(Spacer(1, 0.2 * inch))

        total_style = styles['Heading2']
        total_style.fontName = ARABIC_FONT_BOLD
        total_style.alignment = 0
        story.append(Paragraph(f"المجموع الإجمالي: {total_price_num:,.0f} د.ع", total_style))
        story.append(Spacer(1, 0.5 * inch))
        
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

# مسار استقبال الطلب النصي
@app.route('/send-order', methods=['POST'])
def send_order():
    try:
        order_details = request.get_json()
        
        # إرسال الرسالة النصية إلى تيليجرام
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
        
        text_message += f"\n<b><u>{order_details['total']}</u></b>"
        
        send_telegram_message(text_message)
        
        pdf_file = create_order_pdf(order_details)
        if pdf_file:
            send_telegram_document(pdf_file, caption=f"فاتورة طلب السيد {order_details['customer']['name']}")
        
        return jsonify({'status': 'success', 'message': 'Order and PDF sent to Telegram successfully.'})

    except Exception as e:
        print(f"Error processing order: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/send-photo', methods=['POST'])
def send_photo():
    try:
        photo_file = request.files.get('photo')
        if not photo_file:
            return jsonify({'status': 'error', 'message': 'No photo file provided.'}), 400
        
        caption = request.form.get('caption', 'صورة مرفقة بالطلب.')
        
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        files = {'photo': photo_file}
        payload = {
            'chat_id': CHAT_ID,
            'caption': caption
        }
        response = requests.post(url, data=payload, files=files)
        print(f"Telegram API response (photo): {response.json()}")

        return jsonify({'status': 'success', 'message': 'Photo sent successfully.'})

    except Exception as e:
        print(f"Error sending photo to Telegram: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))
