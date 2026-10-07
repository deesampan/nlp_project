"""Stage 6 - export everything the dashboard needs as JSON + a data.js shim
(so web/index.html also works when opened straight from disk), and copy the
dish photos from src/image/ into web/img/."""
import json
import shutil
from PIL import Image
from .common import RESULTS, WEB, ROOT, simple_words

IMAGE_SRC = ROOT / "src" / "image"
IMG_OUT = WEB / "img"
IMG_SIZE = 600


def dish_images(dish_names: set[str]) -> dict[str, str]:
    """Match photos to dishes by word set: 'biryani_veg.png' -> 'Veg Biryani'.
    Spelling is normalised on both sides, so 'Gulab Jamoon' also gets gulab_jamun.png.
    Each photo is trimmed to its visible pixels and padded to a square."""
    if IMG_OUT.exists():
        shutil.rmtree(IMG_OUT)
    IMG_OUT.mkdir(parents=True)
    photos = {frozenset(simple_words(p.stem.replace("_", " "))): p
              for p in sorted(IMAGE_SRC.glob("*")) if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}}
    out, written = {}, {}
    for name in sorted(dish_names):
        src = photos.get(frozenset(simple_words(name)))
        if not src:
            continue
        if src not in written:
            im = Image.open(src).convert("RGBA")
            im = im.crop(im.getchannel("A").getbbox() or (0, 0, *im.size))
            side = max(im.size)
            sq = Image.new("RGBA", (side, side))
            sq.paste(im, ((side - im.width) // 2, (side - im.height) // 2))
            sq.thumbnail((IMG_SIZE, IMG_SIZE), Image.LANCZOS)
            dest = IMG_OUT / (src.stem + ".webp")
            sq.save(dest, quality=86, method=6)
            written[src] = f"img/{dest.name}"
        out[name] = written[src]
    return out


def write(payload: dict) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    WEB.mkdir(parents=True, exist_ok=True)
    payload["images"] = dish_images({d["dish"] for d in payload["dishes"]})
    (RESULTS / "resrec_data.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    (WEB / "data.js").write_text("window.RESREC_DATA = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
