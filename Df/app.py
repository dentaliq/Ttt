import os
import math
import qrcode
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, Rect
from reportlab.graphics import renderPDF
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
import arabic_reshaper
from bidi.algorithm import get_display

# دعم الخطوط العربية - تأكد من وجود هذه الخطوط في مجلد المشروع
try:
    pdfmetrics.registerFont(TTFont('Cairo-Bold', 'Cairo-Bold.ttf'))
    pdfmetrics.registerFont(TTFont('Cairo-Regular', 'Cairo-Regular.ttf'))
    pdfmetrics.registerFont(TTFont('Tajawal-Bold', 'Tajawal-Bold.ttf'))
    pdfmetrics.registerFont(TTFont('Tajawal-Regular', 'Tajawal-Regular.ttf'))
    ARABIC_FONT = 'Tajawal-Regular'
    ARABIC_FONT_BOLD = 'Tajawal-Bold'
    print("تم تحميل الخطوط العربية بنجاح")
except:
    # استخدام خطوط افتراضية إذا لم تكن الخطوط العربية متوفرة
    ARABIC_FONT = 'Helvetica'
    ARABIC_FONT_BOLD = 'Helvetica-Bold'
    print("تم استخدام الخطوط الافتراضية")

# دالة لمعالجة النص العربي
def rtl(text):
    if not text:
        return ""
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)
    return bidi_text

