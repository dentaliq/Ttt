import os import requests import json import math import qrcode from datetime import datetime from reportlab.lib.pagesizes import letter from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle from reportlab.lib import colors from reportlab.lib.units import inch from reportlab.pdfbase import pdfmetrics from reportlab.pdfbase.ttfonts import TTFont from flask import Flask, request, jsonify from flask_cors import CORS from reportlab.lib.enums import TA_RIGHT, TA_CENTER

دعم العربية

import arabic_reshaper from bidi.algorithm import get_display

إعداد تطبيق Flask

app = Flask(name) CORS(app)

بيانات بوت تيليجرام

BOT_TOKEN = 'ضع_توكن_البوت_هنا' CHAT_ID = 'ضع_ايدي_المحادثة_هنا'

موقع المتجر لحساب المسافة

MARKET_LOCATION = {'lat': 32.6468089, 'lng': 43.9782430}

تسجيل خطوط عربية (Janna LT)

try: pdfmetrics.registerFont(TTFont('JannaLT', 'alfont_com_Janna-LT-Regular.ttf')) pdfmetrics.registerFont(TTFont('JannaLT-Bold', 'alfont_com_Janna-LT-Bold.ttf')) ARABIC_FONT = 'JannaLT' ARABIC_FONT_BOLD = 'JannaLT-Bold' except Exception as e: print(f"خطأ في تحميل الخط العربي: {e}. سيتم استخدام Helvetica كبديل.") ARABIC_FONT = 'Helvetica' ARABIC_FONT_BOLD = 'Helvetica-Bold'

دالة لمعالجة النص العربي (حروف متصلة + RTL)

def rtl(text): if not text: return "" reshaped_text = arabic_reshaper.reshape(text) bidi_text = get_display(reshaped_text) return bidi_text

دالة لحساب المسافة

def haversine_distance(lat1, lon1, lat2, lon2): R = 6371e3 φ1 = math.radians(lat1) φ2 = math.radians(lat2) Δφ = math.radians(lat2 - lat1) Δλ = math.radians(lon2 - lon1) a = math.sin(Δφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ / 2) ** 2 c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)) return R * c

إرسال رسالة نصية

def send_telegram_message(text, chat_id=CHAT_ID): url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage" payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'} try: response = requests.post(url, json=payload, timeout=10) response.raise_for_status() print(f"تم إرسال الرسالة بنجاح: {response.json()}") return response except requests.exceptions.RequestException as e: print(f"خطأ في إرسال الرسالة إلى تيليجرام: {e}") return None

إرسال ملف PDF

def send_telegram_document(file_path, chat_id=CHAT_ID, caption=''): if not os.path.exists(file_path): print(f"خطأ: الملف غير موجود في المسار: {file_path}") return None

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"

try:
    with open(file_path, 'rb') as f:
        files = {'document': f}
        payload = {'chat_id': chat_id, 'caption': caption}
        response = requests.post(url, data=payload, files=files, timeout=30)
        response.raise_for_status()
        print(f"تم إرسال الملف بنجاح: {response.json()}")

        os.remove(file_path)
        print(f"تم حذف ملف PDF: {file_path}")

    return response
except requests.exceptions.RequestException as e:
    print(f"خطأ في إرسال الملف إلى تيليجرام: {e}")
    return None

إنشاء فاتورة PDF

def create_order_pdf(order_details, filename="order.pdf"): qr_img_path = None try: doc = SimpleDocTemplate(filename, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40) story = [] styles = getSampleStyleSheet()

