import os
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
from reportlab.lib.enums import TA_RIGHT, TA_CENTER

# دعم العربية
import arabic_reshaper
from bidi.algorithm import get_display

# تسجيل خطوط عربية
try:
    pdfmetrics.registerFont(TTFont('Cairo', 'Cairo-Regular.ttf'))
    pdfmetrics.registerFont(TTFont('Cairo-Bold', 'Cairo-Bold.ttf'))
    ARABIC_FONT = 'Cairo'
    ARABIC_FONT_BOLD = 'Cairo-Bold'
except Exception as e:
    print(f"خطأ في تحميل الخط: {e}. سيتم استخدام Helvetica.")
    ARABIC_FONT = 'Helvetica'
    ARABIC_FONT_BOLD = 'Helvetica-Bold'

# معالجة النص العربي (اتجاه + تشابك الحروف)
def rtl(text):
    if not text:
        return ""
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)
    return bidi_text


def create_order_pdf(order_details, filename="order.pdf"):
    qr_img_path = None
    try:
        doc = SimpleDocTemplate(
            filename,
            pagesize=letter,
            rightMargin=30,
            leftMargin=30,
            topMargin=30,
            bottomMargin=30
        )
        story = []
        styles = getSampleStyleSheet()

        # ===== أنماط النصوص =====
        normal_style = ParagraphStyle(
            'Normal',
            fontName=ARABIC_FONT,
            fontSize=12,
            alignment=TA_RIGHT,
            textColor=colors.HexColor('#424242')
        )
        bold_style = ParagraphStyle(
            'Bold',
            fontName=ARABIC_FONT_BOLD,
            fontSize=12,
            alignment=TA_RIGHT,
            textColor=colors.HexColor('#0d47a1')
        )
        title_style = ParagraphStyle(
            'Title',
            fontName=ARABIC_FONT_BOLD,
            fontSize=20,
            alignment=TA_CENTER,
            textColor=colors.white
        )
        footer_style = ParagraphStyle(
            'Footer',
            fontName=ARABIC_FONT_BOLD,
            fontSize=12,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#607d8b')
        )

        # ===== رأس الفاتورة =====
        header_table = Table(
            [[Paragraph(rtl("فاتورة طلب - سوبرماركت العراق"), title_style)]],
            colWidths=[7.5*inch]
        )
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#0d47a1')),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#0d47a1'))
        ]))
        story.append(header_table)
        story.append(Spacer(1, 0.3*inch))

        # ===== بيانات العميل =====
        customer_table = Table(
            [
                [Paragraph(rtl("<b>اسم العميل:</b>"), bold_style),
                 Paragraph(rtl(order_details['customer']['name']), normal_style)],
                [Paragraph(rtl("<b>رقم الهاتف:</b>"), bold_style),
                 Paragraph(rtl(order_details['customer']['phone']), normal_style)],
                [Paragraph(rtl("<b>تاريخ الطلب:</b>"), bold_style),
                 Paragraph(rtl(datetime.now().strftime('%Y-%m-%d %H:%M')), normal_style)]
            ],
            colWidths=[2*inch, 5*inch]
        )
        customer_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#e3f2fd')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#0d47a1')),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#b0bec5')),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#b0bec5')),
        ]))
        story.append(customer_table)
        story.append(Spacer(1, 0.4*inch))

        # ===== جدول المنتجات =====
        table_header = [
            Paragraph(rtl("المنتج"), bold_style),
            Paragraph(rtl("الكمية"), bold_style),
            Paragraph(rtl("السعر"), bold_style),
            Paragraph(rtl("الإجمالي"), bold_style)
        ]

        table_data = [table_header]
        subtotal = 0
        row_colors = [colors.whitesmoke, colors.HexColor('#f5f5f5')]

        for idx, (item_name, item_data) in enumerate(order_details['items'].items()):
            item_total = item_data['price'] * item_data['quantity']
            subtotal += item_total
            row = [
                Paragraph(rtl(item_name), normal_style),
                Paragraph(rtl(str(item_data['quantity'])), normal_style),
                Paragraph(rtl(f"{item_data['price']:,.0f} د.ع"), normal_style),
                Paragraph(rtl(f"{item_total:,.0f} د.ع"), normal_style)
            ]
            table_data.append(row)

        order_table = Table(table_data, colWidths=[3*inch, 1*inch, 1.5*inch, 1.5*inch])
        order_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0d47a1')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,-1), ARABIC_FONT),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#b0bec5')),
        ]))

        # تلوين الصفوف بالتناوب
        for i in range(1, len(table_data)):
            bg_color = row_colors[i % 2]
            order_table.setStyle(TableStyle([
                ('BACKGROUND', (0,i), (-1,i), bg_color)
            ]))

        story.append(order_table)
        story.append(Spacer(1, 0.4*inch))

        # ===== الملخص المالي =====
        tax = subtotal * 0.05  # ضريبة 5% كمثال
        total = subtotal + tax
        summary_data = [
            [Paragraph(rtl("المجموع الفرعي:"), bold_style),
             Paragraph(rtl(f"{subtotal:,.0f} د.ع"), normal_style)],
            [Paragraph(rtl("الضريبة (5%):"), bold_style),
             Paragraph(rtl(f"{tax:,.0f} د.ع"), normal_style)],
            [Paragraph(rtl("<b>الإجمالي:</b>"), bold_style),
             Paragraph(rtl(f"{total:,.0f} د.ع"), bold_style)]
        ]
        summary_table = Table(summary_data, colWidths=[2*inch, 2.5*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#e3f2fd')),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#0d47a1')),
            ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#90a4ae'))
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 0.5*inch))

        # ===== QR Code =====
        if order_details['customer'].get('location'):
            lat = order_details['customer']['location']['lat']
            lng = order_details['customer']['location']['lng']
            qr_data = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
            qr_img = qrcode.make(qr_data)
            qr_img_path = "qr_code.png"
            qr_img.save(qr_img_path)

            story.append(Paragraph(rtl("امسح الباركود للوصول إلى موقع العميل"), bold_style))
            qr_image = Image(qr_img_path, width=2*inch, height=2*inch)
            qr_table = Table([[qr_image]], colWidths=[7.5*inch])
            qr_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BOX', (0,0), (-1,-1), 2, colors.HexColor('#0d47a1'))
            ]))
            story.append(qr_table)
            story.append(Spacer(1, 0.5*inch))

        # ===== Footer =====
        story.append(Paragraph(rtl("شكراً لتسوقكم من سوبرماركت العراق 🌸"), footer_style))

        # بناء ملف PDF
        doc.build(story)
        print(f"تم إنشاء ملف PDF بنجاح: {filename}")
        return filename

    except Exception as e:
        print(f"خطأ في إنشاء ملف PDF: {e}")
        return None
    finally:
        if qr_img_path and os.path.exists(qr_img_path):
            os.remove(qr_img_path)
            print(f"تم حذف صورة QR: {qr_img_path}")
