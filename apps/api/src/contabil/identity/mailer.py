from __future__ import annotations

import logging
from typing import Protocol

import boto3
from botocore.exceptions import ClientError

from contabil.platform.settings import get_settings

logger = logging.getLogger(__name__)


class Mailer(Protocol):
    def send(self, recipient: str, subject: str, body: str) -> bool: ...


class UnavailableMailer:
    def send(self, recipient: str, subject: str, body: str) -> bool:
        del recipient, subject, body
        logger.info("mailer unavailable")
        return False


class SesMailer:
    def __init__(self, client, sender: str) -> None:
        self._client = client
        self._sender = sender

    def send(self, recipient: str, subject: str, body: str) -> bool:
        try:
            self._client.send_email(
                Source=self._sender,
                Destination={"ToAddresses": [recipient]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
                },
            )
        except ClientError:
            logger.warning("ses send failed")
            return False
        return True


def get_mailer() -> Mailer:
    settings = get_settings()
    sender = settings.mail_from.strip()
    access_key = settings.ses_access_key.strip()
    secret_key = settings.ses_secret_key.strip()
    if not sender or not access_key or not secret_key:
        return UnavailableMailer()
    client = boto3.client(
        "ses",
        region_name="us-east-2",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )
    return SesMailer(client, sender)


def notice_text(title: str, due_on: str, portal_url: str) -> tuple[str, str]:
    subject = f"Pedido de documento: {title}"
    link = portal_url.strip() or "o portal do escritório"
    body = f"Pedido: {title}\nPrazo: {due_on}\nAcesse: {link}\n"
    return subject, body
