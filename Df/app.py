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

# معلومات المتجر
MARKET_INFO = {
    'name': 'سوقنا الإلكتروني',
    'website': 'www.oursite.com',
    'phone': '07701234567'
}

# تسجيل خطوط عربية
try:
    # يجب أن تكون هذه الملفات موجودة في نفس مجلد الكود
    pdfmetrics.registerFont(TTFont('Janna-LT-Regular', 'alfont_com_Janna-LT-Regular.ttf'))
    pdfmetrics.registerFont(TTFont('Janna-LT-Bold', 'alfont_com_Janna-LT-Bold.ttf'))
    ARABIC_FONT = 'Janna-LT-Regular'
    ARABIC_FONT_BOLD = 'Janna-LT-Bold'
except Exception as e:
    print(f"Error loading Arabic fonts: {e}. Falling back to Helvetica.")
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
        print(f"الملف غير موجود: {file_path}")
        return None
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    response = None
    try:
        with open(file_path, 'rb') as f:
            files = {'document': f}
            payload = {'chat_id': chat_id, 'caption': caption}
            response = requests.post(url, data=payload, files=files, timeout=30)
            response.raise_for_status()
    except Exception as e:
        print(f"خطأ إرسال PDF: {e}")
    finally:
        # تأكد من حذف الملف بعد الإرسال أو عند حدوث خطأ
        if os.path.exists(file_path):
            os.remove(file_path)
    return response

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
def page_layout(canvas, doc):
    canvas.saveState()
    # Header Rectangle
    header_height = 1.0 * inch
    canvas.setFillColor(colors.HexColor('#3C4043'))
    canvas.rect(0, doc.height + doc.topMargin - header_height, doc.width + 2*doc.leftMargin, header_height, fill=1, stroke=0)
    
    # Add market name to the header
    market_name = rtl(MARKET_INFO['name'])
    canvas.setFillColor(colors.white)
    canvas.setFont(ARABIC_FONT_BOLD, 28)
    canvas.drawCentredString(doc.width/2 + doc.leftMargin, doc.height + doc.topMargin - 0.7*inch, market_name)

    # Footer Rectangle
    footer_height = 0.5 * inch
    canvas.setFillColor(colors.HexColor('#3C4043'))
    canvas.rect(0, 0, doc.width + 2*doc.leftMargin, footer_height, fill=1, stroke=0)
    
    # Footer Text (with website removed)
    canvas.setFillColor(colors.white)
    canvas.setFont(ARABIC_FONT, 10)
    footer_text = rtl(f"{MARKET_INFO['name']} - {MARKET_INFO['phone']}")
    canvas.drawCentredString(doc.width/2 + doc.leftMargin, 0.2*inch, footer_text)
    
    canvas.restoreState()

