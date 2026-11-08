"""Public file hosting for Instagram (IG only accepts media by public URL).

Uses Cloudflare R2 (free tier) through its S3-compatible API.
Env: R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET, R2_PUBLIC_BASE (e.g. https://pub-xxxx.r2.dev)
If these are not set, Instagram posting is skipped and only Facebook is used.
"""
import mimetypes, os


def enabled():
    return all(os.environ.get(k) for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET", "R2_PUBLIC_BASE"))


def upload(path, key):
    import boto3
    s3 = boto3.client("s3", endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
                      aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"], aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
                      region_name="auto")
    ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
    s3.upload_file(path, os.environ["R2_BUCKET"], key, ExtraArgs={"ContentType": ctype})
    return f"{os.environ['R2_PUBLIC_BASE'].rstrip('/')}/{key}"
