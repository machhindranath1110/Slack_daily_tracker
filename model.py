# model.py

import csv
import json
from datetime import datetime, timedelta
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import openai
import sqlite3
from flask import Flask, request, jsonify
# Set API keys
import os
from flask import jsonify
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


today_date = datetime.today().strftime('%Y-%m-%d')

client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))
openai.api_key = os.getenv("OPENAI_API_KEY")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")


# Useful dates
today_date = datetime.today().strftime('%Y-%m-%d')
yesterday_date = (datetime.today() - timedelta(days=1)).strftime('%Y-%m-%d')
CSV_FILE = "timesheet_submissions.csv"




# SQLite setup
DB_NAME = "timesheets.db"

APPROVER_USERS = {
    "U06RALZ1C11": "Machhindranath",
    "U06XYZ78901": "Priya Sharma",
    "U06ABC34567": "Rahul Kumar"
}





def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_db():
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS timesheets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            user_id TEXT,
            user_name TEXT,
            project_name TEXT,
            task TEXT,
            hours TEXT,
            approver_id TEXT,
            approver_name TEXT,
            status TEXT,
            comments TEXT
        );
    """)
    conn.commit()
    conn.close()
    print("✅ SQLite DB initialized.")

# Save submission to DB
def save_timesheet(data):
    conn = get_db_connection()
    conn.execute("""
        INSERT INTO timesheets (date, user_id, user_name, project_name, task, hours,
                                approver_id, approver_name, status, comments)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        today_date, data["user_id"], data["user_name"],
        data["project_name"], data["task"], data["hours"],
        data["approver_id"], data["approver_name"], "Pending", ""
    ))
    conn.commit()
    conn.close()

# Update status (Approve/Reject
def update_timesheet_status(user_id, status, comment=""):
    print(f"🔍 Trying to update user_id: {user_id} to status: {status} with comment: {comment}")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE timesheets
        SET status = ?, comments = ?
        WHERE id = (
            SELECT id FROM timesheets
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 1
        )
    """, (status, comment, user_id))
    conn.commit()
    updated = cursor.rowcount
    conn.close()
    print(f"✅ UPDATE COMPLETE | Rows affected: {updated}")



# Fetch filled users for a date
def get_filled_user_ids():
    conn = get_db_connection()
    rows = conn.execute("SELECT DISTINCT user_id FROM timesheets")
    return {row["user_id"] for row in rows.fetchall()}

# Clear all timesheet data
def clear_timesheets():
    conn = get_db_connection()
    conn.execute("DELETE FROM timesheets")
    conn.commit()
    conn.close()
    print("🧹 Timesheet table cleared for new day.")

# Slack helper
def get_all_users():
    try:
        response = client.users_list()
        if response["ok"]:
            return {
                user["id"]: user.get("real_name", user["name"])
                for user in response["members"]
                if not user["is_bot"] and not user["deleted"]
            }
    except SlackApiError as e:
        print("🚨 Slack error:", e.response["error"])
    return {}

# Reminder logic
def send_timesheet_reminder(user_id):
    try:
        client.chat_postMessage(
            channel=user_id,
            text=f"👋 Reminder: You haven't filled your timesheet for *{yesterday_date}*. Please update it! ⏳"
        )
        print(f"📩 Reminder sent to {user_id}")
    except SlackApiError as e:
        print(f"🚨 Error sending to {user_id}: {e.response['error']}")

def check_and_remind_users():

    all_user_ids = get_all_users()  # ✅ should return a list
    filled_user_ids = get_filled_user_ids()  # ✅ also list
    print("all_user_ids",all_user_ids)

    pending_users = set(all_user_ids) - set(filled_user_ids)

    print("🧑‍💻 Users who have NOT filled timesheet:", pending_users)

    for user_id in pending_users:
        send_timesheet_reminder(user_id)

def generate_motivational_quote():
    """Generates a motivational quote using OpenAI API."""
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a motivational speaker."},
            {"role": "user", "content": "Give me a short motivational quote to inspire employees at work."}
        ],
        max_tokens=50
    )
    quote = response["choices"][0]["message"]["content"]
    print(f"Today's Motivational Quote at 7 PM: \n\"{quote}\"")
    return quote
    

def get_slack_user_name(user_id):
    """Fetches the real name of a Slack user using their user ID."""
    if not SLACK_BOT_TOKEN:
        print("🚨 Error: Slack Bot Token is missing!")
        return "Unknown User"
    
    try:
        response = client.users_info(user=user_id)
        # print(json.dumps(response.data, indent=4))  # 🔍 Print API response

        if response.get("ok"):
            user_info = response.get("user", {})
            return user_info.get("profile", {}).get("real_name", "Unknown User")
        else:
            # print(f"🚨 Slack API Error: {response.get('error')}")
            return "Unknown User"

    except SlackApiError as e:
        # print(f"🚨 Slack API Error: {e.response['error']}")
        return "Unknown User"
    
def get_all_users():
    try:
        response = client.users_list()
        if response["ok"]:
            return [user["id"] for user in response["members"] if not user["is_bot"] and not user["deleted"]]
        else:
            print("Error fetching users:", response["error"])
            return []
    except SlackApiError as e:
        print(f"Error fetching users: {e.response['error']}")
        return []

def send_message_with_button(user_id):
    try:
        # Open a direct message (IM) channel
        im_response = client.conversations_open(users=[user_id])
        if im_response["ok"]:
            dm_channel = im_response["channel"]["id"]

            # Send a message with a button
            client.chat_postMessage(
                channel=dm_channel,
                text="Hello! Please click the button below to fill out a quick form. 🚀",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"""🌟 Good Evening Team!

                                Hope you had a great day! 💪 Please take a moment to fill out your timesheet for today before EOD.
                                """
                                #  **{quote_of_the_day}**
                        }
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Update Timesheet"
                                },
                                "action_id": "open_form",  # This action triggers the modal
                                "style": "primary",
                                "value": f"{user_id}"
                            }
                        ]
                    }
                ]
            )
            print(f"Message with button sent to {user_id}")
        else:
            print(f"Failed to open DM with {user_id}: {im_response['error']}")
    except SlackApiError as e:
        print(f"Error sending message to {user_id}: {e.response['error']}")


def send_timesheet_reminder(user_id):
    """Sends a Slack reminder to users who haven't submitted their timesheets."""
    try:
        client.chat_postMessage(
            channel=user_id,
            text="🚨 *Reminder: Timesheet Not Submitted!* 🚨\n\n"
                 "Hello! We noticed that you haven't filled out your timesheet for yesterday. "
                 "Please update it as soon as possible. ⏳",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"👋 Hey there! We noticed that you haven't filled out your timesheet for *{yesterday_date}*.\n"
                                "Please take a moment to update it now. 🙌"
                    }
                }
            ]
        )
        print(f"📩 Reminder sent to {user_id}")
    except SlackApiError as e:
        print(f"🚨 Error sending reminder to {user_id}: {e.response['error']}")



