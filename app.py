# app.py
import streamlit as st
from pathlib import Path
from datetime import date
import pandas as pd
import plotly.express as px

from main import FamilyExpenseTracker

st.set_page_config(page_title="Family Expense Tracker", layout="wide")
st.title("Family Expense Tracker — Integrated")

# ensure one tracker stored in session_state
if "tracker" not in st.session_state:
    st.session_state.tracker = FamilyExpenseTracker()

tracker: FamilyExpenseTracker = st.session_state.tracker

# Layout: left column for inputs, right column for overview & visuals
left, right = st.columns([1, 2])

with left:
    st.header("Members")
    with st.form("member_form", clear_on_submit=True):
        name = st.text_input("Member name").strip().title()
        earning = st.checkbox("Earning status")
        earnings = 0.0
        if earning:
            earnings = st.number_input("Earnings (monthly)", min_value=0.0, value=0.0, step=100.0)
        submit_member = st.form_submit_button("Save member")
        if submit_member:
            try:
                tracker.add_member(name, earning, earnings)
                st.success(f"Saved '{name}'")
            except Exception as e:
                st.error(str(e))

    st.markdown("---")
    st.header("Add expense")
    members = tracker.available_persons()
    if not members:
        st.info("No members yet. Add a member to start logging expenses.")
    else:
        with st.form("expense_form", clear_on_submit=True):
            person = st.selectbox("Person", members)
            category_period = st.selectbox("Period Category", ["one-time", "monthly", "quarterly", "2-quarter", "3-quarter", "yearly"])
            category = st.selectbox("Category", ["Housing", "Food", "Transportation", "Entertainment", "Child-Related", "Medical", "Investment", "Miscellaneous"])
            expense_type = st.selectbox("Expense type", ["big", "small"])
            sub_map = {
                "big": ["EMI1", "EMI2", "HomeLoan", "CarLoan", "SIP1", "SIP2"],
                "small": ["Groceries", "Transport", "Utility", "Dining", "Pocket", "Misc"]
            }
            sub_type = st.selectbox("Sub-type", sub_map.get(expense_type, ["Other"]))
            description = st.text_input("Description (optional)")
            amount = st.number_input("Amount", min_value=0.0, value=0.0, step=10.0)
            exp_date = st.date_input("Date", value=date.today())
            submit_exp = st.form_submit_button("Add expense")
            if submit_exp:
                try:
                    tracker.add_expense(person, float(amount), category_period, category, expense_type, sub_type, description, exp_date.isoformat())
                    st.success("Expense added.")
                except Exception as e:
                    st.error(str(e))

with right:
    st.header("Overview & Visuals")
    df = tracker.get_expenses_df()
    if df.empty:
        st.info("No expenses recorded yet.")
    else:
        st.subheader("Filters")
        c1, c2, c3, c4 = st.columns([1,1,2,2])
        persons = ["All"] + sorted(df["person"].unique().tolist())
        filt_person = c1.selectbox("Person", options=persons)
        periods = ["All"] + sorted(df["category_period"].fillna("Unknown").unique().tolist())
        filt_period = c2.selectbox("Period", options=periods)
        min_date = df["date"].min().date()
        max_date = df["date"].max().date()
        date_range = c3.date_input("Date range", value=(min_date, max_date))
        search = c4.text_input("Search description/sub-type")

        filtered = df.copy()
        if filt_person != "All":
            filtered = filtered[filtered["person"] == filt_person]
        if filt_period != "All":
            filtered = filtered[filtered["category_period"] == filt_period]
        start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
        filtered = filtered[(filtered["date"] >= start) & (filtered["date"] <= end)]
        if search:
            filtered = filtered[filtered["description"].str.contains(search, case=False, na=False) | filtered["sub_type"].str.contains(search, case=False, na=False)]

        st.subheader("Expenses table")
        st.dataframe(filtered.sort_values("date", ascending=False), use_container_width=True)

        st.subheader("Metrics")
        total = filtered["amount"].sum()
        st.metric("Filtered total", f"{total:.2f}")
        st.metric("Overall earnings", f"{tracker.total_earnings():.2f}")
        st.metric("Overall expenditure", f"{tracker.total_expenditure():.2f}")
        st.metric("Remaining balance", f"{tracker.remaining_balance():.2f}")

        st.markdown("---")
        st.subheader("Charts")

        # Pie by category
        by_cat = filtered.groupby("category", as_index=False)["amount"].sum()
        if not by_cat.empty:
            fig = px.pie(by_cat, names="category", values="amount", title="Spending by Category", hole=0.3)
            st.plotly_chart(fig, use_container_width=True)

        # Trend (monthly)
        temp = filtered.copy()
        temp["month"] = temp["date"].dt.to_period("M").dt.to_timestamp()
        trend = temp.groupby("month", as_index=False)["amount"].sum()
        if not trend.empty:
            fig2 = px.line(trend, x="month", y="amount", title="Monthly spending trend")
            st.plotly_chart(fig2, use_container_width=True)

        # By person
        by_person = filtered.groupby("person", as_index=False)["amount"].sum()
        if not by_person.empty:
            fig3 = px.bar(by_person, x="person", y="amount", title="Spending by Person")
            st.plotly_chart(fig3, use_container_width=True)

        st.markdown("---")
        st.subheader("Manage records")
        cols = st.columns([2,1])
        with cols[0]:
            ids = filtered["id"].tolist()
            if ids:
                del_id = st.selectbox("Delete expense id", options=["None"] + ids)
                if del_id != "None" and st.button("Delete selected"):
                    tracker.delete_expense(int(del_id))
                    st.experimental_rerun()
        with cols[1]:
            # member deletion UI
            mems = tracker.get_members_df()
            if not mems.empty:
                del_mem = st.selectbox("Delete member", options=["None"] + mems["name"].tolist())
                if del_mem != "None" and st.button("Delete member"):
                    tracker.delete_member(del_mem)
                    st.experimental_rerun()
