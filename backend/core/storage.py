from storages.backends.s3 import S3Storage
from storages.utils import clean_name

from .s3 import get_public_s3_client


class PrivateS3Storage(S3Storage):
    """Penyimpanan bucket privat (SeaweedFS).

    Objek tidak pernah dibuka untuk publik. URL berkas selalu berupa presigned URL
    berumur pendek yang ditandatangani untuk endpoint publik (S3_PUBLIC_ENDPOINT_URL),
    karena endpoint internal (http://storage:8333) tidak bisa dibuka peramban.
    """

    def url(self, name, parameters=None, expire=None, http_method=None):
        name = self._normalize_name(clean_name(name))
        params = {"Bucket": self.bucket_name, "Key": name}
        if parameters:
            params.update(parameters)
        if expire is None:
            expire = self.querystring_expire
        return get_public_s3_client().generate_presigned_url(
            "get_object", Params=params, ExpiresIn=expire, HttpMethod=http_method
        )
