"""Auditable subdivision metadata; no change to reference scoring mathematics."""
from kp_engine import PLANETS,YEARS,star_lord,sub_lord
def subdivision(longitude):
    x=longitude%360
    width=360/27
    nak=int(x/width)
    edge=nak*width
    for step in range(9):
        i=(nak%9+step)%9
        end=edge+width*YEARS[i]/120
        if x<end or step==8:
            return {'longitude':x,'nakshatra':nak+1,'pada':int((x-nak*width)/(width/4))+1,
                'within_nakshatra_degrees':x-nak*width,'star_lord':star_lord(x),
                'sub_lord':sub_lord(x),'sub_start_degrees':edge,'sub_end_degrees':end,
                'boundary_convention':'Start inclusive, end exclusive; longitude modulo 360'}
        edge=end
