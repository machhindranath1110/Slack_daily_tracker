from model import get_db_connection

def print_all_timesheets():
    conn = get_db_connection()
    cursor = conn.execute("SELECT * FROM timesheets")
    rows = cursor.fetchall()

    if not rows:
        print("🚫 No data found in the timesheets table.")
    else:
        print("📄 Timesheet entries:")
        for row in rows:
            print(dict(row))

    conn.close()

# Call this if running standalone
if __name__ == "__main__":
    print_all_timesheets()
