import os
import json
from datetime import datetime


class Memory:

    def __init__(self):
        self.file = os.path.expanduser(
            "~/AIOperator/memory/history.json"
        )

        os.makedirs(
            os.path.dirname(self.file),
            exist_ok=True
        )

        if not os.path.exists(self.file):
            self.save([])


    def load(self):

        with open(self.file, "r") as f:
            return json.load(f)


    def save(self, data):

        with open(self.file, "w") as f:
            json.dump(
                data,
                f,
                indent=2
            )


    def remember(self, event):

        history = self.load()

        history.append({
            "time": str(datetime.now()),
            "event": event
        })

        self.save(history)


    def recent(self, limit=10):

        return self.load()[-limit:]