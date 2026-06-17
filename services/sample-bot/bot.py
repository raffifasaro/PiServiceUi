"""A tiny demo 'service'.

It does nothing useful: it just logs a heartbeat every few seconds and burns
a little CPU so you can watch the metrics move in the UI. Use it to verify
start/stop/restart, logs and metrics without needing a real Discord token.
"""
import datetime
import itertools
import time

print("sample-bot starting up", flush=True)

for i in itertools.count(1):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    # A small busy spin so CPU% is visibly non-zero in the UI.
    x = 0
    for _ in range(200_000):
        x += 1
    print(f"[{now}] heartbeat #{i}", flush=True)
    time.sleep(3)
