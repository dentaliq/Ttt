import os
import requests
import json
import math
import qrcode
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from flask import Flask, request, jsonify
from flask_cors import CORS
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
import arabic_reshaper
from bidi.algorithm import get_display

# إعداد تطبيق Flask
app = Flask(__name__)
CORS(app)

# بيانات بوت تيليجرام
BOT_TOKEN = '8256210377:AAH7ogEPTvIUo9hyY2p8uCkF-Yby13weXkk'
CHAT_ID = '7836619198'

# موقع المتجر الفعلي
MARKET_LOCATION = {'lat': 32.6468089, 'lng': 43.9782430}

# تسجيل خطوط عربية
try:
    pdfmetrics.registerFont(TTFont('Janna-LT-Regular', 'alfont_com_Janna-LT-Regular.ttf'))
    pdfmetrics.registerFont(TTFont('Janna-LT-Bold', 'alfont_com_Janna-LT-Bold.ttf'))
    ARABIC_FONT = 'Janna-LT-Regular'
    ARABIC_FONT_BOLD = 'Janna-LT-Bold'
except Exception:
    ARABIC_FONT = 'Helvetica'
    ARABIC_FONT_BOLD = 'Helvetica-Bold'

# دالة لمعالجة النص العربي
def rtl(text):
    if not text:
        return ""
    reshaped_text = arabic_reshaper.reshape(text)
    return get_display(reshaped_text)

