"""Generate Udemy course cover images with referral QR code overlays."""

from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "assets" / "resource_covers"

COURSES = [
    {
        "slug": "yemba",
        "filename": "udemy_yemba.png",
        "title": "Yemba Language Phrasebook",
        "subtitle": "Arjwa'ne mekamɛshunne",
        "url": "https://www.udemy.com/course/yemba-language-phrasebook/?referralCode=84AB32546A069CBA0658",
    },
    {
        "slug": "ewondo",
        "filename": "udemy_ewondo.png",
        "title": "Ewondo Language Phrasebook",
        "subtitle": "Evɔ̀li ńkɔ̀bɔ ewondo",
        "url": "https://www.udemy.com/course/ewondo-language-phrasebook/?referralCode=740AD0C91EE6CED271AA",
    },
    {
        "slug": "bamoun",
        "filename": "udemy_bamoun.png",
        "title": "Bamoun (Shupamom) Language Phrasebook",
        "subtitle": "Shupamom phrasebook",
        "url": "https://www.udemy.com/course/bamoun-shupamom-language-phrasebook/?referralCode=3C7611D33714B72A9795",
    },
    {
        "slug": "duala",
        "filename": "udemy_duala.png",
        "title": "Duala (Douala) Language Phrasebook",
        "subtitle": "Duala phrasebook",
        "url": "https://www.udemy.com/course/duala-douala-language-phrasebook/?referralCode=93D2EDA4091A48F2C424",
    },
    {
        "slug": "kiswahili",
        "filename": "udemy_kiswahili.png",
        "title": "Kiswahili Phrasebook",
        "subtitle": "Kiswahili phrasebook",
        "url": "https://www.udemy.com/course/kiswahili-phrasebook/?referralCode=851A6F1091CC3994B11D",
    },
    {
        "slug": "yoruba",
        "filename": "udemy_yoruba.png",
        "title": "Yoruba Language Phrasebook",
        "subtitle": "Yoruba phrasebook",
        "url": "https://www.udemy.com/course/yoruba-language-phrasebook/?referralCode=DDE095733860B3F6FE15",
    },
    {
        "slug": "nufi",
        "filename": "udemy_nufi.png",
        "title": "Bamileke (Nufi) Language Phrasebook",
        "subtitle": "Ŋwa'ni njá'ghəə",
        "url": "https://www.udemy.com/course/bamileke-nufi-language-phrasebook/?referralCode=453B34DB58BB12C23D52",
    },
]

VIEWPORT = {"width": 1280, "height": 900}
SCREENSHOT_HEIGHT = 760
QR_SIZE = 220
QR_PADDING = 14
QR_Y_RATIO = 0.52


def dismiss_overlays(page) -> None:
    for selector in (
        'button[data-purpose="close-cookie-banner"]',
        'button:has-text("Accept")',
        'button:has-text("Reject")',
        'button:has-text("Close")',
    ):
        try:
            button = page.locator(selector).first
            if button.is_visible(timeout=1500):
                button.click(timeout=1500)
        except Exception:
            pass


def is_cloudflare_block(page) -> bool:
    try:
        content = page.content()
    except Exception:
        return True
    return "Performing security verification" in content or "Verify you are human" in content


def capture_course_screenshot(page, url: str) -> Image.Image:
    page.goto("https://www.udemy.com/", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2000)
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    dismiss_overlays(page)
    page.wait_for_timeout(2500)
    if is_cloudflare_block(page):
        raise RuntimeError("Cloudflare verification page detected")
    png_bytes = page.screenshot(full_page=False, clip={"x": 0, "y": 0, "width": VIEWPORT["width"], "height": SCREENSHOT_HEIGHT})
    return Image.open(BytesIO(png_bytes)).convert("RGB")


