"""Geração dos ícones de instalação a partir da marca oficial do RITMOX."""
from pathlib import Path
import io
import cairosvg
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"static/ritmox-mark.svg"
OUT=ROOT/"static/pwa"
OUT.mkdir(parents=True,exist_ok=True)
for size in (192,512):
    canvas=Image.new("RGBA",(size,size),(0,0,0,0))
    ImageDraw.Draw(canvas).rounded_rectangle((0,0,size-1,size-1),radius=round(size*.22),fill="#08101F")
    inner=round(size*.80)
    mark=Image.open(io.BytesIO(cairosvg.svg2png(url=str(SOURCE),output_width=inner,output_height=inner))).convert("RGBA")
    canvas.alpha_composite(mark,((size-inner)//2,(size-inner)//2))
    path=OUT/f"icon-{size}.png"
    canvas.save(path,"PNG",optimize=True)
    assert Image.open(path).size==(size,size)
    print(path.relative_to(ROOT))
