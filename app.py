"""
SNAP Dashboard — Sai Amatör Yatırım
Google Sheets bağlantılı | Tüm metrikler seçilebilir
"""

import streamlit as st
import streamlit.components.v1 as components
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import os
import unicodedata
import json
from pathlib import Path
import time

AYARLAR_DOSYASI = Path(__file__).parent / "snap_ayarlar.json"

def ayarlari_yukle():
    try:
        if AYARLAR_DOSYASI.exists():
            return json.loads(AYARLAR_DOSYASI.read_text(encoding="utf-8"))
    except:
        pass
    return {}

def ayarlari_kaydet(d):
    try:
        AYARLAR_DOSYASI.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    except:
        pass


def normalize_col(s):
    """Türkçe karakter duyarsız sütun karşılaştırması için normalize et"""
    if not isinstance(s, str):
        return str(s)
    tr_map = str.maketrans("çÇğĞıIİişŞöÖüÜ", "cCgGiIIisSOouU")
    return s.translate(tr_map).upper().strip()

def find_col(df, aranan):
    """DataFrame'de Türkçe karakter duyarsız sütun bul"""
    norm_aranan = normalize_col(aranan)
    for col in df.columns:
        if normalize_col(col) == norm_aranan:
            return col
    return None

def tr_fmt(v, decimals=2):
    """Türkçe sayı formatı: binlik ayırıcı nokta, ondalık virgül"""
    try:
        fv = float(v)
        if decimals == 0:
            s = f"{fv:,.0f}"
        elif decimals == 1:
            s = f"{fv:,.1f}"
        else:
            s = f"{fv:,.2f}"
        return s.replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return str(v)

def tr_kpi(fv):
    """KPI kartları için kısa format"""
    if abs(fv) >= 1e9:
        return tr_fmt(fv/1e9) + " Mr"
    elif abs(fv) >= 1e6:
        return tr_fmt(fv/1e6, 1) + " Mn"
    else:
        return tr_fmt(fv)

def fmt_mn(v):
    """Grafik etiket formatı: Mn TL cinsinden, tam sayı, birim yok"""
    if v is None:
        return "—"
    try:
        fv = float(v)
        if np.isnan(fv):
            return "—"
        mn = fv / 1_000_000
        return tr_fmt(mn, 0)
    except:
        return str(v) if v else "—"

def tr_df_fmt(v):
    """DataFrame hücresi için Türkçe format.
    |değer| >= 1.000.000 → Mn TL tam sayı
    |değer| >= 1000 → tam sayı
    küçük sayılar → 2 ondalık"""
    if v is None:
        return "—"
    try:
        fv = float(v)
        if np.isnan(fv):
            return "—"
        if abs(fv) >= 1_000_000:
            return tr_fmt(fv / 1_000_000, decimals=0)
        if abs(fv) >= 1000:
            return tr_fmt(fv, decimals=0)
        return tr_fmt(fv)
    except:
        return str(v) if v else "—"

def df_goster(df, height=None, use_container_width=True, mn_tl=False, puan_stili=False):
    """Sayısal sütunları Türkçe formatlı Styler ile göster (sıralama bozulmaz)."""
    num_cols = df.select_dtypes(include="number").columns.tolist()
    fmt_dict = {c: tr_df_fmt for c in num_cols}
    styled = df.style.format(fmt_dict, na_rep="—").hide(axis="index")
    if puan_stili:
        styled = styled.set_table_styles([
            {"selector": "table",
             "props": [("background-color", "#FFFFFF"), ("border-collapse", "collapse"), ("width", "100%")]},
            {"selector": "thead tr th",
             "props": [
                 ("background-color", PUAN_HEADER_BG),
                 ("color", "#FFFFFF"),
                 ("font-weight", "700"),
                 ("font-size", "12px"),
                 ("letter-spacing", "0.05em"),
                 ("text-transform", "uppercase"),
                 ("text-align", "center"),
                 ("vertical-align", "middle"),
                 ("border-bottom", f"3px solid {PUAN_HEADER_BORDER}"),
                 ("border-right", f"1px solid {PUAN_HEADER_DIVIDER}"),
                 ("padding", "11px 14px"),
                 ("white-space", "nowrap"),
             ]},
            {"selector": "tbody tr",
             "props": [("background-color", "#FFFFFF")]},
            {"selector": "tbody tr:nth-child(even)",
             "props": [("background-color", "#F2F6FB")]},
            {"selector": "tbody tr:hover",
             "props": [("background-color", "#DDEAF7")]},
            {"selector": "tbody tr td",
             "props": [
                 ("color", "#000000"),
                 ("font-size", "13px"),
                 ("font-weight", "500"),
                 ("padding", "9px 14px"),
                 ("border-bottom", "1px solid #D6E4F0"),
                 ("border-right", "1px solid #EBF2FA"),
             ]},
            {"selector": "tbody tr td:first-child",
             "props": [("font-weight", "700"), ("color", "#000000")]},
        ])
    kwargs = {"use_container_width": use_container_width}
    if height:
        kwargs["height"] = height
    if mn_tl:
        st.markdown(f"<p style='color:{MAIN_SOLUK};font-size:11px;margin-bottom:4px;'>💡 Büyük sayılar Mn TL cinsinden gösterilmektedir.</p>", unsafe_allow_html=True)
    st.dataframe(styled, **kwargs)


# ─────────────────────────────────────────────
# AYARLAR
# ─────────────────────────────────────────────
CREDENTIALS_PATH = r"C:\Users\%USERNAME%\Desktop\snap code\credentials.json"
SHEET_ID = "1SGam3PHCH8EtjQT0bk9RkdwdvdsWE49MsMvdl8O1gz8"
SHEET_URL = "https://docs.google.com/spreadsheets/d/1SGam3PHCH8EtjQT0bk9RkdwdvdsWE49MsMvdl8O1gz8/edit?gid=988578347#gid=988578347"

DONEM_SAYFALARI = [
    ("2025/12", "2025/12",  "SNAP 25/12"),
    ("2025/9",  "2025/9",   "SNAP 25/9"),
    ("2025/6",  "2025/6",   "SNAP 25/6"),
    ("2025/3",  "2025/3",   "SNAP 25/3"),
    ("2024/12", "2024/12",  "SNAP 24/12"),
    ("2024/9",  "2024/9",   "SNAP 24/9"),
    ("2024/6",  "2024/6",   "SNAP 24/6"),
    ("2024/3",  "2024/3",   "SNAP 24/3"),
]
PUAN_SAYFASI = "SNAP SON"
AYAR_SAYFASI = "AYAR"
CIKTI_SAYFALARI = ["ÇIKTI 1", "ÇIKTI 2", "ÇIKTI 3"]

PUAN_SABIT_SUTUNLAR = [
    "SNAP", "NAKİT", "EFK", "BİLANÇO SONRASI",
    "BİLANÇO SONRASI XU100", "ALFA", "DÖNEM",
]

def puan_sabit_filtrele(mevcut_cols, istenenler=None):
    def _puan_col_key(s):
        s = normalize_col(s)
        s = s.replace(" ", "")
        s = s.replace("／", "/")
        return s

    norm = {_puan_col_key(c): c for c in mevcut_cols}
    alternatifler = {
        _puan_col_key("PDDD"): ["PD/DD", "PD / DD", "PD-DD", "PD DD"],
        _puan_col_key("NET BORÇ/FAVÖK"): ["NET BORÇ / FAVÖK", "NET BORC/FAVOK", "NET BORC / FAVOK", "NETBORÇ/FAVÖK", "NETBORC/FAVOK"],
        _puan_col_key("FD/FAVÖK"): ["FD / FAVÖK", "FD/FAVOK", "FD / FAVOK"],
        _puan_col_key("ÖZKAYNAK"): ["ÖZKAYNAKLAR", "OZKAYNAKLAR"],
        _puan_col_key("BİLANÇO SONRASI XU100"): ["BILANCO SONRASI XU100", "BİLANÇO SONRASI XU 100", "BILANCO SONRASI XU 100"],
    }
    sonuc = []
    for aranan in (istenenler or PUAN_SABIT_SUTUNLAR):
        adaylar = [aranan] + alternatifler.get(_puan_col_key(aranan), [])
        for aday in adaylar:
            eslesme = norm.get(_puan_col_key(aday))
            if eslesme and eslesme not in sonuc:
                sonuc.append(eslesme)
                break
    return sonuc

TEMALAR = {
    "1 Gece Laciverd":    {"BG":"#030810","SURFACE":"#060D1A","CARD":"#0A1428","ALTIN":"#60A5FA","BAR":"#3B82F6"},
    "2 Koyu Lacivert":    {"BG":"#0F1923","SURFACE":"#1A2744","CARD":"#1E293B","ALTIN":"#F59E0B","BAR":"#2E75B6"},
    "3 Derin Lacivert":   {"BG":"#0F2040","SURFACE":"#162850","CARD":"#1E3460","ALTIN":"#38BDF8","BAR":"#0EA5E9"},
    "4 Slate Lacivert":   {"BG":"#263B60","SURFACE":"#2E4570","CARD":"#354E7A","ALTIN":"#7DD3FC","BAR":"#38BDF8"},
    "5 İndigo-1":         {"BG":"#0F0F2D","SURFACE":"#13134A","CARD":"#1A1A5E","ALTIN":"#818CF8","BAR":"#6366F1"},
    "6 İndigo-2":         {"BG":"#13134A","SURFACE":"#1A1A5E","CARD":"#222278","ALTIN":"#A5B4FC","BAR":"#818CF8"},
    "7 İndigo-3":         {"BG":"#1A1A5E","SURFACE":"#222278","CARD":"#2A2A90","ALTIN":"#C7D2FE","BAR":"#A5B4FC"},
    "⬛ Siyah":            {"BG":"#0A0A0A","SURFACE":"#141414","CARD":"#1C1C1C","ALTIN":"#F59E0B","BAR":"#6366F1"},
    "🟣 Açık Mor":         {"BG":"#1A1030","SURFACE":"#261845","CARD":"#32205C","ALTIN":"#C4B5FD","BAR":"#C4B5FD"},
}

st.set_page_config(page_title="SNAP Dashboard", page_icon="📊", layout="wide")

if "ayarlar_yuklendi" not in st.session_state:
    _kayit = ayarlari_yukle()
    _tema_kayit = _kayit.get("tema_adi", "2 Koyu Lacivert")
    if _tema_kayit not in TEMALAR:
        _tema_kayit = list(TEMALAR.keys())[0]
    st.session_state.tema_adi     = _tema_kayit
    st.session_state.bg_custom    = _kayit.get("bg_custom", None)
    st.session_state.surf_custom  = _kayit.get("surf_custom", None)
    st.session_state.altin_custom = _kayit.get("altin_custom", None)
    st.session_state.pozitif_renk = _kayit.get("pozitif_renk", "#10B981")
    st.session_state.negatif_renk = _kayit.get("negatif_renk", "#EF4444")
    st.session_state.bar_tek_renk = _kayit.get("bar_tek_renk", None)
    _eski = _kayit.get("kpi_ham", []) + _kayit.get("kpi_snap", [])
    st.session_state.kpi_cols_kayit = _kayit.get("kpi_cols", _eski)
    st.session_state.ozet_grafikler_kayit = _kayit.get("ozet_grafikler", [])
    st.session_state.puan_m6_kayit  = PUAN_SABIT_SUTUNLAR
    st.session_state.puan_sr6_kayit = _kayit.get("puan_sr6", "")
    st.session_state["m6"] = PUAN_SABIT_SUTUNLAR
    if _kayit.get("puan_sr6"):
        st.session_state["sr6"] = _kayit["puan_sr6"]
    st.session_state.ayarlar_yuklendi = True

_tema = TEMALAR[st.session_state.tema_adi]
BG      = st.session_state.bg_custom   or _tema["BG"]
SURFACE = st.session_state.surf_custom or _tema["SURFACE"]
CARD    = _tema["CARD"]
ALTIN   = st.session_state.altin_custom or _tema["ALTIN"]
YESIL   = st.session_state.pozitif_renk
KIRMIZI = st.session_state.negatif_renk
MAVI    = "#1F4E79"; ACIK = "#2E75B6"
TEMA_BAR = st.session_state.get("bar_tek_renk") or _tema.get("BAR", "#2E75B6")

def bg_parlaklik(hex_renk):
    try:
        h = hex_renk.lstrip("#")
        r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
        return 0.299*r + 0.587*g + 0.114*b
    except:
        return 0

_parlak = bg_parlaklik(BG)
METIN       = "#1E293B" if _parlak > 128 else "#E2E8F0"
METIN_SOLUK = "#475569" if _parlak > 128 else "#94A3B8"
METIN_ZAYIF = "#64748B"
GRID_RENK   = "#CBD5E1" if _parlak > 128 else "#1E293B"

MAIN_BG       = "#FFFFFF"
MAIN_SURFACE  = "#F8FAFC"
MAIN_CARD     = "#FFFFFF"
MAIN_METIN    = "#0F2B4C"
MAIN_SOLUK    = "#1F4E79"
MAIN_GRID     = "#E2E8F0"
MAIN_BASLIK   = "#0F2B4C"
MAIN_BORDER   = "#CBD5E1"
MAIN_HEADER   = "#1E3A5F"
PUAN_HEADER_BG = "#0F2B4C"
PUAN_HEADER_BORDER = "#081727"
PUAN_HEADER_DIVIDER = "#29527A"
PUAN_ILK50_RENKLER = ["#B4D9B4", "#C7E6C7", "#D9F0D9", "#EAF8EA", "#F5FCF5"]

