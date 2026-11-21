import argparse,json,csv
from datetime import date,datetime
from kp_engine import KPChart,slots
from backtest import read_prices,make_events,history_report,save_events

p=argparse.ArgumentParser(description='Research-only NIFTY KP engine')
s=p.add_subparsers(dest='command',required=True)
a=s.add_parser('point');a.add_argument('timestamp',help='ISO with offset, e.g. 2026-11-20T09:15:00+05:30')
a=s.add_parser('day');a.add_argument('day',help='YYYY-MM-DD');a.add_argument('--output',default='kp_day.csv')
a=s.add_parser('backtest');a.add_argument('--prices',required=True);a.add_argument('--split',required=True);a.add_argument('--horizon',type=int,default=15);a.add_argument('--step',type=int,default=15);a.add_argument('--minimum',type=int,default=10);a.add_argument('--output',default='nifty_events.csv');a.add_argument('--report',default='backtest_report.json')
args=p.parse_args()
if args.command=='point':
 print(json.dumps(KPChart(datetime.fromisoformat(args.timestamp)).calculate(),indent=2))
elif args.command=='day':
 with open(args.output,'w',newline='') as f:
  w=csv.writer(f);w.writerow(['timestamp','day','moon_sign','moon_star','moon_sub','lagna','gain','loss','mixed','majority','kp_score','signature'])
  for ts in slots(date.fromisoformat(args.day)):
   x=KPChart(ts).calculate();r=x['ruling_planets'];w.writerow([ts.isoformat(),*r.values(),x['gain_count'],x['loss_count'],x['mixed_count'],x['majority'],x['kp_score'],x['signature']])
 print(f'Wrote {args.output}')
else:
 events=make_events(read_prices(args.prices),args.horizon,args.step)
 save_events(events,args.output)
 report=history_report(events,date.fromisoformat(args.split),args.minimum)
 with open(args.report,'w') as f:json.dump(report,f,indent=2)
 print(json.dumps({k:v for k,v in report.items() if k!='matches'},indent=2))
 print('Saved',args.output,args.report)
