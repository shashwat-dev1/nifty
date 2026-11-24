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
    # Compare API outcomes directly with independent stored candle lookups.
    from historical import connect
    from kp_engine import KPChart
    import pandas as pd
    response=page.request.post('http://127.0.0.1:8520/api/matches',data={'timestamp':'2026-11-20T10:30:00+05:30','start':'1995-11-03','end':'2026-11-20'}).json()
    target=KPChart(pd.Timestamp('2026-11-20T10:30:00+05:30')).calculate()['ruling_planets']
    with connect() as con:
        for row in response['rows']:
            assert KPChart(pd.Timestamp(row['timestamp'])).calculate()['ruling_planets']==target
            if row.get('price_15') is not None:
                t=pd.Timestamp(row['timestamp'])
                start=con.execute('select close from intraday where timestamp=?',[t]).fetchall()[0][0]
                end=con.execute("select close from intraday where timestamp=?",[t+pd.Timedelta(minutes=15)]).fetchall()[0][0]
                assert abs(row['return_15']-100*(end/start-1))<1e-7
    page.get_by_label('Matching method',exact=True).select_option('partial')
    page.get_by_label('Required ruling lords',exact=False).select_option(['moon_star','moon_sub'])
    with page.expect_response(lambda r:'/api/matches' in r.url and r.request.method=='POST') as pending:
        page.get_by_role('button',name='Find historical matches',exact=True).click()
    partial=pending.value.json()
    assert partial['total']>=response['total']
    for row in partial['rows']:
        independent=KPChart(pd.Timestamp(row['timestamp'])).calculate()['ruling_planets']
        assert all(independent[k]==target[k] for k in ['moon_star','moon_sub'])
    page.get_by_label('Neutral threshold',exact=True).fill('0.05')
    with page.expect_response(lambda r:'/api/statistics' in r.url) as pending:
        page.get_by_role('button',name='Summarize all matching observations').click()
    stat=pending.value.json()
    assert stat['positive']+stat['negative']+stat['flat']==stat['complete_forward_windows']
    if stat['complete_forward_windows']:assert abs(stat['positive_percent']+stat['negative_percent']+stat['neutral_percent']-100)<1e-8
    assert '24,852.15' not in page.locator('body').inner_text()
    page.get_by_role('button',name='Intraday timeline',exact=True).click()
    expect(page.get_by_role('heading',name='Intraday KP timeline')).to_be_visible(timeout=15000)
    for name in ['Overview','Data manager','Settings','Feedback','Research lab','Backtesting']:
        page.get_by_role('complementary').get_by_role('button',name=name,exact=True).click()
        expect(page.get_by_role('heading',name=name,exact=True)).to_be_visible()
    page.goto('http://127.0.0.1:8520/demo')
    expect(page.get_by_text('Read-only demo',exact=False)).to_be_visible()
    assert page.get_by_role('button',name='Data manager',exact=True).count()==0
    assert not errors,errors
    browser.close()
    print(json.dumps({'status':'passed','timestamp':'2026-11-20 10:30 IST','matches':9,'chart_session':'2023-09-01 15:15 IST','console_errors':errors}))

