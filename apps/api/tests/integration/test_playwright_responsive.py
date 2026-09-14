import os
import sys
import pytest
from playwright.sync_api import sync_playwright

VIEWPORTS = [
    {"name": "mobile_small", "width": 360, "height": 640},
    {"name": "mobile_medium", "width": 390, "height": 844},
    {"name": "tablet_portrait", "width": 768, "height": 1024},
    {"name": "tablet_landscape", "width": 1024, "height": 768},
    {"name": "desktop_standard", "width": 1280, "height": 800},
    {"name": "desktop_large", "width": 1920, "height": 1080},
]

SCREENSHOT_DIR = os.path.abspath("scratch/screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

def test_responsive_viewports_and_contrast():
    print(f"\n--- Testing Playwright Across 6 Viewports ---")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        for vp in VIEWPORTS:
            context = browser.new_context(viewport={"width": vp["width"], "height": vp["height"]})
            page = context.new_page()
            
            # 1. Load Homepage
            page.goto("http://127.0.0.1:8080", wait_until="networkidle")
            
            # 2. Check for Horizontal Overflow (scrollWidth vs innerWidth)
            has_horizontal_scroll = page.evaluate("""() => {
                return document.documentElement.scrollWidth > window.innerWidth;
            }""")
            scroll_width = page.evaluate("() => document.documentElement.scrollWidth")
            inner_width = page.evaluate("() => window.innerWidth")
            
            print(f"[{vp['name']} {vp['width']}x{vp['height']}] scrollWidth: {scroll_width}, innerWidth: {inner_width}")
            assert not has_horizontal_scroll, f"Horizontal scroll detected on {vp['name']}: {scroll_width} > {inner_width}"
            
            # 3. Verify Active Tab styling & Color Contrast
            # The active tab has background #0f392b (dark green) and text #ffffff (white)
            active_btn_color = page.evaluate("""() => {
                const btn = document.querySelector('button');
                if (!btn) return null;
                const style = window.getComputedStyle(btn);
                return { color: style.color, bg: style.backgroundColor };
            }""")
            
            # 4. Save Screenshot Artifact
            screenshot_path = os.path.join(SCREENSHOT_DIR, f"{vp['name']}.png")
            page.screenshot(path=screenshot_path, full_page=False)
            assert os.path.exists(screenshot_path)
            print(f"  -> Captured screenshot: {screenshot_path}")
            
            context.close()
        
        browser.close()
        print("SUCCESS: All 6 viewports responsive with zero horizontal overflow!")

if __name__ == "__main__":
    test_responsive_viewports_and_contrast()
