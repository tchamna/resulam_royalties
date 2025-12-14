#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
from datetime import datetime

import boto3
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

# -------------------------------------------------------------------
# Load environment
# -------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(ENV_PATH, override=True)

KDP_EMAIL = os.getenv("KDP_EMAIL")
KDP_PASSWORD = os.getenv("KDP_PASSWORD")

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET = os.getenv("S3_BUCKET")
S3_PREFIX = os.getenv("S3_PREFIX", "kdp-reports/")

# Orders page (Lifetime report)
KDP_REPORTS_URL = os.getenv(
    "KDP_REPORTS_URL",
    "https://kdpreports.amazon.com/orders",
)

print("[DEBUG] KDP_REPORTS_URL from env:", repr(KDP_REPORTS_URL))

# Local download folder
LOCAL_DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
os.makedirs(LOCAL_DOWNLOAD_DIR, exist_ok=True)

# Toggle S3 upload
ENABLE_S3_UPLOAD = False  # set to True when ready

if not KDP_EMAIL or not KDP_PASSWORD:
    raise RuntimeError("Missing required env vars (KDP_EMAIL, KDP_PASSWORD).")
if ENABLE_S3_UPLOAD and not S3_BUCKET:
    raise RuntimeError("ENABLE_S3_UPLOAD=True but S3_BUCKET is not set in .env")

# For debugging: see browser (must be False if you want totally headless)
HEADLESS = False  # keep False because you must type the SMS code


# -------------------------------------------------------------------
# Login + SMS MFA
# -------------------------------------------------------------------
def login_to_kdp(page):
    """
    Logs into KDP with email/password.
    You enter SMS code manually in the browser; script waits automatically
    until Amazon leaves the MFA page, then goes to the Orders report.
    """

    # 1) Open KDP landing page
    page.goto("https://kdp.amazon.com/en_US/")
    page.wait_for_load_state("networkidle")
    print("[DEBUG] After goto, URL:", page.url)

    # 2) If we are already on the Amazon sign-in page, skip to email
    if "ap/signin" not in page.url:
        print("[DEBUG] Not yet on sign-in page, trying to click Sign in...")

        sign_in_selectors = [
            "a#signin-button",            # common KDP "Sign in" button
            "text='Sign in'",             # generic visible text
            "a[href*='ap/signin']",       # any link that goes to Amazon sign-in
            "button:has-text('Sign in')", # if it's a button
        ]

        clicked = False
        for sel in sign_in_selectors:
            try:
                if page.is_visible(sel):
                    print(f"[DEBUG] Clicking sign-in using selector: {sel}")
                    page.click(sel)
                    clicked = True
                    break
            except Exception as e:
                print(f"[DEBUG] Selector {sel} failed with: {e}")

        if not clicked:
            raise RuntimeError(
                "Could not find a Sign in button/link on KDP landing page. "
                "Open https://kdp.amazon.com/en_US/ in your normal browser, "
                "right-click the Sign in element, Inspect, and adjust selectors."
            )

        page.wait_for_load_state("networkidle")
        print("[DEBUG] After clicking sign-in, URL:", page.url)

    # 3) Amazon login form
    print("[DEBUG] Waiting for email field on Amazon login page...")
    page.wait_for_selector("input#ap_email", timeout=30000)
    page.fill("input#ap_email", KDP_EMAIL)
    page.click("input#continue")

    print("[DEBUG] Waiting for password field...")
    page.wait_for_selector("input#ap_password", timeout=30000)
    page.fill("input#ap_password", KDP_PASSWORD)
    page.click("input#signInSubmit")

    # 4) Handle SMS MFA (user types code in browser, no ENTER in terminal)
    handle_mfa_sms(page)

    # 5) After MFA, explicitly go to the Orders reports page
    page.wait_for_load_state("networkidle")
    print("[DEBUG] After login/MFA, URL:", page.url)

    print("[DEBUG] Navigating to reports URL after login...")
    page.goto(KDP_REPORTS_URL)
    page.wait_for_load_state("networkidle")
    print("[DEBUG] After forcing navigation to reports, URL:", page.url)


def handle_mfa_sms(page):
    """
    Detects the SMS 2SV page and waits AUTOMATICALLY until the user enters the SMS code
    and Amazon redirects away from the MFA/sign-in URL.
    No ENTER key needed.
    """

    page.wait_for_load_state("networkidle")
    time.sleep(1)

    # Detect OTP field
    otp_selectors = [
        "input#auth-mfa-otpcode",
        "input[name='otpCode']",
        "input[type='tel']",
        "input[autocomplete='one-time-code']",
    ]

    mfa_shown = False
    for sel in otp_selectors:
        try:
            if page.is_visible(sel):
                print(f"[INFO] SMS 2-Step Verification detected (selector: {sel}).")
                mfa_shown = True
                break
        except Exception:
            continue

    if not mfa_shown:
        print("[DEBUG] No MFA prompt detected (maybe trusted device).")
        return

    print(
        "[INFO] Please:\n"
        "  1) Check your phone for the SMS code.\n"
        "  2) In the Playwright browser window, type the code in the field.\n"
        "  3) Click the yellow 'Sign in' button.\n"
        "The script will continue automatically once Amazon finishes logging you in."
    )

    # Wait until we leave /ap/mfa and /ap/signin
    max_wait_seconds = 180
    start = time.time()

    while True:
        page.wait_for_load_state("networkidle")
        url = page.url

        # SUCCESS: left the MFA/sign-in pages
        if "ap/mfa" not in url and "ap/signin" not in url:
            print("[INFO] Amazon accepted the SMS code. Continuing…")
            break

        if time.time() - start > max_wait_seconds:
            raise RuntimeError(
                "Timed out waiting for Amazon to accept the SMS code. "
                "Still on MFA or sign-in page."
            )

        time.sleep(1)


