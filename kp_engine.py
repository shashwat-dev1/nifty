"""Faithful port of the uploaded VBA's KP module (not a validated forecasting model).
Timezone: Asia/Kolkata; reference chart: Jaipur, Lahiri sidereal/Placidus/mean node.
"""
from __future__ import annotations
from datetime import datetime, date, time, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo
import swisseph as swe

IST = ZoneInfo('Asia/Kolkata')
PLANETS = ('Ketu','Venus','Sun','Moon','Mars','Rahu','Jupiter','Saturn','Mercury')
YEARS = (7,20,6,10,7,18,16,19,17)
SIGN_LORD = (4,1,8,3,2,8,1,4,6,7,7,6)
IDS = {'Sun':swe.SUN,'Moon':swe.MOON,'Mercury':swe.MERCURY,
       'Venus':swe.VENUS,'Mars':swe.MARS,'Jupiter':swe.JUPITER,
       'Saturn':swe.SATURN,'Rahu':swe.MEAN_NODE}
GAIN = {2,6,10,11}; LOSS = {5,8,12}
# Exact values from KP_Astrology!B3:B10 in the uploaded .xlsm.
DEFAULT_WEIGHTS = {'gain':2.0,'loss':-2.0,'timing':1.0,'ruling_majority':2.0,
                   'sub_confirmation':3.0,'lagna_confirmation':2.0,'mixed':-2.0}
LAT = 26.9124; LON = 75.7873


def normalize_time(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError('Timestamp needs timezone; e.g. +05:30 or Asia/Kolkata')
    return value.astimezone(IST)


def julian_day(value: datetime) -> float:
    value = normalize_time(value)
    utc = value.astimezone(ZoneInfo('UTC'))
    h = utc.hour + utc.minute/60 + (utc.second+utc.microsecond/1e6)/3600
    return swe.julday(utc.year, utc.month, utc.day, h, swe.GREG_CAL)


def sign_lord(longitude: float) -> str:
    return PLANETS[SIGN_LORD[int((longitude % 360)/30)]]


def star_lord(longitude: float) -> str:
    return PLANETS[int((longitude % 360)/(360/27)) % 9]


def sub_lord(longitude: float) -> str:
    long_mod = longitude % 360
    nak = int(long_mod / (360/27))
    start = nak % 9
    within = long_mod - nak*(360/27)
    elapsed = 0.0
    for step in range(9):
        i = (start + step) % 9
        elapsed += YEARS[i]/120*(360/27)
        if within < elapsed:
            return PLANETS[i]
    return PLANETS[(start+8) % 9]


def day_lord(d: date) -> str:
    return ('Moon','Mars','Mercury','Jupiter','Venus','Saturn','Sun')[d.weekday()]

class KPChart:
    def __init__(self, when: datetime, lat: float = LAT, lon: float = LON, ephe_path: str | None = None):
        self.when = normalize_time(when)
        self.jd = julian_day(self.when)
        self.lat, self.lon = lat, lon
        if ephe_path:
            swe.set_ephe_path(ephe_path)
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        self.flags = swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL
        self.cusps, self.ascmc = swe.houses_ex(self.jd, lat, lon, b'P', swe.FLG_SIDEREAL)

    @lru_cache(maxsize=64)
    def longitude(self, name: str) -> float:
        if name == 'Ketu':
            return (self.longitude('Rahu') + 180) % 360
        if name not in IDS:
            raise ValueError(f'Unknown planet {name}')
        result, returned_flags = swe.calc_ut(self.jd, IDS[name], self.flags)
        # Swiss can silently fall back to Moshier if Swiss files are absent.
        # Both paths give astronomical calculations, but parity may differ.
        return result[0] % 360

    def house(self, longitude: float) -> int:
        x = longitude % 360
        for h in range(12):
            start, end = self.cusps[h] % 360, self.cusps[(h+1)%12] % 360
            if (start <= x < end) if start <= end else (x >= start or x < end):
                return h+1
        raise ArithmeticError('No house found: check cusps')

    @lru_cache(maxsize=64)
    def basic_houses(self, name: str) -> frozenset[int]:
        p = self.longitude(name)
        result = {self.house(p)}
        for h,cusp in enumerate(self.cusps, 1):
            if sign_lord(cusp) == name:
                result.add(h)
        return frozenset(result)

    @lru_cache(maxsize=64)
    def significator_houses(self, name: str) -> frozenset[int]:
        p = self.longitude(name)
        names = [name, star_lord(p), sub_lord(p)]
        if name in ('Rahu','Ketu'):
            names.append(sign_lord(p))
        result = set()
        for n in names:
            result.update(self.basic_houses(n))
        return frozenset(result)

    def calculate(self, weights: dict | None = None) -> dict:
        weights = dict(DEFAULT_WEIGHTS if weights is None else weights)
        moon = self.longitude('Moon')
        ruling = (day_lord(self.when.date()), sign_lord(moon), star_lord(moon),
                  sub_lord(moon), sign_lord(self.ascmc[0]))
        rows = []
        for role, name in zip(('day','moon_sign','moon_star','moon_sub','lagna'),ruling):
            houses = self.significator_houses(name)
            g,l = len(houses & GAIN),len(houses & LOSS)
            status = 'gain' if g>l else 'loss' if l>g else 'mixed' if g>0 and l>0 else 'none'
            rows.append({'role':role,'planet':name,'houses':','.join(map(str,sorted(houses))),
                         'gain_houses':g,'loss_houses':l,'class':status})
        gain = sum(x['class']=='gain' for x in rows)
        loss = sum(x['class']=='loss' for x in rows)
        mixed = sum(x['class']=='mixed' for x in rows)
        majority = 'bullish' if gain>=3 and gain>loss else 'bearish' if loss>=3 and loss>gain else 'none'
        sub = rows[3]['class']; lag = rows[4]['class']
        timing = int(sub in ('gain','loss'))
        confirm_sub = int((majority=='bullish' and sub=='gain') or (majority=='bearish' and sub=='loss'))
        confirm_lagna = int((majority=='bullish' and lag=='gain') or (majority=='bearish' and lag=='loss'))
        # Exactly reproduces VBA B12-B13+B14+B15+B16+B17-B18.
        components = {
          'B12':gain*weights['gain'],
          'B13':loss*abs(weights['loss']),
          'B14':timing*weights['timing'],
          'B15':int(majority!='none')*weights['ruling_majority'],
          'B16':confirm_sub*weights['sub_confirmation'],
          'B17':confirm_lagna*weights['lagna_confirmation'],
          'B18':mixed*abs(weights['mixed'])}
        score = components['B12']-components['B13']+sum(components[k] for k in ('B14','B15','B16','B17'))-components['B18']
        return {'timestamp':self.when.isoformat(),'ruling_planets':dict(zip(('day','moon_sign','moon_star','moon_sub','lagna'),ruling)),
                'ruling_details':rows,'gain_count':gain,'loss_count':loss,'mixed_count':mixed,
                'majority':majority,'components':components,'kp_score':score,
                'signature':'|'.join(ruling), 'moon_longitude':round(moon,8),
                'ascendant_longitude':round(self.ascmc[0],8),
                'config':{'lat':self.lat,'lon':self.lon,'ayanamsa':'Lahiri','houses':'Placidus','node':'Mean'}}


def slots(d: date, step_minutes: int = 15):
    if step_minutes<=0: raise ValueError('step must be positive')
    current = datetime.combine(d,time(9,15),tzinfo=IST)
    finish = datetime.combine(d,time(15,30),tzinfo=IST)
    while current<=finish:
        yield current
        current += timedelta(minutes=step_minutes)
