import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def create_queqq_dev_icon(output_ico_path="assets/queqq_dev.ico", output_png_path="assets/queqq_dev.png"):
    size = (512, 512)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Outer Metallic Gold Border & Hextech Background Shield
    margin = 24
    rect = [margin, margin, size[0] - margin, size[1] - margin]
    corner_radius = 80

    # Shadow under icon
    shadow = Image.new("RGBA", size, (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow)
    s_draw.rounded_rectangle(rect, radius=corner_radius, fill=(0, 0, 0, 180))
    shadow = shadow.filter(ImageFilter.GaussianBlur(16))
    img.paste(shadow, (0, 0), shadow)

    # Base Outer Ring (Gold)
    draw.rounded_rectangle(rect, radius=corner_radius, fill=(200, 170, 110, 255), outline=(240, 230, 210, 255), width=6)

    # Inner Dark Background Panel
    inner_rect = [margin + 12, margin + 12, size[0] - margin - 12, size[1] - margin - 12]
    draw.rounded_rectangle(inner_rect, radius=corner_radius - 8, fill=(10, 20, 40, 255), outline=(120, 90, 40, 255), width=4)

    # 2. Golden "Q" Rendering
    # Try loading high quality font or draw custom vector Q
    font_q = None
    font_dev = None
    font_paths = [
        "C:\\Windows\\Fonts\\arialbd.ttf",
        "C:\\Windows\\Fonts\\segoeui.ttf",
        "C:\\Windows\\Fonts\\impact.ttf",
        "C:\\Windows\\Fonts\\verdana.ttf"
    ]

    for fp in font_paths:
        if os.path.exists(fp):
            try:
                font_q = ImageFont.truetype(fp, 320)
                font_dev = ImageFont.truetype(fp, 72)
                break
            except Exception:
                pass

    if not font_q:
        font_q = ImageFont.load_default()
        font_dev = ImageFont.load_default()

    # Draw Golden "Q"
    q_text = "Q"
    # Measure Q bbox
    bbox = draw.textbbox((0, 0), q_text, font=font_q)
    qw = bbox[2] - bbox[0]
    qh = bbox[3] - bbox[1]
    qx = (size[0] - qw) // 2 - bbox[0]
    qy = (size[1] - qh) // 2 - bbox[1] - 25

    # Outer Q Glow / Shadow
    draw.text((qx + 4, qy + 6), q_text, font=font_q, fill=(40, 30, 10, 200))
    # Golden Q Gradient Layer
    draw.text((qx, qy), q_text, font=font_q, fill=(200, 170, 110, 255))
    # Golden Q Highlight Top Layer
    draw.text((qx - 2, qy - 2), q_text, font=font_q, fill=(240, 230, 210, 255))

    # 3. Red "DEV" Stamp Overlay
    # Angle Stamp Frame on bottom right
    stamp_w, stamp_h = 240, 90
    stamp_x = size[0] - stamp_w - 40
    stamp_y = size[1] - stamp_h - 55

    stamp_img = Image.new("RGBA", (stamp_w, stamp_h), (0, 0, 0, 0))
    stamp_draw = ImageDraw.Draw(stamp_img)

    # Red Stamp Background with dark red border
    stamp_draw.rounded_rectangle([0, 0, stamp_w, stamp_h], radius=16, fill=(220, 38, 38, 255), outline=(139, 0, 0, 255), width=4)
    # Inner gold border line for stamp
    stamp_draw.rounded_rectangle([4, 4, stamp_w - 4, stamp_h - 4], radius=12, fill=None, outline=(255, 255, 255, 220), width=2)

    # DEV Text inside Stamp
    dev_text = "DEV"
    dev_bbox = stamp_draw.textbbox((0, 0), dev_text, font=font_dev)
    dw = dev_bbox[2] - dev_bbox[0]
    dh = dev_bbox[3] - dev_bbox[1]
    dx = (stamp_w - dw) // 2 - dev_bbox[0]
    dy = (stamp_h - dh) // 2 - dev_bbox[1]

    # Text Shadow & Crisp White Text
    stamp_draw.text((dx + 2, dy + 2), dev_text, font=font_dev, fill=(60, 0, 0, 220))
    stamp_draw.text((dx, dy), dev_text, font=font_dev, fill=(255, 255, 255, 255))

    # Rotate Stamp slightly for a cool angled "STAMP" look (-12 degrees)
    rotated_stamp = stamp_img.rotate(-12, resample=Image.BICUBIC, expand=True)

    # Paste rotated stamp onto icon
    img.paste(rotated_stamp, (stamp_x - 10, stamp_y - 20), rotated_stamp)

    # Ensure output directories exist
    os.makedirs(os.path.dirname(output_ico_path), exist_ok=True)

    # Save PNG
    img.save(output_png_path, format="PNG")

    # Save ICO with standard sizes
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img.save(output_ico_path, format="ICO", sizes=sizes)
    print(f"Generated {output_png_path} and {output_ico_path} successfully!")

if __name__ == "__main__":
    create_queqq_dev_icon()
