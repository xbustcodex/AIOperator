# services/logger.py
import time

class Logger:
    @staticmethod
    def log(message: str):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}")
        # Optional: write to file
        # with open('/sdcard/AI/log.txt', 'a') as f:
        #     f.write(f"[{timestamp}] {message}\n")
