from pathlib import Path
import pypdfium2 as pdfium


def main():
    pdf_path = Path('PDFs/Edit Salary Cap Draft List Draft Strategy 2025.pdf')
    out_path = Path('PDFs/parsed_edit_salary_cap_pdfium.txt')
    raw = []
    pdf = pdfium.PdfDocument(str(pdf_path))
    n = len(pdf)
    for i in range(n):
        page = pdf.get_page(i)
        textpage = page.get_textpage()
        raw.append(textpage.get_text_range())
        textpage.close()
        page.close()
    del pdf
    out_path.write_text('\n\n'.join(raw), encoding='utf-8')
    print('Wrote text using pdfium to', out_path)


if __name__ == '__main__':
    main()
