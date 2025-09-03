import os
import requests
import json
import math
import qrcode
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, Flowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics import renderPDF
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

# موقع المتجر الفعلي (تم تحديثه)
MARKET_LOCATION = {'lat': 32.6468089, 'lng': 43.9782430}

# تسجيل خطوط عربية جديدة
try:
    pdfmetrics.registerFont(TTFont('Janna-LT-Regular', 'alfont_com_Janna-LT-Regular.ttf'))
    pdfmetrics.registerFont(TTFont('Janna-LT-Bold', 'alfont_com_Janna-LT-Bold.ttf'))
    ARABIC_FONT = 'Janna-LT-Regular'
    ARABIC_FONT_BOLD = 'Janna-LT-Bold'
    print("تم تحميل خطوط Janna بنجاح")
except Exception as e:
    print(f"خطأ في تحميل الخط العربي: {e}. سيتم استخدام الخطوط الافتراضية كبديل.")
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
            os.remove(file_path)
            print(f"تم حذف ملف PDF: {file_path}")
            return response
    except requests.exceptions.RequestException as e:
        print(f"خطأ في إرسال الملف إلى تيليجرام: {e}")
        return None
    except Exception as e:
        print(f"خطأ غير متوقع: {e}")
        return None

def get_file_link(file_id):
    """الحصول على رابط الملف من التيليجرام."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile"
    payload = {'file_id': file_id}
    try:
        response = requests.get(url, params=payload)
        response.raise_for_status()
        file_path = response.json()['result']['file_path']
        file_link = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        return file_link
    except requests.exceptions.RequestException as e:
        print(f"خطأ في الحصول على رابط الملف: {e}")
        return None


def create_order_pdf(order_details, photo_link=None, filename="order.pdf"):
    print(f"محاولة إنشاء ملف PDF: {filename}")
    qr_img_path_customer = None
    qr_img_path_market = None
    qr_img_path_photo = None
    
    try:
        doc = SimpleDocTemplate(filename, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        story = []
        styles = getSampleStyleSheet()

        # تعريف أنماط الفقرات المخصصة
        styles.add(ParagraphStyle(
            'InvoiceTitle',
            fontName=ARABIC_FONT_BOLD,
            fontSize=28,
            textColor=colors.HexColor('#FFFFFF'),
            alignment=TA_CENTER,
            spaceAfter=5,
        ))
        styles.add(ParagraphStyle(
            'SectionHeader',
            fontName=ARABIC_FONT_BOLD,
            fontSize=16,
            textColor=colors.HexColor('#FFFFFF'),
            alignment=TA_RIGHT,
            spaceAfter=10,
            spaceBefore=10,
        ))
        styles.add(ParagraphStyle(
            'LabelText',
            fontName=ARABIC_FONT_BOLD,
            fontSize=12,
            textColor=colors.HexColor('#2C3E50'),
            alignment=TA_RIGHT,
            spaceAfter=5,
        ))
        styles.add(ParagraphStyle(
            'ValueText',
            fontName=ARABIC_FONT,
            fontSize=12,
            textColor=colors.HexColor('#34495E'),
            alignment=TA_RIGHT,
            spaceAfter=15,
        ))
        styles.add(ParagraphStyle(
            'TableHeader',
            fontName=ARABIC_FONT_BOLD,
            fontSize=12,
            textColor=colors.HexColor('#FFFFFF'),
            alignment=TA_CENTER,
        ))
        styles.add(ParagraphStyle(
            'TableData',
            fontName=ARABIC_FONT,
            fontSize=11,
            textColor=colors.HexColor('#2C3E50'),
            alignment=TA_CENTER,
        ))
        styles.add(ParagraphStyle(
            'FooterStyle',
            fontName=ARABIC_FONT,
            fontSize=10,
            textColor=colors.HexColor('#BDC3C7'),
            alignment=TA_CENTER,
        ))
        styles.add(ParagraphStyle(
            'SummaryText',
            fontName=ARABIC_FONT_BOLD,
            fontSize=14,
            textColor=colors.HexColor('#2C3E50'),
            alignment=TA_CENTER,
            spaceAfter=5,
        ))
        styles.add(ParagraphStyle(
            'QRCodeLabel',
            fontName=ARABIC_FONT,
            fontSize=10,
            textColor=colors.HexColor('#7F8C8D'),
            alignment=TA_CENTER,
            spaceAfter=5,
        ))
        
        # رأس الفاتورة بتصميم مميز
        header_table = Table([
            [Paragraph(rtl("فاتورة طلب من سوبر ماركت العراق"), styles['InvoiceTitle'])]
        ], colWidths=[7.5*inch])
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#2C3E50')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#34495E')),
            ('ROUNDEDCORNERS', [10, 10, 10, 10]),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 0.3 * inch))

        # معلومات العميل والطلب بتصميم مميز
        customer_card = Table([
            [Paragraph(rtl("👤 معلومات العميل"), styles['SectionHeader'])]
        ], colWidths=[7.5*inch])
        customer_card.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#3498DB')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#2980B9')),
            ('ROUNDEDCORNERS', [10, 10, 10, 10]),
        ]))
        story.append(customer_card)
        
        info_data = [
            [Paragraph(rtl("<b>الاسم:</b>"), styles['LabelText']), Paragraph(rtl(order_details['customer']['name']), styles['ValueText'])],
            [Paragraph(rtl("<b>الهاتف:</b>"), styles['LabelText']), Paragraph(rtl(order_details['customer']['phone']), styles['ValueText'])],
            [Paragraph(rtl("<b>تاريخ الطلب:</b>"), styles['LabelText']), Paragraph(rtl(datetime.now().strftime('%Y-%m-%d %H:%M')), styles['ValueText'])],
        ]
        
        info_table = Table(info_data, colWidths=[1.5*inch, 5.5*inch])
        info_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F8F9F9')),
            ('BACKGROUND', (0,1), (-1,1), colors.HexColor('#EAF2F8')),
            ('BACKGROUND', (0,2), (-1,2), colors.HexColor('#F8F9F9')),
            ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#D5D8DC')),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#BDC3C7')),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 0.3 * inch))

        # جدول المنتجات بتصميم مميز
        products_header = Table([
            [Paragraph(rtl("🛒 تفاصيل المنتجات"), styles['SectionHeader'])]
        ], colWidths=[7.5*inch])
        products_header.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#2ECC71')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#27AE60')),
            ('ROUNDEDCORNERS', [10, 10, 10, 10]),
        ]))
        story.append(products_header)
        
        table_header = [
            Paragraph(rtl("السعر الإجمالي"), styles['TableHeader']),
            Paragraph(rtl("السعر"), styles['TableHeader']),
            Paragraph(rtl("الكمية"), styles['TableHeader']),
            Paragraph(rtl("المنتج"), styles['TableHeader'])
        ]
        
        table_data = [table_header]
        total_price_num = 0
        items_count = 0

        for item_name, item_data in order_details['items'].items():
            item_total = item_data['price'] * item_data['quantity']
            total_price_num += item_total
            items_count += item_data['quantity']
            
            table_data.append([
                Paragraph(rtl(f"{item_total:,.0f} د.ع"), styles['TableData']),
                Paragraph(rtl(f"{item_data['price']:,.0f} د.ع"), styles['TableData']),
                Paragraph(rtl(str(item_data['quantity'])), styles['TableData']),
                Paragraph(rtl(item_name), styles['TableData'])
            ])

        summary_row_data = [
            Paragraph(rtl(f"<b>{total_price_num:,.0f} د.ع</b>"), styles['TableHeader']),
            Paragraph(rtl("المجموع"), styles['TableHeader']),
            Paragraph(rtl(f"<b>{items_count}</b>"), styles['TableHeader']),
            Paragraph(rtl("الإجمالي"), styles['TableHeader'])
        ]
        
        table_data.append(summary_row_data)

        table_style = TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, -1), ARABIC_FONT),
            ('FONTNAME', (0, 0), (-1, 0), ARABIC_FONT_BOLD),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#16A085')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#FFFFFF')),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#E74C3C')),
            ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#FFFFFF')),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, -1), (-1, -1), 10),
            ('TOPPADDING', (0, -1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#BDC3C7')),
            ('BOX', (0, 0), (-1, -1), 2, colors.HexColor('#2C3E50')),
        ])
        
        order_table = Table(table_data, colWidths=[1.5*inch, 1.5*inch, 1*inch, 2.5*inch])
        order_table.setStyle(table_style)
        story.append(order_table)
        story.append(Spacer(1, 0.3 * inch))

        # قسم ملخص الطلب بتصميم مميز
        summary_card = Table([
            [Paragraph(rtl("📊 ملخص الطلب"), styles['SectionHeader'])]
        ], colWidths=[7.5*inch])
        summary_card.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#9B59B6')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#8E44AD')),
            ('ROUNDEDCORNERS', [10, 10, 10, 10]),
        ]))
        story.append(summary_card)
        
        summary_data = [
            [Paragraph(rtl("عدد المنتجات:"), styles['SummaryText']), Paragraph(rtl(str(items_count)), styles['SummaryText'])],
            [Paragraph(rtl("المجموع الإجمالي:"), styles['SummaryText']), Paragraph(rtl(f"{total_price_num:,.0f} د.ع"), styles['SummaryText'])]
        ]
        
        summary_table = Table(summary_data, colWidths=[3.5*inch, 3.5*inch])
        summary_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8F9F9')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#D5D8DC')),
            ('BOX', (0, 0), (-1, -1), 2, colors.HexColor('#2C3E50')),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 0.4 * inch))

        # باركودات الموقع بتصميم مميز
        locations_card = Table([
            [Paragraph(rtl("📍 مواقع مهمة"), styles['SectionHeader'])]
        ], colWidths=[7.5*inch])
        locations_card.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F39C12')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#D68910')),
            ('ROUNDEDCORNERS', [10, 10, 10, 10]),
        ]))
        story.append(locations_card)
        story.append(Spacer(1, 0.2 * inch))
        
        qr_table_data = [[],[]]
        
        # باركود موقع المتجر
        qr_data_market = f"https://www.google.com/maps/search/?api=1&query={MARKET_LOCATION['lat']},{MARKET_LOCATION['lng']}"
        qr_img_market = qrcode.make(qr_data_market)
        qr_img_path_market = "qr_market.png"
        qr_img_market.save(qr_img_path_market)
        market_image = Image(qr_img_path_market)
        market_image.drawHeight = 1.5 * inch
        market_image.drawWidth = 1.5 * inch
        qr_table_data[0].append(market_image)
        qr_table_data[1].append(Paragraph(rtl("امسح لموقع المتجر"), styles['QRCodeLabel']))
        
        # باركود موقع العميل
        if order_details['customer']['location']:
            lat = order_details['customer']['location']['lat']
            lng = order_details['customer']['location']['lng']
            qr_data_customer = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
            qr_img_customer = qrcode.make(qr_data_customer)
            qr_img_path_customer = "qr_customer.png"
            qr_img_customer.save(qr_img_path_customer)
            customer_image = Image(qr_img_path_customer)
            customer_image.drawHeight = 1.5 * inch
            customer_image.drawWidth = 1.5 * inch
            qr_table_data[0].append(customer_image)
            qr_table_data[1].append(Paragraph(rtl("امسح لموقع العميل"), styles['QRCodeLabel']))
            
            # حساب المسافة وإضافتها
            distance = haversine_distance(MARKET_LOCATION['lat'], MARKET_LOCATION['lng'], lat, lng)
            distance_text = Paragraph(rtl(f"<b>المسافة بين المتجر والعميل:</b> {distance:,.2f} متر"), styles['LabelText'])
            story.append(distance_text)
            story.append(Spacer(1, 0.2 * inch))
        else:
            no_location = Paragraph(rtl("<b>ملاحظة:</b> لم يتم توفير موقع العميل."), styles['LabelText'])
            story.append(no_location)
            story.append(Spacer(1, 0.2 * inch))
        
        # باركود الصورة المرفقة
        if photo_link:
            photo_card = Table([
                [Paragraph(rtl("🖼️ الصورة المرفقة"), styles['SectionHeader'])]
            ], colWidths=[7.5*inch])
            photo_card.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#E74C3C')),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CB4335')),
                ('ROUNDEDCORNERS', [10, 10, 10, 10]),
            ]))
            story.append(photo_card)
            story.append(Spacer(1, 0.2 * inch))

            qr_img_photo = qrcode.make(photo_link)
            qr_img_path_photo = "qr_photo.png"
            qr_img_photo.save(qr_img_path_photo)
            
            photo_image_qr = Image(qr_img_path_photo)
            photo_image_qr.drawHeight = 1.5 * inch
            photo_image_qr.drawWidth = 1.5 * inch

            qr_table_data[0].append(photo_image_qr)
            qr_table_data[1].append(Paragraph(rtl("امسح لرؤية الصورة"), styles['QRCodeLabel']))
            
        # إنشاء الجدول للباركودات
        qr_table = Table(qr_table_data, colWidths=[2*inch] * len(qr_table_data[0]), hAlign='CENTER')
        qr_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8F9F9')),
        ]))
        
        story.append(qr_table)
        story.append(Spacer(1, 0.5 * inch))

        # تذييل الفاتورة
        footer = Table([
            [Paragraph(rtl("شكراً لثقتكم بنا. نتمنى لكم يوماً سعيداً."), styles['FooterStyle'])]
        ], colWidths=[7.5*inch])
        footer.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#2C3E50')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#1B2631')),
        ]))
        story.append(footer)

        doc.build(story)
        print(f"تم إنشاء ملف PDF بنجاح: {filename}")
        return filename

    except Exception as e:
        print(f"خطأ في إنشاء ملف PDF: {e}")
        return None
    finally:
        # حذف صور QR بعد استخدامها
        if qr_img_path_customer and os.path.exists(qr_img_path_customer):
            os.remove(qr_img_path_customer)
        if qr_img_path_market and os.path.exists(qr_img_path_market):
            os.remove(qr_img_path_market)
        if qr_img_path_photo and os.path.exists(qr_img_path_photo):
            os.remove(qr_img_path_photo)
        print("تم حذف صور QR المؤقتة.")


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
        
        temp_path = f"temp_{photo_file.filename}"
        photo_file.save(temp_path)
        
        with open(temp_path, 'rb') as f:
            files = {'photo': f}
            data = {'chat_id': CHAT_ID, 'caption': caption}
            response = requests.post(url, data=data, files=files, timeout=30)
        
        os.remove(temp_path)
        
        response.raise_for_status()
        
        file_id = response.json()['result']['photo'][-1]['file_id']
        photo_link = get_file_link(file_id)
        
        print(f"تم إرسال الصورة بنجاح: {response.json()}")
        return jsonify({'status': 'success', 'message': 'تم إرسال الصورة بنجاح.', 'photo_link': photo_link})

    except requests.exceptions.RequestException as e:
        print(f"خطأ في إرسال الصورة إلى تيليجرام: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
    except Exception as e:
        print(f"خطأ غير متوقع: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


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

        send_telegram_message(text_message)
        
        photo_link = order_details.get('photo_link')
        
        pdf_file = create_order_pdf(order_details, photo_link)
        if pdf_file:
            send_telegram_document(
                pdf_file, 
                caption=
f"فاتورة طلب السيد {order_details['customer']['name']} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )

        return jsonify({'status': 'success', 'message': 'تم إرسال الطلب والفاتورة بنجاح.'})

    except Exception as e:
        print(f"خطأ في معالجة الطلب: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000), debug=True)
