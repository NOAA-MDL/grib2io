import icechunk
import inspect

print("s3_anonymous:", type(icechunk.s3_anonymous_credentials()))
try:
    c = icechunk.Credentials(s3=icechunk.s3_anonymous_credentials())
    print("Credentials(s3=anon) OK:", type(c))
except Exception as e:
    print("Credentials(s3=anon) FAIL:", e)

try:
    c = icechunk.containers_credentials({"s3://": icechunk.s3_anonymous_credentials()})
    print("containers_credentials OK:", type(c))
except Exception as e:
    print("containers_credentials FAIL:", e)
