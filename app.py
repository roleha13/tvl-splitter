import os
import io
import tempfile  # For temporary server-side folders
import zipfile  # For zipping output PDFs
import asyncio  # For async processing
from datetime import datetime
import re
from nicegui import ui, events  # Main NiceGUI import
import pdfplumber
from PyPDF2 import PdfReader, PdfWriter

# === Mapping of account codes to apartment numbers (unchanged) ===
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
    'DT00961': '161', 'DT00962': '162', 'DT00963': '163', 'DT00964': '164', 'DT00965': '165'
}

# === Extract month name from earliest date in text (unchanged) ===
def extract_month_from_text(text):
    dates = re.findall(r'\b\d{2}/\d{2}/\d{4}\b', text)
    if dates:
        try:
            date_objs = [datetime.strptime(date, '%d/%m/%Y') for date in dates]
            first_date = min(date_objs)
            return first_date.strftime("%B'%y")  # e.g., February'25
        except Exception:
            pass
    return "Unknown"

# === PDF splitting logic (mostly unchanged, but added async for web) ===
async def split_statements(pdf_path, output_dir, progress):
    used_filenames = {}
    with pdfplumber.open(pdf_path) as pdf:
        reader = PdfReader(pdf_path)
        total = len(pdf.pages)
        i = 0

        while i < total:
            text = pdf.pages[i].extract_text()
            if not text:
                i += 1
                continue

            found = False
            for code, apt_num in code_to_apartment.items():
                if code in text:
                    writer = PdfWriter()
                    writer.add_page(reader.pages[i])

                    # Add second page if it doesn't contain another code
                    combined_text = text
                    if i + 1 < total:
                        next_text = pdf.pages[i + 1].extract_text()
                        if next_text and not any(c in next_text for c in code_to_apartment):
                            writer.add_page(reader.pages[i + 1])
                            combined_text += "\n" + next_text
                            i += 1

                    month_label = extract_month_from_text(combined_text)
                    base_name = f"Apt {apt_num}-Tvl-{month_label}"

                    count = used_filenames.get(base_name, 0)
                    used_filenames[base_name] = count + 1
                    suffix = f"_{count + 1}" if count else ""
                    file_name = f"{base_name}{suffix}.pdf"

                    output_path = os.path.join(output_dir, file_name)
                    with open(output_path, "wb") as f_out:
                        writer.write(f_out)

                    found = True
                    break

            # Update progress (reactive in NiceGUI)
            progress.set_value((i + 1) / total)
            await asyncio.sleep(0)  # Yield to keep UI responsive

            i += 1 if not found else 1

# Will hold the last uploaded PDF
uploaded_pdf = {
    'name': None,   # filename
    'bytes': None,  # file content as bytes
}

# === Main UI Page ===
@ui.page('/')
async def main_page():
    ui.label('TVL Statement PDF Generator').style('font-size: 24px; font-weight: bold;')

    # Upload input for PDF
    async def handle_upload(e: events.UploadEventArguments):
        # Save file in memory so the button can use it later
        uploaded_pdf['name'] = e.file.name
        uploaded_pdf['bytes'] = await e.file.read()   # <-- IMPORTANT: await here
        ui.notify(f'PDF "{e.file.name}" uploaded successfully!', color='positive')

    upload = ui.upload(
        label='Upload TVL Statements PDF',
        on_upload=handle_upload,
    ).props('accept=.pdf')

    progress = ui.linear_progress(value=0).style('width: 100%;')

    # Button to start processing
    async def on_start():
        # 1. Ensure a file was uploaded
        if not uploaded_pdf['bytes']:
            ui.notify('Please upload a PDF file first.', color='negative')
            return

        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # 2. Save uploaded PDF into a temp file
                pdf_filename = uploaded_pdf['name'] or 'input.pdf'
                pdf_path = os.path.join(temp_dir, pdf_filename)

                with open(pdf_path, 'wb') as f:
                    f.write(uploaded_pdf['bytes'])

                progress.set_value(0)

                # 3. Run splitting
                await split_statements(pdf_path, temp_dir, progress)

                # 4. Zip all generated PDFs in memory
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w') as zipf:
                    for file in os.listdir(temp_dir):
                        if file.endswith('.pdf'):
                            zipf.write(os.path.join(temp_dir, file), arcname=file)

                zip_buffer.seek(0)

                # 5. Trigger download
                ui.download(zip_buffer.read(), filename='output_pdfs.zip')
                ui.notify('PDFs generated successfully! Download will start.', color='positive')

            except Exception as e:
                ui.notify(f'An error occurred: {str(e)}', color='negative')

    ui.button('Generate to PDF', on_click=on_start).style('background-color: #007BFF; color: white;')

    # User guide button (replaces open_user_guide)
    async def show_guide():
        dialog = ui.dialog().props('full-width')
        with dialog, ui.card():
            ui.markdown("""
# TVL Statement PDF Generator - User Guide

**Overview**  
This tool extracts apartment statements from a combined PDF.

**Steps to Use:**  
1. Upload the input PDF file (TVL Statements PDF).  
2. Click 'Generate to PDF'.  
3. Progress is shown in the progress bar.  
4. Download the zip file with generated PDFs once done.

**File Naming:**  
- Apt <Number>-Tvl-April'25.pdf  
- Duplicate files get suffixes like _1, _2.

**Troubleshooting:**  
- Ensure PDF has valid account codes.  
- Upload valid PDF.  

**Security:**  
- Processing happens on the server; no data stored permanently.
            """)
        dialog.open()

    ui.button('📘 Open User Guide', on_click=show_guide).style('background-color: #6c757d; color: white;')
app = ui.run(
    title='TVL Statement PDF Generator',
    dark=False,
    reload=False,
    show=False,  # no browser window on the server
    port=int(os.environ.get('PORT', 8080)),  # important for Render
)