def render_fallback_screenshot(page, course: dict) -> Image.Image:
    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ margin: 0; font-family: "Udemy Sans", "SF Pro Text", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #fff; color: #1c1d1f; }}
    .topbar {{ display:flex; align-items:center; gap:16px; padding: 12px 24px; border-bottom: 1px solid #d1d7dc; }}
    .logo {{ font-weight: 800; font-size: 22px; letter-spacing: -1px; }}
    .search {{ flex:1; border:1px solid #1c1d1f; border-radius:999px; padding: 10px 16px; color:#6a6f73; }}
    .nav {{ display:flex; gap:16px; color:#1c1d1f; font-size:14px; }}
    .banner {{ position: relative; background: #1c1d1f; color: #fff; padding: 24px 32px 120px; min-height: 420px; }}
    .crumb {{ color: #c0c4fc; font-size: 14px; margin-bottom: 12px; }}
    h1 {{ font-size: 32px; line-height: 1.2; margin: 0 0 8px; max-width: 700px; }}
    .subtitle {{ color: #d1d7dc; margin-bottom: 16px; font-size: 18px; }}
    .meta {{ color: #d1d7dc; font-size: 14px; }}
    .card {{ position: absolute; top: 24px; right: 32px; width: 340px; background: #fff; border: 1px solid #d1d7dc; box-shadow: 0 2px 4px rgba(0,0,0,.08), 0 4px 12px rgba(0,0,0,.08); }}
    .preview {{ height: 190px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); display:flex; align-items:center; justify-content:center; color:#fff; font-weight:700; }}
    .card-body {{ padding: 24px; }}
    .btn {{ display:block; width:100%; padding: 12px; text-align:center; border-radius: 0; font-weight:700; margin-bottom: 12px; box-sizing:border-box; }}
    .btn-primary {{ background:#a435f0; color:#fff; border:none; }}
    .btn-outline {{ background:#fff; color:#a435f0; border:1px solid #a435f0; }}
    .learn {{ margin: -80px 32px 0; border: 1px solid #d1d7dc; padding: 24px; max-width: 760px; background:#fff; position:relative; z-index:1; }}
    .learn h2 {{ margin-top: 0; font-size: 24px; }}
    .grid {{ display:grid; grid-template-columns: 1fr 1fr; gap: 8px 24px; }}
    .item {{ display:flex; gap:8px; font-size: 14px; align-items:flex-start; }}
  </style>
</head>
<body>
  <div class="topbar">
    <div class="logo">udemy</div>
    <div class="search">Search for anything</div>
    <div class="nav"><span>Plans &amp; Pricing</span><span>Udemy Business</span><span>Log in</span></div>
  </div>
  <div class="banner">
    <div class="crumb">Teaching &amp; Academics &gt; Language Learning</div>
    <h1>{course["title"]}</h1>
    <div class="subtitle">{course["subtitle"]}</div>
    <div class="meta">Created by <u>Shck Tchamna</u> · Last updated 1/2026 · English</div>
    <div class="card">
      <div class="preview">Preview this course</div>
      <div class="card-body">
        <button class="btn btn-primary">Add to cart</button>
        <button class="btn btn-outline">Buy now</button>
      </div>
    </div>
  </div>
  <div class="learn">
    <h2>What you'll learn</h2>
    <div class="grid">
      <div class="item">✓ 2000+ Well curated phrases subdivided by themes</div>
      <div class="item">✓ 32 Chapters</div>
      <div class="item">✓ 8+ hours of Lecture</div>
      <div class="item">✓ The course focuses on sentences curated to start conversation.</div>
    </div>
  </div>
</body>
</html>"""
    page.set_content(html, wait_until="load")
    page.wait_for_timeout(500)
    png_bytes = page.screenshot(full_page=False, clip={"x": 0, "y": 0, "width": VIEWPORT["width"], "height": SCREENSHOT_HEIGHT})
    return Image.open(BytesIO(png_bytes)).convert("RGB")


def make_qr_overlay(url: str, size: int, padding: int) -> Image.Image:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    qr_img = qr_img.resize((size, size), Image.Resampling.NEAREST)

    total = size + padding * 2
    canvas = Image.new("RGB", (total, total), "white")
    canvas.paste(qr_img, (padding, padding))
    return canvas


def overlay_qr(screenshot: Image.Image, qr_overlay: Image.Image) -> Image.Image:
    result = screenshot.copy()
    x = (result.width - qr_overlay.width) // 2
    y = int(result.height * QR_Y_RATIO) - qr_overlay.height // 2

    shadow = Image.new("RGBA", (qr_overlay.width + 8, qr_overlay.height + 8), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle(
        (4, 4, qr_overlay.width + 4, qr_overlay.height + 4),
        radius=8,
        fill=(0, 0, 0, 60),
    )
    result.paste(shadow, (x - 4, y), shadow)

    result.paste(qr_overlay, (x, y))
    return result


def generate_cover(playwright, course: dict, output_dir: Path) -> Path:
    screenshot = None
    last_error = None
    for attempt in range(3):
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport=VIEWPORT,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        try:
            screenshot = capture_course_screenshot(page, course["url"])
            break
        except Exception as exc:
            last_error = exc
            page.wait_for_timeout(4000 * (attempt + 1))
        finally:
            browser.close()

    if screenshot is None:
        print(f"Warning: live Udemy capture failed for {course['slug']} ({last_error}); using styled fallback.")
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport=VIEWPORT)
        page = context.new_page()
        screenshot = render_fallback_screenshot(page, course)
        browser.close()

    qr_overlay = make_qr_overlay(course["url"], QR_SIZE, QR_PADDING)
    final = overlay_qr(screenshot, qr_overlay)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / course["filename"]
    final.save(output_path, "PNG", optimize=True)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--slug",
        action="append",
        help="Generate only the given course slug(s). Defaults to all courses.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Directory for generated PNG files.",
    )
    args = parser.parse_args()

    selected = COURSES
    if args.slug:
        wanted = {slug.lower() for slug in args.slug}
        selected = [course for course in COURSES if course["slug"] in wanted]
        missing = wanted - {course["slug"] for course in selected}
        if missing:
            raise SystemExit(f"Unknown slug(s): {', '.join(sorted(missing))}")

    with sync_playwright() as playwright:
        for course in selected:
            output_path = generate_cover(playwright, course, args.output_dir)
            print(f"Saved {output_path}")


if __name__ == "__main__":
    main()
