"""Credential-free readiness over the run's verified TLS; no bypass/reports."""
import os
import ssl
import time
import urllib.request
context = ssl.create_default_context(cafile=os.environ['L4_CA_FILE'])
for _ in range(40):
    try:
        with urllib.request.urlopen('https://nabhold.int03.test/sign-in', context=context, timeout=4) as response:
            if response.status == 200:
                raise SystemExit(0)
    except (OSError, ValueError):
        pass
    time.sleep(2)
raise SystemExit(2)
