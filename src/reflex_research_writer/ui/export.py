import io
import tempfile
import pymupdf
from typing import Union, List, Optional
from markdown_pdf import MarkdownPdf, Section


def convert_md_to_pdf(md_text: Union[str, List[str]]) -> Optional[str]:
    """Converts markdown text to a PDF file and returns the file path."""
    if not md_text:
        return None

    # Normalize input: if it's a string, make it a single-item list
    if isinstance(md_text, str):
        md_texts = [md_text]
    else:
        md_texts = md_text

    # Filter out any empty strings or None values to prevent blank pages
    md_texts = [text for text in md_texts if text]

    # If the list was entirely empty strings, exit early
    if not md_texts:
        return None

    # Create a temporary file
    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    temp_pdf.close()

    # Initialize PDF
    pdf = MarkdownPdf(toc_level=2, optimize=True)

    css = """
    p, li { 
        text-align: justify; 
    } 
    a {
        word-break: break-all;
        overflow-wrap: anywhere;
    }
    """

    # Add a separate section for each markdown text chunk
    for text in md_texts:
        section = Section(text, toc=False)
        pdf.add_section(section, user_css=css)

    # Public markdown-pdf API
    buffer = io.BytesIO()
    pdf.save_bytes(buffer)

    # Work entirely in memory from here
    doc = pymupdf.open(stream=buffer.getvalue(), filetype="pdf")

    for page_number, page in enumerate(doc, start=1):
        rect = page.rect

        footer = pymupdf.Rect(
            rect.x0,
            rect.y1 - 30,
            rect.x1,
            rect.y1 - 10,
            )

        page.insert_textbox(
            footer,
            str(page_number),
            fontsize=10,
            align=pymupdf.TEXT_ALIGN_CENTER,
            )

    # Final output
    doc.save(temp_pdf.name)
    doc.close()

    return temp_pdf.name