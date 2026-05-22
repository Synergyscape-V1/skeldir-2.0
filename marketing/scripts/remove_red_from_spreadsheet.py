"""
Remove only the red arrow and red X from spreadsheet-iteration-2.png.
Scientific approach: replace pixels in the red color range with white;
leave all other pixels (spreadsheet oranges, white background) unchanged.
"""
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    raise SystemExit("Install Pillow: pip install Pillow")

# Paths
script_dir = Path(__file__).resolve().parent
images_dir = script_dir.parent / "public" / "images"
src_path = images_dir / "spreadsheet-iteration-2.png"
out_path = images_dir / "spreadsheet-iteration-2.png"  # overwrite: only red arrow/X removed

def is_red(r: int, g: int, b: int) -> bool:
    """True only for red arrow/X pixels; exclude orange (spreadsheet) and background."""
    # Red: R dominant, G and B low. Orange has noticeably higher G/B.
    if r < 100:
        return False
    if r <= g + 40 and r <= b + 40:
        return False
    if g > 110 or b > 110:
        return False
    return True

def main():
    img = Image.open(src_path).convert("RGBA")
    w, h = img.size
    data = img.load()
    changed = 0
    white = (255, 255, 255, 255)
    for y in range(h):
        for x in range(w):
            r, g, b, a = data[x, y]
            if is_red(r, g, b):
                data[x, y] = (255, 255, 255, a)
                changed += 1
    img.save(out_path, "PNG")
    print(f"Replaced {changed} red pixels; saved to {out_path}")

if __name__ == "__main__":
    main()
