import shutil
import os


class DeviceObserver:


    def collect(self):

        total, used, free = shutil.disk_usage("/")

        return {
            "device": "android",
            "storage": {
                "total_mb": total // 1024 // 1024,
                "used_mb": used // 1024 // 1024,
                "free_mb": free // 1024 // 1024
            },
            "home": os.path.expanduser("~")
        }