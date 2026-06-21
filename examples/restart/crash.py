import time


print("restart-demo started", flush=True)
time.sleep(2)
print("restart-demo exiting with code 1", flush=True)
raise SystemExit(1)
