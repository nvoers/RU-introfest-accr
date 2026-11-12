"""Development e-mail backend that prints messages readably.

Django's console backend prints the raw MIME message. Bodies end up quoted-printable
encoded, which wraps long lines with a trailing "=" – so invite and ticket links get cut
in half when you copy them from the terminal. This prints the decoded text instead.
"""

from django.core.mail.backends.console import EmailBackend as ConsoleBackend


class EmailBackend(ConsoleBackend):
    def write_message(self, message):
        line = "-" * 79
        self.stream.write(
            f"{line}\n"
            f"From: {message.from_email}\n"
            f"To: {', '.join(message.to)}\n"
            f"Subject: {message.subject}\n\n"
            f"{message.body}\n"
            f"{line}\n"
        )
