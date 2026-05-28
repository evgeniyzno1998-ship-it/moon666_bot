import io
from PIL import Image, ImageDraw, ImageFont

_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
]

_BG        = (11, 12, 16)
_CARD      = (17, 18, 25)
_GOLD      = (240, 185, 11)
_GREEN     = (14, 203, 129)
_TEXT      = (234, 236, 239)
_SUBTLE    = (132, 142, 156)
_BORDER    = (28, 30, 46)
_TETHER    = (38, 161, 123)


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def generate_card(username: str, ref_count: int, earned: float) -> bytes:
    """Generate a 800×400 PNG referral card and return as bytes."""
    W, H = 800, 400

    img = Image.new("RGB", (W, H), _BG)
    draw = ImageDraw.Draw(img)

    # Card background with gold border
    draw.rounded_rectangle([6, 6, W - 7, H - 7], radius=18, fill=_CARD, outline=_GOLD, width=2)

    # Header band
    draw.rounded_rectangle([6, 6, W - 7, 68], radius=18, fill=(20, 21, 30))
    draw.rectangle([6, 40, W - 7, 68], fill=(20, 21, 30))  # square bottom corners

    # Title
    draw.text((W // 2, 38), "MOON666 · REFERRAL PROGRAM", fill=_GOLD, font=_font(24), anchor="mm")

    # Crescent moon (left side, centred at 130, 225)
    cx, cy = 130, 225
    draw.ellipse([cx - 80, cy - 80, cx + 80, cy + 80], fill=_GOLD)
    draw.ellipse([cx - 35, cy - 100, cx + 105, cy + 60], fill=_CARD)  # cut-out

    # USDT coin inside crescent curve
    draw.ellipse([cx + 30, cy - 18, cx + 78, cy + 28], fill=_TETHER)
    draw.text((cx + 54, cy + 5), "T", fill=(255, 255, 255), font=_font(26), anchor="mm")

    # Vertical divider
    draw.line([(240, 88), (240, H - 30)], fill=_BORDER, width=1)

    # Username
    uname = f"@{username}" if not username.startswith("@") else username
    draw.text((520, 130), uname, fill=_TEXT, font=_font(26), anchor="mm")

    # Horizontal divider under username
    draw.line([(265, 165), (775, 165)], fill=_BORDER, width=1)

    # Vertical stat divider
    draw.line([(520, 175), (520, 345)], fill=_BORDER, width=1)

    # Referrals
    draw.text((390, 255), str(ref_count), fill=_GOLD, font=_font(56), anchor="mm")
    draw.text((390, 315), "REFERRALS", fill=_SUBTLE, font=_font(14), anchor="mm")

    # Earned
    draw.text((650, 255), f"${earned:.2f}", fill=_GREEN, font=_font(52), anchor="mm")
    draw.text((650, 315), "EARNED", fill=_SUBTLE, font=_font(14), anchor="mm")

    # Footer
    draw.line([(6, H - 52), (W - 7, H - 52)], fill=_BORDER, width=1)
    draw.text((W // 2, H - 28), "Earn USDT by inviting friends  ·  @moon666_bot",
              fill=_SUBTLE, font=_font(14), anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
