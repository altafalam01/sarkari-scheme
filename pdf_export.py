"""
PDF report generator - fpdf2 based.
"""

from fpdf import FPDF
from fpdf.enums import XPos, YPos
import datetime


def _clean(text):
    text = str(text).replace("₹", "Rs.")
    return text.encode("latin-1", "replace").decode("latin-1")


def build_pdf(results, profile=None):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Sarkari Scheme - Search Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(120, 120, 120)
    generated = datetime.datetime.now().strftime("%d-%m-%Y %H:%M")
    pdf.cell(0, 7, f"Generated on: {generated}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    if profile:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, "Search Profile:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 10)
        for key, value in profile.items():
            pdf.cell(0, 6, _clean(f"{key}: {value}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(3)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, f"Total Schemes Found: {len(results)}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    for r in results:
        status = ""
        if "eligible" in r:
            status = "  [ELIGIBLE]" if r["eligible"] else "  [NOT ELIGIBLE]"

        pdf.set_font("Helvetica", "B", 12)
        pdf.multi_cell(0, 7, _clean(r["scheme_name"] + status), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, _clean(f"Category: {r['category_type']}   |   State: {r['applicable_state']}"),
                        new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.multi_cell(0, 6, _clean(f"What is it: {r['description']}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.multi_cell(0, 6, _clean(f"Benefit: {r['benefits']}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.multi_cell(0, 6, _clean(f"Apply / Official Site: {r['apply_link']}"),
                        new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.ln(2)
        y = pdf.get_y()
        pdf.set_draw_color(210, 210, 210)
        pdf.line(10, y, 200, y)
        pdf.ln(4)

    raw = pdf.output()
    if isinstance(raw, str):
        return raw.encode("latin-1")
    return bytes(raw)


if __name__ == "__main__":
    sample = [{
        "scheme_name": "PM Kisan Samman Nidhi",
        "category_type": "Agriculture",
        "applicable_state": "All",
        "description": "Income support for farmers",
        "benefits": "Rs 6000 per year",
        "apply_link": "https://pmkisan.gov.in",
        "eligible": True,
    }]
    data = build_pdf(sample, profile={"Age": 25, "State": "Madhya Pradesh"})
    with open("test_report.pdf", "wb") as f:
        f.write(data)
    print("PDF generated:", len(data), "bytes")