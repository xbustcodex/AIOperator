# services/loop_service.py
import time
from core.agent import Agent
from services.logger import Logger

class LoopService:
    @staticmethod
    def start(auto_mode: bool = False, interval: int = 5):
        Logger.log("LoopService started")
        try:
            while True:
                if auto_mode:
                    # Example: poll a predefined task file
                    with open('/sdcard/AI/tasks.txt', 'r') as f:
                        tasks = f.readlines()
                    for task in tasks:
                        task = task.strip()
                        if task:
                            Logger.log(f"Running auto task: {task}")
                            results = Agent.run(task)
                            Logger.log(f"Results: {results}")
                    time.sleep(interval)
                else:
                    time.sleep(interval)
        except KeyboardInterrupt:
            Logger.log("LoopService stopped")
