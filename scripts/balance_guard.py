"""Stop `lcverus run` when the DeepSeek balance drops below a floor. Usage: balance_guard.py PID [floor_usd]"""
import os, signal, sys, time

import openai

from lcverus.config import load

pid, floor = int(sys.argv[1]), float(sys.argv[2]) if len(sys.argv) > 2 else 0.10
cl = openai.OpenAI(api_key=load().api_key, base_url="https://api.deepseek.com")
while True:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        break
    try:
        bal = float(cl.get("/user/balance", cast_to=object)["balance_infos"][0]["total_balance"])
        print(time.strftime("%H:%M:%S"), f"balance ${bal:.2f}", flush=True)
        if bal < floor:
            print("below floor, sending SIGTERM (checkpointed nodes are kept)", flush=True)
            os.kill(pid, signal.SIGTERM)
            break
    except Exception as e:
        print("balance check failed:", e, flush=True)
    time.sleep(60)
