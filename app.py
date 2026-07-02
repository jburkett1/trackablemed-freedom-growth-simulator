import base64
from io import BytesIO
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from reportlab.lib import colors
from datetime import datetime
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

APP_DIR = Path(__file__).parent
LOGO_PATH = APP_DIR / "assets" / "trackablemed_logo.svg"
LOGO_PNG_PATH = APP_DIR / "assets" / "trackablemed_logo.png"

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

logo_uri = svg_to_data_uri(LOGO_PATH)
logo_html = f'<img src="{logo_uri}" style="height:44px; margin-bottom:14px; background:white; padding:8px 10px; border-radius:12px;" />' if logo_uri else ""

st.markdown(f"""
<div class="hero">
  {logo_html}
  <h1>Freedom Growth Economics Simulator</h1>
  <p>Translate Curonix Freedom PNS growth goals into physician revenue, ASC contribution margin, payback, and ROI.</p>
</div>
""", unsafe_allow_html=True)

# Baseline reimbursement assumptions from Curonix guide.
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

left, right = st.columns([1.05, .95])
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


def _pdf_footer(canvas_obj: canvas.Canvas, doc):
    """Draw a TrackableMed footer and planning disclaimer on every PDF page."""
    page_w, page_h = landscape(letter)
    canvas_obj.saveState()
    canvas_obj.setStrokeColor(colors.HexColor("#E5E7EB"))
    canvas_obj.setLineWidth(0.7)
    canvas_obj.line(0.45 * inch, 0.52 * inch, page_w - 0.45 * inch, 0.52 * inch)
    canvas_obj.setFillColor(colors.HexColor("#111827"))
    canvas_obj.setFont("Helvetica-Bold", 8.5)
    canvas_obj.drawString(0.50 * inch, 0.35 * inch, "Prepared by TrackableMed")
    canvas_obj.setFont("Helvetica", 8.5)
    canvas_obj.drawString(2.10 * inch, 0.35 * inch, "www.trackablemed.com")
    canvas_obj.setFillColor(colors.HexColor("#6B7280"))
    canvas_obj.setFont("Helvetica", 7.2)
    canvas_obj.drawRightString(page_w - 0.50 * inch, 0.35 * inch, f"Page {doc.page}")
    disclaimer = (
        "Planning note: This calculator is for business planning only and does not constitute reimbursement, coding, legal, or compliance advice. "
        "Payer coverage, coding, medical necessity, documentation, contract terms, device pricing, and final payment amounts must be verified by the provider and ASC."
    )
    canvas_obj.drawString(0.50 * inch, 0.18 * inch, disclaimer[:205] + "...")
    canvas_obj.restoreState()


def _kpi_card(label: str, value: str, subtext: str):
    label_style = ParagraphStyle("kpi_label", fontName="Helvetica-Bold", fontSize=7.3, textColor=colors.HexColor("#6B7280"), leading=9)
    value_style = ParagraphStyle("kpi_value", fontName="Helvetica-Bold", fontSize=17.5, textColor=colors.HexColor("#111827"), leading=20)
    sub_style = ParagraphStyle("kpi_sub", fontName="Helvetica", fontSize=7.3, textColor=colors.HexColor("#4B5563"), leading=9)
    t = Table(
        [[Paragraph(label.upper(), label_style)], [Paragraph(value, value_style)], [Paragraph(subtext, sub_style)]],
        colWidths=[2.46 * inch],
        rowHeights=[0.17 * inch, 0.32 * inch, 0.24 * inch],
    )
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#E5E7EB")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _styled_table(headers, rows, col_widths):
    t = Table([headers] + rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8.2),
        ("FONTSIZE", (0, 1), (-1, -1), 7.9),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D1D5DB")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _bar_chart(title, labels, values):
    max_val = max(values) if values else 1
    title_style = ParagraphStyle("chart_title", fontName="Helvetica-Bold", fontSize=9.2, textColor=colors.HexColor("#111827"))
    label_style = ParagraphStyle("bar_label", fontName="Helvetica", fontSize=7.6, textColor=colors.HexColor("#374151"))
    value_style = ParagraphStyle("bar_value", fontName="Helvetica-Bold", fontSize=7.6, textColor=colors.HexColor("#111827"), alignment=TA_RIGHT)
    rows = [[Paragraph(title, title_style), "", ""]]
    for label, value in zip(labels, values):
        width = max(0.05, value / max_val) * 2.65 * inch if max_val else 0.05 * inch
        bar = Table([[""]], colWidths=[width], rowHeights=[0.16 * inch])
        bar.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFC300")), ("BOX", (0, 0), (-1, -1), 0.2, colors.HexColor("#FFC300"))]))
        display = fmt_money(value) if value >= 1000 else fmt_num(value)
        rows.append([Paragraph(label, label_style), bar, Paragraph(display, value_style)])
    t = Table(rows, colWidths=[1.35 * inch, 2.70 * inch, 0.70 * inch])
    t.setStyle(TableStyle([
        ("SPAN", (0, 0), (-1, 0)),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#E5E7EB")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 1), (-1, -1), "MIDDLE"),
    ]))
    return t


