#!/data/data/com.termux/files/usr/bin/python
import time
from core.agent import Agent
from services.logger import Logger
from services.device_observer import DeviceObserver
from memory.memory import Memory
from core.goals import Goals


class AIWorker:

    def __init__(self):
        self.agent = Agent()
        self.logger = Logger()
        
        # Autonomous subsystems
        self.observer = DeviceObserver()
        self.memory = Memory()
        self.goals = Goals()
        
        self.running = True

    def heartbeat(self):
        self.logger.log("Worker heartbeat")

    def observe(self):

         return {
            **self.observer.collect(),
            "goals": self.goals.current(),
            "memory": self.memory.recent(5),
            "allowed_actions": [
                "list_dir",
                "read_file",
                "write_file",
                "run_command"
            ]
         }

    def cycle(self):

        self.heartbeat()

        state = self.observe()

        
        result =                                  result = self.agent.run(state) 

        self.logger.log({
            "state": state,
            "result": result
        })

    def run(self):

        while self.running:
            try:
                self.cycle()

            except Exception as e:
                self.logger.log(
                    f"Worker error: {e}"
                )

            time.sleep(60)


if __name__ == "__main__":
    worker = AIWorker()
    worker.run()