def puan_donem_sutunu_mu(col_name):
    return any(k in str(col_name).upper() for k in ("DÖNEM", "DONEM", "PERIOD", "TARİH", "TARIH", "DATE"))

def puan_kolon_sirasi(cols):
    cols = list(dict.fromkeys(cols))
    donem_cols = [c for c in cols if puan_donem_sutunu_mu(c)]
    if not donem_cols:
        return cols
    alfa_cols = puan_sabit_filtrele(cols, ["ALFA"])
    diger_cols = [c for c in cols if c not in donem_cols and c not in alfa_cols]
    return diger_cols + alfa_cols + donem_cols

def puan_satir_rengi(row_pos):
    if row_pos < 50:
        return PUAN_ILK50_RENKLER[min(row_pos // 10, len(PUAN_ILK50_RENKLER) - 1)]
    return "#FFFFFF"

def puan_hucre_yazi_rengi(col_name, value):
    col_norm = normalize_col(col_name)
    if col_norm == normalize_col("SNAP"):
        return PUAN_HEADER_BG
    if col_norm == normalize_col("ALFA"):
        fv = safe_float(value)
        if pd.notna(fv):
            if fv > 10:
                return "#166534"
            if fv > 0:
                return "#16A34A"
            if fv < 0:
                return "#DC2626"
    return "#000000"

def snap_amblem_html(compact=False):
    if compact:
        return f"""
        <div style='display:flex;flex-direction:column;align-items:flex-start;gap:2px;'>
          <div style='font-size:22px;font-weight:800;letter-spacing:-0.03em;line-height:1;'>
            <span style='color:#A855F7;'>S</span><span style='color:#22D3EE;'>NAP</span>
          </div>
          <div style='font-size:11px;color:{MAIN_SOLUK};font-weight:500;letter-spacing:0.02em;text-transform:uppercase;'>sai amatör yatırım</div>
        </div>
        """
    return f"""
    <div style='display:flex;align-items:baseline;gap:8px;padding:6px 0 14px 0;border-bottom:2px solid {MAIN_GRID};margin-bottom:20px;'>
      <span style='font-size:22px;font-weight:800;letter-spacing:-0.03em;'>
        <span style='color:#A855F7;'>S</span><span style='color:#22D3EE;'>NAP</span>
      </span>
      <span style='font-size:13px;color:{MAIN_SOLUK};font-weight:400;letter-spacing:0.02em;'>sai amatör yatırım</span>
    </div>
    """

st.markdown(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

  html, body, p, h1, h2, h3, h4, h5, h6,
  .stMarkdown *, .stButton > button,
  div[data-testid="metric-container"] *,
  .stSelectbox > div, .stMultiSelect > div,
  .stTextInput input, .stNumberInput input,
  .stDataFrame, .stTable {{ font-family: 'Inter', sans-serif !important; }}

  .stApp {{ background-color:{MAIN_BG}; }}
  .main .block-container {{ padding: 1.5rem 2rem 2rem 2rem; max-width: 1400px; }}

  .main p, .main span, .main div, .main label {{ color: {MAIN_METIN}; }}
  .main h1, .main h2, .main h3 {{ color: {MAIN_BASLIK} !important; font-weight: 700 !important; letter-spacing: -0.02em; }}
  .main h3 {{ font-size: 18px !important; border-bottom: 1px solid {MAIN_BORDER}; padding-bottom: 10px; margin-bottom: 20px; }}

  [data-testid="stSidebar"] {{
    background-color:{SURFACE};
    border-right: 1px solid {GRID_RENK};
  }}
  [data-testid="stSidebar"] .block-container {{ padding: 1.5rem 1rem; }}
  [data-testid="stSidebar"] p,
  [data-testid="stSidebar"] span,
  [data-testid="stSidebar"] div,
  [data-testid="stSidebar"] label {{ color: {METIN}; }}

  .stRadio [data-testid="stWidgetLabel"] {{ display: none; }}
  [data-testid="stSidebar"] .stRadio > div {{
    display: flex; flex-direction: column; gap: 2px;
  }}
  [data-testid="stSidebar"] .stRadio label {{
    background: transparent !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 8px 12px !important;
    cursor: pointer !important;
    transition: all 0.15s !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    text-transform: none !important;
    letter-spacing: normal !important;
    color: {METIN} !important;
  }}
  [data-testid="stSidebar"] .stRadio label:hover {{
    background: {CARD} !important;
  }}
  [data-testid="stSidebar"] .stRadio label[data-checked="true"],
  [data-testid="stSidebar"] .stRadio label:has(input:checked) {{
    background: {CARD} !important;
    color: {ALTIN} !important;
    font-weight: 600 !important;
    border-left: 3px solid {ALTIN} !important;
  }}

  div[data-testid="metric-container"] {{
    background: {MAIN_CARD};
    border: 1px solid {MAIN_BORDER};
    border-radius: 12px;
    padding: 16px 20px;
    transition: box-shadow 0.2s;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  }}
  div[data-testid="metric-container"]:hover {{
    box-shadow: 0 4px 16px rgba(31,78,121,0.12);
  }}
  div[data-testid="metric-container"] label,
  div[data-testid="metric-container"] label p,
  div[data-testid="metric-container"] label span,
  div[data-testid="metric-container"] label div,
  div[data-testid="metric-container"] [data-testid="stMetricLabel"],
  div[data-testid="metric-container"] [data-testid="stMetricLabel"] p,
  div[data-testid="metric-container"] [data-testid="stMetricLabel"] span,
  div[data-testid="metric-container"] [data-testid="stMetricLabel"] div,
  div[data-testid="metric-container"] [data-testid="stMetricLabel"] * {{
    color: {MAIN_BASLIK} !important;
    font-size: 12px !important;
    font-weight: 700 !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
    opacity: 1 !important;
  }}
  div[data-testid="stMetricValue"],
  div[data-testid="stMetricValue"] div,
  div[data-testid="stMetricValue"] * {{
    color: {MAIN_BASLIK} !important;
    font-size: 24px !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em !important;
    opacity: 1 !important;
  }}

  .main .stSelectbox > div > div {{
    background: {MAIN_CARD} !important;
    border: 1px solid {MAIN_BORDER} !important;
    border-radius: 8px !important;
    color: {MAIN_METIN} !important;
  }}
  .main .stMultiSelect > div > div {{
    background: {MAIN_CARD} !important;
    border: 1px solid {MAIN_BORDER} !important;
    border-radius: 8px !important;
  }}
  .main .stSelectbox label, .main .stMultiSelect label, .main .stSlider label {{
    color: {MAIN_SOLUK} !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
  }}

  [data-testid="stSidebar"] .stSelectbox > div > div {{
    background: {CARD} !important;
    border: 1px solid {GRID_RENK} !important;
    border-radius: 8px !important;
    color: {METIN} !important;
  }}
  [data-testid="stSidebar"] .stMultiSelect > div > div {{
    background: {CARD} !important;
    border: 1px solid {GRID_RENK} !important;
    border-radius: 8px !important;
  }}
  [data-testid="stSidebar"] .stSelectbox label,
  [data-testid="stSidebar"] .stMultiSelect label {{
    color: {METIN_SOLUK} !important;
    font-size: 11px !important;
    font-weight: 600 !important;
  }}

  [data-testid="stSidebar"] .stButton > button {{
    background: {ALTIN} !important;
    color: #0F1923 !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    padding: 8px 16px !important;
    transition: all 0.2s !important;
  }}
  .main .stButton > button {{
    background: {MAIN_BASLIK} !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    padding: 8px 16px !important;
    transition: all 0.2s !important;
  }}
  .stButton > button:hover {{
    opacity: 0.88 !important;
    transform: translateY(-1px) !important;
  }}

  .stDataFrame {{ border-radius: 12px; overflow: hidden; border: 1px solid {MAIN_BORDER}; }}
  iframe {{ border-radius: 12px; }}

  .main hr {{ border-color: {MAIN_GRID}; opacity: 0.7; }}
  [data-testid="stSidebar"] hr {{ border-color: {GRID_RENK}; opacity: 0.5; }}

  .stRadio > div {{ gap: 8px; }}
  .stRadio [data-testid="stMarkdownContainer"] p {{ font-size: 13px !important; }}

  .stSuccess {{ border-radius: 8px; border-left: 3px solid {YESIL}; }}
  .stWarning {{ border-radius: 8px; }}

  ::-webkit-scrollbar {{ width: 5px; height: 5px; }}
  ::-webkit-scrollbar-track {{ background: {MAIN_BG}; }}
  ::-webkit-scrollbar-thumb {{ background: {MAIN_BORDER}; border-radius: 3px; }}
  [data-testid="stSidebar"] ::-webkit-scrollbar-track {{ background: {SURFACE}; }}
  [data-testid="stSidebar"] ::-webkit-scrollbar-thumb {{ background: {GRID_RENK}; }}

</style>
""", unsafe_allow_html=True)

def safe_float(x):
    try:
        if isinstance(x, str):
            x = x.strip()
            if not x:
                return np.nan
            import re as _re
            if _re.match(r"^\d{4}-\d{2}-\d{2}", x) or _re.match(r"^\d{2}\.\d{2}\.\d{4}", x):
                return np.nan
            is_pct = x.endswith("%")
            x2 = x.replace("%", "").replace(".", "").replace(",", ".").strip()
            v = float(x2)
        else:
            v = float(x)
        return v if np.isfinite(v) else np.nan
    except:
        return np.nan

def gc_connect():
    scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    # 1) Streamlit Cloud (secrets.toml)
    try:
        if "gcp_service_account" in st.secrets:
            creds = Credentials.from_service_account_info(
                dict(st.secrets["gcp_service_account"]), scopes=scopes)
            return gspread.authorize(creds)
    except Exception:
        pass
    # 2) Lokal (credentials.json)
    creds_path = os.path.expandvars(CREDENTIALS_PATH)
    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    return gspread.authorize(creds)

def read_ws(sh, sayfa_adi):
    try:
        ws = sh.worksheet(sayfa_adi)
        raw = ws.get_all_values(value_render_option="FORMATTED_VALUE")
        if len(raw) < 2:
            return pd.DataFrame()
        cols_raw = raw[0]
        data = raw[1:]
        seen = {}
        cols = []
        for c in cols_raw:
            c = str(c).strip()
            if c in seen:
                seen[c] += 1
                cols.append(f"{c}_{seen[c]}")
            else:
                seen[c] = 0
                cols.append(c)
        df_raw = pd.DataFrame(data, columns=cols)
        df_raw.rename(columns={df_raw.columns[0]: "Hisse"}, inplace=True)
        df_raw = df_raw[df_raw["Hisse"].astype(str).str.strip().str.len() > 1].copy()

        pct_cols = set()
        for col in df_raw.columns[1:]:
            vals = df_raw[col].astype(str)
            pct_count = vals.str.strip().str.endswith("%").sum()
            if pct_count > len(vals) * 0.3:
                pct_cols.add(col)

        _STR_ANAHTAR = ("tarih", "date", "not", "açıklama", "aciklama", "kategori",
                        "tip", "tür", "tur", "durum", "status", "label", "etiket")

        df = df_raw.copy()
        for col in df.columns[1:]:
            col_lower = col.lower().strip()

            if any(k in col_lower for k in _STR_ANAHTAR):
                df[col] = df_raw[col].apply(
                    lambda x: str(x).strip() if (x is not None and str(x).strip() not in ("", "None", "nan", "NaT")) else None
                )
                continue

            converted = df_raw[col].apply(safe_float)
            orig_nonempty = df_raw[col].astype(str).str.strip().replace("", pd.NA).dropna()

            if converted.isna().all() and len(orig_nonempty) > 0:
                df[col] = df_raw[col].apply(
                    lambda x: str(x).strip() if (x is not None and str(x).strip() not in ("", "None", "nan", "NaT")) else None
                )
            else:
                mixed = converted.copy().astype(object)
                for idx in converted[converted.isna()].index:
                    orig_val = str(df_raw.loc[idx, col]).strip()
                    if orig_val and orig_val.lower() not in ("", "nan", "none", "nat"):
                        mixed[idx] = orig_val
                df[col] = mixed

        df.attrs["pct_cols"] = pct_cols
        return df
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=900, show_spinner=False)
def load_all_data():
    gc = gc_connect()
    try:
        sid = st.secrets.get("sheets", {}).get("sheet_id", SHEET_ID)
    except Exception:
        sid = SHEET_ID
    sh = gc.open_by_key(sid)

    sektor_map = {}
    try:
        ws = sh.worksheet(AYAR_SAYFASI)
        raw = ws.get_all_values(value_render_option="FORMATTED_VALUE")
        adf = pd.DataFrame(raw[1:], columns=raw[0])
        s_col = next((c for c in adf.columns if "sektör" in c.lower() or "sektor" in c.lower()), None)
        h_col = next((c for c in adf.columns if "şirket" in c.lower() or "sirket" in c.lower()), None)
        if s_col and h_col:
            sektor_map = dict(zip(adf[h_col].str.strip(), adf[s_col].str.strip()))
    except:
        pass

    ham_data = {}
    snap_data = {}
    for donem, ham_s, snap_s in DONEM_SAYFALARI:
        df_h = read_ws(sh, ham_s)
        if not df_h.empty:
            ham_data[donem] = df_h
        df_s = read_ws(sh, snap_s)
        if not df_s.empty:
            snap_data[donem] = df_s

    puan_data = read_ws(sh, PUAN_SAYFASI)
    son_data  = read_ws(sh, "son")
    ayar_data = read_ws(sh, AYAR_SAYFASI)

    cikti_data = {}
    for sayfa in CIKTI_SAYFALARI:
        df_c = read_ws(sh, sayfa)
        if not df_c.empty:
            cikti_data[sayfa] = df_c

    ya_data = read_ws(sh, "YA")

    return ham_data, snap_data, sektor_map, puan_data, son_data, cikti_data, ayar_data, ya_data

def _ayarlar_dict():
    return {
        "tema_adi":     st.session_state.get("tema_adi", "2 Koyu Lacivert"),
        "bg_custom":    st.session_state.get("bg_custom"),
        "surf_custom":  st.session_state.get("surf_custom"),
        "altin_custom": st.session_state.get("altin_custom"),
        "pozitif_renk": st.session_state.get("pozitif_renk", "#10B981"),
        "negatif_renk": st.session_state.get("negatif_renk", "#EF4444"),
        "bar_tek_renk": st.session_state.get("bar_tek_renk"),
        "kpi_cols":       st.session_state.get("kpi_cols", []),
        "ozet_grafikler": st.session_state.get("m_det_ozet", []),
        "puan_m6":        st.session_state.get("m6", []),
        "puan_sr6":       st.session_state.get("sr6", ""),
    }

# ─── SIDEBAR ───
with st.sidebar:
    st.markdown(f"""
    <div style='padding:4px 0 12px 0;border-bottom:1px solid {GRID_RENK};margin-bottom:16px;'>
      <div style='font-size:13px;color:{METIN_SOLUK};font-weight:500;'>⚙️ Ayarlar</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("↺  Veriyi Yenile", use_container_width=True):
        st.cache_data.clear()
        load_all_data.clear()
        st.rerun()
    st.markdown(f"<p style='color:{METIN_SOLUK};font-size:10px;margin-top:6px;text-align:center;'>Sheets değişince yenile</p>", unsafe_allow_html=True)

    st.divider()
    st.markdown(f"<p style='color:{ALTIN};font-weight:bold;font-size:13px'>📸 Ekran Görüntüsü</p>", unsafe_allow_html=True)
    if st.button("📸  Sayfayı PNG İndir", use_container_width=True, key="foto_indir"):
        st.session_state["_screenshot_ts"] = time.time()
        st.session_state["_screenshot_tetik"] = True

    if st.session_state.get("_screenshot_tetik"):
        st.session_state["_screenshot_tetik"] = False
        components.html(f"""
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
        <script>
        (function() {{
            function bekleVeCek() {{
                if (typeof window.parent.html2canvas === 'undefined') {{
                    var s = window.parent.document.createElement('script');
                    s.src = 'https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js';
                    s.onload = function() {{ ekranGoruntusuAl(); }};
                    window.parent.document.head.appendChild(s);
                }} else {{
                    ekranGoruntusuAl();
                }}
            }}

            function ekranGoruntusuAl() {{
                var parentDoc = window.parent.document;
                var overlay = parentDoc.createElement('div');
                overlay.id = 'snap-ss-overlay';
                overlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;' +
                    'background:rgba(0,0,0,0.6);z-index:999999;display:flex;align-items:center;' +
                    'justify-content:center;';
                overlay.innerHTML = '<div style="background:{MAIN_SURFACE};color:{MAIN_BASLIK};padding:30px 50px;' +
                    'border-radius:16px;font-family:Inter,sans-serif;font-size:18px;font-weight:600;' +
                    'box-shadow:0 8px 32px rgba(0,0,0,0.3);">' +
                    '📸 Ekran görüntüsü alınıyor...</div>';
                parentDoc.body.appendChild(overlay);

                var sidebar = parentDoc.querySelector('[data-testid="stSidebar"]');
                var sidebarBtn = parentDoc.querySelector('[data-testid="stSidebarCollapsedControl"]');
                if (sidebar) sidebar.style.display = 'none';
                if (sidebarBtn) sidebarBtn.style.display = 'none';

                var mainEl = parentDoc.querySelector('[data-testid="stMain"]')
                             || parentDoc.querySelector('.main .block-container')
                             || parentDoc.querySelector('.main');

                if (!mainEl) {{
                    alert('Sayfa içeriği bulunamadı!');
                    if (sidebar) sidebar.style.display = '';
                    if (sidebarBtn) sidebarBtn.style.display = '';
                    overlay.remove();
                    return;
                }}

                window.parent.html2canvas(mainEl, {{
                    backgroundColor: '{MAIN_BG}',
                    scale: 2,
                    useCORS: true,
                    logging: false,
                    allowTaint: true,
                    scrollX: 0,
                    scrollY: -window.parent.scrollY,
                    windowWidth: mainEl.scrollWidth,
                    windowHeight: mainEl.scrollHeight,
                    ignoreElements: function(el) {{
                        if (el.getAttribute && el.getAttribute('data-testid') === 'stSidebar') return true;
                        if (el.getAttribute && el.getAttribute('data-testid') === 'stSidebarCollapsedControl') return true;
                        return false;
                    }}
                }}).then(function(canvas) {{
                    var tarih = new Date().toISOString().slice(0,10);
                    var saat = new Date().toTimeString().slice(0,5).replace(':','');
                    var hisse = '';
                    var selects = parentDoc.querySelectorAll('[data-testid="stSelectbox"]');
                    if (selects.length > 0) {{
                        var secili = selects[0].querySelector('[data-testid="stMarkdownContainer"] p');
                        if (!secili) secili = selects[0].querySelector('div[class*="value"]');
                        if (secili) hisse = secili.textContent.trim();
                    }}
                    var dosyaAdi = 'SNAP_' + (hisse ? hisse + '_' : '') + tarih + '_' + saat + '.png';

                    var link = parentDoc.createElement('a');
                    link.download = dosyaAdi;
                    link.href = canvas.toDataURL('image/png', 0.95);
                    link.click();

                    setTimeout(function() {{ overlay.remove(); }}, 500);
                    if (sidebar) sidebar.style.display = '';
                    if (sidebarBtn) sidebarBtn.style.display = '';
                }}).catch(function(err) {{
                    console.error('Screenshot hatası:', err);
                    alert('Ekran görüntüsü alınamadı: ' + err.message);
                    overlay.remove();
                    if (sidebar) sidebar.style.display = '';
                    if (sidebarBtn) sidebarBtn.style.display = '';
                }});
            }}
            setTimeout(bekleVeCek, 500);
        }})();
        </script>
        """, height=0)

    st.divider()
    st.markdown(f"<p style='color:{ALTIN};font-weight:bold;font-size:13px'>📂 Sayfalar</p>", unsafe_allow_html=True)

    SAYFA_LISTESI = [
        "📋 Özet",
        "📊 Metrik Tablosu",
        "🏭 Sektör Kıyası",
        "🔍 Fırsat Tarama",
        "📈 Çeyreklik Trend",
        "🏆 Puan Tablosu",
        "🧮 Formül Hesaplayıcı",
        "🌍 Yabancı Akım",
    ]
    aktif_sayfa = st.radio("Sayfa:", SAYFA_LISTESI, label_visibility="collapsed", key="nav_sayfa")

sidebar_kpi_placeholder = st.sidebar.empty()
sidebar_ozet_placeholder = st.sidebar.empty()

# ─── VERİ ───
with st.spinner("Google Sheets'ten yükleniyor..."):
    try:
        ham_data, snap_data, sektor_map, puan_data, son_data, cikti_data, ayar_data, ya_data = load_all_data()
    except FileNotFoundError:
        st.error("Credentials bulunamadı. Streamlit secrets veya credentials.json gerekli.")
        st.stop()
    except Exception as e:
        st.error(f"Bağlantı hatası: {e}")
        st.stop()

if not ham_data and not snap_data:
    st.error("Hiçbir sayfadan veri okunamadı.")
    st.stop()

son_donem = next(iter(ham_data)) if ham_data else next(iter(snap_data))
tum_hisseler = sorted(set(h for df in {**ham_data,**snap_data}.values() for h in df["Hisse"].dropna().unique() if str(h).strip()))

merged_data = {}
tum_donemler = sorted(set(list(ham_data.keys()) + list(snap_data.keys())), reverse=True)
for _d in tum_donemler:
    _dfs = []
    if _d in ham_data and not ham_data[_d].empty:
        _dfs.append(ham_data[_d])
    if _d in snap_data and not snap_data[_d].empty:
        _snap_extra = snap_data[_d][[c for c in snap_data[_d].columns
                                     if c not in (ham_data[_d].columns.tolist() if _d in ham_data else []) or c == "Hisse"]]
        _dfs.append(_snap_extra)
    if len(_dfs) == 2:
        merged_data[_d] = _dfs[0].merge(_dfs[1], on="Hisse", how="outer")
    elif len(_dfs) == 1:
        merged_data[_d] = _dfs[0].copy()

with sidebar_kpi_placeholder.container():
    st.divider()
    st.markdown(f"<p style='color:{ALTIN};font-weight:bold;font-size:13px'>📌 KPI Kartları</p>", unsafe_allow_html=True)

    _tum_kpi_cols = sorted(set(
        ([c for c in puan_data.columns if c not in ["Hisse","Sektör"]] if not puan_data.empty else []) +
        ([c for c in son_data.columns  if c not in ["Hisse","Sektör"]] if not son_data.empty  else []) +
        [c for df in merged_data.values() for c in df.columns if c not in ["Hisse","Sektör"]]
    ))

    with st.expander("🔍 Tüm Sütun Adları"):
        st.markdown(f"<p style='color:{METIN_SOLUK};font-size:10px'>{', '.join(_tum_kpi_cols[:40])}</p>", unsafe_allow_html=True)

    _kpi_sabit_istek = [
        "SNAP",
        "NAKİT",
        "EFK",
        "PDDD",
        "NET BORÇ / FAVÖK",
        "FD/FAVÖK",
        "BİLANÇO SONRASI",
    ]

    def _kpi_norm(s):
        s = normalize_col(s)
        s = s.replace(" ", "")
        s = s.replace("／", "/")
        return s

    _norm2col = {}
    for _c in _tum_kpi_cols:
        _norm2col[_kpi_norm(_c)] = _c

    _alternatifler = {
        "NAKİT": ["NAKIT"],
        "PDDD": ["PD/DD", "PD / DD", "PD-DD", "PD DD"],
        "NET BORÇ / FAVÖK": ["NET BORÇ/FAVÖK", "NET BORC/FAVOK", "NETBORÇ/FAVÖK", "NETBORC/FAVOK"],
        "FD/FAVÖK": ["FD / FAVÖK", "FD/FAVOK", "FD / FAVOK"],
        "BİLANÇO SONRASI": ["BILANCO SONRASI", "BİLANÇO PD", "BILANCO PD", "BİLANÇO PDDD", "BILANCO PDDD"],
    }

    _secili_sabit = []
    _bulunamayan = []

    for _want in _kpi_sabit_istek:
        _found = _norm2col.get(_kpi_norm(_want))

        if not _found:
            for _alt in _alternatifler.get(_want, []):
                _found = _norm2col.get(_kpi_norm(_alt))
                if _found:
                    break

        if _found:
            _secili_sabit.append(_found)
        else:
            _bulunamayan.append(_want)

    # Tekrarları kaldır (sıra korunur)
    _secili_sabit = list(dict.fromkeys(_secili_sabit))

    if _bulunamayan:
        st.warning("KPI sabitlemede bulunamayan sütun(lar): " + ", ".join(_bulunamayan))

    # Widget state'i sabit listeye çek (kullanıcı değiştirirse bile geri sabitlenir)
    st.session_state["kpi_cols"] = _secili_sabit

    # Sidebar'da sadece görüntüle (değiştirmeye kapalı)
    st.multiselect(
        "KPI Kartları (sabit):",
        _tum_kpi_cols,
        default=_secili_sabit,
        key="kpi_cols",
        label_visibility="collapsed",
        disabled=True
    )

    # Kalıcı kaydet (dashboard tekrar açıldığında da aynı gelsin)
    if _secili_sabit != st.session_state.get("kpi_cols_son"):
        st.session_state.kpi_cols_son = _secili_sabit
        ayarlari_kaydet({**ayarlari_yukle(), "kpi_cols": _secili_sabit})

    # Uygulamada kullanılacak seçim (kartların sırası da buna göre)
    sec_kpi_snap = _secili_sabit
    sec_kpi_ham = sec_kpi_snap

with sidebar_ozet_placeholder.container():
    st.divider()
    st.markdown(f"<p style='color:{ALTIN};font-weight:bold;font-size:13px'>📋 Özet Kontrolleri</p>", unsafe_allow_html=True)

    sec_hisse = st.selectbox("Hisse:", sorted(set(h for df in {**ham_data,**snap_data}.values() for h in df["Hisse"].dropna().unique() if str(h).strip())), key="ozet_hisse")

    _dd_ozet = merged_data
    tum_m_det = sorted(set(
        c for df in _dd_ozet.values()
        for c in df.columns
        if c not in ["Hisse", "Sektör"]
        and not pd.to_numeric(
            df[df["Hisse"] == sec_hisse][c] if sec_hisse in df["Hisse"].values else pd.Series(dtype=float),
            errors="coerce").isna().all()
    ))
    tum_m_det_genisletilmis = sorted(set(
        tum_m_det +
        ([c for c in puan_data.columns if c not in ["Hisse","Sektör"]] if not puan_data.empty else []) +
        ([c for c in son_data.columns  if c not in ["Hisse","Sektör"]] if not son_data.empty  else [])
    ))
    SABIT_METRIKLER = ["SATIŞLAR Y","BRÜT KAR Y","EFK Y","NAKİT Y","Net Borç","ÖZKAYNAKLAR"]
    _m_det_kayit = st.session_state.get("ozet_grafikler_kayit", [])
    _m_det_kayit = [m for m in _m_det_kayit if m in tum_m_det_genisletilmis]
    if not _m_det_kayit:
        _m_det_kayit = [m for m in SABIT_METRIKLER if m in tum_m_det_genisletilmis]
    sec_m_det = st.multiselect(
        "Grafikler:", tum_m_det_genisletilmis,
        default=_m_det_kayit,
        key="m_det_ozet"
    )
    if sec_m_det != st.session_state.get("ozet_grafikler_son"):
        st.session_state.ozet_grafikler_son = sec_m_det
        st.session_state.ozet_grafikler_kayit = sec_m_det
        _kayit_simdiki = ayarlari_yukle()
        _kayit_simdiki["ozet_grafikler"] = sec_m_det
        ayarlari_kaydet(_kayit_simdiki)
    n_donem_det = st.selectbox("Son kaç çeyrek:", [4, 5, 6, 8], index=1, key="nd1_det")

if aktif_sayfa != "🏆 Puan Tablosu":
    st.markdown(snap_amblem_html(), unsafe_allow_html=True)

def kaynak_coz(sec):
    if sec in ham_data: return ham_data[sec].copy()
    elif sec in snap_data: return snap_data[sec].copy()
    elif sec == "SNAP SON": return puan_data.copy()
    elif sec == "son": return son_data.copy()
    elif sec in cikti_data: return cikti_data[sec].copy()
    return pd.DataFrame()

def kaynak_listesi_olustur():
    ham_liste  = [f"Ham: {d}" for d in ham_data.keys()]
    snap_liste = [f"SNAP: {d}" for d in snap_data.keys()]
    sabit = ["SNAP SON", "son"]
    cikti = list(cikti_data.keys())
    return ham_liste + snap_liste + sabit + cikti

def kaynak_coz_etiketli(sec):
    if sec.startswith("Ham: "):
        return ham_data.get(sec[5:], pd.DataFrame()).copy()
    elif sec.startswith("SNAP: "):
        return snap_data.get(sec[6:], pd.DataFrame()).copy()
    elif sec == "SNAP SON": return puan_data.copy()
    elif sec == "son": return son_data.copy()
    elif sec in cikti_data: return cikti_data[sec].copy()
    return pd.DataFrame()

def ham_snap_merge(sec):
    df_base = kaynak_coz_etiketli(sec)
    if df_base.empty: return df_base

    if sec.startswith("Ham: "):
        donem = sec[5:]
        df_snap_donem = snap_data.get(donem, pd.DataFrame())
        if not df_snap_donem.empty:
            extra_cols = [c for c in df_snap_donem.columns if c not in df_base.columns and c not in ["Hisse","Sektör"]]
            df_base = df_base.merge(df_snap_donem[["Hisse"]+extra_cols], on="Hisse", how="left")

    if not puan_data.empty:
        snap_son_extra = [c for c in puan_data.columns if c not in df_base.columns and c not in ["Hisse","Sektör"]]
        if snap_son_extra:
            df_base = df_base.merge(puan_data[["Hisse"]+snap_son_extra], on="Hisse", how="left")
    return df_base

# ══ SAYFA 1 — HİSSE ANALİZİ ══════════════════
if aktif_sayfa == "📋 Özet":
    sektoru_ozet = sektor_map.get(sec_hisse, "—")
    dd = merged_data
    donems = list(dd.keys())

    sec_kpi = sec_kpi_snap
    _kpi_row = {}
    _pct_cols_kpi = set()
    if sec_kpi:
        for _src_df, _src_name in [(puan_data, "puan"), (son_data, "son")]:
            if not _src_df.empty and sec_hisse in _src_df["Hisse"].values:
                _kpi_row.update(_src_df[_src_df["Hisse"] == sec_hisse].iloc[0].to_dict())
                _pct_cols_kpi |= _src_df.attrs.get("pct_cols", set())
        for _d in list(merged_data.keys())[:1]:
            _df_son = merged_data[_d]
            if sec_hisse in _df_son["Hisse"].values:
                _kpi_row.update({k: v for k, v in _df_son[_df_son["Hisse"] == sec_hisse].iloc[0].to_dict().items()
                                  if k not in _kpi_row or _kpi_row.get(k) in [None, "", np.nan]})

    def _kpi_card_html(col, row, pct_cols):
        v = row.get(col)
        _PCT_ANAHTAR = ["MARJ","GETİRİ","GETIRI","BÜYÜME","BUYUME","ORAN","YÜZDE","YUZDE","ROTE","ROIC","ROE","ROA"]
        try:
            fv = float(v)
            if v is None or (isinstance(fv, float) and __import__("math").isnan(fv)):
                g = "—"
            elif col in pct_cols or any(k in col.upper() for k in _PCT_ANAHTAR):
                g = tr_fmt(fv, 2) + " %"
            else:
                g = tr_kpi(fv)
        except:
            g = str(v) if v else "—"
        return (
            '<div style="background:#FFFFFF;border:1px solid #CBD5E1;border-radius:12px;'
            'padding:12px 18px;box-shadow:0 1px 3px rgba(0,0,0,0.06);min-height:62px;'
            'display:flex;align-items:center;gap:8px;">'
            '<span style="color:#1F4E79;font-size:14px;font-weight:700;'
            'letter-spacing:0.02em;text-transform:uppercase;line-height:1.3;flex:1;">'
            f'{col}</span>'
            '<span style="color:#0A3D6E;font-size:18px;font-weight:800;'
            'letter-spacing:-0.02em;white-space:nowrap;flex:1;text-align:center;">'
            f'{g}</span></div>'
        )

    header_kpi_html = ""
    if _kpi_row and sec_kpi:
        for col in sec_kpi[:3]:
            header_kpi_html += _kpi_card_html(col, _kpi_row, _pct_cols_kpi)

    # ── Sağ boşlukta gösterilecek: Son PD (mr) ──
    son_pd_mr = "—"
    if _kpi_row:
        def _dict_find_key(d, wanted):
            nw = normalize_col(wanted)
            for kk in d.keys():
                if normalize_col(kk) == nw:
                    return kk
            return None

        pd_key = (
            _dict_find_key(_kpi_row, "SON PD")
            or _dict_find_key(_kpi_row, "Son PD")
            or _dict_find_key(_kpi_row, "PİYASA DEĞERİ")
            or _dict_find_key(_kpi_row, "PIYASA DEGERI")
            or _dict_find_key(_kpi_row, "PD")
        )

        if pd_key:
            pd_fv = safe_float(_kpi_row.get(pd_key))
            if isinstance(pd_fv, (int, float)) and np.isfinite(pd_fv):
                son_pd_mr = tr_fmt(pd_fv / 1_000_000_000, 1) + " mr"

    st.markdown(f"""
    <div style="display:grid;grid-template-columns:1.4fr 1fr 1fr 1fr;
                gap:10px;margin-bottom:10px;align-items:stretch;">
      <div style="background:{MAIN_SURFACE};border:1px solid {MAIN_BORDER};border-radius:12px;
                  padding:14px 22px;min-height:62px;
                  display:flex;flex-direction:row;align-items:center;justify-content:flex-start;gap:14px;flex-wrap:wrap;">
        <span style="font-size:24px;font-weight:800;color:{MAIN_BASLIK};letter-spacing:-0.02em;line-height:1;">{sec_hisse}</span>
        <span style="font-size:12px;color:{MAIN_SOLUK};background:{MAIN_BG};
                     padding:3px 12px;border-radius:20px;border:1px solid {MAIN_BORDER};
                     word-break:break-word;white-space:normal;line-height:1.4;">{sektoru_ozet}</span>
        <span style="margin-left:auto;font-size:18px;font-weight:800;color:{MAIN_BASLIK};
                     letter-spacing:-0.02em;white-space:nowrap;">{son_pd_mr}</span>
      </div>
      {header_kpi_html}
    </div>
    """, unsafe_allow_html=True)

    if _kpi_row and sec_kpi and len(sec_kpi) > 3:
        kalan_cards = ""
        for col in sec_kpi[3:12]:
            kalan_cards += _kpi_card_html(col, _kpi_row, _pct_cols_kpi)
        st.markdown(
            '<div style="display:grid;grid-template-columns:repeat(4,1fr);'
            'gap:10px;margin-bottom:18px;">' + kalan_cards + '</div>',
            unsafe_allow_html=True
        )

    st.markdown(f"<hr style='border-color:{MAIN_GRID};margin:20px 0 14px 0;'>", unsafe_allow_html=True)
    st.markdown(f"<p style='color:{MAIN_BASLIK};font-weight:700;font-size:15px;margin-bottom:12px;'>📊 Çeyreklik Detay <span style='font-size:12px;font-weight:400;color:{MAIN_SOLUK};'>(Mn TL)</span></p>", unsafe_allow_html=True)

    if sec_m_det:
        donem_sirasi_det = [d for d, _, _ in reversed(DONEM_SAYFALARI)]
        secili_donemler_det = []
        metrik_verileri_det = {m: [] for m in sec_m_det}

        for donem in donem_sirasi_det:
            if donem not in dd: continue
            df_d = dd[donem]
            if sec_hisse not in df_d["Hisse"].values: continue
            satir = df_d[df_d["Hisse"] == sec_hisse].iloc[0]
            for m in sec_m_det:
                v = pd.to_numeric(satir.get(m, np.nan), errors="coerce") if m in df_d.columns else np.nan
                metrik_verileri_det[m].append(v)
            secili_donemler_det.append(donem)

        secili_donemler_det = secili_donemler_det[-n_donem_det:]
        for m in sec_m_det:
            metrik_verileri_det[m] = metrik_verileri_det[m][-n_donem_det:]

        if secili_donemler_det:
            metrik_listesi_det = [m for m in sec_m_det
                                  if any(v is not None and not np.isnan(v) for v in metrik_verileri_det[m])]
            satirlar_det = [metrik_listesi_det[i:i+4] for i in range(0, len(metrik_listesi_det), 4)]

            for idx_satir, satir_det in enumerate(satirlar_det):
                if idx_satir > 0: st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                cols_det = st.columns(4)
                for j, metrik in enumerate(satir_det):
                    with cols_det[j]:
                        degerler = metrik_verileri_det[metrik]
                        _ters_renk = "net borç" in metrik.lower() or "net borc" in metrik.lower()
                        renkler = []
                        for v in degerler:
                            if v is None or np.isnan(v): renkler.append(METIN_ZAYIF)
                            elif v >= 0: renkler.append(st.session_state.bar_tek_renk or (KIRMIZI if _ters_renk else YESIL))
                            else: renkler.append(st.session_state.bar_tek_renk or (YESIL if _ters_renk else KIRMIZI))

                        _PCT_K = ["MARJ","GETİRİ","GETIRI","BÜYÜME","BUYUME","ORAN","ROTE","ROIC","ROE","ROA","YÜZDE"]
                        _is_pct_metrik = any(k in metrik.upper() for k in _PCT_K)
                        if not _is_pct_metrik:
                            for _src in [puan_data, son_data] + list(merged_data.values())[:1]:
                                if not _src.empty and metrik in _src.attrs.get("pct_cols", set()):
                                    _is_pct_metrik = True
                                    break

                        def _fmt_bar(v):
                            if v is None or (isinstance(v, float) and np.isnan(v)): return "—"
                            if _is_pct_metrik: return tr_fmt(float(v), 2) + " %"
                            return fmt_mn(v)

                        fig_det = go.Figure()
                        fig_det.add_trace(go.Bar(
                            x=secili_donemler_det, y=degerler,
                            marker_color=renkler,
                            text=[_fmt_bar(v) for v in degerler],
                            textposition="outside",
                            textfont=dict(size=13, color=MAIN_BASLIK, family="Inter"),
                            name=metrik,
                        ))
                        trend_x = [secili_donemler_det[k] for k, v in enumerate(degerler) if v is not None and not np.isnan(v)]
                        trend_y = [v for v in degerler if v is not None and not np.isnan(v)]
                        if len(trend_y) >= 2:
                            fig_det.add_trace(go.Scatter(
                                x=trend_x, y=trend_y,
                                mode="lines+markers", line=dict(color=ALTIN, width=2, dash="dot"),
                                marker=dict(size=6, color=ALTIN), showlegend=False,
                            ))
                        fig_det.add_hline(y=0, line_dash="dot", line_color=MAIN_GRID, line_width=1)

                        _vals_clean = [v for v in degerler if v is not None and not np.isnan(v)]
                        if _vals_clean:
                            _ymax_raw = max(_vals_clean); _ymin_raw = min(_vals_clean)
                            _span = max(abs(_ymax_raw), abs(_ymin_raw), 1); _pad = _span * 0.18
                            _ymax = _ymax_raw + _pad if _ymax_raw >= 0 else _ymax_raw + abs(_ymax_raw) * 0.05
                            _ymin = _ymin_raw - _pad if _ymin_raw < 0 else min(0, _ymin_raw - _span * 0.05)
                            _yrange = [_ymin, _ymax]
                        else: _yrange = None

                        fig_det.update_layout(
                            height=320, showlegend=False, margin=dict(l=8, r=8, t=42, b=8),
                            title=dict(text=f"<b>{metrik}</b>", font=dict(color=MAIN_BASLIK, size=12), x=0),
                            paper_bgcolor=MAIN_BG, plot_bgcolor=MAIN_SURFACE,
                            font=dict(color=MAIN_BASLIK, size=11),
                            xaxis=dict(showgrid=False, color=MAIN_BASLIK, tickangle=-30,
                                       tickfont=dict(size=10, color=MAIN_BASLIK),
                                       categoryorder="array", categoryarray=secili_donemler_det),
                            yaxis=dict(gridcolor=MAIN_GRID, color=MAIN_BASLIK, showticklabels=False, range=_yrange),
                            bargap=0.30,
                        )
                        st.plotly_chart(fig_det, use_container_width=True)

# ══ SAYFA 2 — METRİK TABLOSU ══════════════════
if aktif_sayfa == "📊 Metrik Tablosu":
    st.markdown("### 📋 Dönem & Metrik Seç → Tablo Al")
    c1,c2,c3 = st.columns(3)
    with c1:
        donem_listesi = kaynak_listesi_olustur()
        sec_d2 = st.selectbox("Dönem/Kaynak:", donem_listesi, key="d2")

    data2 = kaynak_coz_etiketli(sec_d2)

    if not data2.empty:
        data2["Sektör"] = data2["Hisse"].map(sektor_map).fillna("Diğer")
        num_c2 = [c for c in data2.columns if c not in ["Hisse","Sektör"]]
        with c2:
            sec_m2 = st.multiselect("Metrikler:", num_c2, default=num_c2[:5], key="m2")
        with c3:
            sek_list2 = ["Tümü"]+sorted(data2["Sektör"].unique())
            sec_s2 = st.selectbox("Sektör:", sek_list2, key="s2")

        if sec_m2:
            tablo2 = data2[["Hisse","Sektör"]+sec_m2].copy()
            if sec_s2!="Tümü":
                tablo2 = tablo2[tablo2["Sektör"]==sec_s2]

            c_sira,c_yon = st.columns([2,1])
            with c_sira: sira2 = st.selectbox("Sırala:", sec_m2, key="sr2")
            with c_yon: yon2 = st.radio("Yön:", ["↑ Küçük→Büyük","↓ Büyük→Küçük"], horizontal=True, key="y2")

            for c in sec_m2:
                col_data = tablo2[c]
                if isinstance(col_data, pd.DataFrame): col_data = col_data.iloc[:, 0]
                converted = pd.to_numeric(col_data, errors="coerce")
                if not converted.isna().all(): tablo2[c] = converted.round(4)

            tablo2 = tablo2.sort_values(sira2, ascending=("↑" in yon2)).reset_index(drop=True)

            st.markdown(f"**{len(tablo2)} hisse** | {sec_d2}")
            df_goster(tablo2, height=550)

            if len(tablo2) <= 80:
                col_bar = sec_m2[0]
                fig2 = go.Figure(go.Bar(
                    x=tablo2["Hisse"], y=tablo2[col_bar],
                    marker_color=[st.session_state.bar_tek_renk or (YESIL if (pd.notna(v) and float(v)>=0) else KIRMIZI) for v in tablo2[col_bar].tolist()],
                    text=[tr_fmt(v) if v else "" for v in tablo2[col_bar]], textposition="outside"
                ))
                fig2.update_layout(height=380,showlegend=False,
                    title=dict(text=f"<b>{col_bar}</b> — {sec_d2}",font=dict(color=MAIN_BASLIK)),
                    xaxis=dict(showgrid=False,color=MAIN_METIN,tickangle=-45,tickfont=dict(size=12,color=MAIN_BASLIK)),
                    yaxis=dict(gridcolor=MAIN_GRID,color=MAIN_SOLUK),
                    paper_bgcolor=MAIN_BG,plot_bgcolor=MAIN_SURFACE,font=dict(color=MAIN_METIN))
                st.plotly_chart(fig2,use_container_width=True)

# ══ SAYFA 3 — SEKTÖR KIYASI ══════════════════
if aktif_sayfa == "🏭 Sektör Kıyası":
    st.markdown("### 🏭 Sektörel Kıyas")

    # Kontrolleri sayfanın ALTINA alacağız.
    # Streamlit rerun mantığında, widget değerleri rerun başında session_state'e yazıldığı için
    # grafikleri üstte üretip kontrolleri altta göstermek sorunsuz çalışır.

    kaynak_listesi3 = kaynak_listesi_olustur()
    if "d3" not in st.session_state or st.session_state.get("d3") not in kaynak_listesi3:
        st.session_state["d3"] = kaynak_listesi3[0] if kaynak_listesi3 else ""

    sec_d3 = st.session_state.get("d3", "")
    data3 = kaynak_coz_etiketli(sec_d3)

    if not data3.empty:
        data3["Sektör"] = data3["Hisse"].map(sektor_map).fillna("Diğer")
        num_c3 = [c for c in data3.columns if c not in ["Hisse","Sektör"]]

        if "m3" not in st.session_state or st.session_state.get("m3") not in num_c3:
            st.session_state["m3"] = num_c3[0] if num_c3 else ""

        sec_m3 = st.session_state.get("m3", "")

        sek3 = sorted(data3["Sektör"].unique())
        if "s3" not in st.session_state or not isinstance(st.session_state.get("s3"), list):
            st.session_state["s3"] = sek3
        else:
            # Eski kayıttan gelen sektör seçimi listesinde artık olmayanlar varsa temizle
            st.session_state["s3"] = [s for s in st.session_state.get("s3", []) if s in sek3] or sek3

        sec_s3 = st.session_state.get("s3", sek3)

        # ── Grafikler (üstte) ──
        if sec_m3:
            d3f = data3[data3["Sektör"].isin(sec_s3)].dropna(subset=[sec_m3])

            if d3f.empty:
                st.warning("Seçimlere göre gösterilecek veri kalmadı.")
            else:
                stats3 = d3f.groupby("Sektör")[sec_m3].median().sort_values()

                fig3a = go.Figure(go.Bar(
                    y=stats3.index, x=stats3.values, orientation="h",
                    marker_color=[st.session_state.bar_tek_renk or (YESIL if float(v)>=0 else KIRMIZI) for v in stats3.values.tolist()],
                    text=[tr_fmt(v) for v in stats3.values], textposition="outside"
                ))
                fig3a.add_vline(x=stats3.median(), line_dash="dash", line_color=ALTIN,
                    annotation_text=f"Medyan:{tr_fmt(stats3.median())}", annotation_font_color=ALTIN)
                fig3a.update_layout(height=max(350,len(stats3)*32), showlegend=False,
                    title=dict(text=f"<b>Sektör Medyan — {sec_m3}</b>",font=dict(color=MAIN_BASLIK)),
                    xaxis=dict(gridcolor=MAIN_GRID,color=MAIN_SOLUK), yaxis=dict(showgrid=False,color=MAIN_METIN),
                    paper_bgcolor=MAIN_BG,plot_bgcolor=MAIN_SURFACE,font=dict(color=MAIN_METIN))
                st.plotly_chart(fig3a, use_container_width=True)

                fig3b = px.box(d3f, x="Sektör", y=sec_m3, color="Sektör", hover_name="Hisse", points="all")
                fig3b.update_layout(height=420, showlegend=False,
                    title=dict(text=f"<b>Dağılım — {sec_m3}</b>",font=dict(color=MAIN_BASLIK)),
                    xaxis=dict(showgrid=False,color=MAIN_METIN,tickangle=-30,tickfont=dict(size=12,color=MAIN_BASLIK)),
                    yaxis=dict(gridcolor=MAIN_GRID,color=MAIN_SOLUK),
                    paper_bgcolor=MAIN_BG,plot_bgcolor=MAIN_SURFACE,font=dict(color=MAIN_METIN))
                st.plotly_chart(fig3b, use_container_width=True)

        # ── Kontroller (altta + lacivert yazı) ──
        st.markdown(f"""<div style="margin-top:18px;padding:14px 16px;background:{MAIN_SURFACE};
                        border:1px solid {MAIN_BORDER};border-radius:12px;">""", unsafe_allow_html=True)

        cc1, cc2 = st.columns(2)
        with cc1:
            st.markdown(f"<p style='color:{MAIN_SOLUK};font-size:11px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;margin:0 0 6px 0;'>DÖNEM / KAYNAK</p>", unsafe_allow_html=True)
            st.selectbox("", kaynak_listesi3, key="d3", label_visibility="collapsed")
        with cc2:
            st.markdown(f"<p style='color:{MAIN_SOLUK};font-size:11px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;margin:0 0 6px 0;'>METRİK</p>", unsafe_allow_html=True)
            st.selectbox("", num_c3, key="m3", label_visibility="collapsed")

        st.markdown(f"<p style='color:{MAIN_SOLUK};font-size:11px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;margin:12px 0 6px 0;'>SEKTÖR</p>", unsafe_allow_html=True)
        st.multiselect("", sek3, default=sek3, key="s3", label_visibility="collapsed")

        st.markdown("</div>", unsafe_allow_html=True)

    else:
        st.warning("Seçili kaynak/dönem için veri okunamadı.")

# ══ SAYFA 4 — FIRSAT TARAMA ══════════════════
if aktif_sayfa == "🔍 Fırsat Tarama":
    st.markdown("### 🎯 Fırsat Tarama — Çoklu Kriter")

    c1, c2 = st.columns([1, 2])
    with c1:
        kaynak_listesi4 = kaynak_listesi_olustur()
        sec_d4 = st.selectbox("Dönem/Kaynak:", kaynak_listesi4, key="k4src")

    if sec_d4.startswith("Ham: "): data4 = ham_snap_merge(sec_d4)
    else:
        data4 = kaynak_coz_etiketli(sec_d4)
        if sec_d4 != "SNAP SON" and not puan_data.empty and not data4.empty:
            snap_son_extra = [c for c in puan_data.columns if c not in data4.columns and c not in ["Hisse","Sektör"]]
            if snap_son_extra: data4 = data4.merge(puan_data[["Hisse"]+snap_son_extra], on="Hisse", how="left")

    if data4.empty:
        st.warning(f"{sec_d4} sayfasından veri okunamadı.")
    else:
        data4["Sektör"] = data4["Hisse"].map(sektor_map).fillna("Diğer")
        num_c4 = [c for c in data4.columns if c not in ["Hisse", "Sektör"]]

        with c2:
            sek4 = st.multiselect("Sektör filtresi:", sorted(data4["Sektör"].unique()), default=[], key="sek4", placeholder="Tümü (boş bırak)")
        if sek4: data4 = data4[data4["Sektör"].isin(sek4)]

        st.markdown("#### Kriterler")
        if "kriter_sayisi" not in st.session_state: st.session_state.kriter_sayisi = 3

        col_ekle, col_bos = st.columns([1, 4])
        with col_ekle:
            if st.button("＋ Kriter Ekle", key="kriter_ekle"):
                st.session_state.kriter_sayisi += 1
                st.rerun()

        kriterler = []
        sil_index = None
        for i in range(st.session_state.kriter_sayisi):
            col1, col2, col3, col4 = st.columns([3, 1, 2, 0.4])
            with col1: m = st.selectbox(f"Metrik {i+1}:", ["(boş)"] + num_c4, key=f"k4m{i}")
            with col2: op = st.selectbox("Op:", [">", ">=", "<", "<="], key=f"k4op{i}")
            with col3:
                if m != "(boş)" and m in data4.columns:
                    col_vals = pd.to_numeric(data4[m], errors="coerce").dropna()
                    default_v = float(col_vals.median()) if len(col_vals) > 0 else 0.0
                    esik = st.number_input("Eşik:", value=default_v, key=f"k4e{i}", format="%.4f", label_visibility="collapsed")
                    kriterler.append((m, op, esik))
                else: st.empty()
            with col4:
                if st.button("✕", key=f"k4del{i}"): sil_index = i

        if sil_index is not None and st.session_state.kriter_sayisi > 1:
            st.session_state.kriter_sayisi -= 1
            for sfx in ["m", "op", "e"]:
                k = f"k4{sfx}{sil_index}"
                if k in st.session_state: del st.session_state[k]
            st.rerun()

        if kriterler:
            filtre = pd.Series([True] * len(data4), index=data4.index)
            for m, op, esik in kriterler:
                col_s = pd.to_numeric(data4[m], errors="coerce")
                if op == ">":    filtre &= col_s > esik
                elif op == ">=": filtre &= col_s >= esik
                elif op == "<":  filtre &= col_s < esik
                elif op == "<=": filtre &= col_s <= esik

            sonuc_cols = list(dict.fromkeys(["Hisse", "Sektör"] + [m for m, _, _ in kriterler]))
            sonuc = data4[filtre][sonuc_cols].reset_index(drop=True)
            st.success(f"✅ **{len(sonuc)} hisse** kriterleri karşılıyor")

            for c in [m for m, _, _ in kriterler]:
                col_data = sonuc[c]
                if isinstance(col_data, pd.DataFrame): col_data = col_data.iloc[:, 0]
                converted = pd.to_numeric(col_data, errors="coerce")
                if not converted.isna().all(): sonuc[c] = converted.round(4)

            df_goster(sonuc, height=500, mn_tl=True)

            if len(sonuc) > 0:
                ilk_m = kriterler[0][0]
                s4 = sonuc.dropna(subset=[ilk_m]).sort_values(ilk_m)
                fig4 = go.Figure(go.Bar(
                    x=s4["Hisse"], y=s4[ilk_m],
                    marker_color=[st.session_state.bar_tek_renk or (YESIL if (pd.notna(v) and float(v) >= 0) else KIRMIZI) for v in s4[ilk_m].tolist()],
                    text=[tr_fmt(v) if v else "" for v in s4[ilk_m]], textposition="outside"
                ))
                fig4.update_layout(height=420, showlegend=False,
                    title=dict(text=f"<b>Sonuçlar — {ilk_m}</b>", font=dict(color=MAIN_BASLIK)),
                    xaxis=dict(showgrid=False, color=MAIN_METIN, tickangle=-45, tickfont=dict(size=12, color=MAIN_BASLIK)),
                    yaxis=dict(gridcolor=MAIN_GRID, color=MAIN_SOLUK),
                    paper_bgcolor=MAIN_BG, plot_bgcolor=MAIN_SURFACE, font=dict(color=MAIN_METIN))
                st.plotly_chart(fig4, use_container_width=True)

# ══ SAYFA 5 — ÇEYREKLİK TREND ══════════════════
if aktif_sayfa == "📈 Çeyreklik Trend":
    st.markdown("### 📈 Çeyreklik Trend")
    dd5 = merged_data
    tum_c5 = sorted(set(c for df in dd5.values() for c in df.columns if c!="Hisse"))
    c2, c3 = st.columns([3, 1])
    with c2: sec_m5 = st.selectbox("METRİK:", tum_c5, key="m5")
    with c3: mod5 = st.radio("Görünüm:", ["Hisse","Sektör"], horizontal=True, key="mod5")

    fig5 = go.Figure()

    if mod5=="Hisse":
        sec_h5 = st.multiselect("Hisse(ler):", tum_hisseler, default=tum_hisseler[:3], key="h5")
        for hisse in sec_h5:
            vals = []
            for d,df in dd5.items():
                if sec_m5 in df.columns and hisse in df["Hisse"].values:
                    v = df[df["Hisse"]==hisse][sec_m5].values[0]
                    vals.append({"Dönem":d,"Değer":v})
            if vals:
                dg = pd.DataFrame(vals).dropna()
                fig5.add_trace(go.Scatter(x=dg["Dönem"],y=dg["Değer"], mode="lines+markers",name=hisse,line=dict(width=2.5),marker=dict(size=8)))
    else:
        sek5 = sorted(set(sektor_map.values())) if sektor_map else []
        sec_s5 = st.multiselect("Sektör(ler):", sek5, default=sek5[:4], key="s5")
        for sek in sec_s5:
            sek_hisseler = [h for h,s in sektor_map.items() if s==sek]
            vals = []
            for d,df in dd5.items():
                if sec_m5 in df.columns:
                    df_s = df[df["Hisse"].isin(sek_hisseler)]
                    ort = df_s[sec_m5].mean()
                    vals.append({"Dönem":d,"Değer":ort})
            if vals:
                dg = pd.DataFrame(vals).dropna()
                fig5.add_trace(go.Scatter(x=dg["Dönem"],y=dg["Değer"], mode="lines+markers",name=sek,line=dict(width=2.5),marker=dict(size=8)))

    fig5.add_hline(y=0,line_dash="dot",line_color="#475569")
    fig5.update_layout(height=480,
        title=dict(text=f"<b>{sec_m5}</b> — Çeyreklik Trend",font=dict(color=MAIN_BASLIK,size=15)),
        paper_bgcolor=MAIN_BG,plot_bgcolor=MAIN_SURFACE,font=dict(color=MAIN_METIN),
        legend=dict(bgcolor=CARD,bordercolor="#334155",borderwidth=1),
        xaxis=dict(showgrid=False,color=MAIN_SOLUK,categoryorder="array",categoryarray=[d for d,_,_ in reversed(DONEM_SAYFALARI)]),
        yaxis=dict(gridcolor=MAIN_GRID,color=MAIN_SOLUK))
    st.plotly_chart(fig5, use_container_width=True)

# ══ SAYFA 6 — PUAN TABLOSU ══════════════════
@st.fragment
def puan_tablosu_fragment(puan_data, son_data, cikti_data, sektor_map, ayar_data):
    st.markdown("### 🏆 Puan Tablosu")

    if "filtre6_sayisi" not in st.session_state: st.session_state.filtre6_sayisi = 1

    base6 = pd.DataFrame()

    def _merge6(base, yeni, suffix):
        if yeni.empty: return base
        yeni = yeni.copy()
        if base.empty: return yeni
        ortak = [c for c in yeni.columns if c in base.columns and c not in ["Hisse", "Sektör"]]
        yeni = yeni.rename(columns={c: f"{c}_{suffix}" for c in ortak})
        return base.merge(yeni.drop(columns=["Sektör"], errors="ignore"), on="Hisse", how="outer")

    if not puan_data.empty: base6 = puan_data.copy()
    if not son_data.empty: base6 = _merge6(base6, son_data, "son")
    if not ayar_data.empty and "Hisse" in ayar_data.columns: base6 = _merge6(base6, ayar_data, "ayar")
    for _cikti_adi, _cikti_df in cikti_data.items():
        if not _cikti_df.empty: base6 = _merge6(base6, _cikti_df, _cikti_adi)

    if base6.empty:
        st.warning("Veri okunamadı.")
        return

    if "Hisse" in base6.columns: base6["Sektör"] = base6["Hisse"].map(sektor_map).fillna("Diğer")
    tum_cols6 = puan_sabit_filtrele(
        [c for c in base6.columns if c not in ["Hisse", "Sektör"]],
        PUAN_SABIT_SUTUNLAR,
    )

    sec_s6 = st.session_state.get("s6", "Tümü")
    yon6   = st.session_state.get("y6", "↓")

    _m6_kayit = puan_sabit_filtrele(
        tum_cols6,
        st.session_state.get("puan_m6_kayit", PUAN_SABIT_SUTUNLAR),
    )
    _alfa_eslesme = puan_sabit_filtrele(tum_cols6, ["ALFA"])
    if _alfa_eslesme:
        for _col in _alfa_eslesme:
            if _col not in _m6_kayit:
                _m6_kayit.append(_col)
    if not _m6_kayit: _m6_kayit = puan_sabit_filtrele(tum_cols6) or tum_cols6[:6]
    _m6_kayit = puan_kolon_sirasi(_m6_kayit)
    _m6_state = st.session_state.get("m6", [])
    _m6_state_filtreli = puan_sabit_filtrele(tum_cols6, _m6_state)
    if _alfa_eslesme:
        for _col in _alfa_eslesme:
            if _col not in _m6_state_filtreli:
                _m6_state_filtreli.append(_col)
    _m6_state_filtreli = puan_kolon_sirasi(_m6_state_filtreli or _m6_kayit)
    if _m6_state_filtreli != _m6_state:
        st.session_state["m6"] = _m6_state_filtreli or _m6_kayit
    sec_m6 = puan_kolon_sirasi(_m6_kayit)

    _sira_opts = [c for c in sec_m6 if c in tum_cols6]
    sira6 = st.session_state.get("sr6")
    if sira6 not in _sira_opts: sira6 = _sira_opts[0] if _sira_opts else None
    if st.session_state.get("sr6") != sira6:
        st.session_state["sr6"] = sira6

    filtre6_kriterler = []
    filtre6_metrikler = ["(boş)"] + tum_cols6
    for i in range(st.session_state.filtre6_sayisi):
        fm  = st.session_state.get(f"f6m{i}", "(boş)")
        fop = st.session_state.get(f"f6op{i}", ">")
        fe  = st.session_state.get(f"f6e{i}")
        if fm and fm != "(boş)" and fm in base6.columns and fe is not None:
            _col_num = pd.to_numeric(base6[fm], errors="coerce")
            if not _col_num.isna().all() and fop not in ("=", "≠"):
                filtre6_kriterler.append((fm, fop, fe, "num"))
            else:
                filtre6_kriterler.append((fm, fop, str(fe), "txt"))

    filtre6_base = base6.copy()
    if sec_s6 != "Tümü": filtre6_base = filtre6_base[filtre6_base["Sektör"] == sec_s6]

    if filtre6_kriterler:
        filtre6_mask = pd.Series([True] * len(filtre6_base), index=filtre6_base.index)
        for _fm, _fop, _fval, _ftype in filtre6_kriterler:
            if _fm not in filtre6_base.columns: continue
            if _ftype == "txt" or _fop in ("=", "≠"):
                _fs_txt = filtre6_base[_fm].astype(str).str.strip()
                if _fop == "=":   filtre6_mask &= _fs_txt == str(_fval).strip()
                elif _fop == "≠": filtre6_mask &= _fs_txt != str(_fval).strip()
            else:
                _fs = pd.to_numeric(filtre6_base[_fm], errors="coerce")
                if _fop == ">":    filtre6_mask &= _fs > _fval
                elif _fop == ">=": filtre6_mask &= _fs >= _fval
                elif _fop == "<":  filtre6_mask &= _fs < _fval
                elif _fop == "<=": filtre6_mask &= _fs <= _fval
        filtre6_base = filtre6_base[filtre6_mask]

    goster_cols = list(dict.fromkeys(["Hisse", "Sektör"] + [c for c in sec_m6 if c in filtre6_base.columns]))
    tablo6 = filtre6_base[[c for c in goster_cols if c in filtre6_base.columns]].copy()

    for c in [c for c in sec_m6 if c in tablo6.columns]:
        col_data = tablo6[c]
        if isinstance(col_data, pd.DataFrame): col_data = col_data.iloc[:, 0]
        converted6 = pd.to_numeric(col_data, errors="coerce")
        if not converted6.isna().all():
            mask = converted6.notna()
            tablo6.loc[mask, c] = converted6[mask].round(4)

    if sira6 and sira6 in tablo6.columns:
        _sort_key = pd.to_numeric(tablo6[sira6], errors="coerce")
        tablo6 = tablo6.assign(_sort_key=_sort_key).sort_values("_sort_key", ascending=(yon6 == "↑"), na_position="last").drop(columns=["_sort_key"]).reset_index(drop=True)

    tablo6.insert(0, "#", range(1, len(tablo6) + 1))
    st.markdown(
        f"""
        <div style='display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin:2px 0 10px 0;'>
          {snap_amblem_html(compact=True)}
          <div style='padding-top:4px;color:{MAIN_SOLUK};font-size:13px;font-weight:700;white-space:nowrap;'>{len(tablo6)} hisse</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tablo6_goster = tablo6.drop(columns=["#"]).reset_index(drop=True)
    tablo6_goster.index = tablo6_goster.index + 1
    tablo6_goster = tablo6_goster[puan_kolon_sirasi(tablo6_goster.columns.tolist())]

    if tablo6_goster.empty or len([c for c in tablo6_goster.columns if c not in ["Hisse","Sektör"]]) == 0:
        st.warning("Gösterilecek sütun seçilmedi. Aşağıdan sütun seçin.")
    else:
        import streamlit.components.v1 as _comp
        import math as _math

        def _col_default_w(col_name, col_idx):
            cn = col_name.upper()
            if col_idx == 0:   return 70
            if "SEKTÖR" in cn or "SEKTOR" in cn: return 152
            if len(col_name) <= 4:  return 80
            if len(col_name) <= 8:  return 95
            return 110

        def _html_puan_tablosu(df):
            cols = list(df.columns)
            default_widths = [_col_default_w(c, j) for j, c in enumerate(cols)]

            th_base = (f"background:{PUAN_HEADER_BG};color:#FFFFFF;font-size:11px;font-weight:700;"
                       "letter-spacing:0.05em;text-transform:uppercase;"
                       f"padding:10px 22px 10px 10px;border-right:1px solid {PUAN_HEADER_DIVIDER};"
                       f"border-bottom:3px solid {PUAN_HEADER_BORDER};"
                       "white-space:normal;word-break:break-word;vertical-align:middle;")
            header_html = "<tr>"
            for j, c in enumerate(cols):
                align = "center"
                w = default_widths[j]
                header_html += (f"<th data-col='{j}' style='text-align:{align};{th_base}"
                                f"width:{w}px;min-width:40px;'>{c}<div class='resizer'></div></th>")
            header_html += "</tr>"

            td_base = ("font-size:13px;padding:8px 10px;"
                       "border-bottom:1px solid #E2E8F0;border-right:1px solid #F1F5F9;"
                       "overflow:hidden;text-overflow:ellipsis;white-space:nowrap;")
            rows_html = ""
            for row_pos, (_, row) in enumerate(df.iterrows()):
                bg = puan_satir_rengi(row_pos)
                cells = ""
                for j, c in enumerate(cols):
                    v = row[c]
                    _v_str = str(v).strip() if v is not None else ""
                    _is_empty = (v is None or _v_str == "" or _v_str.lower() in ("none", "nan", "nat", "-"))
                    _is_snap_col = normalize_col(c) == normalize_col("SNAP")
                    _renk = puan_hucre_yazi_rengi(c, v)
                    try:
                        if _is_empty: raise ValueError("boş")
                        fv = float(v)
                        if _math.isnan(fv): raise ValueError
                        disp = tr_df_fmt(fv)
                        _agirlik = "700" if (_is_snap_col or j == 0 or j >= 2) else "500"
                        color = f"{_renk};font-weight:{_agirlik};"
                    except:
                        if _is_empty:
                            disp = "—"
                            color = f"{_renk};"
                        else:
                            disp = _v_str
                            _agirlik = "700" if (_is_snap_col or j == 0) else "500"
                            color = f"{_renk};font-weight:{_agirlik};"
                    align = "right" if j >= 2 else "left"
                    w = default_widths[j]
                    _extra = f"max-width:{w}px;overflow:hidden;text-overflow:ellipsis;" if j == 1 else ""
                    cells += (f"<td data-col='{j}' title='{disp}' style='text-align:{align};background:{bg};"
                              f"width:{w}px;{_extra}{td_base}color:{color}'>{disp}</td>")
                hover_in  = "onmouseover=\"this.style.background='#DDEAF7'\""
                hover_out = f"onmouseout=\"this.style.background='{bg}'\""
                rows_html += f"<tr {hover_in} {hover_out}>{cells}</tr>"

            ss_key = "snap_col_widths_" + "_".join(str(w) for w in default_widths[:5])
            html = f"""<!DOCTYPE html>
<html>
<head>
<style>
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:Inter,sans-serif; }}
  .wrap {{ overflow:auto; max-height:1150px; border-radius:10px;
           border:2px solid {PUAN_HEADER_BG}; box-shadow:0 4px 20px rgba(79,129,189,0.16); }}
  table {{ border-collapse:collapse; background:#FFFFFF; table-layout:fixed; }}
  thead {{ position:sticky; top:0; z-index:10; }}
  th {{ position:relative; overflow:hidden; }}
  .resizer {{ position:absolute; right:0; top:0; height:100%; width:10px; cursor:col-resize; user-select:none; z-index:1; background:linear-gradient(to right, transparent 0%, rgba(255,255,255,0.3) 50%, rgba(255,255,255,0.6) 100%); transition:background 0.15s; }}
  .resizer:hover, .resizer.dragging {{ background:rgba(255,255,255,0.85); }}
</style>
</head>
<body>
<div class="wrap"><table id="tbl"><thead>{header_html}</thead><tbody>{rows_html}</tbody></table></div>
<script>
(function() {{
  var SS_KEY = "{ss_key}"; var table = document.getElementById("tbl"); var ths = Array.from(table.querySelectorAll("thead th"));
  var saved = {{}}; try {{ var raw = sessionStorage.getItem(SS_KEY); if (raw) saved = JSON.parse(raw); }} catch(e) {{}}
  function setColWidth(idx, w) {{ ths[idx].style.width = w + "px"; table.querySelectorAll("tbody tr").forEach(function(row) {{ var td = row.querySelector("[data-col='" + idx + "']"); if (td) td.style.width = w + "px"; }}); }}
  function saveWidths() {{ var out = {{}}; ths.forEach(function(th, i) {{ out[i] = th.offsetWidth; }}); try {{ sessionStorage.setItem(SS_KEY, JSON.stringify(out)); }} catch(e) {{}} }}
  ths.forEach(function(th, i) {{ var w = saved[i] !== undefined ? saved[i] : th.offsetWidth; setColWidth(i, w); }});
  ths.forEach(function(th, i) {{
    var resizer = th.querySelector(".resizer"); if (!resizer) return; var startX, startW;
    resizer.addEventListener("mousedown", function(e) {{
      startX = e.pageX; startW = th.offsetWidth; resizer.classList.add("dragging"); e.preventDefault();
      function onMove(e) {{ setColWidth(i, Math.max(40, startW + (e.pageX - startX))); }}
      function onUp() {{ resizer.classList.remove("dragging"); saveWidths(); document.removeEventListener("mousemove", onMove); document.removeEventListener("mouseup", onUp); }}
      document.addEventListener("mousemove", onMove); document.addEventListener("mouseup", onUp);
    }});
  }});
}})();
</script>
</body>
</html>"""
            return html

        _ss_mode = (time.time() - st.session_state.get("_screenshot_ts", 0) < 15)


        if _ss_mode:

            # html2canvas iframe içini yakalayamadığı için screenshot anında tabloyu Streamlit dataframe olarak basıyoruz
            tablo6_ss = tablo6_goster.copy()
            try:
                tablo6_ss.insert(0, "#", list(tablo6_ss.index))
            except Exception:
                tablo6_ss.insert(0, "#", range(1, len(tablo6_ss) + 1))
            _fmt_dict_ss = {c: tr_df_fmt for c in tablo6_ss.select_dtypes(include="number").columns.tolist()}

            def _ss_satir_stili(_row):
                _bg = puan_satir_rengi(max(int(_row.name) - 1, 0))
                return [f"background-color: {_bg}"] * len(_row)

            def _ss_yazi_stili(df):
                stiller = pd.DataFrame("", index=df.index, columns=df.columns)
                for idx in df.index:
                    for col in df.columns:
                        _is_snap_col = normalize_col(col) == normalize_col("SNAP")
                        _is_alfa_col = normalize_col(col) == normalize_col("ALFA")
                        _renk = puan_hucre_yazi_rengi(col, df.at[idx, col])
                        _agirlik = "700" if (_is_snap_col or _is_alfa_col or col == "#" or col == "Hisse") else "500"
                        stiller.at[idx, col] = f"color: {_renk}; font-weight: {_agirlik}"
                return stiller

            _styled_ss = (
                tablo6_ss.style
                .format(_fmt_dict_ss, na_rep="—")
                .hide(axis="index")
                .apply(_ss_satir_stili, axis=1)
                .apply(_ss_yazi_stili, axis=None)
                .set_table_styles([
                    {"selector": "table",
                     "props": [("background-color", "#FFFFFF"), ("border-collapse", "collapse"), ("width", "100%")]},
                    {"selector": "thead tr th",
                     "props": [
                         ("background-color", PUAN_HEADER_BG),
                         ("color", "#FFFFFF"),
                         ("font-weight", "700"),
                         ("font-size", "12px"),
                         ("letter-spacing", "0.05em"),
                         ("text-transform", "uppercase"),
                         ("text-align", "center"),
                         ("vertical-align", "middle"),
                         ("border-bottom", f"3px solid {PUAN_HEADER_BORDER}"),
                         ("border-right", f"1px solid {PUAN_HEADER_DIVIDER}"),
                         ("padding", "11px 14px"),
                         ("white-space", "nowrap"),
                     ]},
                    {"selector": "tbody tr td",
                     "props": [
                         ("color", "#000000"),
                         ("font-size", "13px"),
                         ("font-weight", "500"),
                         ("padding", "9px 14px"),
                         ("border-bottom", "1px solid #D6E4F0"),
                         ("border-right", "1px solid #EBF2FA"),
                     ]},
                    {"selector": "tbody tr td:first-child",
                     "props": [("font-weight", "700"), ("color", "#000000")]},
                ])
            )
            st.dataframe(_styled_ss, height=1200, use_container_width=True)
        else:
            _comp.html(_html_puan_tablosu(tablo6_goster), height=1200, scrolling=False)

    import io as _io
    from datetime import datetime as _dt
    _dl1, _dl2 = st.columns([1, 5])
    with _dl1:
        _buf = _io.BytesIO()
        with pd.ExcelWriter(_buf, engine="openpyxl") as _wr: tablo6_goster.to_excel(_wr, index=True, sheet_name="Puan Tablosu")
        st.download_button(label="⬇️ Excel indir", data=_buf.getvalue(), file_name=f"puan_tablosu_{_dt.now():%Y%m%d}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl6_xlsx")
    with _dl2:
        _csv = tablo6_goster.to_csv(index=True)
        st.download_button(label="⬇️ CSV indir", data=_csv.encode("utf-8-sig"), file_name=f"puan_tablosu_{_dt.now():%Y%m%d}.csv", mime="text/csv", key="dl6_csv")

    st.markdown("---")
    st.markdown(f"<p style='color:{ALTIN};font-weight:600;font-size:13px;margin-bottom:6px;'>⚙️ Tablo Ayarları</p>", unsafe_allow_html=True)

    sek_list6 = ["Tümü"] + sorted(base6["Sektör"].unique())
    _s6_idx = sek_list6.index(sec_s6) if sec_s6 in sek_list6 else 0
    st.selectbox("Sektör:", sek_list6, index=_s6_idx, key="s6")

    _b1, _b2, _b3 = st.columns([3, 2, 1])
    with _b1: st.multiselect("Gösterilecek sütunlar:", tum_cols6, default=_m6_kayit, key="m6")
    with _b2:
        if _sira_opts:
            _sr_idx = _sira_opts.index(sira6) if sira6 in _sira_opts else 0
            st.selectbox("Sırala:", _sira_opts, index=_sr_idx, key="sr6")

    _m6_simdiki  = puan_kolon_sirasi(st.session_state.get("m6", []))
    if _m6_simdiki != st.session_state.get("m6", []):
        st.session_state["m6"] = _m6_simdiki
    _sr6_simdiki = st.session_state.get("sr6", "")
    if _m6_simdiki != st.session_state.get("puan_m6_son"):
        st.session_state.puan_m6_son   = _m6_simdiki
        st.session_state.puan_m6_kayit = _m6_simdiki
        _k_simdiki = ayarlari_yukle()
        _k_simdiki["puan_m6"]  = _m6_simdiki
        _k_simdiki["puan_sr6"] = _sr6_simdiki
        ayarlari_kaydet(_k_simdiki)
    with _b3: st.radio("Yön:", ["↓", "↑"], index=0 if yon6 == "↓" else 1, horizontal=True, key="y6")

    st.markdown(f"<p style='color:{ALTIN};font-weight:600;font-size:13px;margin-top:8px;margin-bottom:4px;'>🔍 Metrik Filtreleri</p>", unsafe_allow_html=True)

    col_ekle6, col_sifirla6 = st.columns([1, 5])
    with col_ekle6:
        if st.button("➕ Filtre Ekle", key="f6_ekle"):
            st.session_state.filtre6_sayisi += 1
            st.rerun(scope="fragment")
    with col_sifirla6:
        if st.button("🗑️ Filtreleri Sıfırla", key="f6_sifirla"):
            st.session_state.filtre6_sayisi = 1
            for _k in list(st.session_state.keys()):
                if _k.startswith("f6m") or _k.startswith("f6op") or _k.startswith("f6e"): del st.session_state[_k]
            st.rerun(scope="fragment")

    filtre6_sil = None
    for i in range(st.session_state.filtre6_sayisi):
        fc1, fc2, fc3, fc4 = st.columns([3, 1, 2, 0.4])
        with fc1: st.selectbox("Metrik:", filtre6_metrikler, key=f"f6m{i}", label_visibility="collapsed")
        with fc2: st.selectbox("Op:", ["=", "≠", ">", ">=", "<", "<="], key=f"f6op{i}", label_visibility="collapsed")
        with fc3:
            _fm_i = st.session_state.get(f"f6m{i}", "(boş)")
            _fop_i = st.session_state.get(f"f6op{i}", ">")
            if _fm_i != "(boş)" and _fm_i in base6.columns:
                _col_num_i = pd.to_numeric(base6[_fm_i], errors="coerce")
                if not _col_num_i.isna().all() and _fop_i not in ("=", "≠"):
                    _fvals_i = _col_num_i.dropna()
                    _fdef_i = float(_fvals_i.median()) if len(_fvals_i) > 0 else 0.0
                    st.number_input("Eşik:", value=_fdef_i, key=f"f6e{i}", format="%.4f", label_visibility="collapsed")
                else:
                    _uniq_i = sorted(base6[_fm_i].dropna().astype(str).unique().tolist())
                    if _uniq_i: st.selectbox("Değer:", _uniq_i, key=f"f6e{i}", label_visibility="collapsed")
                    else: st.empty()
            else: st.empty()
        with fc4:
            if st.button("✕", key=f"f6del{i}"): filtre6_sil = i

    if filtre6_sil is not None and st.session_state.filtre6_sayisi > 1:
        st.session_state.filtre6_sayisi -= 1
        for _sfx in ["m", "op", "e"]:
            _k = f"f6{_sfx}{filtre6_sil}"
            if _k in st.session_state: del st.session_state[_k]
        st.rerun(scope="fragment")

if aktif_sayfa == "🏆 Puan Tablosu":
    puan_tablosu_fragment(puan_data, son_data, cikti_data, sektor_map, ayar_data)

# ══ SAYFA 7 — FORMÜL HESAPLAYICI ══════════════════
@st.fragment
def formul_hesaplayici_fragment(ham_data, snap_data, sektor_map, tum_hisseler):
    st.markdown("### 🧮 Formül Hesaplayıcı")
    st.markdown(f"<p style='color:{MAIN_SOLUK};font-size:13px;margin-top:-10px;margin-bottom:16px;'>Metrikler arasında aritmetik işlemler yaparak yeni sütunlar oluştur.</p>", unsafe_allow_html=True)

    dd7 = merged_data
    donemler7 = list(dd7.keys())
    sec_donem7 = st.selectbox("Dönem:", donemler7, key="d7")

    if sec_donem7 not in dd7 or dd7[sec_donem7].empty:
        st.warning("Seçili dönem için veri bulunamadı.")
        return

    df7 = dd7[sec_donem7].copy()
    df7["Sektör"] = df7["Hisse"].map(sektor_map).fillna("Diğer")
    metrikler7 = [c for c in df7.columns if c not in ["Hisse", "Sektör"]]
    num_metrikler7 = [m for m in metrikler7 if not pd.to_numeric(df7[m], errors="coerce").isna().all()]

    st.markdown(f"<p style='color:{ALTIN};font-weight:600;font-size:13px;margin-bottom:6px;'>⚙️ Formüller</p>", unsafe_allow_html=True)

    if "formul7_sayisi" not in st.session_state: st.session_state.formul7_sayisi = 1

    fa, fb = st.columns([1, 5])
    with fa:
        if st.button("➕ Formül Ekle", key="f7_ekle"):
            st.session_state.formul7_sayisi += 1
            st.rerun(scope="fragment")
    with fb:
        if st.button("🗑️ Sıfırla", key="f7_sifirla"):
            st.session_state.formul7_sayisi = 1
            for _k in list(st.session_state.keys()):
                if _k.startswith("f7"): del st.session_state[_k]
            st.rerun(scope="fragment")

    OPERATORLER = ["+", "-", "*", "/"]
    formüller = []
    sil7 = None

    for i in range(st.session_state.formul7_sayisi):
        hc1, hc2, hc3, hc4, hc5, hc6 = st.columns([2, 2, 1, 2, 2, 0.4])
        with hc1: ad = st.text_input("Sonuç adı:", value=f"Formül_{i+1}", key=f"f7ad{i}", label_visibility="collapsed", placeholder="Sonuç adı")
        with hc2: sol = st.selectbox("Sol metrik:", num_metrikler7, key=f"f7sol{i}", label_visibility="collapsed")
        with hc3: op = st.selectbox("İşlem:", OPERATORLER, key=f"f7op{i}", label_visibility="collapsed")
        with hc4: sag_tip = st.radio("", ["Metrik", "Sabit"], horizontal=True, key=f"f7sagt{i}", label_visibility="collapsed")
        with hc5:
            if sag_tip == "Metrik": sag = st.selectbox("Sağ metrik:", num_metrikler7, key=f"f7sag{i}", label_visibility="collapsed")
            else: sag = st.number_input("Sabit değer:", value=1.0, key=f"f7sag{i}", format="%.4f", label_visibility="collapsed")
        with hc6:
            if st.button("✕", key=f"f7del{i}"): sil7 = i
        formüller.append((ad, sol, op, sag_tip, sag))

    if sil7 is not None and st.session_state.formul7_sayisi > 1:
        st.session_state.formul7_sayisi -= 1
        for _sfx in ["ad", "sol", "op", "sagt", "sag"]:
            _k = f"f7{_sfx}{sil7}"
            if _k in st.session_state: del st.session_state[_k]
        st.rerun(scope="fragment")

    st.divider()

    sonuc7 = df7[["Hisse", "Sektör"]].copy()
    hatalar = []

    for (ad, sol, op, sag_tip, sag) in formüller:
        try:
            sol_s = pd.to_numeric(df7[sol], errors="coerce")
            if sag_tip == "Metrik": sag_s = pd.to_numeric(df7[sag], errors="coerce")
            else: sag_s = float(sag)

            if op == "+":   sonuc7[ad] = sol_s + sag_s
            elif op == "-": sonuc7[ad] = sol_s - sag_s
            elif op == "*": sonuc7[ad] = sol_s * sag_s
            elif op == "/":
                if sag_tip == "Metrik": sag_safe = sag_s.replace(0, np.nan)
                else: sag_safe = float(sag) if float(sag) != 0 else np.nan
                sonuc7[ad] = sol_s / sag_safe
        except Exception as e:
            hatalar.append(f"'{ad}': {e}")

    for h in hatalar: st.error(f"⚠️ {h}")

    formul_cols = [c for c in sonuc7.columns if c not in ["Hisse", "Sektör"]]
    if not formul_cols:
        st.info("Henüz geçerli bir formül yok.")
        return

    sc1, sc2, sc3 = st.columns([2, 2, 1])
    with sc1:
        sek_list7 = ["Tümü"] + sorted(sonuc7["Sektör"].unique())
        sec_sek7 = st.selectbox("Sektör filtresi:", sek_list7, key="sek7")
    with sc2: sira7 = st.selectbox("Sırala:", formul_cols, key="sira7")
    with sc3: yon7 = st.radio("Yön:", ["↓", "↑"], horizontal=True, key="yon7")

    if sec_sek7 != "Tümü": sonuc7 = sonuc7[sonuc7["Sektör"] == sec_sek7]

    for c in formul_cols: sonuc7[c] = pd.to_numeric(sonuc7[c], errors="coerce").round(4)
    sonuc7 = sonuc7.sort_values(sira7, ascending=(yon7 == "↑")).reset_index(drop=True)

    st.markdown(f"**{len(sonuc7)} hisse** | {sec_donem7}")
    df_goster(sonuc7, height=550)

    s7 = sonuc7.dropna(subset=[sira7]).sort_values(sira7)
    if len(s7) > 0:
        fig7 = go.Figure(go.Bar(
            x=s7["Hisse"], y=s7[sira7],
            marker_color=[st.session_state.bar_tek_renk or (YESIL if float(v) >= 0 else KIRMIZI) for v in s7[sira7].tolist()],
            text=[tr_fmt(v) for v in s7[sira7].tolist()], textposition="outside"
        ))
        fig7.update_layout(height=420, showlegend=False,
            title=dict(text=f"<b>{sira7}</b> — {sec_donem7}", font=dict(color=MAIN_BASLIK)),
            xaxis=dict(showgrid=False, color=MAIN_METIN, tickangle=-45, tickfont=dict(size=12, color=MAIN_BASLIK)),
            yaxis=dict(gridcolor=MAIN_GRID, color=MAIN_SOLUK),
            paper_bgcolor=MAIN_BG, plot_bgcolor=MAIN_SURFACE, font=dict(color=MAIN_METIN))
        st.plotly_chart(fig7, use_container_width=True)

if aktif_sayfa == "🧮 Formül Hesaplayıcı":
    formul_hesaplayici_fragment(ham_data, snap_data, sektor_map, tum_hisseler)

# ══ SAYFA 8 — YABANCI SERMAYE AKIMI (PROFESYONEL GÖRÜNÜM) ══════════════════
if aktif_sayfa == "🌍 Yabancı Akım":
    st.markdown("### 🌍 Haftalık Yabancı Sermaye Akımları")

    if ya_data.empty:
        st.info("💡 Henüz 'YA' sayfasında veri bulunmuyor. Lütfen önce yabanci_akim.py botunu çalıştırarak Merkez Bankası verilerini Sheets'e aktarın.")
    else:
        df_ya = ya_data.copy()
        for c in df_ya.columns:
            if c != "Tarih": df_ya[c] = pd.to_numeric(df_ya[c], errors="coerce")

        son_hafta = df_ya.iloc[-1]

        st.markdown(f"""
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:15px;margin-bottom:25px;">
            <div style="background:{MAIN_CARD};border:1px solid {MAIN_BORDER};border-radius:12px;padding:20px;box-shadow:0 4px 6px rgba(0,0,0,0.05);border-left:4px solid {MAIN_BASLIK};">
                <div style="color:{MAIN_SOLUK};font-size:12px;font-weight:700;text-transform:uppercase;margin-bottom:5px;">SON HAFTA AKIMI</div>
                <div style="color:{YESIL if son_hafta['TOPLAM YABANCI AKIMI (mn $)'] > 0 else KIRMIZI};font-size:24px;font-weight:800;">{son_hafta['TOPLAM YABANCI AKIMI (mn $)']:+,.0f} Mn $</div>
                <div style="color:{METIN_ZAYIF};font-size:11px;margin-top:5px;">{son_hafta['Tarih']}</div>
            </div>
            <div style="background:{MAIN_CARD};border:1px solid {MAIN_BORDER};border-radius:12px;padding:20px;box-shadow:0 4px 6px rgba(0,0,0,0.05);">
                <div style="color:{MAIN_SOLUK};font-size:12px;font-weight:700;text-transform:uppercase;margin-bottom:5px;">KÜMÜLATİF TOPLAM</div>
                <div style="color:{MAIN_BASLIK};font-size:24px;font-weight:800;">{son_hafta['Kümülatif Toplam (mn $)']/1000:+,.1f} Mr $</div>
                <div style="color:{METIN_ZAYIF};font-size:11px;margin-top:5px;">Eylül 2020'den Bugüne</div>
            </div>
            <div style="background:{MAIN_CARD};border:1px solid {MAIN_BORDER};border-radius:12px;padding:20px;box-shadow:0 4px 6px rgba(0,0,0,0.05);">
                <div style="color:{MAIN_SOLUK};font-size:12px;font-weight:700;text-transform:uppercase;margin-bottom:5px;">26H PENCERE (6 AY)</div>
                <div style="color:{YESIL if son_hafta['26H Yuvarlanan Toplam (6 Ay)'] > 0 else KIRMIZI};font-size:24px;font-weight:800;">{son_hafta['26H Yuvarlanan Toplam (6 Ay)']:+,.0f} Mn $</div>
                <div style="color:{METIN_ZAYIF};font-size:11px;margin-top:5px;">Orta Vade Trend</div>
            </div>
            <div style="background:{MAIN_CARD};border:1px solid {MAIN_BORDER};border-radius:12px;padding:20px;box-shadow:0 4px 6px rgba(0,0,0,0.05);">
                <div style="color:{MAIN_SOLUK};font-size:12px;font-weight:700;text-transform:uppercase;margin-bottom:5px;">HİSSE SENEDİ (HAFTALIK)</div>
                <div style="color:{YESIL if son_hafta['Hisse Senedi'] > 0 else KIRMIZI};font-size:24px;font-weight:800;">{son_hafta['Hisse Senedi']:+,.0f} Mn $</div>
                <div style="color:{METIN_ZAYIF};font-size:11px;margin-top:5px;">BİST Net Yabancı Takası</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"<p style='color:{MAIN_BASLIK};font-weight:700;font-size:16px;margin-bottom:5px;'>Grafik 1 — Haftalık Toplam Yabancı Akım ve 8H Hareketli Ortalama</p>", unsafe_allow_html=True)

        df_plot = df_ya.tail(150).copy()
        renkler = [YESIL if v >= 0 else KIRMIZI for v in df_plot['TOPLAM YABANCI AKIMI (mn $)']]

        fig1 = go.Figure()
        fig1.add_trace(go.Bar(
            x=df_plot['Tarih'], y=df_plot['TOPLAM YABANCI AKIMI (mn $)'],
            marker_color=renkler, name="Haftalık Akım", opacity=0.85
        ))
        fig1.add_trace(go.Scatter(
            x=df_plot['Tarih'], y=df_plot['8H Hareketli Ortalama'],
            mode='lines', line=dict(color='#1E3A8A', width=3), name='8H Ort.'
        ))
        fig1.add_hline(y=0, line_dash="solid", line_color=MAIN_GRID, line_width=1)

        fig1.update_layout(
            height=400, margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor=MAIN_BG, plot_bgcolor=MAIN_SURFACE,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(showgrid=False, color=MAIN_SOLUK, tickangle=-45, tickfont=dict(size=10)),
            yaxis=dict(gridcolor=MAIN_GRID, color=MAIN_SOLUK, title="Milyon Dolar ($)")
        )
        st.plotly_chart(fig1, use_container_width=True)

        st.markdown(f"<p style='color:{MAIN_BASLIK};font-weight:700;font-size:16px;margin-top:20px;margin-bottom:5px;'>Grafik 2 — Kümülatif Toplam Yabancı Akım (Eylül 2020'den itibaren)</p>", unsafe_allow_html=True)

        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=df_ya['Tarih'], y=df_ya['Kümülatif Toplam (mn $)'],
            mode='lines', fill='tozeroy',
            line=dict(color='#0F2B4C', width=3),
            fillcolor='rgba(46, 117, 182, 0.15)',
            name='Kümülatif Toplam'
        ))
        fig2.add_hline(y=0, line_dash="solid", line_color=MAIN_GRID, line_width=1)

        fig2.update_layout(
            height=350, margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor=MAIN_BG, plot_bgcolor=MAIN_SURFACE,
            xaxis=dict(showgrid=False, color=MAIN_SOLUK, tickangle=-45, tickfont=dict(size=10)),
            yaxis=dict(gridcolor=MAIN_GRID, color=MAIN_SOLUK, title="Milyon Dolar ($)")
        )
        st.plotly_chart(fig2, use_container_width=True)