def open_modal(trigger_id):
    try:
        client.views_open(
            trigger_id=trigger_id,
            view={
                "type": "modal",
                "callback_id": "timesheet_form",
                "title": {"type": "plain_text", "text": "Submit Timesheet"},
                "submit": {"type": "plain_text", "text": "Submit"},
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "project",
                        "element": {
                            "type": "static_select",
                            "action_id": "project_selected",
                            "options": [
                                {"text": {"type": "plain_text", "text": "Carbon Assistant"}, "value": "Carbon Assistant"},
                                {"text": {"type": "plain_text", "text": "Al-Salam"}, "value": "Al-Salam"},
                                {"text": {"type": "plain_text", "text": "IDH"}, "value": "IDH"},
                                {"text": {"type": "plain_text", "text": "Aware"}, "value": "Aware"},
                                {"text": {"type": "plain_text", "text": "SADMS"}, "value": "SADMS"},
                                {"text": {"type": "plain_text", "text": "ZADMS"}, "value": "ZADMS"},
                                {"text": {"type": "plain_text", "text": "MDMS"}, "value": "MDMS"}
                            ]
                        },
                        "label": {"type": "plain_text", "text": "Select a Project"}
                    },
                    {
                        "type": "input",
                        "block_id": "task",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "task_description",
                            "multiline": True
                        },
                        "label": {"type": "plain_text", "text": "Describe Your Task"}
                    },
                    {
                        "type": "input",
                        "block_id": "hours",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "working_hours"
                        },
                        "label": {"type": "plain_text", "text": "Enter Working Hours"}
                    },
                    {
                        "type": "input",
                        "block_id": "approver",
                        "element": {
                            "type": "users_select",
                            "action_id": "approver_selected"
                        },
                        "label": {"type": "plain_text", "text": "Select an Approver"}
                    }
                ]
            }
        )
    except SlackApiError as e:
        print(f"Error opening modal: {e.response['error']}")

