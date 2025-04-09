import os
from model import (
    clear_timesheets,
    send_email_to_hr,
    check_and_remind_users,
    send_scheduled_message
)

task = os.getenv("TASK")

if task == "clear":
    clear_timesheets()

elif task == "email":
    send_email_to_hr("machindranath70@gmail.com")

elif task == "reminder":
    check_and_remind_users()

elif task == "scheduled_message":
    send_scheduled_message()

else:
    print("⚠️ No valid task specified.")
