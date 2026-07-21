"""Generate Udemy course cover images with referral QR code overlays."""

from __future__ import annotations

import argparse
import json
import re
from io import BytesIO
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFont
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
TOP_PROMO_CROP = 38
PRICE_PATTERN = re.compile(r"[$€£¥₹]|%\s*off|coupon|discount", re.IGNORECASE)


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


def capture_course_screenshot(page, course: dict) -> tuple[Image.Image, dict]:
    """Capture one genuine Udemy page from an already-running normal Chrome session."""
    response = page.goto(course["url"], wait_until="domcontentloaded", timeout=60000)
    expected_title = course["title"]
    actual_title = ""
    for _ in range(18):
        page.wait_for_timeout(2500)
        actual_title = page.locator("h1").first.inner_text() if page.locator("h1").count() else ""
        if actual_title == expected_title and page.title() != "Just a moment...":
            break
    else:
        status = response.status if response else "unknown"
        raise RuntimeError(
            f"{course['slug']}: direct Udemy page did not become ready "
            f"(status={status}, page_title={page.title()!r}, h1={actual_title!r})"
        )

    dismiss_overlays(page)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(5000)
    if is_cloudflare_block(page):
        raise RuntimeError("Cloudflare verification page detected")

    preview_box = None
    preview_candidates = page.get_by_text("Preview this course", exact=True)
    for index in range(preview_candidates.count()):
        candidate = preview_candidates.nth(index)
        if candidate.is_visible():
            preview_box = candidate.bounding_box()
            break
    if not preview_box:
        raise RuntimeError(f"{course['slug']}: genuine course preview is not visible")

    price_nodes = page.evaluate(
        """() => Array.from(document.querySelectorAll('body *')).map(el => {
            const rect = el.getBoundingClientRect();
            const ownText = Array.from(el.childNodes)
                .filter(node => node.nodeType === Node.TEXT_NODE)
                .map(node => node.textContent)
                .join(' ')
                .trim();
            return {
                text: ownText,
                x: rect.x,
                y: rect.y,
                width: rect.width,
                height: rect.height,
                visible: Boolean(rect.width && rect.height),
            };
        }).filter(item =>
            item.visible
            && /[$€£¥₹]|%\\s*off|coupon|discount/i.test(item.text)
            && item.y < 760
        )"""
    )
    png_bytes = page.screenshot(full_page=False, clip={"x": 0, "y": 0, "width": VIEWPORT["width"], "height": SCREENSHOT_HEIGHT})
    screenshot = Image.open(BytesIO(png_bytes)).convert("RGB")
    return screenshot, {
        "slug": course["slug"],
        "source_url": course["url"],
        "final_url": page.url,
        "h1": actual_title,
        "preview_box": preview_box,
        "price_nodes": price_nodes,
    }


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


