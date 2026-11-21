"""Cloudflare R2 media store (Nov 21): big files (4K episode masters) go to the private bucket `nobodystown-media`,
then a short-lived signed link hands them to vidIQ. The bucket is never public; the key can only touch this one bucket.
  python3 -m nt.r2 put <file> [<key>]     -> uploads, prints the key
  python3 -m nt.r2 link <key> [<hours>]   -> prints a signed download link (default 6 hours)
  python3 -m nt.r2 ls
Credentials only in ~/.secrets/r2_account_id, r2_access_key_id, r2_secret_access_key (chmod 600). Edit layer only."""
import os, sys

BUCKET = "nobodystown-media"


def _s(name):
    return open(os.path.expanduser(f"~/.secrets/{name}")).read().strip()


def client():
    import boto3
    from botocore.config import Config
    return boto3.client("s3", endpoint_url=f"https://{_s('r2_account_id')}.r2.cloudflarestorage.com",
                        aws_access_key_id=_s("r2_access_key_id"), aws_secret_access_key=_s("r2_secret_access_key"),
                        region_name="auto", config=Config(signature_version="s3v4", retries={"max_attempts": 5}))


def put(path, key=None):
    key = key or os.path.basename(path)
    client().upload_file(path, BUCKET, key, ExtraArgs={"ContentType": "video/mp4" if path.endswith(".mp4") else "application/octet-stream"})
    return key


def link(key, hours=6):
    return client().generate_presigned_url("get_object", Params={"Bucket": BUCKET, "Key": key}, ExpiresIn=int(hours * 3600))


def ls():
    return [(o["Key"], o["Size"]) for o in client().list_objects_v2(Bucket=BUCKET).get("Contents", [])]


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "put": print(put(a[1], a[2] if len(a) > 2 else None))
    elif a[0] == "link": print(link(a[1], float(a[2]) if len(a) > 2 else 6))
    elif a[0] == "ls": [print(k, s) for k, s in ls()]