# -------------------------------------------------------------------
# Reports download (Orders page)
# -------------------------------------------------------------------
def click_download_button(page):
    """
    Clicks the download/export button on https://kdpreports.amazon.com/orders.
    """
    candidate_selectors = [
        "button:has-text('Download')",
        "button:has-text('Download report')",
        "button:has-text('Export')",
        "text='Download'",
        "[data-testid*='download']",
        "[aria-label*='Download']",
    ]

    for sel in candidate_selectors:
        try:
            if page.is_visible(sel):
                print(f"[DEBUG] Clicking download using selector: {sel}")
                page.click(sel)
                return
        except Exception as e:
            print(f"[DEBUG] Download selector {sel} failed with: {e}")
            continue

    raise RuntimeError(
        "Could not find a visible Download/Export button. "
        "Inspect the element in your browser and update selectors in click_download_button()."
    )


def set_lifetime_range(page):
    """
    On the Orders reports page (kdpreports.amazon.com/orders),
    open the date picker and select 'Lifetime'.
    """

    opened = False
    try:
        page.get_by_label("End Date").click()
        opened = True
        print("[DEBUG] Opened date picker via 'End Date' label")
    except Exception as e:
        print(f"[DEBUG] Could not click End Date by label: {e}")

    if not opened:
        try:
            page.get_by_label("Start Date").click()
            opened = True
            print("[DEBUG] Opened date picker via 'Start Date' label")
        except Exception as e:
            print(f"[DEBUG] Could not click Start Date by label: {e}")

    if not opened:
        print("[WARN] Could not open date picker (Start/End Date not found).")
        return

    page.wait_for_timeout(1000)

    try:
        page.get_by_role("button", name="Lifetime").click()
        print("[DEBUG] Clicked 'Lifetime' range button")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)
    except Exception as e:
        print(f"[WARN] Could not click 'Lifetime' button: {e}")


def download_report(page, download_dir: str) -> str:
    """
    Open the KDP Orders reports page and download the Lifetime orders report.
    """
    print("[DEBUG] Navigating to orders page:", KDP_REPORTS_URL)
    page.goto(KDP_REPORTS_URL)
    page.wait_for_load_state("networkidle")
    print("[DEBUG] After navigating to reports, URL:", page.url)

    # Guard: if MFA/login failed, kdpreports will usually redirect back to ap/signin
    if "kdpreports.amazon.com" not in page.url:
        raise RuntimeError(
            f"Not on kdpreports after login, current URL is: {page.url}\n"
            "This means login/MFA did not succeed."
        )

    set_lifetime_range(page)

    with page.expect_download() as download_info:
        click_download_button(page)
    download = download_info.value

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    suggested = download.suggested_filename or f"kdp_orders_{timestamp}.csv"
    local_path = os.path.join(download_dir, suggested)
    download.save_as(local_path)

    return local_path


# -------------------------------------------------------------------
# S3 upload
# -------------------------------------------------------------------
def upload_to_s3(local_path: str) -> str:
    s3 = boto3.client("s3", region_name=AWS_REGION)

    today = datetime.utcnow().strftime("%Y-%m-%d")
    filename = os.path.basename(local_path)
    s3_key = f"{S3_PREFIX}{today}/{filename}"

    s3.upload_file(local_path, S3_BUCKET, s3_key)
    print(f"Uploaded to s3://{S3_BUCKET}/{s3_key}")
    return s3_key


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------
def main():
    print(f"[INFO] Local download folder: {LOCAL_DOWNLOAD_DIR}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, slow_mo=500)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        try:
            print("[INFO] Logging into KDP...")
            login_to_kdp(page)
            print("[INFO] Login + SMS 2SV successful (session cookies set).")
            print("[INFO] Downloading Lifetime report...")

            csv_path = download_report(page, LOCAL_DOWNLOAD_DIR)
            print(f"[INFO] Report downloaded to: {csv_path}")

            size_bytes = os.path.getsize(csv_path)
            print(f"[INFO] File size: {size_bytes} bytes")

            if ENABLE_S3_UPLOAD:
                s3_key = upload_to_s3(csv_path)
                print(f"[INFO] Uploaded to S3 as: {s3_key}")
            else:
                print("[INFO] S3 upload is DISABLED (testing local save only).")

        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    main()
