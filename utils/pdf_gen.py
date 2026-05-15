from fpdf import FPDF
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def generate_esim_pdf(order_id, region, smdp, activation, qr_path=None):
    # A4 dimensions: 210mm width x 297mm height
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_auto_page_break(auto=False) # We will manage the layout manually
    
    # ---------------------------------------------------------
    # 1. THE DARK BLUE BANNER (Background)
    # ---------------------------------------------------------
    pdf.set_fill_color(32, 35, 69)  # Lyca-style Dark Blue
    pdf.rect(0, 0, 210, 65, 'F')
    
    # Success Icon & Text
    pdf.set_xy(0, 25)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", 'B', 18)
    pdf.cell(0, 10, "Your order is confirmed", align='C', ln=True)
    
    # ---------------------------------------------------------
    # 2. THE OVERLAPPING SUMMARY CARD
    # ---------------------------------------------------------
    card_x = 15
    card_w = 180
    
    # Slight grey shadow trick (Draw a grey box slightly lower/right)
    pdf.set_fill_color(230, 230, 230)
    pdf.rect(card_x + 1, 51, card_w, 28, 'F')
    
    # Main White Overlap Card
    pdf.set_fill_color(255, 255, 255)
    pdf.rect(card_x, 50, card_w, 28, 'F')
    
    # The Green Accent Line on the left
    pdf.set_fill_color(0, 200, 110)
    pdf.rect(card_x, 50, 2, 28, 'F')
    
    # Text inside the Overlap Card
    pdf.set_xy(card_x + 6, 53)
    pdf.set_text_color(32, 35, 69)
    pdf.set_font("Helvetica", 'B', 10)
    pdf.cell(0, 6, f"Order reference : {order_id} ({region})", ln=True)
    
    pdf.set_x(card_x + 6)
    pdf.set_text_color(100, 100, 100)
    pdf.set_font("Helvetica", '', 9)
    pdf.multi_cell(card_w - 12, 5, "You'll receive a Telegram confirmation with this order summary. If you ordered an eSIM plan and need to reinstall it later, please refer to these manual details.")

    # ---------------------------------------------------------
    # 3. THE MAIN SIM INFORMATION SECTION
    # ---------------------------------------------------------
    info_y = 85
    pdf.set_draw_color(220, 220, 220)
    pdf.rect(card_x, info_y, card_w, 80, 'D') # Outlined Box
    
    # Section Title
    pdf.set_xy(card_x + 6, info_y + 5)
    pdf.set_text_color(32, 35, 69)
    pdf.set_font("Helvetica", 'B', 11)
    pdf.cell(0, 8, "eSIM information", ln=True)
    
    # ----- LEFT SIDE: MANUAL DETAILS -----
    left_x = card_x + 6
    pdf.set_xy(left_x, info_y + 20)
    pdf.set_text_color(120, 120, 120)
    pdf.set_font("Helvetica", 'B', 10)
    pdf.cell(0, 6, "Copy manually", ln=True)
    
    pdf.set_x(left_x)
    pdf.set_font("Helvetica", '', 9)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 5, "SM-DP+ Address", ln=True)
    
    pdf.set_x(left_x)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", 'B', 9)
    pdf.cell(100, 5, smdp, ln=True)
    
    pdf.ln(4)
    pdf.set_x(left_x)
    pdf.set_font("Helvetica", '', 9)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 5, "Activation code", ln=True)
    
    pdf.set_x(left_x)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", 'B', 9)
    # multi_cell prevents the long activation code from running off the page
    pdf.multi_cell(110, 5, activation) 

    # ----- RIGHT SIDE: QR CODE -----
    qr_x = 140  # Pushed to the right
    qr_y = info_y + 15
    qr_size = 45
    
    if qr_path and os.path.exists(qr_path):
        pdf.image(qr_path, x=qr_x, y=qr_y, w=qr_size)
    else:
        pdf.set_draw_color(200, 200, 200)
        pdf.rect(qr_x, qr_y, qr_size, qr_size, 'D')
        pdf.set_xy(qr_x, qr_y + 20)
        pdf.set_font("Helvetica", '', 8)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(qr_size, 5, "No QR Provided", align='C')

    # ---------------------------------------------------------
    # 4. IMPORTANT INFORMATION (YELLOW BOX)
    # ---------------------------------------------------------
    warn_y = 175
    pdf.set_fill_color(255, 251, 235)  # Light Warning Yellow
    pdf.rect(card_x, warn_y, card_w, 25, 'F')
    
    pdf.set_xy(card_x + 6, warn_y + 4)
    pdf.set_text_color(32, 35, 69)
    pdf.set_font("Helvetica", 'B', 10)
    pdf.cell(0, 6, "Important information", ln=True)
    
    pdf.set_x(card_x + 6)
    pdf.set_text_color(80, 80, 80)
    pdf.set_font("Helvetica", '', 9)
    pdf.multi_cell(card_w - 12, 5, "- These details are important & we request you not to share them with anyone else.\n- An eSIM can only be installed once. Do not delete it from your phone after scanning.")

    # ---------------------------------------------------------
    # 5. INSTRUCTIONS
    # ---------------------------------------------------------
    inst_y = 205
    pdf.set_draw_color(220, 220, 220)
    pdf.rect(card_x, inst_y, card_w, 45, 'D')
    
    pdf.set_xy(card_x + 6, inst_y + 5)
    pdf.set_text_color(32, 35, 69)
    pdf.set_font("Helvetica", 'B', 10)
    pdf.cell(0, 6, "How to install this eSIM?", ln=True)
    
    pdf.set_x(card_x + 6)
    pdf.set_text_color(80, 80, 80)
    pdf.set_font("Helvetica", '', 9)
    instructions = (
        "1. Navigate to your phone's settings, then 'Cellular' or 'Mobile Data'.\n"
        "2. Look for options like 'Add eSIM' or 'Add Data Plan' and click it.\n"
        "3. Select 'Use QR Code' and scan the image provided above on the right.\n"
        "4. If you cannot scan the QR code, select 'Enter Details Manually' and use the codes provided."
    )
    pdf.multi_cell(card_w - 12, 6, instructions)

    # Save and Return
    file_path = os.path.join(BASE_DIR, f"esim_{order_id}.pdf")
    pdf.output(file_path)
    return file_path