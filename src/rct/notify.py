import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from rct.settings import settings
from rct.logger import setup_logger

logger = setup_logger()

def send_alert_email(subject, body):
    """
    Sends an alert email using Gmail via SMTP.
    Requires ALERT_EMAIL_SENDER, ALERT_EMAIL_PASSWORD, and ALERT_EMAIL_RECEIVER to be set.
    """
    sender = settings.ALERT_EMAIL_SENDER
    password = settings.ALERT_EMAIL_PASSWORD
    receiver = settings.ALERT_EMAIL_RECEIVER

    if not sender or not password or not receiver:
        logger.warning("Email alert settings are missing. Skipping email notification.")
        return

    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = receiver
    msg['Subject'] = f"[RCT Alert] {subject}"

    msg.attach(MIMEText(body, 'plain'))

    try:
        # Connect to Gmail SMTP server
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender, password)
        text = msg.as_string()
        server.sendmail(sender, receiver, text)
        server.quit()
        logger.info(f"Alert email sent to {receiver}")
    except Exception as e:
        logger.error(f"Failed to send alert email: {e}")