# إنشاء فاتورة PDF بتصميم متميز
def create_beautiful_invoice(order_details, filename="beautiful_invoice.pdf"):
    doc = SimpleDocTemplate(
        filename, 
        pagesize=letter, 
        rightMargin=20, 
        leftMargin=20, 
        topMargin=30, 
        bottomMargin=30
    )
    story = []
    styles = getSampleStyleSheet()
    
    # تعريف أنماط التصميم الجديدة
    styles.add(ParagraphStyle(
        'BeautifulTitle',
        fontName=ARABIC_FONT_BOLD,
        fontSize=28,
        textColor=colors.HexColor('#2c3e50'),
        alignment=TA_CENTER,
        spaceAfter=30,
    ))
    
    styles.add(ParagraphStyle(
        'GradientHeader',
        fontName=ARABIC_FONT_BOLD,
        fontSize=20,
        textColor=colors.white,
        alignment=TA_CENTER,
        spaceAfter=15,
    ))
    
    styles.add(ParagraphStyle(
        'SectionHeader',
        fontName=ARABIC_FONT_BOLD,
        fontSize=16,
        textColor=colors.HexColor('#1a5276'),
        alignment=TA_RIGHT,
        spaceAfter=12,
        spaceBefore=20,
    ))
    
    styles.add(ParagraphStyle(
        'ElegantLabel',
        fontName=ARABIC_FONT_BOLD,
        fontSize=13,
        textColor=colors.HexColor('#4a4a4a'),
        alignment=TA_RIGHT,
        spaceAfter=6,
        backColor=colors.HexColor('#f8f9fa'),
    ))
    
    styles.add(ParagraphStyle(
        'ElegantValue',
        fontName=ARABIC_FONT,
        fontSize=13,
        textColor=colors.HexColor('#2c3e50'),
        alignment=TA_RIGHT,
        spaceAfter=15,
    ))
    
    styles.add(ParagraphStyle(
        'TotalStyle',
        fontName=ARABIC_FONT_BOLD,
        fontSize=20,
        textColor=colors.HexColor('#c0392b'),
        alignment=TA_RIGHT,
        spaceBefore=20,
        spaceAfter=25,
    ))
    
    styles.add(ParagraphStyle(
        'FooterStyle',
        fontName=ARABIC_FONT,
        fontSize=11,
        textColor=colors.HexColor('#7f8c8d'),
        alignment=TA_CENTER,
        spaceBefore=30,
    ))
    
    # رأس الفاتورة مع تدرج لوني
    header_drawing = Drawing(500, 100)
    header_rect = Rect(0, 0, 500, 100, fill=1)
    header_rect.fillColor = colors.HexColor('#2c3e50')
    header_drawing.add(header_rect)
    
    # إضافة الرأس إلى القصة
    story.append(header_drawing)
    story.append(Paragraph(rtl("فاتورة شراء"), styles['BeautifulTitle']))
    story.append(Spacer(1, 0.3 * inch))
    
    # معلومات العميل في مربع أنيق
    customer_data = [
        [Paragraph(rtl("معلومات العميل"), styles['SectionHeader']), ""],
        [Paragraph(rtl("الاسم:"), styles['ElegantLabel']), 
         Paragraph(rtl(order_details['customer']['name']), styles['ElegantValue'])],
        [Paragraph(rtl("الهاتف:"), styles['ElegantLabel']), 
         Paragraph(rtl(order_details['customer']['phone']), styles['ElegantValue'])],
        [Paragraph(rtl("تاريخ الطلب:"), styles['ElegantLabel']), 
         Paragraph(rtl(datetime.now().strftime('%Y-%m-%d %H:%M')), styles['ElegantValue'])],
    ]
    
    customer_table = Table(customer_data, colWidths=[2.5*inch, 4*inch])
    customer_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), ARABIC_FONT_BOLD),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
        ('BOX', (0, 0), (-1, -1), 2, colors.HexColor('#2980b9')),
    ]))
    
    story.append(customer_table)
    story.append(Spacer(1, 0.4 * inch))
    
    # جدول المنتجات بتصميم حديث
    story.append(Paragraph(rtl("المنتجات المشتراة"), styles['SectionHeader']))
    
    # عناوين الأعمدة
    table_header = [
        Paragraph(rtl("السعر الإجمالي"), styles['ElegantLabel']),
        Paragraph(rtl("السعر"), styles['ElegantLabel']),
        Paragraph(rtl("الكمية"), styles['ElegantLabel']),
        Paragraph(rtl("اسم المنتج"), styles['ElegantLabel'])
    ]
    
    table_data = [table_header]
    total_price = 0
    
    # بيانات المنتجات
    for item_name, item_data in order_details['items'].items():
        item_total = item_data['price'] * item_data['quantity']
        total_price += item_total
        
        table_data.append([
            Paragraph(rtl(f"{item_total:,.0f} د.ع"), styles['ElegantValue']),
            Paragraph(rtl(f"{item_data['price']:,.0f} د.ع"), styles['ElegantValue']),
            Paragraph(rtl(str(item_data['quantity'])), styles['ElegantValue']),
            Paragraph(rtl(item_name), styles['ElegantValue'])
        ])
    
    # تنسيق الجدول
    product_table = Table(table_data, colWidths=[1.5*inch, 1.5*inch, 1*inch, 2.5*inch])
    product_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#16a085')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), ARABIC_FONT_BOLD),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ffffff')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e0e0e0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f9f9f9'), colors.white]),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#bdbdbd')),
    ]))
    
    story.append(product_table)
    story.append(Spacer(1, 0.4 * inch))
    
    # قسم المجموع الكلي
    total_data = [
        [Paragraph(rtl("المجموع الكلي:"), styles['TotalStyle']), 
         Paragraph(rtl(f"{total_price:,.0f} د.ع"), styles['TotalStyle'])]
    ]
    
    total_table = Table(total_data, colWidths=[4*inch, 2*inch])
    total_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#f1c40f')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#f39c12')),
    ]))
    
    story.append(total_table)
    story.append(Spacer(1, 0.5 * inch))
    
    # إنشاء QR Code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    
    qr_data = f"""
    فاتورة شراء
    الاسم: {order_details['customer']['name']}
    الهاتف: {order_details['customer']['phone']}
    التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}
    المجموع: {total_price:,.0f} د.ع
    """
    
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    qr_img = qr.make_image(fill_color="#2c3e50", back_color="#ecf0f1")
    qr_img_path = "temp_qr.png"
    qr_img.save(qr_img_path)
    
    # إضافة QR code إلى الوثيقة
    qr_story = []
    qr_story.append(Paragraph(rtl("باركود الفاتورة"), styles['SectionHeader']))
    
    qr_table_data = [
        [Image(qr_img_path, width=1.5*inch, height=1.5*inch), 
         Paragraph(rtl("امسح الباركود للتحقق من الفاتورة"), styles['ElegantValue'])]
    ]
    
    qr_table = Table(qr_table_data, colWidths=[2*inch, 3*inch])
    qr_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#ecf0f1')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
    ]))
    
    story.append(qr_table)
    story.append(Spacer(1, 0.5 * inch))
    
    # تذييل الصفحة
    footer = Paragraph(rtl("شكراً لثقتكم الغالية • نتمنى لكم يوماً سعيداً"), styles['FooterStyle'])
    story.append(footer)
    
    # بناء الوثيقة
    doc.build(story)
    
    # تنظيف الملف المؤقت
    if os.path.exists(qr_img_path):
        os.remove(qr_img_path)
    
    return filename

# نموذج بيانات للاختبار
if __name__ == "__main__":
    sample_order = {
        'customer': {
            'name': 'أحمد محمد',
            'phone': '07701234567'
        },
        'items': {
            'أرز بسمتي': {'price': 5000, 'quantity': 2},
            'زيت زيتون': {'price': 15000, 'quantity': 1},
            'سكر': {'price': 2000, 'quantity': 3},
            'دقيق': {'price': 2500, 'quantity': 2}
        }
    }
    
    create_beautiful_invoice(sample_order, "فاتورة_مميزة.pdf")
    print("تم إنشاء الفاتورة بنجاح!")
