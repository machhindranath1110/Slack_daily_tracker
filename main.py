import os
import json
import time
from flask import Flask, request, jsonify
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.signature import SignatureVerifier
from apscheduler.schedulers.background import BackgroundScheduler
import schedule
import threading
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import sqlite3
from model import (
    initialize_db,
    open_modal,
    process_form_submission,
    process_approval_decision,
    open_approval_modal,
    save_timesheet,
    update_timesheet_status,
    check_and_remind_users,
    clear_timesheets,
    get_all_users,
    send_message_with_button
)
from model import send_email_to_hr

initialize_db() 

# conn = sqlite3.connect("timesheets.db")

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")
client = WebClient(token=SLACK_BOT_TOKEN)
verifier = SignatureVerifier(SIGNING_SECRET)

# Initialize Flask app
app = Flask(__name__)

# ✅ Get Today's Date
today_date = datetime.today().strftime('%Y-%m-%d')  # Format: YYYY-MM-DD
print(f"📅 Today's Date: {today_date}")

# ✅ Get Yesterday's Date
yesterday_date = (datetime.today() - timedelta(days=1)).strftime('%Y-%m-%d')
print(f"📅 Yesterday's Date: {yesterday_date}")


TEST_USER_NAME = "Machhindranath"  # Replace with the real name of the test user



# ✅ Schedule the reminder & report every day at 11:00 AM
# schedule.every().day.at("18:35").do(daily_task)


# ✅ Get Yesterday's Date
yesterday_date = (datetime.today() - timedelta(days=1)).strftime('%Y-%m-%d')

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~APP~~~~~~~~~~~~~~~~~~~~~~~~~~

@app.route("/slack/events", methods=["POST"])
def slack_events():
    payload = json.loads(request.form["payload"])

    if payload["type"] == "block_actions":  # Handles button click
        action = payload["actions"][0]["action_id"]
        trigger_id = payload["trigger_id"]

        # if action == "open_form":
        #     open_modal(trigger_id)
        #     return jsonify({"message": "Modal Opened!"})
        if action == "open_form":
            current_hour = datetime.now().hour
            trigger_id = payload["trigger_id"]
            user_id = payload["user"]["id"]

            if 12 <= current_hour < 19:
                # ❗ Between 1 PM and 7 PM → show modal with warning
                client.views_open(
                    trigger_id=trigger_id,
                    view={
                        "type": "modal",
                        "title": {"type": "plain_text", "text": "Timesheet Locked"},
                        "close": {"type": "plain_text", "text": "OK"},
                        "blocks": [
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": "🚫 You should fill the timesheet before *12 PM*.\n\nAll the best for tomorrow! 💪"
                                }
                            }
                        ]
                    }
                )
                return jsonify({"message": "Locked modal shown"})
            else:
                # ✅ Allowed: Show normal form modal
                open_modal(trigger_id)
                return jsonify({"message": "Form modal opened"})


        elif action in ["approve_timesheet", "reject_timesheet"]:
            user_id, approver_id = payload["actions"][0]["value"].split(",")
            action_type = "approve" if action == "approve_timesheet" else "reject"
            open_approval_modal(trigger_id, action_type, user_id, approver_id)
            return jsonify({"message": "Approval modal opened!"})

    elif payload["type"] == "view_submission":  # Handles form submission
        view_callback_id = payload["view"]["callback_id"]

        if view_callback_id in ["approve_timesheet_form", "reject_timesheet_form"]:
            return process_approval_decision(payload)  # 🔄 CALL NEW FUNCTION HERE

        else:
            process_form_submission(payload)  # ✅ Call the function but don't return immediately
            return jsonify({"response_action": "clear"})  # ✅ Ensure response is cleared properly

    return jsonify({"message": "OK"})



####################################################################################################

@app.route("/submit_timesheet", methods=["POST"])
def submit_timesheet():
    data = request.json
    user_id = data.get("user_id")
    project_name = data.get("project_name")

    if not user_id or not project_name:
        return jsonify({"error": "User ID and Project Name are required"}), 400

    update_submission_status(user_id, project_name)
    return jsonify({"message": "Timesheet submitted successfully!"})

@app.route("/approve_timesheet", methods=["POST"])
def approve_timesheet():
    data = request.json
    user_id = data.get("user_id")
    approval_status = data.get("approval_status")
    approver_id = data.get("approver_id")  # Get approver ID

    if not user_id or not approval_status or not approver_id:
        return jsonify({"error": "User ID, Approval Status, and Approver ID are required"}), 400

    uupdate_timesheet_status(user_id, approval_status, comments)
    return jsonify({"message": f"Timesheet status updated to {approval_status} by {approver_id}!"})

@app.route("/debug/view-data")
def view_data():
    conn = sqlite3.connect("timesheets.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM timesheets")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(rows)


# ✅ Function to send a scheduled message **Sequentially**
def send_scheduled_message():
    users = get_all_users()  # Fetch users
    for user_id in users:
        send_message_with_button(user_id)
        time.sleep(2)  # Ensure sequential execution

# ✅ Function to send timesheet reminders **Sequentially**
def send_reminders():
    check_and_remind_users()

# ✅ Function to send daily report email **Sequentially**
def daily_task_mail_HR():
    hr_email = "machindranath70@gmail.com"
    send_email_to_hr(hr_email)
    time.sleep(2)
    
# ✅ Background Scheduler for Precise Timing
scheduler = BackgroundScheduler()

# Schedule Jobs **Sequentially**
scheduler.add_job(clear_timesheets, "cron", hour=13, minute=15)  # Clear table at midnight
scheduler.add_job(send_scheduled_message, "cron", hour=19, minute=2)  # Send message at 7:00 PM
schedule.every().day.at("10:00").do(send_reminders)  # Send reminders at 6:47 PM
# schedule.every().day.at("13:30").do(daily_task_mail_HR)  # Send HR email at midnight
scheduler.add_job(daily_task_mail_HR, "cron", hour=12, minute=00)

# Start the Background Scheduler
scheduler.start()

# ✅ Function to Keep Checking Schedule
def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)  # Reduce delay for better execution

# ✅ Start Scheduler in a Background Thread
scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()

# ✅ Start Flask Server
if __name__ == "__main__":
    print("Scheduler started. Waiting for scheduled tasks...")
    app.run(port=3000, use_reloader=False)