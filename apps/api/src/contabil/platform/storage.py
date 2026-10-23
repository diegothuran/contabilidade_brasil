from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from typing import BinaryIO, Protocol

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from contabil.platform.errors import DomainError
from contabil.platform.settings import get_settings


class ObjectStore(Protocol):
    def put(self, key: str, source: BinaryIO, size: int, media_type: str) -> str: ...

    def open(self, key: str) -> Iterator[bytes]: ...

    def exists(self, key: str) -> bool: ...

    def ensure_bucket(self, name: str) -> None: ...


def document_key(tenant_id: str, sha256: str) -> str:
    return f"{tenant_id}/documents/{sha256}"


def object_ref(bucket: str, key: str) -> str:
    return f"s3://{bucket}/{key}"


@lru_cache
def _client(endpoint: str, access_key: str, secret_key: str, region: str):
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


class S3ObjectStore:
    def __init__(self) -> None:
        settings = get_settings()
        self.bucket = settings.object_storage_bucket
        self._s3 = _client(
            settings.object_storage_endpoint,
            settings.object_storage_access_key,
            settings.object_storage_secret_key,
            settings.object_storage_region,
        )

    def put(self, key: str, source: BinaryIO, size: int, media_type: str) -> str:
        del size
        try:
            self._s3.upload_fileobj(source, self.bucket, key, ExtraArgs={"ContentType": media_type})
        except ClientError as exc:
            raise DomainError(502, "Falha de armazenamento", "Não foi possível guardar o arquivo original.") from exc
        return object_ref(self.bucket, key)

    def open(self, key: str) -> Iterator[bytes]:
        try:
            response = self._s3.get_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {"404", "NoSuchKey", "NotFound"}:
                raise DomainError(404, "Não encontrado", "O arquivo original não está no armazenamento.") from exc
            raise DomainError(502, "Falha de armazenamento", "Não foi possível ler o arquivo original.") from exc
        body = response["Body"]
        try:
            while True:
                chunk = body.read(1024 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            body.close()

    def exists(self, key: str) -> bool:
        try:
            self._s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise DomainError(502, "Falha de armazenamento", "Não foi possível consultar o arquivo original.") from exc

    def ensure_bucket(self, name: str) -> None:
        try:
            self._s3.head_bucket(Bucket=name)
            return
        except ClientError:
            pass
        try:
            self._s3.create_bucket(Bucket=name)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
                return
            raise DomainError(502, "Falha de armazenamento", "Não foi possível preparar o bucket.") from exc


def get_object_store() -> S3ObjectStore:
    return S3ObjectStore()


def ensure_configured_buckets() -> None:
    store = get_object_store()
    settings = get_settings()
    for name in {settings.object_storage_bucket, "contabil-dev", "contabil-test"}:
        store.ensure_bucket(name)
