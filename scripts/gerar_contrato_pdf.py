#!/usr/bin/env python3
"""
Gera PDF a partir de um contrato em Markdown.
Uso: python scripts/gerar_contrato_pdf.py docs/OPERACIONAL/contratos/contrato_grupo_magister_01-04-2026.md
"""
import sys
import os
import re
from fpdf import FPDF


class ContratoPDF(FPDF):
    def header(self):
        if self.page_no() > 1:
            self.set_font('Helvetica', 'I', 8)
            self.set_text_color(150, 150, 150)
            self.cell(0, 5, 'Contrato de Prestação de Serviços - AuroraISP', align='C')
            self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f'Página {self.page_no()}/{{nb}}', align='C')


def parse_md_to_pdf(md_path):
    if not os.path.exists(md_path):
        print(f"Arquivo não encontrado: {md_path}")
        sys.exit(1)

    with open(md_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    pdf = ContratoPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # Fontes
    pdf.set_font('Helvetica', '', 11)

    in_table = False
    table_rows = []
    col_widths = []

    for line in lines:
        line = line.rstrip('\n')

        # Pular linhas vazias de formatação
        if line.strip() == '&nbsp;':
            pdf.ln(6)
            continue

        if line.strip() == '---':
            if not in_table:
                pdf.set_draw_color(226, 232, 240)
                pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                pdf.ln(4)
            continue

        # Tabelas
        if '|' in line and line.strip().startswith('|'):
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            # Separador de tabela
            if all(re.match(r'^[-:]+$', c) for c in cells):
                continue
            if not in_table:
                in_table = True
                table_rows = []
                col_widths = [90, 90]
                if len(cells) > 2:
                    w = 180 // len(cells)
                    col_widths = [w] * len(cells)
            table_rows.append(cells)
            continue
        elif in_table:
            # Flush table
            _render_table(pdf, table_rows, col_widths)
            in_table = False
            table_rows = []

        # H1
        if line.startswith('# '):
            text = line[2:].strip()
            pdf.ln(4)
            pdf.set_font('Helvetica', 'B', 16)
            pdf.set_text_color(30, 41, 59)
            pdf.cell(0, 10, _clean(text), align='C', new_x='LMARGIN', new_y='NEXT')
            pdf.set_draw_color(59, 130, 246)
            pdf.set_line_width(0.5)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.set_line_width(0.2)
            pdf.ln(6)
            continue

        # H2
        if line.startswith('## '):
            text = line[3:].strip()
            pdf.ln(6)
            pdf.set_font('Helvetica', 'B', 12)
            pdf.set_text_color(30, 41, 59)
            pdf.cell(0, 8, _clean(text), new_x='LMARGIN', new_y='NEXT')
            pdf.set_draw_color(226, 232, 240)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(4)
            continue

        # H3
        if line.startswith('### '):
            text = line[4:].strip()
            pdf.ln(3)
            pdf.set_font('Helvetica', 'B', 11)
            pdf.set_text_color(51, 65, 85)
            pdf.cell(0, 7, _clean(text), new_x='LMARGIN', new_y='NEXT')
            pdf.ln(2)
            continue

        # Lista com letras a) b) c)
        if re.match(r'^[a-z]\)', line.strip()):
            pdf.set_font('Helvetica', '', 10)
            pdf.set_text_color(30, 30, 30)
            text = line.strip()
            pdf.cell(8)
            pdf.multi_cell(170, 5.5, _clean(text))
            pdf.ln(1)
            continue

        # Lista numérica
        if re.match(r'^\d+\.', line.strip()):
            pdf.set_font('Helvetica', '', 10)
            pdf.set_text_color(30, 30, 30)
            text = line.strip()
            pdf.cell(5)
            pdf.multi_cell(173, 5.5, _clean(text))
            pdf.ln(1)
            continue

        # Linha de assinatura
        if line.strip().startswith('\\_'):
            pdf.ln(8)
            pdf.set_draw_color(100, 100, 100)
            pdf.line(10, pdf.get_y(), 100, pdf.get_y())
            pdf.ln(2)
            continue

        # Parágrafo normal
        if line.strip():
            pdf.set_font('Helvetica', '', 10)
            pdf.set_text_color(30, 30, 30)
            text = _clean(line.strip())
            pdf.multi_cell(0, 5.5, text)
            pdf.ln(2)

    # Flush remaining table
    if in_table:
        _render_table(pdf, table_rows, col_widths)

    pdf_path = md_path.replace('.md', '.pdf')
    pdf.output(pdf_path)
    print(f"PDF gerado: {pdf_path}")
    return pdf_path


def _render_table(pdf, rows, col_widths):
    if not rows:
        return
    pdf.ln(2)
    for i, row in enumerate(rows):
        is_header = (i == 0)
        if is_header:
            pdf.set_font('Helvetica', 'B', 9)
            pdf.set_fill_color(241, 245, 249)
            pdf.set_text_color(51, 65, 85)
        else:
            pdf.set_font('Helvetica', '', 9)
            pdf.set_fill_color(255, 255, 255)
            pdf.set_text_color(30, 30, 30)

        pdf.set_draw_color(226, 232, 240)
        for j, cell in enumerate(row):
            w = col_widths[j] if j < len(col_widths) else 60
            pdf.cell(w, 7, _clean(cell.strip()), border=1, fill=is_header)
        pdf.ln()
    pdf.ln(4)


def _clean(text):
    """Remove markdown formatting and replace special chars."""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # bold
    text = re.sub(r'\*(.+?)\*', r'\1', text)  # italic
    text = re.sub(r'`(.+?)`', r'\1', text)  # code
    text = text.replace('&nbsp;', ' ')
    # Replace Unicode chars that latin-1 can't handle
    text = text.replace('\u2014', '-')   # em dash
    text = text.replace('\u2013', '-')   # en dash
    text = text.replace('\u201c', '"')   # left double quote
    text = text.replace('\u201d', '"')   # right double quote
    text = text.replace('\u2018', "'")   # left single quote
    text = text.replace('\u2019', "'")   # right single quote
    text = text.replace('\u2026', '...')  # ellipsis
    text = text.replace('\u00ba', 'o')   # º
    text = text.replace('\u00aa', 'a')   # ª
    return text


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python scripts/gerar_contrato_pdf.py <caminho_do_md>")
        sys.exit(1)
    parse_md_to_pdf(sys.argv[1])
