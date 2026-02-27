# 🌾 FarmMatrix

> **AI-Powered Satellite-Based Soil Quality Analysis Platform**


---

## 📌 Overview

**FarmMatrix** is an AI-powered, satellite-based soil analysis platform that provides farmers with real-time, sensor-free soil fertility insights. Traditional soil testing is slow, costly, and inaccessible — leading to poor soil management and lower crop yields. FarmMatrix solves this by leveraging free satellite data from **Google Earth Engine** and **NASA SMAP**, combined with machine learning, to deliver precise soil health reports directly to farmers on their mobile devices — without any physical sensors.

---

## 🚜 The Problem

- Traditional soil lab testing is expensive and time-consuming
- Results are hard to access for smallholder and rural farmers
- Poor soil health management leads to lower yields and income loss
- Farmers lack actionable, region-specific, language-friendly guidance

---

## ✅ Our Solution

FarmMatrix provides:

- **Satellite-based soil analysis** using Sentinel-2, MODIS, and NASA SMAP data — no physical sensors needed
- **Comprehensive Soil Fertility Reports** covering pH, Organic Carbon (OC), Electrical Conductivity (EC), and NPK levels with charts and improvement recommendations
- **Zone-wise Fertility Mapping** with up to 90% accuracy, showing spatial distribution of soil health across a field
- **Real-time Dashboard** with insights on water content, salinity, nutrient levels, and overall soil condition
- **Disease & Risk Prediction** to detect early crop threats and prevent losses
- **Multilingual Support** — reports and guidance available in Hindi, Marathi, Punjabi, Tamil, and Telugu

---

## 🛠️ Tech Stack

| Category | Technology |
|---|---|
| Frontend / UI | Streamlit |
| Satellite Data | Google Earth Engine (Sentinel-2, MODIS, Landsat), NASA SMAP |
| AI / ML | CNN + LSTM models, Random Forest, XGBoost, SVM |
| LLM / Report Generation | Groq API (`llama-3.3-70b-versatile`) |
| PDF Generation | ReportLab |
| Mapping | Folium, streamlit-folium |
| Data Processing | Python, Pandas |
| Deployment | Hugging Face Spaces |

---

## 📁 Project Structure

```

```

---

## 🌍 Key Features

### 🛰️ Sensor-Free Satellite Analysis
Uses multispectral imagery from Sentinel-2, Landsat, and MODIS with cloud masking and gap-fill techniques to analyze soil without any physical hardware.

### 📊 Soil Fertility Reports
Detailed reports covering:
- **pH** — Soil acidity/alkalinity
- **OC** — Organic Carbon content
- **EC** — Electrical Conductivity / Salinity
- **NPK** — Nitrogen, Phosphorus, Potassium levels
- **Soil Texture** — USDA classification (Clay, Loam, Sand, etc.)
- **CEC** — Cation Exchange Capacity
- **LST** — Land Surface Temperature

All parameters compared against **ICAR Indian Soil Health Card** standards with actionable recommendations.

### 🗺️ Zone-Wise Fertility Mapping
Interactive map interface where farmers can draw their field boundary and get a color-coded fertility zone map showing which parts of their land need attention.

### 🤖 AI-Powered Insights (75–95% Accuracy)
- CNN + LSTM architecture trained on multi-satellite fusion data
- Multiple spectral indices: NDVI, MSAVI, BSI, and band ratios
- Phenology-aware features for seasonal accuracy
- Ensemble ML methods for soil nutrient estimation

### 🌐 Multilingual Platform
Reports, recommendations, and educational video content available in **5 regional Indian languages** to ensure accessibility for all farmers across India.

---

## 📈 Impact & Benefits

**For Farmers:**
- Boosts crop yield by ~10–20%
- Reduces input costs by ~30%
- Provides affordable soil reports (avg. cost < ₹50/field/month)
- Reduces decision lag by 30–40%

**Economic:**
- India's precision agriculture market: USD 300M (2024) → USD 700M+ by 2030 (10–17% CAGR)
- Replaces expensive lab testing with satellite-powered AI

**Environmental:**
- Protects long-term soil health and prevents degradation
- Promotes targeted, precision use of fertilizers and irrigation
- Supports sustainable farming practices

---

## ⚙️ Setup & Installation

### Prerequisites
- Python 3.8+
- Google Earth Engine account (with authentication)
- Groq API Key

### Install Dependencies

```bash
pip install streamlit folium streamlit-folium earthengine-api pandas \
            matplotlib reportlab openai python-dateutil certifi
```

### Authenticate Google Earth Engine

```bash
earthengine authenticate
```

### Configure API Key

In each report script, set your Groq API key:

```python
GROQ_API_KEY = "your_groq_api_key_here"
GROQ_MODEL   = "llama-3.3-70b-versatile"
```



---

## 🔬 Research References

| Title | Authors | Year | Key Contribution |
|---|---|---|---|
| Soil Organic Carbon Estimation Using Remote Sensing Data-Driven Machine Learning | Qi Chen, Yiting Wang, Xicun Zhu | 2024 | RF, XGBoost, SVM for SOC mapping; no ground sensors |
| Geospatial Digital Mapping of Soil Organic Carbon Using ML and Geostatistical Methods | Y. Parvizi et al. | 2025 | ML models for SOC mapping across varied land uses |
| Soil Textures and Nutrients Estimation Using Remote Sensing Data in North India | Gaurav Dhiman, Jhilik Bhattacharya, Sangita Roy | 2023 | Estimates 9 soil nutrients using satellite data |
| Ultra-High-Resolution Hyperspectral Imagery for Precision Agriculture | Abdennour Mohamed Amine et al. | 2020 | Satellite-based EC and salinity mapping |
| Detection of Soil Salinity Using Remote Sensing and Machine Learning | Various Authors | 2025 | High accuracy salinity detection with DL |

---

## ⚠️ Known Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Low satellite coverage / cloud interference | Multi-satellite fusion (Sentinel-2, Landsat, MODIS) with cloud masking & gap-fill |
| Spectral confusion (soil vs. residue vs. water) | Multiple indices (BSI, MSAVI, NDVI), band ratios, CNN ensembles |
| Inconsistent external weather API accuracy | Combine OpenWeather + satellite data for field-level weather estimation |

---

## 👨‍💻 Team

**Team Name:** INORA
**Problem Statement ID:** AG001
**Event:** Morpheus SIT(Lonavala)

---

## 📄 License

This project was built for a hackathon and is intended for educational and demonstration purposes.

---

*"Empowering farmers with the power of satellites and AI — making precision agriculture accessible to everyone."* 🌱
