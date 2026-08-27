"""The pass that makes a bank of unrelated photographs look like one account.

Every cover image is mapped to exactly two colours: the post's ink in the
shadows, the ground in the highlights. A museum's botanical plate and a
museum's tile photograph come out of this reading as the same publication,
which is the whole reason a varied bank is allowed in the first place.

    from render.duotone import duotone, halftone
    duotone(src, dst, shadow="#191B20", highlight="#EFEAE1")
    halftone(src, dst, shadow="#191B20", highlight="#EFEAE1", dot=5)

Deterministic: the same input and the same colours give the same bytes, so a
re-render does not churn the output directory.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


def _rgb(hex_colour: str) -> tuple[int, int, int]:
    h = hex_colour.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _ramp(shadow: str, highlight: str) -> list[int]:
    """A 256-entry lookup table running shadow -> highlight."""
    s, h = _rgb(shadow), _rgb(highlight)
    table: list[int] = []
    for channel in range(3):
        table += [round(s[channel] + (h[channel] - s[channel]) * i / 255)
                  for i in range(256)]
    return table


def _prepare(src: Path | str, gamma: float, size: tuple[int, int] | None) -> Image.Image:
    img = Image.open(src).convert("L")
    if size:
        img = ImageOps.fit(img, size, method=Image.LANCZOS, centering=(0.5, 0.4))
    img = ImageOps.autocontrast(img, cutoff=1)
    if gamma and gamma != 1.0:
        table = [round(255 * ((i / 255) ** (1 / gamma))) for i in range(256)]
        img = img.point(table)
    return img


def duotone(src: Path | str, dst: Path | str, shadow: str, highlight: str,
            gamma: float = 1.05, size: tuple[int, int] | None = None) -> Path:
    grey = _prepare(src, gamma, size)
    out = grey.convert("RGB")
    out = out.point(_ramp(shadow, highlight))
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst, "PNG", optimize=True)
    return dst


def halftone(src: Path | str, dst: Path | str, shadow: str, highlight: str,
             dot: int = 5, angle: int = 15, gamma: float = 1.05,
             size: tuple[int, int] | None = None) -> Path:
    """The alternate pass: the same two colours, screened into dots.

    Drawn at 3x and downsampled, which is what keeps the dot edges from
    crawling. Slower than the duotone and worth it only on covers whose
    original is already high contrast.
    """
    grey = _prepare(src, gamma, size)
    w, h = grey.size
    scale = 3
    canvas = Image.new("L", (w * scale, h * scale), 255)
    draw = ImageDraw.Draw(canvas)
    rotated = grey.rotate(angle, resample=Image.BICUBIC, fillcolor=255)
    pixels = rotated.load()
    step = max(dot, 2)
    for y in range(0, h, step):
        for x in range(0, w, step):
            value = pixels[x, y]
            radius = (1 - value / 255) * step * 0.72
            if radius < 0.3:
                continue
            cx, cy = (x + step / 2) * scale, (y + step / 2) * scale
            r = radius * scale
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=0)
    screened = canvas.resize((w, h), Image.LANCZOS).rotate(
        -angle, resample=Image.BICUBIC, fillcolor=255)
    out = screened.convert("RGB").point(_ramp(shadow, highlight))
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst, "PNG", optimize=True)
    return dst
