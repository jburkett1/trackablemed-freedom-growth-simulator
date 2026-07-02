
import base64
from io import BytesIO
from pathlib import Path
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.pdfgen import canvas

APP_DIR = Path(__file__).parent
ASSETS_DIR = APP_DIR / "assets"
LOGO_SVG_PATH = ASSETS_DIR / "trackablemed_logo.svg"
LOGO_PNG_CANDIDATES = [
    ASSETS_DIR / "trackablemed_logo.png",
    ASSETS_DIR / "TrackableMed logo color.png",
    APP_DIR / "trackablemed_logo.png",
    APP_DIR / "TrackableMed logo color.png",
]

st.set_page_config(page_title="Freedom Growth Economics Simulator", page_icon="📈", layout="wide")

CUSTOM_CSS = """
<style>
:root { --tm-yellow: #FFC300; --tm-dark: #111827; --tm-gray: #F3F4F6; }
.block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
.hero {
  border-radius: 22px; padding: 26px 28px; margin-bottom: 18px;
  background: linear-gradient(135deg, #111827 0%, #1f2937 70%, #374151 100%);
  color: white; border: 1px solid #374151;
}
.hero h1 { margin: 0; font-size: 2.15rem; line-height: 1.1; }
.hero p { margin: 0.45rem 0 0 0; color: #E5E7EB; font-size: 1.05rem; }
.kpi-card {
  border: 1px solid #E5E7EB; border-radius: 18px; padding: 18px; background: #FFFFFF;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06); min-height: 125px;
}
.kpi-label { color: #6B7280; font-size: .86rem; font-weight: 700; text-transform: uppercase; letter-spacing: .03em; }
.kpi-value { color: #111827; font-size: 1.85rem; font-weight: 800; margin-top: 4px; }
.kpi-sub { color: #4B5563; font-size: .88rem; margin-top: 4px; }
.small-note { color: #6B7280; font-size: .88rem; }
.stButton>button { border-radius: 12px; font-weight: 700; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def svg_to_data_uri(path: Path) -> str:
    if path.exists():
        encoded = base64.b64encode(path.read_bytes()).decode()
        return f"data:image/svg+xml;base64,{encoded}"
    return ""


def find_logo_png():
    for p in LOGO_PNG_CANDIDATES:
        if p.exists():
            return p
    return None


logo_uri = svg_to_data_uri(LOGO_SVG_PATH)
logo_html = (
    f'<img src="{logo_uri}" style="height:44px; margin-bottom:14px; background:white; padding:8px 10px; border-radius:12px;" />'
    if logo_uri
    else "<div style='font-weight:800; color:#FFC300; margin-bottom:14px;'>TrackableMed</div>"
)

st.markdown(f"""
<div class="hero">
  {logo_html}
  <h1>Freedom Growth Economics Simulator</h1>
  <p>Translate Curonix Freedom PNS growth goals into physician revenue, ASC contribution margin, payback, and ROI.</p>
