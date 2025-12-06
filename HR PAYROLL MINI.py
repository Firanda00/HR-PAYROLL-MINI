import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date, time

DB = "hrpayroll.db"

# -----------------------------
# DATABASE
# -----------------------------
def get_conn():
    conn = sqlite3.connect(DB, check_same_thread=False)
    create_tables(conn)
    return conn

def create_tables(conn):
    c = conn.cursor()

    # Tabel karyawan
    c.execute("""
        CREATE TABLE IF NOT EXISTS employees(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            position TEXT,
            base_salary REAL,
            allowance REAL,
            tax_rate REAL
        )
    """)

    # Tabel absensi
    c.execute("""
        CREATE TABLE IF NOT EXISTS attendance(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER,
            date TEXT,
            check_in TEXT,
            check_out TEXT,
            hours REAL,
            note TEXT
        )
    """)

    conn.commit()

# -----------------------------
# CRUD KARYAWAN
# -----------------------------
def add_employee(conn, name, position, base_salary, allowance, tax_rate):
    c = conn.cursor()
    c.execute("INSERT INTO employees (name, position, base_salary, allowance, tax_rate) VALUES (?,?,?,?,?)",
              (name, position, base_salary, allowance, tax_rate))
    conn.commit()

def get_employees(conn):
    return pd.read_sql("SELECT * FROM employees", conn)

def update_employee(conn, emp_id, name, position, base_salary, allowance, tax_rate):
    c = conn.cursor()
    c.execute("""
        UPDATE employees SET name=?, position=?, base_salary=?, allowance=?, tax_rate=? WHERE id=?
    """, (name, position, base_salary, allowance, tax_rate, emp_id))
    conn.commit()

def delete_employee(conn, emp_id):
    c = conn.cursor()
    c.execute("DELETE FROM employees WHERE id=?", (emp_id,))
    conn.commit()

# -----------------------------
# ABSENSI
# -----------------------------
def add_attendance(conn, emp_id, date, check_in, check_out, hours, note):
    c = conn.cursor()
    c.execute("""
        INSERT INTO attendance (employee_id, date, check_in, check_out, hours, note)
        VALUES (?,?,?,?,?,?)
    """, (emp_id, date, check_in, check_out, hours, note))
    conn.commit()

def get_attendance(conn, start=None, end=None):
    base = """
        SELECT a.*, e.name FROM attendance a 
        LEFT JOIN employees e ON a.employee_id=e.id
    """
    if start and end:
        base += f" WHERE date BETWEEN '{start}' AND '{end}' "

    return pd.read_sql(base, conn)

# -----------------------------
# PAYROLL
# -----------------------------
def compute_payroll(conn, year, month):
    employees = get_employees(conn)
    start = date(year, month, 1)
    
    # hitung akhir bulan
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    
    att = get_attendance(conn, start.isoformat(), (end).isoformat())

    payroll = []

    for _, emp in employees.iterrows():
        emp_att = att[att["employee_id"] == emp["id"]]

        # lembur = jam lebih dari 8
        overtime_hours = emp_att["hours"].apply(lambda x: max(0, x - 8)).sum()

        # asumsi 22 hari kerja
        hadir = len(emp_att)
        absen = max(0, 22 - hadir)

        overtime_pay = overtime_hours * 50000
        gross = emp["base_salary"] + emp["allowance"] + overtime_pay
        tax = gross * emp["tax_rate"]
        absence_cut = absen * 100000
        net = gross - tax - absence_cut

        payroll.append({
            "name": emp["name"],
            "position": emp["position"],
            "base_salary": emp["base_salary"],
            "allowance": emp["allowance"],
            "overtime_hours": overtime_hours,
            "gross": gross,
            "tax": tax,
            "absence": absen,
            "absence_cut": absence_cut,
            "net_pay": net
        })

    return pd.DataFrame(payroll)

# -----------------------------
# UI STREAMLIT
# -----------------------------
def main():
    st.title("💼 HR Payroll Mini — Gaji + Absensi")
    conn = get_conn()

    menu = st.sidebar.selectbox("Menu", ["Dashboard", "Karyawan", "Absensi", "Payroll"])

    # ========== Dashboard ==========
    if menu == "Dashboard":
        st.subheader("📊 Dashboard")
        st.metric("Jumlah Karyawan", len(get_employees(conn)))
        st.metric("Total Absensi", len(get_attendance(conn)))

        st.write("### Data Karyawan")
        st.dataframe(get_employees(conn))

    # ========== Karyawan ==========
    if menu == "Karyawan":
        st.subheader("👨‍💼 Manajemen Karyawan")

        with st.form("add_emp"):
            name = st.text_input("Nama")
            position = st.text_input("Jabatan")
            base_sal = st.number_input("Gaji Pokok", min_value=0)
            allowance = st.number_input("Tunjangan", min_value=0)
            tax = st.number_input("Tarif Pajak (misal 0.05)", min_value=0.0, max_value=1.0, value=0.05)

            submit = st.form_submit_button("Tambah")

            if submit:
                add_employee(conn, name, position, base_sal, allowance, tax)
                st.success("Karyawan berhasil ditambahkan")

        st.write("### Data Karyawan")
        emp = get_employees(conn)
        st.dataframe(emp)

    # ========== Absensi ==========
    if menu == "Absensi":
        st.subheader("🕒 Absensi")

        emp = get_employees(conn)
        emp_list = emp["id"].ast_