# def open_modal(trigger_id):
#     try:
#         # Prepare approver dropdown options
#         approver_options = []
#         for user_id, name in APPROVER_USERS.items():
#             approver_options.append({
#                 "text": {"type": "plain_text", "text": name},
#                 "value": user_id
#             })

#         # Open the modal with dropdown of limited approvers
#         client.views_open(
#             trigger_id=trigger_id,
#             view={
#                 "type": "modal",
#                 "callback_id": "timesheet_form",
#                 "title": {"type": "plain_text", "text": "Submit Timesheet"},
#                 "submit": {"type": "plain_text", "text": "Submit"},
#                 "blocks": [
#                     {
#                         "type": "input",
#                         "block_id": "project",
#                         "element": {
#                             "type": "static_select",
#                             "action_id": "project_selected",
#                             "options": [
#                                 {"text": {"type": "plain_text", "text": "Carbon Assistant"}, "value": "Carbon Assistant"},
#                                 {"text": {"type": "plain_text", "text": "Al-Salam"}, "value": "Al-Salam"},
#                                 {"text": {"type": "plain_text", "text": "IDH"}, "value": "IDH"},
#                                 {"text": {"type": "plain_text", "text": "Aware"}, "value": "Aware"},
#                                 {"text": {"type": "plain_text", "text": "SADMS"}, "value": "SADMS"},
#                                 {"text": {"type": "plain_text", "text": "ZADMS"}, "value": "ZADMS"},
#                                 {"text": {"type": "plain_text", "text": "MDMS"}, "value": "MDMS"}
#                             ]
#                         },
#                         "label": {"type": "plain_text", "text": "Select a Project"}
#                     },
#                     {
#                         "type": "input",
#                         "block_id": "task",
#                         "element": {
#                             "type": "plain_text_input",
#                             "action_id": "task_description",
#                             "multiline": True
#                         },
#                         "label": {"type": "plain_text", "text": "Describe Your Task"}
#                     },
#                     {
#                         "type": "input",
#                         "block_id": "hours",
#                         "element": {
#                             "type": "plain_text_input",
#                             "action_id": "working_hours"
#                         },
#                         "label": {"type": "plain_text", "text": "Enter Working Hours"}
#                     },
#                     {
#                         "type": "input",
#                         "block_id": "approver",
#                         "element": {
#                             "type": "static_select",
#                             "action_id": "approver_selected",
#                             "options": approver_options
#                         },
#                         "label": {"type": "plain_text", "text": "Select an Approver"}
#                     }
#                 ]
#             }
#         )
#     except SlackApiError as e:
#         print(f"🚨 Error opening modal: {e.response['error']}")


def process_form_submission(payload):
    """
    Processes the submitted timesheet form, saves it to SQLite,
    and sends an approval request to the selected mentor.
    """
    user_id = payload["user"]["id"]
    values = payload["view"]["state"]["values"]

    try:
        # Extract form values
        project_selected = values.get("project", {}).get("project_selected", {}).get("selected_option", {}).get("value", "Not Selected")
        task_description = values.get("task", {}).get("task_description", {}).get("value", "No description provided")
        working_hours = values.get("hours", {}).get("working_hours", {}).get("value", "0")
        approver_id = values.get("approver", {}).get("approver_selected", {}).get("selected_user", None)

        user_name = get_slack_user_name(user_id)
        approver_name = get_slack_user_name(approver_id)

        if not approver_id:
            return jsonify({"error": "Approver must be selected"}), 400

        # ✅ Save data to SQLite
        save_timesheet({
            "date": today_date,
            "user_id": user_id,
            "user_name": user_name,
            "project_name": project_selected,
            "task": task_description,
            "hours": working_hours,
            "approver_id": approver_id,
            "approver_name": approver_name
        })

        print(f"✅ Timesheet saved for {user_name} ({user_id})")

        # ✅ Slack Notifications (Approver)
        from model import client
        client.chat_postMessage(
            channel=approver_id,
            text="📝 *Timesheet Approval Request* 📝",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"📝 *Timesheet Approval Request* 📝\n"
                                f"👤 *User:* <@{user_id}>\n"
                                f"📌 *Project:* {project_selected}\n"
                                f"📝 *Task:* {task_description}\n"
                                f"⏳ *Hours:* {working_hours}\n"
                                f"✅ Please approve or reject:"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Approve"},
                            "style": "primary",
                            "action_id": "approve_timesheet",
                            "value": f"{user_id},{approver_id}"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Reject"},
                            "style": "danger",
                            "action_id": "reject_timesheet",
                            "value": f"{user_id},{approver_id}"
                        }
                    ]
                }
            ]
        )

        # ✅ Slack Notifications (Requester)
        client.chat_postMessage(
            channel=user_id,
            text=f"✅ *Your timesheet has been submitted!*\n"
                 f"Project: *{project_selected}*\n"
                 f"Hours: *{working_hours}*\n"
                 f"Waiting for approval from: <@{approver_id}>"
        )

    except Exception as e:
        print(f"🚨 Error processing form: {str(e)}")
        return jsonify({"error": "Internal error processing timesheet"}), 500


