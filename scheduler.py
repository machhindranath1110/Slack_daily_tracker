from model import (
    clear_timesheets,
    send_email_to_hr,
    check_and_remind_users,
    send_scheduled_message
)

# Choose one of these functions depending on the cron job
clear_timesheets()
send_email_to_hr("machindranath70@email.com")
check_and_remind_users()
send_scheduled_message()
