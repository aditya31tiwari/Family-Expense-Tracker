# main.py
from pathlib import Path
import sqlite3
import pandas as pd
from typing import Optional
from datetime import datetime

ROOT = Path(__file__).parent
DB_PATH = ROOT / "expenses.db"

def _get_conn():
    conn = sqlite3.connect(DB_PATH.as_posix(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = _get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            earning_status INTEGER DEFAULT 0,
            earnings REAL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person TEXT NOT NULL,
            description TEXT,
            amount REAL NOT NULL,
            category_period TEXT,   -- daily, one-time, monthly, quarterly, 2-quarter, 3-quarter, yearly
            category TEXT,          -- Housing, Food...
            expense_type TEXT,      -- big / small
            sub_type TEXT,
            date TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        """
    )
    conn.commit()
    conn.close()

# initialize DB on import (idempotent)
init_db()

class FamilyExpenseTracker:
    def __init__(self):
        # class uses DB as source of truth; no heavy memory objects
        pass

    # ---------- members ----------
    def add_member(self, name: str, earning_status: bool=False, earnings: float=0.0):
        name = (name or "").strip().title()
        if not name:
            raise ValueError("Name cannot be empty.")
        conn = _get_conn()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO members (name, earning_status, earnings) VALUES (?, ?, ?)",
                (name, int(bool(earning_status)), float(earnings)),
            )
            conn.commit()
        finally:
            conn.close()

    def update_member(self, name: str, earning_status: bool, earnings: float):
        conn = _get_conn()
        try:
            conn.execute(
                "UPDATE members SET earning_status=?, earnings=? WHERE name=?",
                (int(bool(earning_status)), float(earnings), name.title()),
            )
            conn.commit()
        finally:
            conn.close()

    def delete_member(self, member_name: str):
        conn = _get_conn()
        try:
            conn.execute("DELETE FROM members WHERE name = ?", (member_name,))
            conn.commit()
        finally:
            conn.close()

    def get_members_df(self) -> pd.DataFrame:
        conn = _get_conn()
        df = pd.read_sql_query("SELECT * FROM members ORDER BY name", conn)
        conn.close()
        return df

    # ---------- expenses ----------
    def add_expense(self,
                    person: str,
                    amount: float,
                    category_period: str,
                    category: str,
                    expense_type: str,
                    sub_type: Optional[str],
                    description: Optional[str],
                    date_iso: str):
        # basic validation
        person = (person or "").strip().title()
        if not person:
            raise ValueError("Expense must be associated with a person.")
        if amount is None or float(amount) <= 0:
            raise ValueError("Amount must be positive.")
        conn = _get_conn()
        try:
            conn.execute(
                """INSERT INTO expenses
                (person, description, amount, category_period, category, expense_type, sub_type, date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (person, description or "", float(amount), category_period, category, expense_type, sub_type or "", date_iso),
            )
            conn.commit()
        finally:
            conn.close()

    def delete_expense(self, expense_id: int):
        conn = _get_conn()
        try:
            conn.execute("DELETE FROM expenses WHERE id = ?", (int(expense_id),))
            conn.commit()
        finally:
            conn.close()

    def get_expenses_df(self) -> pd.DataFrame:
        conn = _get_conn()
        df = pd.read_sql_query("SELECT * FROM expenses ORDER BY date DESC, created_at DESC", conn, parse_dates=["date","created_at"])
        conn.close()
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
        return df

    # ---------- aggregates ----------
    def total_earnings(self) -> float:
        df = self.get_members_df()
        if df.empty:
            return 0.0
        return float(df["earnings"].sum())

    def total_expenditure(self) -> float:
        df = self.get_expenses_df()
        if df.empty:
            return 0.0
        return float(df["amount"].sum())

    def remaining_balance(self) -> float:
        return self.total_earnings() - self.total_expenditure()

    # helpers to expose options
    def available_persons(self):
        df = self.get_members_df()
        return df["name"].tolist() if not df.empty else []

    def sanitize_date(self, dt):
        # accepts date or datetime object or iso string
        if hasattr(dt, "isoformat"):
            return dt.isoformat()
        return str(dt)
