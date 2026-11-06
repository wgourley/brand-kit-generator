#!/usr/bin/env python3
"""
brand-kit-generator: build a full logo package from one badge image.

Give it a round badge (transparent PNG), a name and a colour bar, and it
produces wordmarks, stacked and horizontal logos for dark and light
backgrounds, the colour bar on its own (PNG + SVG), avatars, a social banner,
a share image, a 250x70 player logo, broadcast posters and watermarks, plus a
reference sheet, all zipped.

https://github.com/wgourley/brand-kit-generator   (MIT)
"""
import argparse, os, shutil, sys, zipfile
from PIL import Image, ImageDraw, ImageFont

DEFAULT_BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
DEFAULT_REG = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'


def hex_rgb(h):
    h = h.lstrip('#')
    if len(h) != 6:
        raise argparse.ArgumentTypeError(f'not a #rrggbb colour: {h}')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def parse():
    p = argparse.ArgumentParser(description='Build a logo package from one badge image.')
    p.add_argument('--badge', required=True, help='round badge, transparent PNG (512px or larger)')
    p.add_argument('--name', required=True, help='wordmark text, e.g. "MY CHANNEL"')
    p.add_argument('--colours', default='#44628d,#d79546,#b03e59,#eade6b,#38796b',
                   help='colour bar, left to right, comma-separated (default: 5 soft colours)')
    p.add_argument('--text-dark', default='#8fe03a', help='wordmark colour on dark backgrounds')
    p.add_argument('--text-light', default='#2a1360', help='wordmark colour on light backgrounds')
    p.add_argument('--background', default='#110824', help='brand background colour')
    p.add_argument('--font', default=DEFAULT_BOLD, help='bold .ttf for the wordmark')
    p.add_argument('--font-regular', default=DEFAULT_REG, help='regular .ttf for the reference sheet')
    p.add_argument('--out', default='brand-kit', help='output folder (a .zip is made next to it)')
    a = p.parse_args()
    for f in (a.badge, a.font, a.font_regular):
        if not os.path.isfile(f):
            sys.exit(f'File not found: {f}  (set --font / --font-regular on systems without DejaVu)')
    a.bar = [c.strip() for c in a.colours.split(',') if c.strip()]
    a.bar_rgb = [hex_rgb(c) for c in a.bar]
    a.text_dark_rgb, a.text_light_rgb, a.bg_rgb = map(hex_rgb, (a.text_dark, a.text_light, a.background))
    return a