def open_approval_modal(trigger_id, action, requester_id, approver_id):
    """
    Opens a modal for the mentor (approver) to approve or reject the timesheet
    and provide comments.
    """
    
    print(trigger_id, action, requester_id, approver_id, "payload of open proval")
    try:
        title_text = "Approve Timesheet" if action == "approve" else "Reject Timesheet"
        callback_id = "approve_timesheet_form" if action == "approve" else "reject_timesheet_form"

        client.views_open(
            trigger_id=trigger_id,
            view={
                "type": "modal",
                "callback_id": callback_id,
                "private_metadata": json.dumps({"requester_id": requester_id, "approver_id": approver_id}),
                "title": {"type": "plain_text", "text": title_text},
                "submit": {"type": "plain_text", "text": "Submit"},
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "approval_comment",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "comment_input",
                            "multiline": True
                        },
                        "label": {"type": "plain_text", "text": "Provide a comment"}
                    }
                ]
            }
        )
    except SlackApiError as e:
        print(f"Error opening approval modal: {e.response['error']}")


def process_approval_decision(payload):
    """
    Processes the approval/rejection decision, updates the CSV, 
    and sends notifications to both requester (sender) and approver (receiver).
    """
    try:
        # Extract metadata
        metadata = json.loads(payload["view"]["private_metadata"])
        requester_id = metadata.get("requester_id")
        approver_id = metadata.get("approver_id")

        values = payload["view"]["state"]["values"]
        comments = values.get("approval_comment", {}).get("comment_input", {}).get("value", "").strip()
        print("this is the approval status  1: ", values)
        print("this isthe comment that approver give  1: ",comments)
        
        # Determine status (Approved or Rejected)
        status = "Approved" if payload["view"]["callback_id"] == "approve_timesheet_form" else "Rejected"
        print("this isthe comment that approver give  111: ",status)
        # Update CSV file
        # update_timesheet_status(requester_id, status, approver_id)
        update_timesheet_status(requester_id, status, comments)


        # Create status messages
        status_message_requester = f"✅ *Your timesheet has been {status.lower()}!* 🎉\n💬 *Mentor's comment:* {comments}"
        status_message_approver = f"📢 *Timesheet decision recorded!* ✅\n🔹 *Requester:* <@{requester_id}>\n🔹 *Status:* {status}\n🔹 *Comment:* {comments}"

        # Notify the requester (sender)
        try:
            client.chat_postMessage(channel=requester_id, text=status_message_requester)
            print(f"✅ Notified requester {requester_id} about {status}")
        except SlackApiError as e:
            print(f"🚨 Error sending message to requester: {e.response['error']}")

        # Notify the approver (receiver)
        try:
            client.chat_postMessage(channel=approver_id, text=status_message_approver)
            print(f"✅ Notified approver {approver_id} about the decision")
        except SlackApiError as e:
            print(f"🚨 Error sending message to approver: {e.response['error']}")

        return jsonify({"response_action": "clear"})

    except KeyError as e:
        print(f"🚨 KeyError - Missing field: {e}")
        return jsonify({"error": f"Missing field: {e}"}), 400

