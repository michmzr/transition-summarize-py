import boto3

s3 = boto3.client(
    service_name="s3",
    endpoint_url="https://ebb83cb8f33ce07179844c1490ea42f3.r2.cloudflarestorage.com",
    aws_access_key_id="bd64fe79e51c31c33f7492b6944d1349",
    aws_secret_access_key="f0165e31fad8055c8ca47c72f5814672ad2039a7e130f7e3fa0c4ef5e66855cf",
    region_name="auto",
)

# Sprawdź dostęp do bucketu secondbrain
try:
    s3.head_bucket(Bucket="secondbrain")
    print("✅ Dostęp OK!")
except Exception as e:
    print(f"❌ Brak dostępu: {e}")