</div>
""", unsafe_allow_html=True)

MEDICARE_SINGLE_TRIAL = 2236
MEDICARE_DUAL_TRIAL = 3354
MEDICARE_SINGLE_IMPLANT_PRO = 563
MEDICARE_DUAL_IMPLANT_PRO = 711
ASC_SINGLE_REIMB = 21999
ASC_DUAL_REIMB = 27774

with st.sidebar:
    st.header("Practice Inputs")
    current_implants = st.number_input("Current permanent implants / month", min_value=0.0, max_value=200.0, value=4.0, step=1.0)
    target_implants = st.number_input("Target permanent implants / month", min_value=0.0, max_value=250.0, value=10.0, step=1.0)
    current_trials = st.number_input("Current trials / month", min_value=0.0, max_value=300.0, value=8.0, step=1.0)
    two_lead_mix = st.slider("Two-lead implant / trial mix", 0, 100, 50, 5) / 100
    commercial_mix = st.slider("Commercial payer mix", 0, 100, 50, 5) / 100
    commercial_multiplier = st.slider("Commercial reimbursement multiplier vs Medicare", 100, 200, 130, 5) / 100
    asc_ownership = st.slider("Physician / group ASC ownership", 0, 100, 100, 5) / 100

    st.header("Marketing Inputs")
    media_budget = st.slider("Monthly ad budget client pays directly to the selected Advertising Platforms", 5000, 75000, 15000, 2500)
    tm_fee = st.number_input("TrackableMed monthly fee", min_value=0, max_value=50000, value=10000, step=1000)
    cost_per_lead = st.number_input("Estimated qualified lead cost", min_value=25, max_value=2000, value=150, step=25)

    st.header("Funnel Inputs")
    lead_to_schedule = st.slider("Lead → consult scheduled", 10, 100, 50, 5) / 100
    schedule_to_complete = st.slider("Scheduled consult → completed consult", 10, 100, 75, 5) / 100
    consult_to_candidate = st.slider("Completed consult → trial candidate", 10, 100, 50, 5) / 100
    candidate_to_trial = st.slider("Trial candidate → trial performed", 10, 100, 80, 5) / 100
    trial_to_implant = st.slider("Trial → permanent implant", 10, 100, 65, 5) / 100

    st.header("ASC Cost Inputs")
    single_implant_cost = st.number_input("1-lead implant/device + case cost", min_value=0, max_value=50000, value=12000, step=500)
    dual_implant_cost = st.number_input("2-lead implant/device + case cost", min_value=0, max_value=60000, value=16000, step=500)

incremental_implants = max(target_implants - current_implants, 0)
monthly_investment = media_budget + tm_fee
payer_multiplier = (1 - commercial_mix) * 1.0 + commercial_mix * commercial_multiplier

avg_trial_revenue = ((1 - two_lead_mix) * MEDICARE_SINGLE_TRIAL + two_lead_mix * MEDICARE_DUAL_TRIAL) * payer_multiplier
avg_implant_pro_revenue = ((1 - two_lead_mix) * MEDICARE_SINGLE_IMPLANT_PRO + two_lead_mix * MEDICARE_DUAL_IMPLANT_PRO) * payer_multiplier
avg_physician_revenue_per_pathway = avg_trial_revenue + avg_implant_pro_revenue

avg_asc_reimbursement = ((1 - two_lead_mix) * ASC_SINGLE_REIMB + two_lead_mix * ASC_DUAL_REIMB) * payer_multiplier
avg_asc_cost = (1 - two_lead_mix) * single_implant_cost + two_lead_mix * dual_implant_cost
avg_asc_margin = max(avg_asc_reimbursement - avg_asc_cost, 0) * asc_ownership

monthly_physician_revenue = incremental_implants * avg_physician_revenue_per_pathway
monthly_asc_profit = incremental_implants * avg_asc_margin
monthly_total_economics = monthly_physician_revenue + monthly_asc_profit
net_monthly_gain = monthly_total_economics - monthly_investment
roi_multiple = monthly_total_economics / monthly_investment if monthly_investment else 0
payback_months = monthly_investment / monthly_total_economics if monthly_total_economics > 0 else None
annual_opportunity = monthly_total_economics * 12

leads_generated = media_budget / cost_per_lead if cost_per_lead else 0
completed_consults = leads_generated * lead_to_schedule * schedule_to_complete
trials_generated = completed_consults * consult_to_candidate * candidate_to_trial
implants_from_marketing = trials_generated * trial_to_implant

combined_value_per_pathway = avg_physician_revenue_per_pathway + avg_asc_margin
break_even_implants = monthly_investment / combined_value_per_pathway if combined_value_per_pathway > 0 else 0
break_even_trials = break_even_implants / trial_to_implant if trial_to_implant else 0
break_even_consults = break_even_trials / (consult_to_candidate * candidate_to_trial) if consult_to_candidate * candidate_to_trial else 0
break_even_leads = break_even_consults / (lead_to_schedule * schedule_to_complete) if lead_to_schedule * schedule_to_complete else 0
max_allowable_cpl = monthly_investment / break_even_leads if break_even_leads else 0

fmt_money = lambda x: f"${x:,.0f}"
fmt_num = lambda x: f"{x:,.1f}"

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Incremental Implants</div><div class='kpi-value'>{fmt_num(incremental_implants)}/mo</div><div class='kpi-sub'>Target minus current volume</div></div>", unsafe_allow_html=True)
with k2:
    st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Monthly Economics</div><div class='kpi-value'>{fmt_money(monthly_total_economics)}</div><div class='kpi-sub'>Physician revenue + ASC margin</div></div>", unsafe_allow_html=True)
with k3:
    st.markdown(f"<div class='kpi-card'><div class='kpi-label'>ROI Multiple</div><div class='kpi-value'>{roi_multiple:.1f}x</div><div class='kpi-sub'>Before income tax or distributions</div></div>", unsafe_allow_html=True)
with k4:
    payback_text = f"{payback_months:.1f} mo" if payback_months else "N/A"
    st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Payback Period</div><div class='kpi-value'>{payback_text}</div><div class='kpi-sub'>Based on monthly economics</div></div>", unsafe_allow_html=True)

st.divider()

left, right = st.columns([1.05, 0.95])
with left:
    st.subheader("Economic Output")
    df = pd.DataFrame({
        "Metric": [
            "Incremental physician professional revenue / month",
            "Incremental ASC contribution margin / month",
            "Combined monthly economics",
            "Monthly TrackableMed + media investment",
            "Net monthly gain after investment",
            "Annualized growth opportunity",
        ],
        "Value": [
            fmt_money(monthly_physician_revenue),
            fmt_money(monthly_asc_profit),
            fmt_money(monthly_total_economics),
            fmt_money(monthly_investment),
            fmt_money(net_monthly_gain),
            fmt_money(annual_opportunity),
        ],
    })
    st.dataframe(df, hide_index=True, use_container_width=True)

    st.subheader("Break-Even Thresholds")
    be_df = pd.DataFrame({
        "Break-even Requirement": ["Implant pathways", "Trials", "Completed consults", "Qualified leads", "Maximum allowable lead cost"],
        "Monthly Amount": [fmt_num(break_even_implants), fmt_num(break_even_trials), fmt_num(break_even_consults), fmt_num(break_even_leads), fmt_money(max_allowable_cpl)],
    })
    st.dataframe(be_df, hide_index=True, use_container_width=True)

with right:
    st.subheader("Funnel Forecast From Media Budget")
    funnel_labels = ["Leads", "Completed Consults", "Trials", "Implants"]
    funnel_values = [leads_generated, completed_consults, trials_generated, implants_from_marketing]
    fig = go.Figure(go.Funnel(y=funnel_labels, x=funnel_values, textinfo="value+percent initial"))
    fig.update_layout(height=390, margin=dict(l=10, r=10, t=20, b=10))
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Scenario Comparison")
scenario_implants = [max(incremental_implants * 0.5, 1), incremental_implants, incremental_implants * 1.5]
scenario_names = ["Conservative", "Target", "Aggressive"]
scenario_values = [x * combined_value_per_pathway for x in scenario_implants]
fig2 = go.Figure(data=[go.Bar(x=scenario_names, y=scenario_values, text=[fmt_money(v) for v in scenario_values], textposition="auto")])
fig2.update_layout(yaxis_title="Monthly Economics", height=330, margin=dict(l=10, r=10, t=20, b=10))
st.plotly_chart(fig2, use_container_width=True)

st.subheader("Meeting Follow-Up Summary")
summary = f"""
Based on the current model, moving from {current_implants:.0f} to {target_implants:.0f} Freedom PNS permanent implants per month would create approximately {fmt_money(monthly_physician_revenue)} in incremental monthly physician professional revenue and {fmt_money(monthly_asc_profit)} in incremental monthly ASC contribution margin, adjusted for the selected ASC ownership percentage. The combined monthly economic opportunity is approximately {fmt_money(monthly_total_economics)}, compared with a monthly growth investment of {fmt_money(monthly_investment)}. The model suggests a payback period of {payback_text} and an ROI multiple of {roi_multiple:.1f}x. Break-even requires approximately {break_even_implants:.1f} additional implant pathways per month, supported by roughly {break_even_trials:.1f} trials, {break_even_consults:.1f} completed consults, and {break_even_leads:.1f} qualified leads under the selected conversion assumptions.
""".strip()
st.text_area("Copy-ready summary", summary, height=180)

# PDF report helpers
TM_DARK = colors.HexColor("#111827")
TM_YELLOW = colors.HexColor("#FFC300")
TM_GRAY = colors.HexColor("#F9FAFB")
TM_BORDER = colors.HexColor("#E5E7EB")
TM_TEXT = colors.HexColor("#111827")
TM_MUTED = colors.HexColor("#6B7280")

def _footer(canvas_obj: canvas.Canvas, doc):
    page_w, page_h = letter
    canvas_obj.saveState()
    footer_y = 0.44 * inch
    canvas_obj.setStrokeColor(TM_BORDER)
    canvas_obj.setLineWidth(0.7)
    canvas_obj.line(0.55 * inch, footer_y + 0.18 * inch, page_w - 0.55 * inch, footer_y + 0.18 * inch)
    canvas_obj.setFont("Helvetica-Bold", 8)
    canvas_obj.setFillColor(TM_TEXT)
    canvas_obj.drawString(0.55 * inch, footer_y, "Prepared by TrackableMed")
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.drawString(2.0 * inch, footer_y, "www.trackablemed.com")
    canvas_obj.setFont("Helvetica", 7.5)
    canvas_obj.setFillColor(TM_MUTED)
    canvas_obj.drawRightString(page_w - 0.55 * inch, footer_y, f"Page {doc.page}")
    canvas_obj.restoreState()

def _make_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("HeaderTitle", fontName="Helvetica-Bold", fontSize=15.5, leading=17.5, textColor=TM_TEXT, alignment=TA_RIGHT))
    styles.add(ParagraphStyle("HeaderSubtitle", fontName="Helvetica", fontSize=8.2, leading=9.8, textColor=colors.HexColor("#4B5563"), alignment=TA_RIGHT))
    styles.add(ParagraphStyle("HeaderDate", fontName="Helvetica", fontSize=7.5, leading=9, textColor=TM_MUTED, alignment=TA_RIGHT))
    styles.add(ParagraphStyle("KPILabel", fontName="Helvetica-Bold", fontSize=6.5, leading=8, textColor=TM_MUTED))
    styles.add(ParagraphStyle("KPIValue", fontName="Helvetica-Bold", fontSize=15, leading=17, textColor=TM_TEXT))
    styles.add(ParagraphStyle("KPISub", fontName="Helvetica", fontSize=6.7, leading=8, textColor=colors.HexColor("#4B5563")))
    styles.add(ParagraphStyle("Section", fontName="Helvetica-Bold", fontSize=11, leading=13, textColor=TM_TEXT, spaceBefore=8, spaceAfter=5))
    styles.add(ParagraphStyle("Summary", fontName="Helvetica", fontSize=8, leading=10.2, textColor=TM_TEXT))
    styles.add(ParagraphStyle("Disclaimer", fontName="Helvetica", fontSize=7.2, leading=9, textColor=TM_MUTED))
    styles.add(ParagraphStyle("ChartInside", fontName="Helvetica-Bold", fontSize=7.8, leading=9, textColor=TM_TEXT, alignment=TA_CENTER))
    styles.add(ParagraphStyle("ChartCaption", fontName="Helvetica", fontSize=7.5, leading=9, textColor=TM_TEXT, alignment=TA_CENTER))
    return styles

def _header_block(styles):
    """White branded PDF header matching the Streamlit app hero copy."""
    logo_path = find_logo_png()
    if logo_path:
        logo = Image(str(logo_path), width=2.35 * inch, height=0.45 * inch)
    else:
        logo = Paragraph("TrackableMed", ParagraphStyle("logo_text", fontName="Helvetica-Bold", fontSize=18, textColor=colors.HexColor("#1F77B4")))

    title = Paragraph("Freedom Growth Economics Simulator", styles["HeaderTitle"])
    subtitle = Paragraph(
        "Translate Curonix Freedom PNS growth goals into physician revenue, ASC contribution margin, payback, and ROI.",
        styles["HeaderSubtitle"]
    )
    date_text = Paragraph(datetime.now().strftime("%B %d, %Y"), styles["HeaderDate"])

    header_content = Table(
        [[logo, [title, subtitle, date_text]]],
        colWidths=[2.55 * inch, 4.25 * inch],
        rowHeights=[0.68 * inch],
    )
    header_content.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, 0), 0),
        ("RIGHTPADDING", (1, 0), (1, 0), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    accent_rule = Table([[""]], colWidths=[6.8 * inch], rowHeights=[0.045 * inch])
    accent_rule.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), TM_YELLOW),
        ("BOX", (0, 0), (-1, -1), 0, TM_YELLOW),
    ]))

    wrapper = Table([[header_content], [accent_rule]], colWidths=[6.8 * inch])
    wrapper.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return wrapper

def _kpi_card(label, value, subtext, styles):
    rows = [
        [Paragraph(label.upper(), styles["KPILabel"])],
        [Paragraph(value, styles["KPIValue"])],
        [Paragraph(subtext, styles["KPISub"])],
    ]
    t = Table(rows, colWidths=[1.58 * inch], rowHeights=[0.20 * inch, 0.36 * inch, 0.24 * inch])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.7, TM_BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t

def _styled_table(headers, rows, widths):
    data = [headers] + rows
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TM_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8.2),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D1D5DB")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, TM_GRAY]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ALIGN", (1, 1), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t

def _funnel_pdf_chart(labels, values, styles):
    max_val = max(values) if values else 1
    rows = []
    max_width = 4.05 * inch
    min_width = 1.20 * inch
    for label, value in zip(labels, values):
        width = min_width + ((value / max_val) * (max_width - min_width) if max_val else 0)
        bar = Table([[Paragraph(f"{label}: {fmt_num(value)}", styles["ChartInside"])]], colWidths=[width], rowHeights=[0.28 * inch])
        bar.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), TM_YELLOW),
            ("BOX", (0, 0), (-1, -1), 0.2, TM_YELLOW),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        rows.append([bar])
    t = Table(rows, colWidths=[4.25 * inch])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.7, TM_BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t

def _vertical_bar_chart(labels, values, styles):
    max_val = max(values) if values else 1
    max_height = 1.35 * inch
    bars = []
    captions = []
    for label, value in zip(labels, values):
        bar_height = max(0.12 * inch, (value / max_val) * max_height)
        spacer_height = max_height - bar_height
        bar = Table([[""], [""]], colWidths=[1.3 * inch], rowHeights=[spacer_height, bar_height])
        bar.setStyle(TableStyle([
            ("BACKGROUND", (0, 1), (0, 1), TM_YELLOW),
            ("BOX", (0, 1), (0, 1), 0.2, TM_YELLOW),
        ]))
        bars.append(bar)
        captions.append(Paragraph(f"<b>{label}</b><br/>{fmt_money(value)}", styles["ChartCaption"]))
    t = Table([bars, captions], colWidths=[1.45 * inch, 1.45 * inch, 1.45 * inch])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.7, TM_BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, 0), "BOTTOM"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t

def build_pdf() -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.45 * inch,
        bottomMargin=0.75 * inch,
    )
    styles = _make_styles()
    story = []
    story.append(_header_block(styles))
    story.append(Spacer(1, 0.12 * inch))

    kpis = [
        _kpi_card("Incremental Implants", f"{fmt_num(incremental_implants)}/mo", "Target minus current volume", styles),
        _kpi_card("Monthly Economics", fmt_money(monthly_total_economics), "Physician revenue + ASC margin", styles),
        _kpi_card("ROI Multiple", f"{roi_multiple:.1f}x", "Before income tax or distributions", styles),
        _kpi_card("Payback Period", payback_text, "Based on monthly economics", styles),
    ]
    kpi_table = Table([kpis], colWidths=[1.7 * inch, 1.7 * inch, 1.7 * inch, 1.7 * inch])
    kpi_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(kpi_table)
    story.append(Spacer(1, 0.12 * inch))

    econ_rows = [
        ["Incremental physician professional revenue / month", fmt_money(monthly_physician_revenue)],
        ["Incremental ASC contribution margin / month", fmt_money(monthly_asc_profit)],
        ["Combined monthly economics", fmt_money(monthly_total_economics)],
        ["Monthly TrackableMed + media investment", fmt_money(monthly_investment)],
        ["Net monthly gain after investment", fmt_money(net_monthly_gain)],
        ["Annualized growth opportunity", fmt_money(annual_opportunity)],
    ]
    be_rows = [
        ["Implant pathways", fmt_num(break_even_implants)],
        ["Trials", fmt_num(break_even_trials)],
        ["Completed consults", fmt_num(break_even_consults)],
        ["Qualified leads", fmt_num(break_even_leads)],
        ["Maximum allowable lead cost", fmt_money(max_allowable_cpl)],
    ]

    story.append(Paragraph("Economic Output", styles["Section"]))
    story.append(_styled_table(["Metric", "Value"], econ_rows, [4.85 * inch, 1.95 * inch]))
    story.append(Spacer(1, 0.10 * inch))
    story.append(Paragraph("Break-Even Thresholds", styles["Section"]))
    story.append(_styled_table(["Break-even Requirement", "Monthly Amount"], be_rows, [4.85 * inch, 1.95 * inch]))

    story.append(PageBreak())
    story.append(_header_block(styles))
    story.append(Spacer(1, 0.12 * inch))
    story.append(Paragraph("Funnel Forecast From Media Budget", styles["Section"]))
    story.append(_funnel_pdf_chart(funnel_labels, funnel_values, styles))
    story.append(Spacer(1, 0.14 * inch))
    story.append(Paragraph("Scenario Comparison", styles["Section"]))
    story.append(_vertical_bar_chart(scenario_names, scenario_values, styles))
    story.append(Spacer(1, 0.14 * inch))

    story.append(Paragraph("Meeting Follow-Up Summary", styles["Section"]))
    summary_box = Table([[Paragraph(summary, styles["Summary"])]], colWidths=[6.8 * inch])
    summary_box.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.7, TM_BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), TM_GRAY),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(summary_box)
    story.append(Spacer(1, 0.10 * inch))

    disclaimer = (
        "Compliance/planning disclaimer: This calculator is for business planning only and does not constitute "
        "reimbursement, coding, legal, financial, tax, or compliance advice. Payer coverage, coding, medical necessity, "
        "documentation, contract terms, device pricing, and final payment amounts must be verified by the provider and ASC."
    )
    disclaimer_box = Table([[Paragraph(disclaimer, styles["Disclaimer"])]], colWidths=[6.8 * inch])
    disclaimer_box.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.7, TM_BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(disclaimer_box)

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()

st.download_button(
    "Download Executive Dashboard PDF",
    data=build_pdf(),
    file_name="Freedom_Growth_Economics_Dashboard_Report.pdf",
    mime="application/pdf",
)

st.markdown("""
<div class="small-note">
Assumptions are editable and intended for planning conversations only. Medicare national average reimbursement values are used as the default baseline. Commercial payer assumptions should be replaced with actual contracted reimbursement where available.
</div>
""", unsafe_allow_html=True)