def update_timesheet_status(user_id, status, comment=""):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE timesheets
        SET status = ?, comments = ?
        WHERE id = (
            SELECT id FROM timesheets
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 1
        )
    """, (status, comment, user_id))

    conn.commit()
    updated_rows = cursor.rowcount
    conn.close()

    print(f"✅ Timesheet status updated for {user_id} | Rows affected: {updated_rows}")


# def get_users_from_csv(csv_file):
#     """Extract employee names from the CSV whose date matches yesterday."""
#     csv_users = set()
#     try:
#         with open(csv_file, mode="r", newline="", encoding="utf-8") as file:
#             reader = csv.reader(file)
#             header = next(reader)  # Skip header

#             for row in reader:
#                 if row and len(row) > 1:  # Ensure row is not empty
#                     csv_date = row[0].strip()  # First column should be Date
#                     if csv_date == yesterday_date:
#                         csv_users.add(row[1])  # User Name column

#         return csv_users
#     except FileNotFoundError:
#         print(f"🚨 Error: File '{csv_file}' not found!")
#         return set()
#     except Exception as e:
#         print(f"🚨 Error reading CSV: {str(e)}")
#         return set()

# def compare_users_in_csv_and_slack(csv_file):
#     """Compare Slack users with CSV records and return names instead of IDs."""
#     user_dict = get_all_users_for_check()  # {user_id: user_name}
#     slack_users_set = set(user_dict.keys())  # Convert Slack user IDs to a set
#     csv_users = get_users_from_csv(csv_file)  # CSV users (IDs)

#     # Users present in both CSV and Slack
#     present_in_both = csv_users.intersection(slack_users_set)

#     # Users present in Slack but missing in CSV
#     missing_in_csv = slack_users_set.difference(csv_users)

#     # Convert user IDs to names
#     present_in_both_names = [user_dict.get(user_id, user_id) for user_id in present_in_both]
#     missing_in_csv_names = [user_dict.get(user_id, user_id) for user_id in missing_in_csv]

#     print("\n✅ Employees Who Filled the Timesheet:")
#     for user in present_in_both_names:
#         print(f"🔹 {user}")

#     print("\n🚨 Employees Who Didn't Fill the Timesheet:")
#     for user in missing_in_csv_names:
#         print(f"⚠️ {user}")

#     return present_in_both_names, missing_in_csv_names


def get_csv_table(csv_file):
    """Reads the CSV and formats only yesterday's data as an HTML table."""
    try:
        with open(csv_file, mode="r", newline="", encoding="utf-8") as file:
            reader = csv.reader(file)
            header = next(reader)  # Get column names
            rows = [row for row in reader if row and row[0] == yesterday_date]  # Filter for yesterday's date

        # ✅ If No Data Found for Yesterday
        if not rows:
            return f"<p>🚨 No timesheet records found for {yesterday_date}!</p>"

        # ✅ Define Table Structure
        table_html = f"""<h3>📊 Timesheet Report for {yesterday_date}</h3>
                        <table border="1" cellspacing="0" cellpadding="5" style="border-collapse: collapse;">
                        <tr><th>Date</th><th>Employee Name</th><th>Project Name</th><th>Mentor</th><th>Status</th></tr>"""

        # ✅ Populate Table with Data
        for row in rows:
            if len(row) >= 5:  # Ensure we have enough columns
                Date, employee_name, project_name, mentor, Status = row[0], row[2], row[3], row[5], row[6]
                table_html += f"<tr><td>{Date}</td><td>{employee_name}</td><td>{project_name}</td><td>{mentor}</td><td>{Status}</td></tr>"

        table_html += "</table>"
        return table_html
    except FileNotFoundError:
        print(f"🚨 Error: File '{csv_file}' not found!")
        return "<p>🚨 CSV file not found!</p>"
    except Exception as e:
        print(f"🚨 Error reading CSV: {str(e)}")
        return "<p>🚨 Error reading CSV data!</p>"
    

def get_missing_users_table(missing_users):
    """Creates an HTML table for employees missing from CSV using their names."""
    if not missing_users:
        return "<p>✅ All employees have filled the timesheet!</p>"

    table_html = """<table border="1" cellspacing="0" cellpadding="5" style="border-collapse: collapse;">
                    <tr><th>Employee Name</th></tr>"""

    for user in missing_users:
        table_html += f"<tr><td>⚠️ {user}</td></tr>"  # Usernames now

    table_html += "</table>"
    return table_html

