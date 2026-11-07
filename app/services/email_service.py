import os
import smtplib
from email.message import EmailMessage


class EmailDeliveryError(RuntimeError):
    """Raised when transactional email cannot be delivered."""


def send_password_reset_email(recipient: str, reset_url: str) -> None:
    host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
    port = int(os.getenv('SMTP_PORT', '587'))
    username = os.getenv('SMTP_USERNAME')
    password = os.getenv('SMTP_PASSWORD')
    sender = os.getenv('EMAIL_FROM', username)

    if not username or not password or not sender:
        raise EmailDeliveryError('SMTP password reset email configuration is incomplete')

    message = EmailMessage()
    message['Subject'] = 'Reset your ExamVault password'
    message['From'] = sender
    message['To'] = recipient
    message.set_content(
        'Use the following link to reset your ExamVault password. '
        'This link expires in 30 minutes:\n\n'
        f'{reset_url}\n\n'
        'If you did not request this, you can ignore this email.'
    )
    message.add_alternative(
        f'''
        <html>
          <body>
            <p>We received a request to reset your ExamVault password.</p>
            <p><a href="{reset_url}">Reset your password</a></p>
            <p>This link expires in 30 minutes. If you did not request this,
            you can ignore this email.</p>
          </body>
        </html>
        ''',
        subtype='html',
    )

    try:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(username, password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as error:
        raise EmailDeliveryError('Password reset email delivery failed') from error