def build_pdf() -> bytes:
    """Build a branded, dashboard-style PDF report."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=0.45 * inch,
        leftMargin=0.45 * inch,
        topMargin=0.42 * inch,
        bottomMargin=0.72 * inch,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("tm_title", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=18, leading=21, textColor=colors.white, alignment=TA_RIGHT, spaceAfter=0)
    subtitle_style = ParagraphStyle("tm_subtitle", parent=styles["Normal"], fontName="Helvetica", fontSize=8.4, leading=10, textColor=colors.HexColor("#E5E7EB"), alignment=TA_RIGHT)
    summary_style = ParagraphStyle("summary", parent=styles["BodyText"], fontName="Helvetica", fontSize=8.2, leading=10.2, textColor=colors.HexColor("#111827"))
    section_style = ParagraphStyle("section", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=10.5, textColor=colors.HexColor("#111827"), spaceBefore=7, spaceAfter=4)
    small_style = ParagraphStyle("small", parent=styles["Normal"], fontName="Helvetica", fontSize=7.7, leading=9.0, textColor=colors.HexColor("#6B7280"))

    story = []

    if LOGO_PNG_PATH.exists():
        logo = Image(str(LOGO_PNG_PATH), width=1.75 * inch, height=0.55 * inch)
    else:
        logo = Paragraph("TrackableMed", ParagraphStyle("logo_text", fontName="Helvetica-Bold", fontSize=18, textColor=colors.HexColor("#FFC300")))

    date_text = datetime.now().strftime("%B %d, %Y")
    header_right = [
        Paragraph("Freedom Growth Economics Report", title_style),
        Paragraph(f"Prepared for physician-owned ASC growth discussion  |  {date_text}", subtitle_style),
    ]
    header_table = Table([[logo, header_right]], colWidths=[3.0 * inch, 7.0 * inch], rowHeights=[0.74 * inch])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#111827")),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#111827")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, 0), 16),
        ("RIGHTPADDING", (1, 0), (1, 0), 16),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.10 * inch))

    kpi_wrap = Table([[
        _kpi_card("Incremental Implants", f"{fmt_num(incremental_implants)}/mo", "Target minus current volume"),
        _kpi_card("Monthly Economics", fmt_money(monthly_total_economics), "Physician revenue + ASC margin"),
        _kpi_card("ROI Multiple", f"{roi_multiple:.1f}x", "Before income tax or distributions"),
        _kpi_card("Payback Period", payback_text, "Based on monthly economics"),
    ]], colWidths=[2.5 * inch, 2.5 * inch, 2.5 * inch, 2.5 * inch])
    kpi_wrap.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(kpi_wrap)
    story.append(Spacer(1, 0.09 * inch))

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
    econ_table = _styled_table(["Economic Output", "Value"], econ_rows, [3.25 * inch, 1.25 * inch])
    be_table = _styled_table(["Break-Even Thresholds", "Monthly Amount"], be_rows, [2.95 * inch, 1.35 * inch])
    funnel_chart = _bar_chart("Funnel Forecast From Media Budget", funnel_labels, funnel_values)

    mid_row = Table([[econ_table, be_table, funnel_chart]], colWidths=[3.55 * inch, 3.30 * inch, 3.18 * inch])
    mid_row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]))
    story.append(mid_row)
    story.append(Spacer(1, 0.10 * inch))

    story.append(_bar_chart("Scenario Comparison", scenario_names, scenario_values))
    story.append(Spacer(1, 0.08 * inch))

    story.append(Paragraph("Meeting Follow-Up Summary", section_style))
    summary_table = Table([[Paragraph(summary, summary_style)]], colWidths=[10.04 * inch])
    summary_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#E5E7EB")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 0.06 * inch))
    story.append(Paragraph("Prepared by TrackableMed | www.trackablemed.com", small_style))

    doc.build(story, onFirstPage=_pdf_footer, onLaterPages=_pdf_footer)
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
