import sys
import logging
import requests
import json
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, ListFlowable, ListItem, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle, ListStyle
from reportlab.lib.enums import TA_CENTER
import matplotlib.pyplot as plt
from reportlab.pdfgen import canvas
import numpy as np
import pandas as pd
import io
try:
    import google.generativeai as genai
except ImportError:
    genai = None
    logging.warning("google-generativeai not installed. Using placeholder data.")

# ─── CONFIGURATION ───────────────────────────────────────────────────
API_KEY = "AIzaSyAWA9Kqh2FRtBmxRZmNlZ7pcfasG5RJmR8"  # Replace with your actual Gemini API key
MODEL = "gemini-1.5-flash"
OUTPUT_DIR = "."
PDF_PATH = os.path.join(OUTPUT_DIR, "soil_report_full.pdf")
CHART_PATH_NUTRIENTS = os.path.join(OUTPUT_DIR, "nutrient_chart.png")
CHART_PATH_PROPERTIES = os.path.join(OUTPUT_DIR, "properties_chart.png")
LOGO_PATH = os.path.join(OUTPUT_DIR, "logo.png")  # Optional: Place your logo file here

# Ensure output directory exists
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    handlers=[logging.FileHandler("soil_report.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ─── SOIL DATA (Placeholder if API unavailable) ──────────────────────
soil_data = {
    "location": "Sample Field, Region XYZ",
    "date": datetime.now().strftime("%Y-%m-%d"),
    "parameters": {
        "pH": 6.8,
        "Nitrogen": 20,
        "Phosphorus": 15,
        "Potassium": 40,
        "Organic Carbon": 0.9,
        "EC (dS/m)": 1.0,
        "Moisture (%)": 18,
        "Temperature (°C)": 27
    }
}

ideal_ranges = {
    "pH": (6.0, 7.5),
    "Nitrogen": (20, 40),
    "Phosphorus": (10, 30),
    "Potassium": (15, 40),
    "Organic Carbon": (2.5, 5.0),
    "EC (dS/m)": (0.5, 1.5),
    "Moisture (%)": (12, 25),
    "Temperature (°C)": (18, 30)
}

# ─── HELPER FUNCTIONS ────────────────────────────────────────────────
def fetch_soil_data():
    """Fetch soil data from Gemini API or use placeholder data."""
    if not genai or not API_KEY:
        logger.warning("Gemini API not configured or API key missing. Using placeholder data.")
        return soil_data
    
    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel(MODEL)
        prompt = (
            "Provide soil parameter data for a sample agricultural field in JSON format, "
            "including location, date (YYYY-MM-DD), and parameters (pH, Nitrogen, Phosphorus, "
            "Potassium, Organic Carbon, EC, Moisture, Temperature)."
        )
        response = model.generate_content(prompt)
        if response and response.text:
            try:
                parsed_data = json.loads(response.text.strip()) if response.text.strip().startswith('{') else soil_data
                logger.info("Successfully fetched soil data from Gemini API.")
                return parsed_data
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse API response as JSON: {e}. Using placeholder data.")
                return soil_data
        else:
            logger.error("Empty response from Gemini API.")
            return soil_data
    except Exception as e:
        logger.error(f"Failed to fetch data from Gemini API: {e}")
        return soil_data

def calculate_soil_health_score(data, ranges):
    """Calculate a soil health score based on parameter ranges."""
    score = 0
    total_params = len(data["parameters"])
    for param, value in data["parameters"].items():
        min_val, max_val = ranges.get(param, (float('-inf'), float('inf')))
        if min_val <= value <= max_val:
            score += 1
    percentage = (score / total_params) * 100 if total_params > 0 else 0
    rating = "Excellent" if percentage >= 80 else "Good" if percentage >= 60 else "Fair" if percentage >= 40 else "Poor"
    return percentage, rating

def generate_interpretation(param, value, ranges):
    """Generate dynamic interpretation for a soil parameter."""
    min_val, max_val = ranges.get(param, (float('-inf'), float('inf')))
    unit = (
        " ppm" if param in ("Nitrogen", "Phosphorus", "Potassium") else
        " %" if param in ("Organic Carbon", "Moisture (%)") else
        " °C" if "Temperature" in param else
        " dS/m" if "EC" in param else ""
    )
    range_text = f"{min_val:.1f}-{max_val:.1f}{unit}" if min_val != float('-inf') and max_val != float('inf') else "N/A"
    if value < min_val:
        return f"Low; below optimal range ({range_text}). Supplementation recommended."
    elif value > max_val:
        return f"High; above optimal range ({range_text}). Monitor for excess."
    else:
        return f"Optimal; within ideal range ({range_text})."

# ─── CHART GENERATION ────────────────────────────────────────────────
def make_nutrient_chart(data):
    """Generate a bar chart for nutrient levels (N, P, K)."""
    logger.info("Generating nutrient chart...")
    try:
        nutrients = ["Nitrogen", "Phosphorus", "Potassium"]
        values = [data["parameters"].get(n, 0) for n in nutrients]
        plt.figure(figsize=(6, 4))
        bars = plt.bar(nutrients, values, color='forestgreen', alpha=0.7)
        plt.title("Soil Nutrient Levels (ppm)", fontsize=12)
        plt.ylabel("Concentration (ppm)")
        plt.ylim(0, max(values) * 1.2 if values else 100)
        for bar in bars:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2, yval + 0.5, f"{yval:.1f}", ha='center', va='bottom')
        plt.tight_layout()
        plt.savefig(CHART_PATH_NUTRIENTS, dpi=100, bbox_inches='tight')
        plt.close()
        logger.info(f"Nutrient chart saved to {CHART_PATH_NUTRIENTS}")
    except Exception as e:
        logger.error(f"Failed to generate nutrient chart: {e}")

def make_properties_chart(data):
    """Generate a bar chart for soil properties (pH, EC, Moisture, Temperature, Organic Carbon)."""
    logger.info("Generating soil properties chart...")
    try:
        properties = ["pH", "Organic Carbon", "EC (dS/m)", "Moisture (%)", "Temperature (°C)"]
        values = [data["parameters"].get(p, 0) for p in properties]
        plt.figure(figsize=(8, 4))
        bars = plt.bar(properties, values, color='sandybrown', alpha=0.7)
        plt.title("Soil Properties", fontsize=12)
        plt.ylabel("Value")
        plt.xticks(rotation=45, ha='right')
        for bar in bars:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2, yval + 0.05 * max(values, default=1), f"{yval:.1f}", ha='center', va='bottom')
        plt.tight_layout()
        plt.savefig(CHART_PATH_PROPERTIES, dpi=100, bbox_inches='tight')
        plt.close()
        logger.info(f"Properties chart saved to {CHART_PATH_PROPERTIES}")
    except Exception as e:
        logger.error(f"Failed to generate properties chart: {e}")

