"""
Junta os 16 PNGs da proposta Hubtrix v3 (exportados do Paper) em um PDF unico.

Pega a versao mais recente de cada slide (Paper adiciona "(1)", "(2)" no nome
quando reexporta). Salva em robo/docs/GTM/propostas/proposta_hubtrix_v3.pdf.
"""
from pathlib import Path
from PIL import Image
import re

DOWNLOADS = Path(r"C:\Users\lucas\Downloads")
OUT_PATH = Path(r"C:\Users\lucas\Desktop\hub\robo\docs\GTM\propostas\proposta_hubtrix_v3_05-05-2026.pdf")

SLIDES = [
    "01 Capa", "02 Sobre", "03 Dores", "04 Visao Geral",
    "05 Modulo Comercial", "06 Modulo Atendimento", "07 Modulo Marketing",
    "08 Modulo CS", "09 Diferenciais",
    "10 Matriz Modulos", "11 Combos Sugeridos", "12 Custos Variaveis",
    "13 Simulacao", "14 Cronograma",
]

def latest_png(slide_label: str) -> Path:
    pattern = re.compile(rf"^Proposta · {re.escape(slide_label)}@2x.*\.png$")
    candidates = [p for p in DOWNLOADS.iterdir() if pattern.match(p.name)]
    if not candidates:
        raise FileNotFoundError(f"Nenhum PNG encontrado para: {slide_label}")
    return max(candidates, key=lambda p: p.stat().st_mtime)

images = []
for label in SLIDES:
    path = latest_png(label)
    print(f"[OK] {label:30s} -> {path.name}")
    img = Image.open(path).convert("RGB")
    images.append(img)

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
images[0].save(OUT_PATH, save_all=True, append_images=images[1:], format="PDF", resolution=150.0)
print(f"\nPDF salvo: {OUT_PATH}")
print(f"Tamanho: {OUT_PATH.stat().st_size / 1024:.0f} KB")
