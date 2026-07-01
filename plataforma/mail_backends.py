# # plataforma/mail_backends.py
# import requests
# from django.conf import settings
# from django.core.mail.backends.base import BaseEmailBackend

# class MailgunBackend(BaseEmailBackend):
#     def send_messages(self, email_messages):
#         for message in email_messages:
#             url = f"https://api.mailgun.net/v3/{settings.MAILGUN_DOMAIN}/messages"
#             data = {
#                 "from": message.from_email,
#                 "to": ", ".join(message.to),
#                 "subject": message.subject,
#                 "text": message.body,
#             }
#             if hasattr(message, 'alternatives'):
#                 for content, mime in message.alternatives:
#                     if mime == "text/html":
#                         data["html"] = content
#                         break
#             try:
#                 response = requests.post(
#                     url,
#                     auth=("api", settings.MAILGUN_API_KEY),
#                     data=data
#                 )
#                 response.raise_for_status()
#                 print("Email enviado con Mailgun OK")
#             except Exception as e:
#                 print("Error Mailgun:", str(e))


# plataforma/mail_backends.py
import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

class BrevoBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        num_sent = 0
        for message in email_messages:
            url = "https://api.brevo.com/v3/smtp/email"
            
            data = {
                "sender": {"email": settings.DEFAULT_FROM_EMAIL},
                "to": [{"email": e} for e in message.to],
                "subject": message.subject,
            }
            
            if message.body:  # solo si existe
                data["textContent"] = message.body
            
            if hasattr(message, 'alternatives'):
                for content, mime in message.alternatives:
                    if mime == "text/html":
                        data["htmlContent"] = content
                        break
            
            headers = {
                "accept": "application/json",
                "api-key": settings.BREVO_API_KEY,
                "content-type": "application/json"
            }
            
            response = requests.post(url, json=data, headers=headers)
            print("Payload enviado:", data)
            print("Respuesta:", response.status_code, response.text)
            response.raise_for_status()
            num_sent += 1
        return num_sent
