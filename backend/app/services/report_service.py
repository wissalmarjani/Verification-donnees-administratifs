from io import BytesIO
from typing import Dict

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_report_pdf(shipment_reference: str, analysis: Dict[str, object]) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title=f"Analysis {shipment_reference}")
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"Shipment: <b>{shipment_reference}</b>", styles["Title"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Final Status: <b>{analysis['status']}</b>", styles["Heading2"]))
    story.append(Spacer(1, 12))

    table_data = [["Field", "Level", "Message"]]
    for issue in analysis["issues"]:
        table_data.append([issue["field"], issue["level"], issue["message"]])

    if len(table_data) == 1:
        table_data.append(["-", "-", "No inconsistencies found"])

    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
            ]
        )
    )
    story.append(table)
    doc.build(story)
    return buffer.getvalue()
