import os
import base64

for i in range(100):
    print(base64.urlsafe_b64encode(os.urandom(24)).decode())