class Kit:
    BAR_RATIO = 32  # bar width : height

    def __init__(self, a):
        self.a = a
        b = Image.open(a.badge).convert('RGBA')
        self.badge = b.crop(b.getbbox())
        self.key = a.bg_rgb + (110,)  # thin keyline round the bar on light backgrounds

    def bar(self, w, light=False):
        h = max(2, round(w / self.BAR_RATIO))
        im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        n = len(self.a.bar_rgb)
        for i, c in enumerate(self.a.bar_rgb):
            d.rectangle((round(i * w / n), 0, round((i + 1) * w / n) - 1, h - 1), fill=c + (255,))
        if light:
            d.rectangle((0, 0, w - 1, h - 1), outline=self.key, width=max(1, round(h * 0.06)))
        return im

    def text(self, txt, size, colour):
        f = ImageFont.truetype(self.a.font, size)
        bb = ImageDraw.Draw(Image.new('L', (1, 1))).textbbox((0, 0), txt, font=f)
        im = Image.new('RGBA', (bb[2] - bb[0] + 4, bb[3] - bb[1] + 4), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((2 - bb[0], 2 - bb[1]), txt, font=f, fill=colour + (255,))
        return im

    def wordmark(self, width, light=False):
        size = 20
        while self.text(self.a.name, size + 2, self.a.text_dark_rgb).width <= width:
            size += 2
        t = self.text(self.a.name, size, self.a.text_light_rgb if light else self.a.text_dark_rgb)
        bar = self.bar(t.width - 4, light)
        gap = round(t.height * 0.22)
        im = Image.new('RGBA', (t.width, t.height + gap + bar.height), (0, 0, 0, 0))
        im.alpha_composite(t, (0, 0)); im.alpha_composite(bar, (2, t.height + gap))
        return im

    def stacked(self, d, light=False):
        b = self.badge.resize((d, d), Image.LANCZOS)
        wm = self.wordmark(round(1.64 * d), light); gap = round(0.146 * d)
        im = Image.new('RGBA', (max(wm.width, d), d + gap + wm.height), (0, 0, 0, 0))
        im.alpha_composite(b, ((im.width - d) // 2, 0)); im.alpha_composite(wm, ((im.width - wm.width) // 2, d + gap))
        return im

    def horizontal(self, d, light=False):
        b = self.badge.resize((d, d), Image.LANCZOS)
        wm = self.wordmark(round(2.1 * d), light); gap = round(0.22 * d)
        im = Image.new('RGBA', (d + gap + wm.width, d), (0, 0, 0, 0))
        im.alpha_composite(b, (0, 0)); im.alpha_composite(wm, (d + gap, (d - wm.height) // 2))
        return im


def pad(img, p):
    im = Image.new('RGBA', (img.width + 2 * p, img.height + 2 * p), (0, 0, 0, 0)); im.alpha_composite(img, (p, p)); return im


def on_bg(img, size, bg, scale=0.8):
    W, H = size; c = Image.new('RGBA', size, bg + (255,))
    r = min(W * scale / img.width, H * scale / img.height)
    i = img.resize((round(img.width * r), round(img.height * r)), Image.LANCZOS)
    c.alpha_composite(i, ((W - i.width) // 2, (H - i.height) // 2)); return c


def faded(img, alpha=0.85):
    img = img.copy(); img.putalpha(img.getchannel('A').point(lambda v: int(v * alpha))); return img


def main():
    a = parse(); k = Kit(a); OUT = a.out; slug = a.name.lower().replace(' ', '')
    shutil.rmtree(OUT, ignore_errors=True)
    for d in ('dark-backgrounds', 'light-backgrounds', 'bar', 'web-and-social', 'broadcast'):
        os.makedirs(f'{OUT}/{d}')

    for light, folder in ((False, 'dark-backgrounds'), (True, 'light-backgrounds')):
        tag = 'light' if light else 'dark'
        pad(k.wordmark(1600, light), 40).save(f'{OUT}/{folder}/{slug}-wordmark-for-{tag}-bg.png')
        pad(k.stacked(900, light), 40).save(f'{OUT}/{folder}/{slug}-full-logo-for-{tag}-bg.png')
        pad(k.horizontal(400, light), 30).save(f'{OUT}/{folder}/{slug}-horizontal-for-{tag}-bg.png')
        bg = (255, 255, 255) if light else a.bg_rgb
        on_bg(k.stacked(900, light), (2048, 1536), bg, 0.78).convert('RGB').save(
            f'{OUT}/{folder}/{slug}-full-logo-on-{"white" if light else "brand-bg"}.png')

    k.bar(1600).save(f'{OUT}/bar/{slug}-bar.png')
    k.bar(1600, True).save(f'{OUT}/bar/{slug}-bar-keyline-for-light-bg.png')
    n = len(a.bar); seg = 160 / n
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 5" width="1600" height="50">'
           + ''.join(f'<rect x="{i * seg:g}" y="0" width="{seg:g}" height="5" fill="{c}"/>' for i, c in enumerate(a.bar)) + '</svg>')
    open(f'{OUT}/bar/{slug}-bar.svg', 'w').write(svg)

    for s in (512, 1024):
        on_bg(k.stacked(900), (s, s), a.bg_rgb, 0.82).convert('RGB').save(f'{OUT}/web-and-social/{slug}-avatar-{s}.png')
    on_bg(k.horizontal(400), (1500, 500), a.bg_rgb).convert('RGB').save(f'{OUT}/web-and-social/{slug}-banner-1500x500.png')
    on_bg(k.horizontal(400), (1200, 630), a.bg_rgb).convert('RGB').save(f'{OUT}/web-and-social/{slug}-share-1200x630.png')
    pl = Image.new('RGBA', (250, 70), (0, 0, 0, 0)); h = k.horizontal(240)
    h = h.resize((round(h.width * 62 / h.height), 62), Image.LANCZOS)
    if h.width > 244: h = h.resize((244, round(h.height * 244 / h.width)), Image.LANCZOS)
    pl.alpha_composite(h, (3, (70 - h.height) // 2)); pl.save(f'{OUT}/web-and-social/{slug}-player-logo-250x70.png')

    on_bg(k.stacked(900), (1280, 720), a.bg_rgb, 0.78).convert('RGB').save(f'{OUT}/broadcast/{slug}-poster-1280x720.png')
    on_bg(k.stacked(900), (1920, 1080), a.bg_rgb, 0.78).convert('RGB').save(f'{OUT}/broadcast/{slug}-poster-1920x1080.png')
    pad(faded(k.bar(220)), 4).save(f'{OUT}/broadcast/{slug}-watermark-bar.png')
    pad(faded(k.wordmark(300)), 4).save(f'{OUT}/broadcast/{slug}-watermark-wordmark.png')

    sheet = Image.new('RGB', (1600, 900), (255, 255, 255)); d = ImageDraw.Draw(sheet)
    d.rectangle((0, 0, 800, 900), fill=a.bg_rgb)
    s1 = k.stacked(330); sheet.paste(s1, ((800 - s1.width) // 2, 70), s1)
    s2 = k.stacked(330, True); sheet.paste(s2, (800 + (800 - s2.width) // 2, 70), s2)
    ft, fs = ImageFont.truetype(a.font, 30), ImageFont.truetype(a.font_regular, 22)
    d.rectangle((0, 640, 1600, 900), fill=(244, 240, 250))
    d.text((60, 670), 'Colour bar (left to right, equal widths)', font=ft, fill=(17, 8, 36))
    step = min(300, 1480 // max(1, n))
    for i, c in enumerate(a.bar):
        x = 60 + i * step; d.rectangle((x, 750, x + 120, 800), fill=c); d.text((x, 812), c, font=fs, fill=(17, 8, 36))
    d.text((60, 860), f'Text {a.text_dark} on dark, {a.text_light} on light  |  Background {a.background}  |  Bar = text width, height = width / 32',
           font=fs, fill=(17, 8, 36))
    sheet.save(f'{OUT}/{slug}-reference-sheet.png')

    open(f'{OUT}/README.txt', 'w').write(
        f'{a.name} LOGO PACKAGE\nColour bar: {", ".join(a.bar)}\nText: {a.text_dark} on dark, {a.text_light} on light. Background {a.background}.\n'
        'dark-backgrounds/  light-backgrounds/  bar/  web-and-social/  broadcast/\n')
    z = zipfile.ZipFile(f'{OUT.rstrip("/")}.zip', 'w', zipfile.ZIP_DEFLATED)
    for root, _, files in os.walk(OUT):
        for f in files:
            z.write(os.path.join(root, f), os.path.relpath(os.path.join(root, f), os.path.dirname(os.path.abspath(OUT))))
    z.close()
    print(f'{sum(len(f) for _, _, f in os.walk(OUT))} files in {OUT}/ and {OUT.rstrip("/")}.zip')


if __name__ == '__main__':
    main()
