"""Opt-in browser acceptance test against the real local archive; no network downloads."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).parent
with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    page=browser.new_page(viewport={'width':1550,'height':1050})
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8520')
    expect(page.get_by_role('heading',name='Historical Planetary Match Explorer')).to_be_visible()
    page.get_by_label('Selected date and time').fill('2026-11-20T10:30')
    page.get_by_role('button',name='Calculate KP',exact=True).click()
    expect(page.get_by_role('heading',name='Selected planetary positions')).to_be_visible(timeout=15000)
    page.get_by_role('button',name='Find historical matches',exact=True).click()
    expect(page.get_by_role('heading',name='9 earlier saved configurations')).to_be_visible(timeout=15000)
    rows=page.get_by_role('row').filter(has_text='2023-09-01 15:15:00 IST')
    assert rows.count()==2
    rows.first.get_by_role('button',name='View movement').click()
    expect(page.locator('.js-plotly-plot')).to_be_visible(timeout=20000)
    page.get_by_label('Candle interval').select_option('5')
    expect(page.locator('.js-plotly-plot')).to_be_visible()
    page.get_by_role('button',name='Summarize all matching observations').click()
    expect(page.get_by_text('Historical observations at 15 minutes',exact=False)).to_be_visible(timeout=15000)
    (ROOT/'verification').mkdir(exist_ok=True)
    page.screenshot(path=str(ROOT/'verification/explorer.png'),full_page=True)
    page.get_by_role('button',name='Intraday timeline',exact=True).click()
    expect(page.get_by_role('heading',name='Intraday KP timeline')).to_be_visible(timeout=15000)
    for name in ['Overview','Data manager','Settings','Feedback','Research lab','Backtesting']:
        page.get_by_role('button',name=name,exact=True).click()
        expect(page.get_by_role('heading',name=name,exact=True)).to_be_visible()
    page.goto('http://127.0.0.1:8520/demo')
    expect(page.get_by_text('PRIVATE DEMO · READ ONLY',exact=True)).to_be_visible()
    assert page.get_by_role('button',name='Data manager',exact=True).count()==0
    assert not errors,errors
    browser.close()
    print(json.dumps({'status':'passed','timestamp':'2026-11-20 10:30 IST','matches':9,'chart_session':'2023-09-01 15:15 IST','console_errors':errors}))
