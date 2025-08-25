import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.utils import formataddr

from flask import current_app

def send_ticket_email(to_email, subject, html_body, tickets=None):
    """
    Send an email with ticket info and QR codes as attachments.
    tickets: list of dicts with keys: 'event_title', 'ticket_type', 'qr_code_url', 'uuid'
    """
    smtp_server = os.environ.get('SMTP_SERVER')
    smtp_port = int(os.environ.get('SMTP_PORT', 587))
    smtp_user = os.environ.get('SMTP_USER')
    smtp_password = os.environ.get('SMTP_PASSWORD')
    sender_email = os.environ.get('SENDER_EMAIL', smtp_user)
    sender_name = os.environ.get('SENDER_NAME', 'Event Hub')

    msg = MIMEMultipart()
    msg['From'] = formataddr((sender_name, sender_email))
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    # Attach QR code images if provided
    if tickets:
        for idx, ticket in enumerate(tickets):
            import requests
            qr_url = ticket.get('qr_code_url')
            if qr_url:
                response = requests.get(qr_url)
                if response.status_code == 200:
                    img = MIMEImage(response.content)
                    img.add_header('Content-ID', f'<qr{idx}>')
                    img.add_header('Content-Disposition', 'inline', filename=f"ticket_{ticket.get('uuid','')}.png")
                    msg.attach(img)

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