# أنماط النصوص
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontName=ARABIC_FONT_BOLD,
        alignment=TA_CENTER,
        fontSize=28,
        textColor=colors.HexColor('#2c3e50')
    )
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontName=ARABIC_FONT,
        alignment=TA_CENTER,
        fontSize=16,
        textColor=colors.HexColor('#7f8c8d')
    )
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Normal'],
        fontName=ARABIC_FONT_BOLD,
        alignment=TA_RIGHT,
        fontSize=13,
        textColor=colors.HexColor('#34495e')
    )
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontName=ARABIC_FONT,
        alignment=TA_RIGHT,
        fontSize=11,
        textColor=colors.HexColor('#34495e')
    )
    total_style = ParagraphStyle(
        'TotalStyle',
        parent=styles['Heading2'],
        fontName=ARABIC_FONT_BOLD,
        alignment=TA_RIGHT,
        fontSize=18,
        textColor=colors.HexColor('#c0392b')
    )
    qr_text_style = ParagraphStyle(
        'QRTextStyle',
        parent=styles['Normal'],
        fontName=ARABIC_FONT_BOLD,
        alignment=TA_CENTER,
        fontSize=13,
        textColor=colors.HexColor('#2c3e50')
    )

    # رأس الفاتورة
    story.append(Paragraph(rtl("سوبر ماركت العراق"), title_style))
    story.append(Paragraph(rtl("فاتورة طلب"), subtitle_style))
    story.append(Spacer(1, 0.2 * inch))

    # تفاصيل العميل
    customer_info_table_data = [
        [
            Paragraph(rtl(f"تاريخ الطلب: {datetime.now().strftime('%Y-%m-%d %H:%M')}"), normal_style),
            Paragraph(rtl(f"الهاتف: {order_details['customer']['phone']}"), normal_style),
            Paragraph(rtl(f"الاسم: {order_details['customer']['name']}"), normal_style)
        ]
    ]
    customer_table = Table(customer_info_table_data, colWidths=[2.5*inch, 2.5*inch, 2.5*inch])
    story.append(customer_table)
    story.append(Spacer(1, 0.3 * inch))

    # جدول المنتجات
    story.append(Paragraph(rtl("المنتجات المطلوبة:"), header_style))
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

    order_table = Table(table_data, colWidths=[1.5*inch, 1.5*inch, 1*inch, 2.5*inch], repeatRows=1)
    order_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), ARABIC_FONT),
        ('FONTNAME', (0, 0), (-1, 0), ARABIC_FONT_BOLD),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
    ]))
    story.append(order_table)
    story.append(Spacer(1, 0.3 * inch))

    # الإجمالي
    story.append(Paragraph(rtl(f"المجموع الإجمالي: {total_price_num:,.0f} د.ع"), total_style))
    story.append(Spacer(1, 0.5 * inch))

    # باركود الموقع
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
        qr_image.drawHeight = 2*inch
        qr_image.drawWidth = 2*inch
        story.append(qr_image)

    doc.build(story)
    return filename

except Exception as e:
    print(f"خطأ في إنشاء ملف PDF: {e}")
    return None
finally:
    if qr_img_path and os.path.exists(qr_img_path):
        os.remove(qr_img_path)

API: استقبال الطلب

@app.route('/send-order', methods=['POST']) def send_order(): try: order_details = request.get_json()

text_message = f"✅ <b>طلب جديد من السوبر ماركت:</b>\n\n"
    text_message += f"- الاسم: {order_details['customer']['name']}\n"
    text_message += f"- الهاتف: {order_details['customer']['phone']}\n"

    if 'location' in order_details['customer'] and order_details['customer']['location']:
        lat = order_details['customer']['location']['lat']
        lng = order_details['customer']['location']['lng']
        distance = haversine_distance(MARKET_LOCATION['lat'], MARKET_LOCATION['lng'], lat, lng)
        text_message += f"- <a href='https://www.google.com/maps/search/?api=1&query={lat},{lng}'>الموقع الجغرافي</a>\n"
        text_message += f"- المسافة: {distance:,.2f} متر\n"

    total_price = 0
    for item_name, item_data in order_details['items'].items():
        item_total = item_data['price'] * item_data['quantity']
        total_price += item_total
        text_message += f"• {item_name} (الكمية: {item_data['quantity']}) - {item_total:,.0f} د.ع\n"

    text_message += f"\n<b>الإجمالي: {total_price:,.0f} د.ع</b>"

    send_telegram_message(text_message)

    pdf_file = create_order_pdf(order_details)
    if pdf_file:
        send_telegram_document(
            pdf_file,
            caption=f"فاتورة طلب {order_details['customer']['name']} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )

    return jsonify({'status': 'success', 'message': 'تم إرسال الطلب والفاتورة بنجاح.'})

except Exception as e:
    print(f"خطأ في معالجة الطلب: {e}")
    return jsonify({'status': 'error', 'message': str(e)}), 500

if name == 'main': app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))

