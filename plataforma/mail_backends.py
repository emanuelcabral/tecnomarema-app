# plataforma/mail_backends.py
import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

class MailgunBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        for message in email_messages:
            url = f"https://api.mailgun.net/v3/{settings.MAILGUN_DOMAIN}/messages"
            data = {
                "from": message.from_email,
                "to": ", ".join(message.to),
                "subject": message.subject,
                "text": message.body,
            }
            if hasattr(message, 'alternatives'):
                for content, mime in message.alternatives:
                    if mime == "text/html":
                        data["html"] = content
                        break
            try:
                response = requests.post(
                    url,
                    auth=("api", settings.MAILGUN_API_KEY),
                    data=data
                )
                response.raise_for_status()
                print("Email enviado con Mailgun OK")
            except Exception as e:
                print("Error Mailgun:", str(e))