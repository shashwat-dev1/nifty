"""Optional local-only Windows Edge acceptance check: python -m tests... or run this file."""
from pathlib import Path
import os
import sys
import tempfile
import sqlite3

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from private_demo import session
from playwright.sync_api import sync_playwright

if __name__=="__main__":
    with tempfile.TemporaryDirectory() as temp:
        session.FEEDBACK=Path(temp)/"feedback.sqlite3"
        network_check=session.owner_preflight
        def check(origin,password):
            network_check(origin,password)
            with sync_playwright() as driver:
                browser=driver.chromium.launch(executable_path=str(Path(os.environ["ProgramFiles(x86)"])/"Microsoft/Edge/Application/msedge.exe"),headless=True)
                try:
                    page=browser.new_page()
                    page.goto(origin)
                    page.get_by_label("Temporary access password").fill(password)
                    page.get_by_role("button",name="Open terminal").click()
                    page.get_by_role("heading",name="NIFTY 50 — KP Astro Market Research Terminal",exact=True).wait_for(timeout=30000)
                    for tab in ["KP calculator","Upstox connection","Data health"]:
                        page.get_by_text(tab,exact=True).first.click()
                        page.get_by_role("heading",name=tab,exact=True).wait_for(timeout=15000)
                    print("Edge: authenticated original dashboard and owner navigation passed.")
                finally:browser.close()
        session.owner_preflight=check
        session.serve(check=True)
