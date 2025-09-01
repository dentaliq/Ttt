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
    # تأكد من أن ملفات الخطوط 'Almarai-Regular.ttf' و 'Almarai-Bold.ttf' موجودة في نفس مجلد السكربت.
    pdfmetrics.registerFont(TTFont('Almarai', 'Almarai-Regular.ttf'))
    pdfmetrics.registerFont(TTFont('Almarai-Bold', 'Almarai-Bold.ttf'))
    ARABIC_FONT = 'Almarai'
    ARABIC_FONT_BOLD = 'Almarai-Bold'
except Exception as e:
    print(f"خطأ في تحميل الخط العربي: {e}. سيتم استخدام Helvetica كبديل.")
    ARABIC_FONT = 'Helvetica'
    ARABIC_FONT_BOLD = 'Helvetica-Bold'

# دالة لمعالجة النص العربي (حروف متصلة + RTL)
def rtl(text):
    if not text:
        return ""
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)
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
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        print(f"تم إرسال الرسالة بنجاح: {response.json()}")
        return response
    except requests.exceptions.RequestException as e:
        print(f"خطأ في إرسال الرسالة إلى تيليجرام: {e}")
        return None

# إرسال ملف PDF
def send_telegram_document(file_path, chat_id=CHAT_ID, caption=''):
    print(f"محاولة إرسال الملف من المسار: {file_path}")
    if not os.path.exists(file_path):
        print(f"خطأ: الملف غير موجود في المسار: {file_path}")
        return None
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    
    try:
        with open(file_path, 'rb') as f:
            files = {'document': f}
            payload = {'chat_id': chat_id, 'caption': caption}
            response = requests.post(url, data=payload, files=files, timeout=30)
            response.raise_for_status()
            print(f"تم إرسال الملف بنجاح: {response.json()}")
            
            # حذف الملف بعد التأكد من اكتمال الإرسال بنجاح
            os.remove(file_path)
            print(f"تم حذف ملف PDF: {file_path}")
            
        return response
    except requests.exceptions.RequestException as e:
        print(f"خطأ في إرسال الملف إلى تيليجرام: {e}")
        return None
    except Exception as e:
        print(f"خطأ غير متوقع: {e}")
        return None