def compose_price_safe_cover(
    screenshot: Image.Image,
    qr_overlay: Image.Image,
    metadata: dict,
) -> Image.Image:
    """Crop the promotional banner and replace only the pricing panel below the preview."""
    preview = metadata["preview_box"]
    panel = {
        "x": float(preview["x"]),
        "y": float(preview["y"]) + float(preview["height"]),
        "width": float(preview["width"]),
        "height": SCREENSHOT_HEIGHT - (float(preview["y"]) + float(preview["height"])),
    }

    for node in metadata["price_nodes"]:
        if not PRICE_PATTERN.search(str(node["text"])):
            continue
        node_right = float(node["x"]) + float(node["width"])
        node_bottom = float(node["y"]) + float(node["height"])
        removed_by_crop = node_bottom <= TOP_PROMO_CROP
        removed_by_panel = (
            float(node["x"]) >= panel["x"]
            and float(node["y"]) >= panel["y"]
            and node_right <= panel["x"] + panel["width"]
        )
        if not (removed_by_crop or removed_by_panel):
            raise RuntimeError(
                f"{metadata['slug']}: detected price text lies outside the redacted regions: "
                f"{node['text']!r} at ({node['x']}, {node['y']})"
            )

    result = Image.new("RGB", screenshot.size, "white")
    visible_page = screenshot.crop((0, TOP_PROMO_CROP, screenshot.width, screenshot.height))
    result.paste(visible_page, (0, 0))

    panel_left = round(panel["x"])
    panel_top = round(panel["y"] - TOP_PROMO_CROP)
    panel_right = round(panel["x"] + panel["width"])
    draw = ImageDraw.Draw(result)
    draw.rectangle(
        (panel_left, panel_top, panel_right, result.height),
        fill="#ffffff",
        outline="#d1d7dc",
        width=2,
    )

    label = "SCAN TO OPEN COURSE"
    try:
        font = ImageFont.truetype("arialbd.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    label_box = draw.textbbox((0, 0), label, font=font)
    label_width = label_box[2] - label_box[0]
    label_x = panel_left + (panel_right - panel_left - label_width) // 2
    label_y = panel_top + 22
    draw.text((label_x, label_y), label, fill="#1c1d1f", font=font)

    qr_x = panel_left + (panel_right - panel_left - qr_overlay.width) // 2
    qr_y = label_y + 32
    result.paste(qr_overlay, (qr_x, qr_y))
    return result


def validate_qr(output_path: Path, expected_url: str) -> str:
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError(
            "QR validation requires opencv-python (use a version compatible with this project's NumPy pin)"
        ) from exc
    decoded, _, _ = cv2.QRCodeDetector().detectAndDecode(cv2.imread(str(output_path)))
    if decoded != expected_url:
        raise RuntimeError(
            f"{output_path.name}: QR decoded as {decoded!r}, expected {expected_url!r}"
        )
    return decoded


def generate_cover(page, course: dict, output_dir: Path) -> tuple[Path, dict]:
    screenshot, metadata = capture_course_screenshot(page, course)
    qr_overlay = make_qr_overlay(course["url"], QR_SIZE, QR_PADDING)
    final = compose_price_safe_cover(screenshot, qr_overlay, metadata)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / course["filename"]
    final.save(output_path, "PNG", optimize=True)
    metadata["qr_url"] = validate_qr(output_path, course["url"])
    metadata["dimensions"] = list(final.size)
    metadata["price_regions_removed"] = len(metadata["price_nodes"])
    return output_path, metadata


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
    parser.add_argument(
        "--cdp-url",
        default="http://127.0.0.1:9222",
        help=(
            "DevTools endpoint for an already-running, normal installed browser. "
            "The script never launches an automated browser or creates fallback pages."
        ),
    )
    parser.add_argument(
        "--metadata-output",
        type=Path,
        help="Optional JSON path for direct-capture and validation evidence.",
    )
    args = parser.parse_args()

    selected = COURSES
    if args.slug:
        wanted = {slug.lower() for slug in args.slug}
        selected = [course for course in COURSES if course["slug"] in wanted]
        missing = wanted - {course["slug"] for course in selected}
        if missing:
            raise SystemExit(f"Unknown slug(s): {', '.join(sorted(missing))}")

    capture_results = []
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.connect_over_cdp(args.cdp_url)
        except Exception as exc:
            raise SystemExit(
                "Could not connect to a normal installed browser. Start Chrome or Edge "
                "in headed mode with a dedicated profile and --remote-debugging-port=9222. "
                "No synthetic fallback is available."
            ) from exc
        contexts = browser.contexts
        if not contexts:
            raise SystemExit("The connected browser has no normal browsing context.")
        pages = contexts[0].pages
        page = pages[0] if pages else contexts[0].new_page()
        page.set_viewport_size(VIEWPORT)
        for index, course in enumerate(selected):
            output_path, metadata = generate_cover(page, course, args.output_dir)
            capture_results.append(metadata)
            print(
                f"Saved {output_path}: direct H1={metadata['h1']!r}, "
                f"QR verified, {metadata['price_regions_removed']} price regions removed"
            )
            if index < len(selected) - 1:
                page.wait_for_timeout(9000)

    if args.metadata_output:
        args.metadata_output.parent.mkdir(parents=True, exist_ok=True)
        args.metadata_output.write_text(
            json.dumps(capture_results, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
