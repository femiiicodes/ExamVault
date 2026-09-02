import os
import boto3
from dotenv import load_dotenv

load_dotenv()
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME")

r2 = boto3.client(
    "s3",
    endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    region_name="auto",
)

def upload_file(
    file,
    object_key: str,
    content_type: str = "application/pdf"
):
    r2.upload_fileobj(
        file,
        R2_BUCKET_NAME,
        object_key,
        ExtraArgs={
            "ContentType": content_type
        }
    )

# print("Account ID:", R2_ACCOUNT_ID)
# print("Access Key:", R2_ACCESS_KEY_ID)
# print("Bucket:", R2_BUCKET_NAME)

def generate_download_url(
    object_key: str,
    expires_in: int = 3600
):
    return r2.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": R2_BUCKET_NAME,
            "Key": object_key,
        },
        ExpiresIn=expires_in,
    )

def delete_file(object_key: str):
    """Delete a file from R2 bucket"""
    try:
        r2.delete_object(
            Bucket=R2_BUCKET_NAME,
            Key=object_key
        )
        return True
    except Exception as e:
        print(f"Error deleting {object_key}: {e}")
        return False