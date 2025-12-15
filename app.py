import os
import io
import tempfile
import zipfile
import re
from datetime import datetime

from flask import Flask, request, send_file, render_template_string
import pdfplumber
from PyPDF2 import PdfReader, PdfWriter

app = Flask(__name__)

# === Mapping of account codes to apartment numbers ===
code_to_apartment = {
    'DT00721': '321', 'DT00722': '322', 'DT00723': '323',
    'DT00821': '221', 'DT00822': '222', 'DT00823': '223', 'DT00824': '224',
    'DT00831': '231', 'DT00832': '232', 'DT00833': '233', 'DT00834': '234',
    'DT00835': '235', 'DT00836': '236', 'DT00837': '237',
    'DT00841': '241', 'DT00842': '242', 'DT00843': '243', 'DT00844': '244',
    'DT00845': '245', 'DT00846': '246', 'DT00847': '247', 'DT00848': '248',
    'DT00849': '249', 'DT00851': '251', 'DT00852': '252', 'DT00853': '253',
    'DT00854': '254', 'DT00855': '255', 'DT00856': '256', 'DT00857': '257',
    'DT00858': '258', 'DT00861': '261', 'DT00862': '262', 'DT00863': '263',
    'DT00864': '264', 'DT00865': '265',
    'DT00911': '111', 'DT00921': '121', 'DT00922': '122',
    'DT00931': '131', 'DT00932': '132', 'DT00933': '133',
    'DT00941': '141', 'DT00942': '142', 'DT00943': '143', 'DT00944': '144',
    'DT00945': '145', 'DT00946': '146', 'DT00951': '151', 'DT00952': '152',
    'DT00953': '153', 'DT00954': '154', 'DT00955': '155',
    'DT00961': '161', 'DT00962': '162', 'DT00963': '163',
    'DT00964': '164', 'DT00965': '165'
}

def extract_month_from_text(text):
    dates = re.findall(r'\b\d{2}/\d{2}/\d{4}\b', text)
    if dates:
        try:
            date_objs = [datetime.strptime(d, '%d/%m/%Y') for d in dates]
            return min(date_objs).strftime("%B'%y")
        except Exception:
            pass
    return "Unknown"

def split_statements(pdf_path, output_dir):
    used_names = {}
    with pdfplumber.open(pdf_path) as pdf:
        reader = PdfReader(pdf_path)

        i = 0
        while i < len(pdf.pages):
            text = pdf.pages[i].extract_text()
            if not text:
                i += 1
                continue

            for code, apt in code_to_apartment.items():
                if code in text:
                    writer = PdfWriter()
                    writer.add_page(reader.pages[i])

                    combined = text
                    if i + 1 < len(pdf.pages):
                        next_text = pdf.pages[i + 1].extract_text()
                        if next_text and not any(c in next_text for c in code_to_apartment):
                            writer.add_page(reader.pages[i + 1])
                            combined += "\n" + next_text
                            i += 1

                    month = extract_month_from_text(combined)
                    base = f"Apt {apt}-Tvl-{month}"
                    count = used_names.get(base, 0)
                    used_names[base] = count + 1

                    suffix = f"_{count + 1}" if count else ""
                    filename = f"{base}{suffix}.pdf"

                    with open(os.path.join(output_dir, filename), "wb") as f:
                        writer.write(f)
                    break

            i += 1

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        pdf_file = request.files.get("pdf")
        if not pdf_file:
            return "No file uploaded", 400

        with tempfile.TemporaryDirectory() as tmp:
            input_path = os.path.join(tmp, pdf_file.filename)
            pdf_file.save(input_path)

            split_statements(input_path, tmp)

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as z:
                for f in os.listdir(tmp):
                    if f.endswith(".pdf"):
                        z.write(os.path.join(tmp, f), f)

            zip_buffer.seek(0)
            return send_file(
                zip_buffer,
                as_attachment=True,
                download_name="TVL_Statements.zip"
            )

    return render_template_string("""
    <h2>TVL Statement PDF Generator</h2>
    <form method="post" enctype="multipart/form-data">
        <input type="file" name="pdf" accept=".pdf" required><br><br>
        <button type="submit">Generate PDFs</button>
    </form>
    """)



