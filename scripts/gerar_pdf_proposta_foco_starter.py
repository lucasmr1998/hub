"""
Gera PDF da proposta focada pra cliente que vai contratar Comercial + Atendimento Starter.

Junta os slides 1-9 (institucional) + slide foco final com a oferta especifica
(R$ 994/mes, setup cortesia, atendimento sem variavel).
"""
from pathlib import Path
from PIL import Image
import re

DOWNLOADS = Path(r"C:\Users\lucas\Downloads")
OUT_PATH = Path(r"C:\Users\lucas\Desktop\hub\robo\docs\GTM\propostas\proposta_hubtrix_foco_starter.pdf")

SLIDES = [
    "01 Capa", "02 Sobre", "03 Dores", "04 Visao Geral",
    "05 Modulo Comercial", "06 Modulo Atendimento", "07 Modulo Marketing",
    "08 Modulo CS", "09 Diferenciais",
    "Foco Cliente Starter",
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
