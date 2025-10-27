# app.py
import streamlit as st
from datetime import date
import pandas as pd
import plotly.express as px

from main import FamilyExpenseTracker

st.set_page_config(page_title="Family Expense Tracker", layout="wide")
st.title("Family Expense Tracker")

# single tracker instance in session
if "tracker" not in st.session_state:
    st.session_state.tracker = FamilyExpenseTracker()

if "last_action" not in st.session_state:
    st.session_state.last_action = None

tracker: FamilyExpenseTracker = st.session_state.tracker

# ---------- helper UI functions ----------
def show_members_page():
    st.header("Members — Add / Manage")
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
                st.session_state.last_action = "member_added"
                st.experimental_rerun()
            except Exception as e:
                st.error(str(e))

    st.markdown("---")
    mems = tracker.get_members_df()
    if mems.empty:
        st.info("No members yet. Add family members to get started.")
    else:
        st.subheader("Existing members")
        for _, row in mems.iterrows():
            col1, col2, col3, col4 = st.columns([2,1,1,1])
            col1.write(f"**{row['name']}**")
            col2.write("Earning" if row["earning_status"] else "Not earning")
            col3.write(f"{row['earnings']:.2f}")
            if col4.button(f"Delete {row['name']}", key=f"del_member_{row['id']}"):
                tracker.delete_member(row["name"])
                st.success(f"Deleted {row['name']}")
                st.experimental_rerun()

def add_expense_form():
    st.header("Add Expense")
    members = tracker.available_persons()
    if not members:
        st.info("No members present. Add members first.")
        return

    with st.form("expense_form", clear_on_submit=True):
        person = st.selectbox("Person", members)
        # expense type first
        expense_type = st.selectbox("Expense type", ["big", "small"])
        # recurring toggle (only show period when recurring or big)
        is_recurring = st.checkbox("Mark as recurring (EMI / yearly / subscription)", value=False)
        show_period = is_recurring or (expense_type == "big")
        if show_period:
            category_period = st.selectbox(
                "Period Category",
                ["daily", "one-time", "monthly", "quarterly", "2-quarter", "3-quarter", "yearly"],
            )
        else:
            category_period = "one-time"
        # category after type/period
        category = st.selectbox("Category", ["Housing", "Food", "Transportation", "Entertainment", "Child-Related", "Medical", "Investment", "Miscellaneous"])
        # sub-type only for big
        sub_map = {
            "big": ["EMI1", "EMI2", "HomeLoan", "CarLoan", "SIP1", "SIP2"],
            "small": []
        }
        sub_type = ""
        if expense_type == "big":
            sub_type = st.selectbox("Sub-type (if applicable)", sub_map["big"])
        description = st.text_input("Description (optional)")
        amount = st.number_input("Amount", min_value=0.0, value=0.0, step=10.0)
        exp_date = st.date_input("Date", value=date.today())
        submitted = st.form_submit_button("Add expense")
        if submitted:
            if amount <= 0:
                st.error("Enter an amount greater than 0.")
            else:
                # for small items we keep sub_type empty and rely on description
                if expense_type == "small":
                    sub_type_to_store = ""  # alternative: description.strip()[:100]
                else:
                    sub_type_to_store = sub_type
                try:
                    tracker.add_expense(person, float(amount), category_period, category, expense_type, sub_type_to_store, description, exp_date.isoformat())
                    st.success("Expense added.")
                    st.session_state.last_action = "expense_added"
                    st.experimental_rerun()
                except Exception as e:
                    st.error(str(e))

def render_dashboard():
    st.header("Dashboard")
    # summary cards
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total earnings", f"{tracker.total_earnings():.2f}")
    col2.metric("Total expenditure", f"{tracker.total_expenditure():.2f}")
    col3.metric("Remaining balance", f"{tracker.remaining_balance():.2f}")
    col4.button("➕ Add Expense", key="dash_add_expense_button")

    st.markdown("---")
    # recent activity
    df = tracker.get_expenses_df()
    if df.empty:
        st.info("No expenses recorded yet. Use 'Add Expense' to log your first expense.")
    else:
        st.subheader("Recent activity")
        recent_n = 5
        recent = df.sort_values("date", ascending=False).head(recent_n)
        st.table(
            recent[["id","date","person","amount","category","expense_type","sub_type","description"]]
            .sort_values("date", ascending=False)
            .reset_index(drop=True)
        )

        # quick link to open full table under expander
        with st.expander("Open full table & filters", expanded=False):
            render_full_table(df)

def render_full_table(df):
    # filters area
    st.subheader("Expenses & Filters")
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

    # pagination and download
    total_rows = len(filtered)
    st.write(f"Matching records: **{total_rows}**")
    page_size = st.selectbox("Rows per page", options=[10,25,50,100], index=1)
    pages = (total_rows + page_size - 1) // page_size if total_rows else 1
    page = st.number_input("Page", min_value=1, max_value=max(1,pages), value=1, step=1)
    start = (page - 1) * page_size
    end = start + page_size
    display_df = filtered.sort_values("date", ascending=False).iloc[start:end]
    st.dataframe(display_df.reset_index(drop=True), use_container_width=True)

    csv = filtered.to_csv(index=False)
    st.download_button(label="Download filtered as CSV", data=csv, file_name="expenses_filtered.csv", mime="text/csv")

    # delete UI
    ids = filtered["id"].tolist()
    if ids:
        del_id = st.selectbox("Delete expense id (from filtered results)", options=["None"] + ids)
        if del_id != "None" and st.button("Delete selected"):
            tracker.delete_expense(int(del_id))
            st.success(f"Deleted expense id {del_id}")
            st.experimental_rerun()

# ---------- Main navigation logic ----------
# Determine initial mode based on DB state
members_df = tracker.get_members_df()
has_members = not members_df.empty

# session navigation state
if "page" not in st.session_state:
    # default: if no members -> members page; else dashboard
    st.session_state.page = "members" if not has_members else "dashboard"

# If we just added members, offer a dialog asking to add expenses
if st.session_state.last_action == "member_added":
    # show a small banner with action buttons
    st.success("Member added successfully.")
    col_a, col_b = st.columns([1,1])
    if col_a.button("Add expenses now"):
        st.session_state.page = "add_expense"
        st.session_state.last_action = None
        st.experimental_rerun()
    if col_b.button("Not now"):
        st.session_state.page = "dashboard"
        st.session_state.last_action = None
        st.experimental_rerun()

# Top navigation (simple)
nav1, nav2, nav3 = st.columns([1,1,1])
if nav1.button("Dashboard"):
    st.session_state.page = "dashboard"
if nav2.button("Add Expense"):
    st.session_state.page = "add_expense"
if nav3.button("Members"):
    st.session_state.page = "members"

st.markdown("---")

# Page render
if st.session_state.page == "members":
    show_members_page()
elif st.session_state.page == "add_expense":
    add_expense_form()
else:
    # dashboard default
    render_dashboard()