# دالة لحساب المسافة
def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371e3
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ, Δλ = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(Δφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(Δλ/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

# إرسال رسالة نصية
def send_telegram_message(text, chat_id=CHAT_ID):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        print(f"خطأ إرسال رسالة: {e}")
        return None

# إرسال ملف PDF
def send_telegram_document(file_path, chat_id=CHAT_ID, caption=''):
    if not os.path.exists(file_path):
        return None
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    try:
        with open(file_path, 'rb') as f:
            files = {'document': f}
            payload = {'chat_id': chat_id, 'caption': caption}
            response = requests.post(url, data=payload, files=files, timeout=30)
            response.raise_for_status()
            os.remove(file_path)
            return response
    except Exception as e:
        print(f"خطأ إرسال PDF: {e}")
        return None

# الحصول على رابط ملف من تيليجرام
def get_file_link(file_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile"
    try:
        response = requests.get(url, params={'file_id': file_id})
        response.raise_for_status()
        file_path = response.json()['result']['file_path']
        return f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
    except Exception as e:
        print(f"خطأ الحصول على رابط: {e}")
        return None

# دالة لرسم خلفية الصفحة
def page_background(canvas, doc):
    canvas.saveState()
    # Solid white background
    canvas.setFillColor(colors.white)
    canvas.rect(0, 0, doc.width + 2 * doc.leftMargin, doc.height + 2 * doc.topMargin, fill=1, stroke=0)
    canvas.restoreState()

# إنشاء PDF للطلب
def create_order_pdf(order_details, photo_link=None, filename="order.pdf"):
    qr_img_path_customer, qr_img_path_market, qr_img_path_photo = None, None, None
    try:
        # Custom styles with better aesthetics
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle('InvoiceTitle', fontName=ARABIC_FONT_BOLD, fontSize=24, textColor=colors.HexColor('#000000'), alignment=TA_CENTER, leading=30))
        styles.add(ParagraphStyle('InvoiceNumber', fontName=ARABIC_FONT, fontSize=12, alignment=TA_CENTER, textColor=colors.HexColor('#6B6E70')))
        styles.add(ParagraphStyle('SectionHeader', fontName=ARABIC_FONT_BOLD, fontSize=16, textColor=colors.HexColor('#3C4043'), alignment=TA_RIGHT, spaceBefore=10, spaceAfter=5))
        styles.add(ParagraphStyle('LabelText', fontName=ARABIC_FONT_BOLD, fontSize=12, textColor=colors.HexColor('#3C4043'), alignment=TA_RIGHT))
        styles.add(ParagraphStyle('ValueText', fontName=ARABIC_FONT, fontSize=12, textColor=colors.HexColor('#6B6E70'), alignment=TA_RIGHT))
        styles.add(ParagraphStyle('TableHeader', fontName=ARABIC_FONT_BOLD, fontSize=12, textColor=colors.white, alignment=TA_CENTER, leading=15))
        styles.add(ParagraphStyle('TableData', fontName=ARABIC_FONT, fontSize=11, textColor=colors.HexColor('#3C4043'), alignment=TA_CENTER, leading=14))
        styles.add(ParagraphStyle('TotalLabel', fontName=ARABIC_FONT_BOLD, fontSize=18, textColor=colors.white, alignment=TA_RIGHT))
        styles.add(ParagraphStyle('TotalValue', fontName=ARABIC_FONT_BOLD, fontSize=20, textColor=colors.HexColor('#34B53A'), alignment=TA_RIGHT)) # Green color for total
        styles.add(ParagraphStyle('FooterText', fontName=ARABIC_FONT, fontSize=10, textColor=colors.HexColor('#6B6E70'), alignment=TA_CENTER))
        styles.add(ParagraphStyle('QRCodeLabel', fontName=ARABIC_FONT_BOLD, fontSize=10, textColor=colors.HexColor('#1E3D59'), alignment=TA_CENTER))

        doc = SimpleDocTemplate(filename, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
        story = []

        # Header for the PDF
        story.append(Paragraph(rtl("فاتورة طلب من سوبر ماركت العراق"), styles['InvoiceTitle']))
        invoice_date_text = rtl(f"رقم الفاتورة: {order_details.get('invoice_id', 'N/A')} | التاريخ: {datetime.now().strftime('%Y-%m-%d')}")
        story.append(Paragraph(invoice_date_text, styles['InvoiceNumber']))
        story.append(Spacer(1, 0.4*inch))
        
        # Customer and Order Details Section
        customer_info_data = [
            [
                Paragraph(rtl("الاسم:"), styles['LabelText']),
                Paragraph(rtl(order_details['customer']['name']), styles['ValueText'])
            ],
            [
                Paragraph(rtl("الهاتف:"), styles['LabelText']),
                Paragraph(rtl(order_details['customer']['phone']), styles['ValueText'])
            ]
        ]
        
        info_table = Table(customer_info_data, colWidths=[1.5*inch, doc.width-1.5*inch])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8F8F8')), # Pale background
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#DDDDDD')), # Light border
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#DDDDDD')),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('RIGHTPADDING', (0,0), (-1,-1), 10),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Products Table
        table_header = [
            Paragraph(rtl("السعر الإجمالي"), styles['TableHeader']),
            Paragraph(rtl("السعر"), styles['TableHeader']),
            Paragraph(rtl("الكمية"), styles['TableHeader']),
            Paragraph(rtl("المنتج"), styles['TableHeader'])
        ]
        products_data = [table_header]
        total_price, total_qty = 0, 0
        
        row_colors = [colors.white, colors.HexColor('#F8F8F8')] # Alternating row colors
        for i, (item_name, item_data) in enumerate(order_details['items'].items()):
            item_total = item_data['price'] * item_data['quantity']
            total_price += item_total
            total_qty += item_data['quantity']
            products_data.append([
                Paragraph(rtl(f"{item_total:,.0f} د.ع"), styles['TableData']),
                Paragraph(rtl(f"{item_data['price']:,.0f} د.ع"), styles['TableData']),
                Paragraph(rtl(str(item_data['quantity'])), styles['TableData']),
                Paragraph(rtl(item_name), styles['TableData'])
            ])
        
        products_table = Table(products_data, colWidths=[1.5*inch, 1.5*inch, 1*inch, doc.width-4*inch])
        products_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4B77A8')), # Dark blue header
            ('GRID', (0, 1), (-1, -1), 0.5, colors.HexColor('#DDDDDD')), # Light grid lines
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#AAAAAA')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('BACKGROUNDS', (0, 1), (-1, -1), row_colors) # Alternating backgrounds
        ]))
        story.append(products_table)
        story.append(Spacer(1, 0.3*inch))

        # Total Box
        total_data = [
            [
                Paragraph(rtl("المجموع الكلي"), styles['TotalLabel']),
                Paragraph(rtl(f"{total_price:,.0f} د.ع"), styles['TotalValue'])
            ]
        ]
        total_table = Table(total_data, colWidths=[doc.width/2, doc.width/2])
        total_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#2C3E50')), # Navy blue background
            ('LEFTPADDING', (0,0), (-1,-1), 15),
            ('RIGHTPADDING', (0,0), (-1,-1), 15),
            ('TOPPADDING', (0,0), (-1,-1), 10),
            ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ]))
        story.append(total_table)
        story.append(Spacer(1, 0.4*inch))

        # Notes section
        story.append(Paragraph(rtl("شكراً لتعاملكم معنا."), styles['FooterText']))
        story.append(Spacer(1, 0.2*inch))

        # QR Codes
        qr_table_data = [[], []]
        
        # QR for Market Location
        qr_data_market = f"https://www.google.com/maps/search/?api=1&query={MARKET_LOCATION['lat']},{MARKET_LOCATION['lng']}"
        qr_img_path_market = "qr_market.png"
        qrcode.make(qr_data_market).save(qr_img_path_market)
        img_market = Image(qr_img_path_market, 1.2*inch, 1.2*inch)
        qr_table_data[0].append(img_market)
        qr_table_data[1].append(Paragraph(rtl("موقع المتجر"), styles['QRCodeLabel']))
        
        # QR for Customer Location
        if order_details['customer'].get('location'):
            lat, lng = order_details['customer']['location']['lat'], order_details['customer']['location']['lng']
            qr_data_customer = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
            qr_img_path_customer = "qr_customer.png"
            qrcode.make(qr_data_customer).save(qr_img_path_customer)
            img_customer = Image(qr_img_path_customer, 1.2*inch, 1.2*inch)
            qr_table_data[0].append(img_customer)
            qr_table_data[1].append(Paragraph(rtl("موقع العميل"), styles['QRCodeLabel']))

        # QR for Photo Link
        if photo_link:
            qr_img_path_photo = "qr_photo.png"
            qrcode.make(photo_link).save(qr_img_path_photo)
            img_photo = Image(qr_img_path_photo, 1.2*inch, 1.2*inch)
            qr_table_data[0].append(img_photo)
            qr_table_data[1].append(Paragraph(rtl("صورة الطلب"), styles['QRCodeLabel']))

        qr_table = Table(qr_table_data, colWidths=[1.5*inch]*len(qr_table_data[0]))
        qr_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('RIGHTPADDING', (0,0), (-1,-1), 10)
        ]))
        story.append(qr_table)

        doc.build(story, onFirstPage=page_background, onLaterPages=page_background)
        return filename
    finally:
        for p in [qr_img_path_customer, qr_img_path_market, qr_img_path_photo]:
            if p and os.path.exists(p):
                os.remove(p)

