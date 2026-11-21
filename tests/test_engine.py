import unittest
from datetime import datetime,date
from zoneinfo import ZoneInfo
from kp_engine import KPChart,sign_lord,star_lord,sub_lord,day_lord,slots,julian_day
from backtest import summarize,history_report,make_events
IST=ZoneInfo('Asia/Kolkata')

class TestKP(unittest.TestCase):
 def test_lords(self):
  self.assertEqual(sign_lord(0),'Mars')
  self.assertEqual(star_lord(0),'Ketu')
  self.assertEqual(sub_lord(0),'Ketu')
  self.assertEqual(sub_lord(1.0),'Venus')
  self.assertEqual(day_lord(date(2026,11,20)),'Venus')
 def test_julian_timezone(self):
  self.assertAlmostEqual(julian_day(datetime(2000,1,1,17,30,tzinfo=IST)),2451545.0,places=7)
 def test_slot_count(self):
  self.assertEqual(len(list(slots(date(2026,11,20)))),26)
 def test_reject_naive(self):
  with self.assertRaises(ValueError):KPChart(datetime(2026,11,20,9,15))
 def test_score_is_component_sum(self):
  x=KPChart(datetime(2026,11,20,9,15,tzinfo=IST)).calculate()
  c=x['components']
  self.assertAlmostEqual(x['kp_score'],c['B12']-c['B13']+c['B14']+c['B15']+c['B16']+c['B17']-c['B18'])
  self.assertEqual(len(x['ruling_details']),5)
 def test_historical_reference(self):
  # The user's workbook FullDay_Analysis row 2 (cached) has KP=18.
  # If this fails under a different Swiss ephemeris backend, investigate parity rather than altering the assertion.
  x=KPChart(datetime(2026,11,20,9,15,tzinfo=IST)).calculate()
  self.assertEqual(x['kp_score'],18)
 def test_all_26_workbook_scores(self):
  # Values read from user's saved FullDay_Analysis U2:U27, not predicted outcomes.
  expected=[18.0, 18.0, 18.0, 18.0, 8.0, 8.0, 8.0, 14.0, 14.0, 14.0, 14.0, 14.0, 6.0, 7.0, -5.0, 2.0, 2.0, 2.0, 6.0, 6.0, -2.0, 6.0, 2.0, -2.0, -2.0, -2.0]
  result=[KPChart(ts).calculate()['kp_score'] for ts in slots(date(2026,11,20))]
  self.assertEqual(result,expected)
 def test_strict_forward_prices(self):
  d=date(2026,11,20)
  vals=[(datetime(2026,11,20,h,m,tzinfo=IST),p) for h,m,p in [(9,15,100),(9,30,101),(9,45,99)]]
  ev=make_events(vals,15)
  self.assertEqual(len(ev),2)
  self.assertAlmostEqual(ev[0]['return'],.01)
 def test_train_test_isolation(self):
  base=datetime(2026,11,18,9,15,tzinfo=IST)
  e1={'date':date(2026,11,18),'timestamp':base,'signature':'A','up':1,'down':0,'return':.01}
  e2={'date':date(2026,11,20),'timestamp':base,'signature':'A','up':0,'down':1,'return':-.01}
  out=history_report([e1,e2],date(2026,11,19),1)
  self.assertEqual(out['matches'][0]['prior_up_frequency'],1)
  self.assertEqual(out['test']['up'],0)

if __name__=='__main__':unittest.main()
