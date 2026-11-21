from contextlib import closing
from datetime import date, datetime, time
from pathlib import Path
import os
import pandas as pd
import plotly.express as px
import streamlit as st
from kp_engine import KPChart, IST
from private_demo.data import FEATURES, add_feedback, open_snapshot

st.set_page_config(page_title="NIFTY 50 · Private research demo",layout="wide",menu_items={"Get Help":None,"Report a bug":None,"About":"Private feedback session"})
st.title("NIFTY 50 · KP research terminal")
st.caption("Private tester session · Jaipur · Lahiri · Placidus · IST")
st.info("KP scores describe astrological rules. Historical frequencies describe observed samples. Neither provides a guaranteed trading probability.")
page=st.sidebar.radio("Workspace",["KP calculator","Historical matches","Backtesting results","Feedback"])
if page in ("KP calculator","Historical matches"):
    day=st.sidebar.date_input("Chart date",date(2026,11,20),min_value=date(1900,1,1),max_value=date(2100,12,31))
    clock=st.sidebar.time_input("Time in Jaipur",time(10,30))
    ts=datetime.combine(day,clock,tzinfo=IST)
    if not date(1900,1,1)<=ts.date()<=date(2100,12,31):st.stop()
    result=KPChart(ts).calculate()
    st.header(page)
    st.caption(ts.strftime("%d %B %Y · %H:%M IST"))
    st.metric("KP score",f"{result['kp_score']:g}")
    if page=="KP calculator":
        st.table(pd.DataFrame(result["ruling_details"]).set_index("role"))
        st.caption("Each row counts the ruling planet's significator houses in the gain and loss groups.")
        st.write("Score components")
        st.bar_chart({k:[v*(-1 if k in ("B13","B18") else 1)] for k,v in result["components"].items()})
    else:
        args=(result["signature"],day.isoformat())
        with closing(open_snapshot(os.environ["KP_DEMO_SNAPSHOT"])) as db:
            n=db.execute("SELECT count(*) FROM charts WHERE signature=? AND stamp<?",args).fetchone()[0]
            rows=db.execute("SELECT stamp,score FROM charts WHERE signature=? AND stamp<? ORDER BY stamp DESC LIMIT 25",args).fetchall()
        st.write(result["signature"].replace("|"," · "))
        st.metric("Earlier saved five-lord matches",n)
        if rows:
            st.caption("Most recent matching snapshots, up to 25. Several timestamps can fall in one session.")
            st.table(pd.DataFrame(rows,columns=["IST timestamp","KP score"]).set_index("IST timestamp"))
elif page=="Backtesting results":
    st.header(page)
    study=st.selectbox("Saved study",["Daily walk-forward","Intraday holdout"])
    with closing(open_snapshot(os.environ["KP_DEMO_SNAPSHOT"])) as db:
        data=pd.read_sql_query("SELECT period,n,correct,baseline FROM studies WHERE study=? ORDER BY period",db,params=[study])
    if len(data):
        st.caption("Daily study uses expanding annual training and open-to-close outcomes." if study=="Daily walk-forward" else "15-minute study trained in September–October 2026 and tested in November 2026.")
        displays=pd.DataFrame({"Year":data.period,"Cases":data.n,"KP accuracy (%)":100*data.correct/data.n,"Baseline accuracy (%)":100*data.baseline/data.n})
        st.plotly_chart(px.bar(displays,x="Year",y=["KP accuracy (%)","Baseline accuracy (%)"],barmode="group"),config={"displayModeBar":False})
        st.table(displays.round(1).set_index("Year"))
        st.caption("The baseline predicts the most common training outcome. A difference in observed accuracy can arise by chance.")
else:
    st.header("Feedback")
    with st.form("tester_feedback",clear_on_submit=True):
        feature=st.selectbox("Feature being reviewed",FEATURES)
        expected=st.text_area("Expected result",max_chars=1800)
        actual=st.text_area("Actual result",max_chars=1800)
        comments=st.text_area("Comments or suggestions",max_chars=1800)
        save=st.form_submit_button("Submit feedback")
    if save:
        try:
            add_feedback(Path(os.environ["KP_DEMO_FEEDBACK"]),feature,expected,actual,comments)
            st.success("Feedback saved for the dashboard owner.")
        except ValueError as exc:
            st.error(str(exc))