# إنشاء PDF للطلب
def create_order_pdf(order_details, photo_link=None, filename="order.pdf"):
    qr_img_path_customer, qr_img_path_market = None, None
    try:
        # Define Color Palette
        COLOR_PRIMARY = colors.HexColor('#3C4043')
        COLOR_ACCENT = colors.HexColor('#1A73E8')
        COLOR_SPECIAL = colors.HexColor('#4CAF50')
        COLOR_TEXT_LIGHT = colors.HexColor('#6B6E70')
        COLOR_TABLE_BG1 = colors.HexColor('#F5F7FA')
        COLOR_SPECIAL_BG = colors.HexColor('#E8F5E9')

        # Custom styles
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle('InvoiceTitle', fontName=ARABIC_FONT_BOLD, fontSize=28, textColor=colors.white, alignment=TA_CENTER, leading=32))
        styles.add(ParagraphStyle('InvoiceSubtitle', fontName=ARABIC_FONT, fontSize=14, textColor=colors.white, alignment=TA_CENTER, leading=18))
        styles.add(ParagraphStyle('SectionHeader', fontName=ARABIC_FONT_BOLD, fontSize=16, textColor=COLOR_PRIMARY, alignment=TA_RIGHT, spaceBefore=18, spaceAfter=8))
        styles.add(ParagraphStyle('LabelText', fontName=ARABIC_FONT_BOLD, fontSize=12, textColor=COLOR_PRIMARY, alignment=TA_RIGHT))
        styles.add(ParagraphStyle('ValueText', fontName=ARABIC_FONT, fontSize=12, textColor=COLOR_TEXT_LIGHT, alignment=TA_RIGHT))
        styles.add(ParagraphStyle('TableHeader', fontName=ARABIC_FONT_BOLD, fontSize=12, textColor=colors.white, alignment=TA_CENTER, leading=15))
        styles.add(ParagraphStyle('TableData', fontName=ARABIC_FONT, fontSize=11, textColor=COLOR_PRIMARY, alignment=TA_CENTER, leading=14))
        styles.add(ParagraphStyle('SpecialTableHeader', fontName=ARABIC_FONT_BOLD, fontSize=12, textColor=colors.white, alignment=TA_CENTER, leading=15))
        styles.add(ParagraphStyle('SpecialTableData', fontName=ARABIC_FONT_BOLD, fontSize=11, textColor=COLOR_SPECIAL, alignment=TA_CENTER, leading=14))
        
        # New styles for summary
        styles.add(ParagraphStyle('SummaryLabel', fontName=ARABIC_FONT_BOLD, fontSize=14, textColor=COLOR_PRIMARY, alignment=TA_RIGHT))
        styles.add(ParagraphStyle('SummaryValue', fontName=ARABIC_FONT, fontSize=14, textColor=COLOR_TEXT_LIGHT, alignment=TA_RIGHT))
        
        styles.add(ParagraphStyle('TotalLabel', fontName=ARABIC_FONT_BOLD, fontSize=18, textColor=COLOR_PRIMARY, alignment=TA_RIGHT))
        styles.add(ParagraphStyle('TotalValue', fontName=ARABIC_FONT_BOLD, fontSize=20, textColor=COLOR_ACCENT, alignment=TA_RIGHT))
        styles.add(ParagraphStyle('FooterText', fontName=ARABIC_FONT, fontSize=10, textColor=colors.white, alignment=TA_CENTER))
        styles.add(ParagraphStyle('QRCodeLabel', fontName=ARABIC_FONT_BOLD, fontSize=10, textColor=COLOR_PRIMARY, alignment=TA_CENTER))

        # A new style to handle right-aligned Arabic text and left-aligned LTR numbers
        styles.add(ParagraphStyle('RightArabic_LeftNumber', fontName=ARABIC_FONT, fontSize=11, textColor=COLOR_PRIMARY, alignment=TA_RIGHT))
        styles.add(ParagraphStyle('SpecialRightArabic_LeftNumber', fontName=ARABIC_FONT_BOLD, fontSize=11, textColor=COLOR_SPECIAL, alignment=TA_RIGHT))
        
        doc = SimpleDocTemplate(filename, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
        story = []

        # Customer and Order Details Section with light background
        story.append(Paragraph(rtl("بيانات العميل"), styles['SectionHeader']))
        customer_info_data = [
            [Paragraph(rtl("الاسم:"), styles['LabelText']), Paragraph(rtl(order_details['customer']['name']), styles['ValueText'])],
            [Paragraph(rtl("الهاتف:"), styles['LabelText']), Paragraph(rtl(order_details['customer']['phone']), styles['ValueText'])]
        ]
        info_table = Table(customer_info_data, colWidths=[1.5*inch, doc.width-1.5*inch])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), COLOR_TABLE_BG1),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#CCCCCC')),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('RIGHTPADDING', (0,0), (-1,-1), 10),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 0.2*inch))
        
        # Products Section - Single table with special styling for quantity and total price
        story.append(Paragraph(rtl("تفاصيل الطلب"), styles['SectionHeader']))
        table_header = [
            Paragraph(rtl("السعر الإجمالي"), styles['SpecialTableHeader']),
            Paragraph(rtl("السعر"), styles['TableHeader']),
            Paragraph(rtl("الكمية"), styles['SpecialTableHeader']),
            Paragraph(rtl("المنتج"), styles['TableHeader'])
        ]
        products_data = [table_header]
        total_price, total_qty = 0, 0
        
        for i, (item_name, item_data) in enumerate(order_details['items'].items()):
            item_total = item_data['price'] * item_data['quantity']
            total_price += item_total
            total_qty += item_data['quantity']
            
            # Apply different styling for special columns (quantity and total price)
            products_data.append([
                Paragraph(rtl(f"{item_total:,.0f} د.ع"), styles['SpecialRightArabic_LeftNumber']),
                Paragraph(rtl(f"{item_data['price']:,.0f} د.ع"), styles['RightArabic_LeftNumber']),
                Paragraph(rtl(str(item_data['quantity'])), styles['SpecialRightArabic_LeftNumber']),
                Paragraph(rtl(item_name), styles['TableData'])
            ])
        
        products_table = Table(products_data, colWidths=[1.5*inch, 1.5*inch, 1*inch, doc.width-4*inch])
        products_table.setStyle(TableStyle([
            # Header row styling
            ('BACKGROUND', (0, 0), (0, 0), COLOR_SPECIAL),
            ('BACKGROUND', (1, 0), (1, 0), COLOR_PRIMARY),
            ('BACKGROUND', (2, 0), (2, 0), COLOR_SPECIAL),
            ('BACKGROUND', (3, 0), (3, 0), COLOR_PRIMARY),
            
            # Data rows styling - alternating colors
            ('BACKGROUND', (0, 1), (0, -1), COLOR_SPECIAL_BG),
            ('BACKGROUND', (1, 1), (1, -1), COLOR_TABLE_BG1),
            ('BACKGROUND', (2, 1), (2, -1), COLOR_SPECIAL_BG),
            ('BACKGROUND', (3, 1), (3, -1), COLOR_TABLE_BG1),
            
            # Apply alternating row colors for better readability
            ('BACKGROUND', (0, 1), (-1, 1), COLOR_TABLE_BG1),
            ('BACKGROUND', (0, 3), (-1, 3), COLOR_TABLE_BG1),
            ('BACKGROUND', (0, 5), (-1, 5), COLOR_TABLE_BG1),
            
            # Grid and borders
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#DDDDDD')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#AAAAAA')),
            
            # Alignment and padding
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('TOPPADDING', (0,0), (-1,-1), 8),
        ]))
        story.append(products_table)
        story.append(Spacer(1, 0.3*inch))

        # Add Summary Section below the products table
        summary_data = [
            [
                Paragraph(rtl(f"{total_price:,.0f} د.ع"), styles['TotalValue']),
                Paragraph(rtl("الإجمالي:"), styles['TotalLabel'])
            ],
            [
                Paragraph(rtl(str(total_qty)), styles['SummaryValue']),
                Paragraph(rtl("الكمية الإجمالية:"), styles['SummaryLabel'])
            ]
        ]
        summary_table = Table(summary_data, colWidths=[3*inch, doc.width-3*inch])
        summary_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('RIGHTPADDING', (0,0), (-1,-1), 10),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('TOPPADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 0.3*inch))

        # QR Codes Section
        if order_details['customer'].get('location'):
            story.append(Paragraph(rtl("رموز QR للوصول السريع"), styles['SectionHeader']))
            
            qr_images_row = []
            qr_labels_row = []
            
            # QR for Market Location
            qr_data_market = f"https://www.google.com/maps/search/?api=1&query={MARKET_LOCATION['lat']},{MARKET_LOCATION['lng']}"
            qr_img_path_market = "qr_market.png"
            qrcode.make(qr_data_market).save(qr_img_path_market)
            img_market = Image(qr_img_path_market, 1.2*inch, 1.2*inch)
            qr_images_row.append(img_market)
            qr_labels_row.append(Paragraph(rtl("موقع المتجر"), styles['QRCodeLabel']))
            
            # QR for Customer Location
            lat, lng = order_details['customer']['location']['lat'], order_details['customer']['location']['lng']
            qr_data_customer = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
            qr_img_path_customer = "qr_customer.png"
            qrcode.make(qr_data_customer).save(qr_img_path_customer)
            img_customer = Image(qr_img_path_customer, 1.2*inch, 1.2*inch)
            qr_images_row.append(img_customer)
            qr_labels_row.append(Paragraph(rtl("موقع العميل"), styles['QRCodeLabel']))
            
            # Create tables for QR codes
            qr_images_table = Table([qr_images_row], colWidths=[1.5*inch]*len(qr_images_row))
            qr_labels_table = Table([qr_labels_row], colWidths=[1.5*inch]*len(qr_labels_row))
            
            # Style the QR tables
            qr_style = TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BACKGROUND', (0,0), (-1,-1), COLOR_TABLE_BG1),
                ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#CCCCCC')),
                ('PADDING', (0,0), (-1,-1), 10),
            ])
            
            qr_images_table.setStyle(qr_style)
            qr_labels_table.setStyle(qr_style)
            
            story.append(qr_images_table)
            story.append(Spacer(1, 0.1*inch))
            story.append(qr_labels_table)
            story.append(Spacer(1, 0.3*inch))

        # Customer distance note
        if order_details['customer'].get('location'):
            lat, lng = order_details['customer']['location']['lat'], order_details['customer']['location']['lng']
            distance = haversine_distance(MARKET_LOCATION['lat'], MARKET_LOCATION['lng'], lat, lng)
            distance_text = rtl(f"مسافة العميل من المتجر: {distance:,.2f} متر")
            story.append(Paragraph(distance_text, styles['ValueText']))

        doc.build(story, onFirstPage=page_layout, onLaterPages=page_layout)
        return filename
    finally:
        for p in [qr_img_path_customer, qr_img_path_market]:
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
        
        # إنشاء رسالة نصية للطلب
        text_message = f"<b>✅ طلب جديد:</b>\n\n<b>- الاسم:</b> {order_details['customer']['name']}\n<b>- الهاتف:</b> {order_details['customer']['phone']}\n"
        
        if order_details['customer'].get('location'):
            lat, lng = order_details['customer']['location']['lat'], order_details['customer']['location']['lng']
            distance = haversine_distance(MARKET_LOCATION['lat'], MARKET_LOCATION['lng'], lat, lng)
            text_message += f"<b>- الموقع:</b> <a href='https://www.google.com/maps/search/?api=1&query={lat},{lng}'>رابط</a>\n<b>- المسافة:</b> {distance:,.2f} متر\n"
        
        total_price = 0
        total_qty = 0
        text_message += "\n<b>المنتجات:</b>\n"
        for item_name, item_data in order_details['items'].items():
            item_total = item_data['price'] * item_data['quantity']
            total_price += item_total
            total_qty += item_data['quantity']
            text_message += f"• {item_name} × {item_data['quantity']} = {item_total:,.0f} د.ع\n"
        text_message += f"\n<b>الإجمالي: {total_price:,.0f} د.ع</b>"

        # إرسال الرسالة النصية
        send_telegram_message(text_message)
        
        # إنشاء وإرسال ملف PDF
        pdf_file = None
        try:
            pdf_file = create_order_pdf(order_details)
        except Exception as pdf_error:
            # طباعة الخطأ في console و إرساله لتيليجرام لتنبيهك
            print(f"Error creating PDF: {pdf_error}")
            send_telegram_message(f"🚨 خطأ في إنشاء الفاتورة لطلب {order_details['customer']['name']}: {pdf_error}")
        
        if pdf_file:
            send_telegram_document(pdf_file, caption=f"فاتورة طلب {order_details['customer']['name']} - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        
        return jsonify({'status': 'success', 'message': 'تم إرسال الطلب والفاتورة بنجاح.'})
    
    except Exception as e:
        print(f"General error: {e}")
        return jsonify({'status': 'error', 'message': f"حدث خطأ عام: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000), debug=True)
