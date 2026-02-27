import sys
import logging
import requests
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, ListFlowable, ListItem
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle, ListStyle
import matplotlib.pyplot as plt

# ─── CONFIGURATION ───────────────────────────────────────────────────
API_KEY     = "AIzaSyAWA9Kqh2FRtBmxRZmNlZ7pcfasG5RJmR8"  # Replace with your Gemini API key
MODEL       = "gemini-1.5-flash"
OUTPUT_DIR  = "."
PDF_PATH    = f"{OUTPUT_DIR}/soil_report_full.pdf"
CHART_PATH  = f"{OUTPUT_DIR}/nutrient_chart.png"
LOGO_PATH   = f"{OUTPUT_DIR}/logo.png"  # Place your logo file here

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

# ─── SOIL DATA ───────────────────────────────────────────────────────
soil_data = {
    "pH": 6.8,
    "Nitrogen": 20,
    "Phosphorus": 15,
    "Potassium": 40,
    "Organic Carbon": 0.9,
    "EC (dS/m)": 1.0,
    "Moisture (%)": 18,
    "Temperature (°C)": 27
}

# Ideal ranges for each parameter
ideal_ranges = {
    "pH": "6.0 - 7.5",
    "Nitrogen": "20 - 40 ppm",
    "Phosphorus": "10 - 30 ppm",
    "Potassium": "15 - 40 ppm",
    "Organic Carbon": "2.5 - 5.0 %",
    "EC (dS/m)": "0.5 - 1.5 dS/m",
    "Moisture (%)": "12 - 25 %",
    "Temperature (°C)": "18 - 30 °C"
}

interpretations = {
    "pH": "Slightly acidic to neutral; generally optimal",
    "Nitrogen": "Low; requires supplementation",
    "Phosphorus": "Low; benefits from increased levels",
    "Potassium": "Moderate; adequate for many crops",
    "Organic Carbon": "Low; improve organic matter",
    "EC (dS/m)": "Low; favorable salinity",
    "Moisture (%)": "Moderate; may need irrigation",
    "Temperature (°C)": "Warm; favorable growth conditions"
}

# ─── NUTRIENT CHART ──────────────────────────────────────────────────
def make_nutrient_chart(data):
    logging.info("Generating nutrient chart...")
    nutrients = ["Nitrogen", "Phosphorus", "Potassium"]
    values = [data[n] for n in nutrients]
    plt.figure()
    plt.bar(nutrients, values, color='green')
    plt.title("Soil Nutrient Levels (ppm)")
    plt.ylabel("Concentration")
    plt.tight_layout()
    plt.savefig(CHART_PATH)
    plt.close()
    logging.info(f"Chart saved to {CHART_PATH}")

# ─── PDF REPORT ───────────────────────────────────────────────────────
def build_pdf():
    logging.info("Creating styled PDF report...")
    doc = SimpleDocTemplate(PDF_PATH, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    title_style = styles['Title']
    h2 = ParagraphStyle('Heading2', parent=styles['Heading2'], spaceAfter=12)
    body = ParagraphStyle('Body', parent=styles['BodyText'], fontSize=11, leading=14)
    list_style = ListStyle('List', leftIndent=12, bulletIndent=0, bulletFontName='Helvetica')

    elements = []
    # Logo
    try:
        elements.append(Image(LOGO_PATH, width=4*cm, height=4*cm))
    except Exception:
        logging.warning("Logo not found, skipping logo.")
    # Title and Date
    elements.append(Paragraph("FarmMatrix Soil Health Report", title_style))
    elements.append(Paragraph(f"Date: {datetime.now():%B %d, %Y}", styles['Normal']))
    elements.append(Spacer(1,12))

    # Section 1: Parameter Table with Ideal Ranges
    elements.append(Paragraph("1. Parameter Interpretation", h2))
    table_data = [["Parameter", "Value", "Ideal Range", "Interpretation"]]
    for key, val in soil_data.items():
        interp = interpretations.get(key, "")
        unit = " ppm" if key in ("Nitrogen", "Phosphorus", "Potassium") else (" %" if key in ("Moisture (%)", "Organic Carbon") else "°C" if "Temperature" in key else " dS/m" if "EC" in key else "")
        table_data.append([
            key,
            f"{val}{unit}",
            ideal_ranges.get(key, ""),
            interp
        ])
    col_widths = [3*cm, 3*cm, 4*cm, 5*cm]
    tbl = Table(table_data, colWidths=col_widths)
    tbl.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.lightgrey),
        ('GRID',(0,0),(-1,-1),0.5,colors.grey),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold')
    ]))
    elements.append(tbl)
    elements.append(Spacer(1,12))

    # Section 2: Chart
    elements.append(Paragraph("2. Nutrient Levels Chart", h2))
    elements.append(Image(CHART_PATH, width=12*cm, height=6*cm))
    elements.append(Spacer(1,12))

    # Section 3: Recommendations
    elements.append(Paragraph("3. Crop Recommendations", h2))
    rec_items = [
        "Legumes (beans, peas) to fix nitrogen",
        "Cover crops (rye, oats) for organic matter",
        "Root vegetables (carrots, beets) with moderate nutrient demand"
    ]
    elements.append(ListFlowable([ListItem(Paragraph(item, body)) for item in rec_items], style=list_style, bulletType='bullet'))
    elements.append(Spacer(1,12))

    # Section 4: Fertilizer & Treatment
    elements.append(Paragraph("4. Fertilizer & Treatment Guidance", h2))
    treat_items = [
        "Apply compost (5-10 cm depth) to improve organic matter",
        "Use NPK 10-10-10 fertilizer to address N and P deficiencies",
        "Consider potassium sulfate if K deficiency observed"
    ]
    elements.append(ListFlowable([ListItem(Paragraph(item, body)) for item in treat_items], style=list_style, bulletType='bullet'))
    elements.append(Spacer(1,12))

    # Section 5: Soil Improvement Tips
    elements.append(Paragraph("5. Soil Improvement Tips", h2))
    tip_items = [
        "No-till farming to maintain soil structure",
        "Crop rotation to balance nutrients",
        "Mulching to retain moisture and add organic matter"
    ]
    elements.append(ListFlowable([ListItem(Paragraph(item, body)) for item in tip_items], style=list_style, bulletType='bullet'))
    elements.append(Spacer(1,12))

    # Section 6: Final Rating
    elements.append(Paragraph("6. Final Soil Health Rating", h2))
    elements.append(Paragraph("Overall Rating: <b>Fair (3/5)</b>", body))

    doc.build(elements)
    logging.info(f"PDF report saved to {PDF_PATH}")

# Main execution
if __name__ == '__main__':
    make_nutrient_chart(soil_data)
    build_pdf()
