from PIL import Image, ImageDraw, ImageFont
import random, math

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

W, H   = 720, 405
FRAMES = 30
DELAY  = 80

BG      = (5,  0,  20)
GOLD    = (255, 215, 55)
GOLD2   = (200, 150, 20)
GOLD3   = (120,  80,  5)
PURPLE  = (170, 130, 255)
TEAL    = ( 60, 180, 255)
CYAN2   = ( 80, 200, 220)

rng = random.Random(7)

# Звёзды: (x, y, яркость 0..1, размер 0/1)
STARS = [
    (rng.randint(0, W-1), rng.randint(0, H-1), rng.random(), rng.random() > 0.85)
    for _ in range(140)
]

# Частицы: (x, y, цвет, фаза)
PARTICLE_COLORS = [PURPLE, TEAL, GOLD2, CYAN2, (150, 80, 255)]
PARTICLES = [
    (rng.randint(20, W-20), rng.randint(10, H-10),
     PARTICLE_COLORS[rng.randint(0, len(PARTICLE_COLORS)-1)],
     rng.random())
    for _ in range(22)
]

# Горизонтальные полосы-туманности (без blur — просто полупрозрачные прямоугольники)
BANDS = [
    (0,   80, 180, (40, 10, 90),  18),
    (200, 60, 220, (15,  5, 70),  12),
    (H-100, 60, W, (30,  8, 80),  14),
]

font_big  = ImageFont.truetype(FONT_BOLD, 64)
font_sub  = ImageFont.truetype(FONT_REG,  21)
font_tiny = ImageFont.truetype(FONT_REG,  14)

def pulse(t, freq=1.0, phase=0.0):
    return (math.sin((t + phase) * math.pi * 2 * freq) + 1) / 2

def cx(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return (W - (bb[2] - bb[0])) // 2

def draw_glow_text(draw, text, tx, ty, font, color, glow, radius=3):
    """Резкое свечение: рисуем текст несколько раз со смещением, без blur."""
    for r in range(radius, 0, -1):
        alpha = max(0, min(255, 80 - r * 18))
        gc = tuple(min(255, int(c * (alpha / 80))) for c in glow)
        for dx in range(-r, r+1, r):
            for dy in range(-r, r+1, r):
                draw.text((tx+dx, ty+dy), text, font=font, fill=gc)
    draw.text((tx, ty), text, font=font, fill=color)

def blend(c1, c2, k):
    return tuple(int(c1[i] + (c2[i]-c1[i])*k) for i in range(3))

frames = []

for f in range(FRAMES):
    t   = f / FRAMES
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # ── Горизонтальные полосы-туманности (без blur) ───────────────
    band_layer = Image.new("RGB", (W, H), BG)
    bd = ImageDraw.Draw(band_layer)
    for by, bh, bw, col, alpha in BANDS:
        pulse_a = int(alpha * (0.7 + 0.3 * pulse(t, 0.5)))
        for row in range(by, min(by + bh, H)):
            dist = min(row - by, by + bh - row)
            fade = min(1.0, dist / max(1, bh * 0.3))
            a = int(pulse_a * fade)
            rc = tuple(min(255, BG[i] + int((col[i]-BG[i]) * a / 40)) for i in range(3))
            bd.line([(0, row), (bw, row)], fill=rc)
    img = Image.blend(img, band_layer, 0.6)
    draw = ImageDraw.Draw(img)

    # ── Звёзды — пиксельные, чёткие ──────────────────────────────
    for sx, sy, ph, big in STARS:
        tw = pulse(t, 1.0 + ph * 1.5, ph)
        br = int(50 + 205 * tw)
        c  = (br, br, min(br + 20, 255))
        if big:
            # крест — 5 пикселей
            for dx, dy in [(0,0),(1,0),(-1,0),(0,1),(0,-1)]:
                nx, ny = sx+dx, sy+dy
                if 0 <= nx < W and 0 <= ny < H:
                    draw.point((nx, ny), fill=c)
        else:
            draw.point((sx, sy), fill=c)

    # ── Частицы — маленькие квадраты 3×3 ─────────────────────────
    for px, py, col, ph in PARTICLES:
        py2 = int(py + f * 2.0) % H
        brf = 0.5 + 0.5 * pulse(t, 1.0, ph)
        pc  = tuple(int(c * brf) for c in col)
        draw.rectangle([px-1, py2-1, px+1, py2+1], fill=pc)

    # ── Заголовок с резким свечением ──────────────────────────────
    title = "Пиши или умри!"
    tx = cx(draw, title, font_big)
    ty = 110
    gp = pulse(t, 1.0)
    gc = blend(GOLD2, GOLD, gp)
    draw_glow_text(draw, title, tx, ty, font_big, gc, (255, 200, 0), radius=3)

    # ── Декоративная линия ────────────────────────────────────────
    line_y = ty + 78
    ll  = int(250 + 55 * gp)
    lx  = (W - ll) // 2
    lc  = blend(GOLD3, GOLD2, gp)
    draw.line([(lx, line_y), (lx + ll, line_y)], fill=lc, width=2)

    # ── Подзаголовок ──────────────────────────────────────────────
    sub  = "Твой ежедневный писательский трекер"
    sx2  = cx(draw, sub, font_sub)
    sy2  = line_y + 9
    sp   = pulse(t, 1.0, 0.2)
    sc   = blend((130, 100, 230), PURPLE, sp)
    draw.text((sx2, sy2), sub, font=font_sub, fill=sc)

    # ── Нижняя строка ─────────────────────────────────────────────
    tag  = "Пиши каждый день"
    tgx  = cx(draw, tag, font_tiny)
    tgy  = H - 32
    tgp  = pulse(t, 0.8, 0.5)
    tgc  = blend(GOLD2, GOLD, tgp)
    draw.text((tgx, tgy), tag, font=font_tiny, fill=tgc)

    frames.append(img)

# ── Сохранение: отдельная палитра на каждый кадр, без дизеринга ──
quantized = [
    f.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=0)
    for f in frames
]

quantized[0].save(
    "welcome.gif",
    save_all=True,
    append_images=quantized[1:],
    loop=0,
    duration=DELAY,
    optimize=False,
)
print(f"Done: welcome.gif — {FRAMES} frames, {W}x{H}px")