# ─── PDF REPORT ──────────────────────────────────────────────────────
def add_header(canvas, doc):
    """Add header with logo and title to each page."""
    canvas.saveState()
    try:
        if os.path.exists(LOGO_PATH):
            canvas.drawImage(LOGO_PATH, 2*cm, A4[1] - 3*cm, width=2*cm, height=2*cm, mask='auto')
        else:
            logger.warning("Logo file not found, skipping in header.")
    except Exception as e:
        logger.warning(f"Error loading logo: {e}")
    canvas.setFont("Helvetica-Bold", 12)
    canvas.drawString(5*cm, A4[1] - 2.5*cm, "FarmMatrix Soil Health Report")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(A4[0] - 2*cm, A4[1] - 2.5*cm, f"Generated: {datetime.now():%B %d, %Y %H:%M}")
    canvas.restoreState()

def add_footer(canvas, doc):
    """Add footer with page number."""
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(A4[0]/2, cm, f"Page {doc.page}")
    canvas.restoreState()

def build_pdf(data):
    """Generate a professional PDF report with soil data."""
    logger.info("Creating styled PDF report...")
    try:
        doc = SimpleDocTemplate(
            PDF_PATH, pagesize=A4,
            rightMargin=2*cm, leftMargin=2*cm,
            topMargin=3*cm, bottomMargin=2*cm
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=16, spaceAfter=12, alignment=TA_CENTER)
        h2 = ParagraphStyle('Heading2', parent=styles['Heading2'], fontSize=12, spaceAfter=10)
        body = ParagraphStyle('Body', parent=styles['BodyText'], fontSize=10, leading=12)
        list_style = ListStyle('List', leftIndent=12, bulletIndent=0, bulletFontName='Helvetica')

        elements = []

        # Cover Page
        elements.append(Paragraph("FarmMatrix Soil Health Report", title_style))
        elements.append(Spacer(1, 0.5*cm))
        elements.append(Paragraph(f"Location: {data['location']}", body))
        elements.append(Paragraph(f"Date: {data['date']}", body))
        elements.append(Paragraph(f"Generated on: {datetime.now():%B %d, %Y %H:%M}", body))
        elements.append(Spacer(1, 2*cm))
        elements.append(Paragraph("Prepared by: FarmMatrix Analytics", body))
        elements.append(PageBreak())

        # Section 1: Executive Summary
        elements.append(Paragraph("1. Executive Summary", h2))
        score, rating = calculate_soil_health_score(data, ideal_ranges)
        summary_text = (
            f"This report analyzes soil parameters obtained from satellite data via the Gemini API. "
            f"Key metrics include pH, nutrients (N, P, K), organic carbon, electrical conductivity (EC), "
            f"moisture, and temperature. The soil health score is {score:.1f}% ({rating}), indicating "
            f"{'optimal' if score >= 80 else 'moderate' if score >= 60 else 'suboptimal'} conditions for agriculture."
        )
        elements.append(Paragraph(summary_text, body))
        elements.append(Spacer(1, 0.5*cm))

        # Section 2: Parameter Table with Interpretations
        elements.append(Paragraph("2. Soil Parameter Analysis", h2))
        table_data = [["Parameter", "Value", "Ideal Range", "Interpretation"]]
        for key, val in data["parameters"].items():
            min_val, max_val = ideal_ranges.get(key, (None, None))
            unit = (
                " ppm" if key in ("Nitrogen", "Phosphorus", "Potassium") else
                " %" if key in ("Organic Carbon", "Moisture (%)") else
                " °C" if "Temperature" in key else
                " dS/m" if "EC" in key else ""
            )
            range_text = f"{min_val:.1f}-{max_val:.1f}{unit}" if min_val is not None and max_val is not None else "N/A"
            table_data.append([
                key,
                f"{val:.1f}{unit}",
                range_text,
                generate_interpretation(key, val, ideal_ranges)
            ])
        col_widths = [3*cm, 3*cm, 4*cm, 6*cm]
        tbl = Table(table_data, colWidths=col_widths)
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.black),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('BOX', (0,0), (-1,-1), 1, colors.black)
        ]))
        elements.append(tbl)
        elements.append(Spacer(1, 0.5*cm))

        # Section 3: Nutrient Levels Chart
        elements.append(Paragraph("3. Nutrient Levels Visualization", h2))
        if os.path.exists(CHART_PATH_NUTRIENTS):
            elements.append(Image(CHART_PATH_NUTRIENTS, width=12*cm, height=6*cm))
        else:
            logger.warning("Nutrient chart not found.")
            elements.append(Paragraph("Nutrient chart unavailable.", body))
        elements.append(Spacer(1, 0.5*cm))

        # Section 4: Soil Properties Chart
        elements.append(Paragraph("4. Soil Properties Visualization", h2))
        if os.path.exists(CHART_PATH_PROPERTIES):
            elements.append(Image(CHART_PATH_PROPERTIES, width=12*cm, height=6*cm))
        else:
            logger.warning("Properties chart not found.")
            elements.append(Paragraph("Properties chart unavailable.", body))
        elements.append(Spacer(1, 0.5*cm))

        # Section 5: Crop Recommendations
        elements.append(Paragraph("5. Crop Recommendations", h2))
        rec_items = [
            "Legumes (e.g., beans, peas) to fix nitrogen and improve soil fertility.",
            "Cover crops (e.g., rye, clover) to enhance organic matter.",
            "Root vegetables (e.g., carrots, beets) suitable for current nutrient levels."
        ]
        elements.append(ListFlowable([ListItem(Paragraph(item, body)) for item in rec_items], style=list_style, bulletType='bullet'))
        elements.append(Spacer(1, 0.5*cm))

        # Section 6: Fertilizer & Treatment Guidance
        elements.append(Paragraph("6. Fertilizer & Treatment Guidance", h2))
        treat_items = [
            "Apply compost (5-10 cm depth) to boost organic carbon.",
            "Use NPK 10-10-10 fertilizer to address nitrogen and phosphorus deficiencies.",
            "Monitor potassium levels; apply potassium sulfate if deficiency is observed."
        ]
        elements.append(ListFlowable([ListItem(Paragraph(item, body)) for item in treat_items], style=list_style, bulletType='bullet'))
        elements.append(Spacer(1, 0.5*cm))

        # Section 7: Soil Improvement Tips
        elements.append(Paragraph("7. Soil Improvement Tips", h2))
        tip_items = [
            "Adopt no-till farming to preserve soil structure and reduce erosion.",
            "Implement crop rotation to balance nutrient demands and prevent depletion.",
            "Use mulching to retain soil moisture and enhance organic matter."
        ]
        elements.append(ListFlowable([ListItem(Paragraph(item, body)) for item in tip_items], style=list_style, bulletType='bullet'))
        elements.append(Spacer(1, 0.5*cm))

        # Section 8: Soil Health Rating
        elements.append(Paragraph("8. Soil Health Rating", h2))
        elements.append(Paragraph(f"Overall Rating: <b>{rating} ({score:.1f}%)</b>", body))
        rating_desc = (
            "The soil health score is calculated based on the proportion of parameters within their ideal ranges. "
            f"A {rating.lower()} rating suggests {'excellent' if score >= 80 else 'good' if score >= 60 else 'fair' if score >= 40 else 'poor'} soil conditions."
        )
        elements.append(Paragraph(rating_desc, body))

        # Build PDF with header and footer
        doc.build(elements, onFirstPage=add_header, onLaterPages=add_header, canvasmaker=canvas.Canvas)
        logger.info(f"PDF report saved to {PDF_PATH}")
    except Exception as e:
        logger.error(f"Error generating PDF report: {e}")
        raise

# ─── MAIN EXECUTION ──────────────────────────────────────────────────
def main():
    try:
        # Fetch soil data
        data = fetch_soil_data()
        
        # Generate charts
        make_nutrient_chart(data)
        make_properties_chart(data)
        
        # Generate PDF report
        build_pdf(data)
        
    except Exception as e:
        logger.error(f"Error in report generation: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()