def send_email_to_hr(hr_email):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM timesheets")
    rows = cursor.fetchall()
    
        # ✅ Get filled user_ids
    cursor.execute("SELECT DISTINCT user_id FROM timesheets")
    filled_user_ids = set(row["user_id"] for row in cursor.fetchall())
    conn.close()
    
        # ✅ Get all users from Slack
    all_user_ids = get_all_users()  # Make sure this returns a list of user_ids
    missing_user_ids = set(all_user_ids) - filled_user_ids

    # ✅ Get user names from Slack
    missing_users_names = [get_slack_user_name(uid) for uid in missing_user_ids]

    # Return early if no data
    if not rows:
        print("No timesheet data to send.")
        return

    # Build HTML table from rows
    table_html = """
    <h3>📊 Timesheet Report</h3>
    <table border="1" cellspacing="0" cellpadding="5" style="border-collapse: collapse;">
        <tr><th>Date</th><th>Employee Name</th><th>Project</th><th>Task</th>
        <th>Hours</th><th>Approver</th><th>Status</th><th>Comment</th></tr>
    """
    for row in rows:
        table_html += f"<tr><td>{row['date']}</td><td>{row['user_name']}</td><td>{row['project_name']}</td><td>{row['task']}</td><td>{row['hours']}</td><td>{row['approver_name']}</td><td>{row['status']}</td><td>{row['comments']}</td></tr>"
    table_html += "</table>"
    
        # ✅ Table 2: Missing users
    table_html += """
    <br><h3>🚨 Users Who Did NOT Fill Timesheet</h3>
    <table border="1" cellspacing="0" cellpadding="5" style="border-collapse: collapse;">
        <tr><th>Employee Name</th></tr>
    """
    for name in missing_users_names:
        table_html += f"<tr><td>⚠️ {name}</td></tr>"
    table_html += "</table>"


    # Email content
    sender_email = os.getenv("SENDER_EMAIL")       # your email
    sender_password = os.getenv("EMAIL_PASSWORD")  # app password
    smtp_server = "smtp.gmail.com"
    smtp_port = 587

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = hr_email
    msg["Subject"] = "📊 Daily Timesheet Report"
    msg.attach(MIMEText(table_html, "html"))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, hr_email, msg.as_string())
        server.quit()
        print(f"✅ Email sent to HR: {hr_email}")
    except Exception as e:
        print(f"🚨 Error sending email: {e}")


# def daily_task_mail_HR():
#     ...
    
def get_all_users_for_remainder():
    """Fetch Slack users and return a dictionary {user_id: user_name}."""
    user_dict = {}
    try:
        response = client.users_list()
        if response["ok"]:
            for user in response["members"]:
                if not user["is_bot"] and not user["deleted"]:
                    user_id = user["id"]
                    user_name = user["real_name"] if "real_name" in user else user["name"]
                    user_dict[user_id] = user_name
        else:
            print("Error fetching users:", response["error"])
    except SlackApiError as e:
        print(f"Error fetching users: {e.response['error']}")
    
    return user_dict


# def compare_users_in_csv_and_slack_for_remainder(csv_file):
#     """Compare Slack users with CSV records and notify users who haven't filled the timesheet."""
#     user_dict = get_all_users_for_check()  # {user_id: user_name}
#     slack_users_set = set(user_dict.keys())  # Convert Slack user IDs to a set
#     csv_users = get_users_from_csv(csv_file)  # CSV users (IDs)
#     print(slack_users_set)
#     print(csv_users)

#     # Users present in both CSV and Slack
#     present_in_both = csv_users.intersection(slack_users_set)
    
#     print(",,,,,,,,,,,,",present_in_both)

#     # Users present in Slack but missing in CSV
#     missing_in_csv = slack_users_set.difference(csv_users)
#     print(",,,,,,,,,,,,",missing_in_csv)

#     # Convert user IDs to names
#     present_in_both_names = [user_dict.get(user_id, user_id) for user_id in present_in_both]
#     missing_in_csv_names = [user_dict.get(user_id, user_id) for user_id in missing_in_csv]

#     # 🚀 **Send Reminder Messages to Missing Users**
#     for user_id in missing_in_csv:
#         send_timesheet_reminder(user_id)

#     return present_in_both_names, missing_in_csv_names


def get_missing_users_table(missing_users):
    """Creates an HTML table for employees missing from CSV using their names."""
    if not missing_users:
        return "<p>✅ All employees have filled the timesheet!</p>"

    table_html = """<table border="1" cellspacing="0" cellpadding="5" style="border-collapse: collapse;">
                    <tr><th>Employee Name</th></tr>"""

    for user in missing_users:
        table_html += f"<tr><td>⚠️ {user}</td></tr>"  # Usernames now

    table_html += "</table>"
    return table_html