# إنشاء فاتورة PDF
def create_order_pdf(order_details, filename="order.pdf"):
    print(f"محاولة إنشاء ملف PDF: {filename}")
    qr_img_path = None
    try:
        doc = SimpleDocTemplate(filename, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
        story = []
        styles = getSampleStyleSheet()

        # تعريف أنماط الفقرات المخصصة للنص العربي
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontName=ARABIC_FONT_BOLD,
            alignment=TA_CENTER,
            spaceAfter=2,
            fontSize=32,
            textColor=colors.HexColor('#2c3e50')
        )
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Normal'],
            fontName=ARABIC_FONT,
            alignment=TA_CENTER,
            spaceAfter=20,
            fontSize=18,
            textColor=colors.HexColor('#7f8c8d')
        )
        header_style = ParagraphStyle(
            'CustomHeader',
            parent=styles['Normal'],
            fontName=ARABIC_FONT_BOLD,
            alignment=TA_RIGHT,
            spaceAfter=8,
            fontSize=14,
            textColor=colors.HexColor('#34495e')
        )
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontName=ARABIC_FONT,
            alignment=TA_RIGHT,
            spaceAfter=4,
            fontSize=12,
            textColor=colors.HexColor('#34495e')
        )
        total_style = ParagraphStyle(
            'TotalStyle',
            parent=styles['Heading2'],
            fontName=ARABIC_FONT_BOLD,
            alignment=TA_RIGHT,
            spaceBefore=15,
            fontSize=22,
            textColor=colors.HexColor('#c0392b')
        )
        qr_text_style = ParagraphStyle(
            'QRTextStyle',
            parent=styles['Normal'],
            fontName=ARABIC_FONT_BOLD,
            alignment=TA_CENTER,
            spaceAfter=10,
            fontSize=14,
            textColor=colors.HexColor('#2c3e50')
        )
        
        # رأس الفاتورة
        story.append(Paragraph(rtl("<b>سوبر ماركت العراق</b>"), title_style))
        story.append(Paragraph(rtl("فاتورة طلب"), subtitle_style))
        story.append(Spacer(1, 0.2 * inch))

        story.append(Paragraph('<hr color="#ecf0f1" size="2"/>', styles['Normal']))
        story.append(Spacer(1, 0.2 * inch))

        # تفاصيل العميل والطلب
        customer_info_table_data = [
            [
                Paragraph(rtl(f"<b>تاريخ الطلب:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}"), normal_style),
                Paragraph(rtl(f"<b>الهاتف:</b> {order_details['customer']['phone']}"), normal_style),
                Paragraph(rtl(f"<b>الاسم:</b> {order_details['customer']['name']}"), normal_style)
            ]
        ]
        
        customer_table = Table(customer_info_table_data, colWidths=[2.5*inch, 2.5*inch, 2.5*inch])
        customer_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#34495e')),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ]))
        story.append(customer_table)
        story.append(Spacer(1, 0.3 * inch))

        # جدول المنتجات
        story.append(Paragraph(rtl("<b>المنتجات المطلوبة:</b>"), header_style))
        table_header = [
            Paragraph(rtl("الإجمالي"), header_style),
            Paragraph(rtl("السعر"), header_style),
            Paragraph(rtl("الكمية"), header_style),
            Paragraph(rtl("المنتج"), header_style)
        ]
        
        table_data = [table_header]
        total_price_num = 0
        for item_name, item_data in order_details['items'].items():
            item_total = item_data['price'] * item_data['quantity']
            total_price_num += item_total
            table_data.append([
                Paragraph(rtl(f"{item_total:,.0f} د.ع"), normal_style),
                Paragraph(rtl(f"{item_data['price']:,.0f} د.ع"), normal_style),
                Paragraph(rtl(str(item_data['quantity'])), normal_style),
                Paragraph(rtl(item_name), normal_style)
            ])

        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#ffffff')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), ARABIC_FONT),
            ('FONTNAME', (0, 0), (-1, 0), ARABIC_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
            ('BOX', (0, 0), (-1, -1), 1.5, colors.HexColor('#3498db')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ])
        
        col_widths = [1.5*inch, 1.5*inch, 1*inch, 2.5*inch]
        order_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        order_table.setStyle(table_style)
        story.append(order_table)
        story.append(Spacer(1, 0.3 * inch))

        # قسم الإجمالي
        total_frame_data = [[Paragraph(rtl(f"<b>المجموع الإجمالي:</b> {total_price_num:,.0f} د.ع"), total_style)]]
        total_table = Table(total_frame_data, colWidths=[7.5*inch])
        total_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#fde6e6')),
            ('BOX', (0,0), (-1,-1), 1.5, colors.HexColor('#c0392b')),
            ('ROUNDEDCORNERS', (0,0), (-1,-1), 5),
            ('TOPPADDING', (0,0), (-1,-1), 10),
            ('BOTTOMPADDING', (0,0), (-1,-1), 10)
        ]))
        story.append(total_table)
        story.append(Spacer(1, 0.5 * inch))

        # قسم الباركود (موقع العميل)
        if order_details['customer']['location']:
            lat = order_details['customer']['location']['lat']
            lng = order_details['customer']['location']['lng']
            qr_data = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
            
            qr_img = qrcode.make(qr_data)
            qr_img_path = "qr_code.png"
            qr_img.save(qr_img_path)

            story.append(Paragraph(rtl("امسح الباركود للوصول إلى موقع العميل"), qr_text_style))
            story.append(Spacer(1, 0.1 * inch))

            qr_image = Image(qr_img_path)
            qr_image.drawHeight = 2.5*inch
            qr_image.drawWidth = 2.5*inch
            
            qr_table_data = [[qr_image]]
            qr_table = Table(qr_table_data, colWidths=[7.5*inch])
            qr_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (0,0), 'CENTER'),
                ('VALIGN', (0,0), (0,0), 'MIDDLE'),
                ('BOX', (0,0), (0,0), 2, colors.HexColor('#2c3e50')),
                ('ROUNDEDCORNERS', (0,0), (0,0), 5)
            ]))
            story.append(qr_table)
        
        doc.build(story)
        print(f"تم إنشاء ملف PDF بنجاح: {filename}")
        return filename

    except Exception as e:
        print(f"خطأ في إنشاء ملف PDF: {e}")
        return None
    finally:
        # حذف صورة QR بعد استخدامها
        if qr_img_path and os.path.exists(qr_img_path):
            os.remove(qr_img_path)
            print(f"تم حذف صورة QR: {qr_img_path}")


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
            text_message += f"<b>- الإحداثيات:</b> <a href='https://www.google.com/maps/search/?api=1&query={lat},{lng}'>الموقع الجغرافي</a>\n"
            text_message += f"<b>- المسافة عن المتجر:</b> {distance:,.2f} متر\n"
        else:
            text_message += f"<b>- ملاحظة:</b> لم يتمكن العميل من إرسال موقعه الجغرافي.\n"
        
        text_message += f"\n<b><u>المنتجات:</u></b>\n"
        total_price = 0
        for item_name, item_data in order_details['items'].items():
            item_total = item_data['price'] * item_data['quantity']
            total_price += item_total
            text_message += f"• {item_name} (الكمية: {item_data['quantity']}) - السعر: {item_total:,.0f} د.ع\n"
        
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
        
        return jsonify({'status': 'success', 'message': 'تم إرسال الطلب والفاتورة بنجاح.'})

    except Exception as e:
        print(f"خطأ في معالجة الطلب: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# API: إرسال صورة
@app.route('/send-photo', methods=['POST'])
def send_photo():
    try:
        photo_file = request.files.get('photo')
        if not photo_file:
            return jsonify({'status': 'error', 'message': 'لم يتم توفير ملف الصورة.'}), 400
        
        caption = request.form.get('caption', 'صورة مرفقة بالطلب.')
        
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        files = {'photo': photo_file}
        payload = {'chat_id': CHAT_ID, 'caption': caption}
        
        response = requests.post(url, data=payload, files=files, timeout=30)
        response.raise_for_status()
        print(f"تم إرسال الصورة بنجاح: {response.json()}")

        return jsonify({'status': 'success', 'message': 'تم إرسال الصورة بنجاح.'})

    except requests.exceptions.RequestException as e:
        print(f"خطأ في إرسال الصورة إلى تيليجرام: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))