# API: إرسال صورة
@app.route('/send-photo', methods=['POST'])
def send_photo():
    try:
        if 'photo' not in request.files:
            return jsonify({'status': 'error', 'message': 'لم يتم توفير ملف الصورة.'}), 400
        photo_file = request.files['photo']
        if photo_file.filename == '':
            return jsonify({'status': 'error', 'message': 'لم يتم اختيار ملف.'}), 400

        caption = request.form.get('caption', 'صورة مرفقة بالطلب.')
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"

        files = {'photo': photo_file.stream}
        data = {'chat_id': CHAT_ID, 'caption': caption}
        response = requests.post(url, data=data, files=files, timeout=30)
        response.raise_for_status()

        result = response.json().get('result', {})
        if not result or 'photo' not in result:
            return jsonify({'status': 'error', 'message': 'لم يتم استلام photo_id من تيليجرام.'}), 500

        file_id = result['photo'][-1]['file_id']
        photo_link = get_file_link(file_id)

        return jsonify({'status': 'success', 'message': 'تم إرسال الصورة بنجاح.', 'photo_link': photo_link})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f"فشل إرسال الصورة: {str(e)}"}), 500

# API: استقبال الطلب
@app.route('/send-order', methods=['POST'])
def send_order():
    try:
        order_details = request.get_json()
        # You can add an invoice ID here if your system generates one
        order_details['invoice_id'] = f"{order_details['customer']['phone']}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        text_message = f"<b>✅ طلب جديد:</b>\n\n<b>- الاسم:</b> {order_details['customer']['name']}\n<b>- الهاتف:</b> {order_details['customer']['phone']}\n"
        if order_details['customer'].get('location'):
            lat, lng = order_details['customer']['location']['lat'], order_details['customer']['location']['lng']
            distance = haversine_distance(MARKET_LOCATION['lat'], MARKET_LOCATION['lng'], lat, lng)
            text_message += f"<b>- الموقع:</b> <a href='https://www.google.com/maps/search/?api=1&query={lat},{lng}'>رابط</a>\n<b>- المسافة:</b> {distance:,.2f} متر\n"
        total_price = 0
        text_message += "\n<b>المنتجات:</b>\n"
        for item_name, item_data in order_details['items'].items():
            item_total = item_data['price'] * item_data['quantity']
            total_price += item_total
            text_message += f"• {item_name} × {item_data['quantity']} = {item_total:,.0f} د.ع\n"
        text_message += f"\n<b>الإجمالي: {total_price:,.0f} د.ع</b>"

        send_telegram_message(text_message)
        pdf_file = create_order_pdf(order_details, order_details.get('photo_link'))
        if pdf_file:
            send_telegram_document(pdf_file, caption=f"فاتورة طلب {order_details['customer']['name']} - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        return jsonify({'status': 'success', 'message': 'تم إرسال الطلب والفاتورة بنجاح.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000), debug=True)
