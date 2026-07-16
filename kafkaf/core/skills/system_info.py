import os
import platform
import shutil
from pathlib import Path

from kafkaf.core.skills.base import Skill

_BYTES_IN_GB = 1024**3


class SystemInfoSkill(Skill):
    name = "system_info"
    description = (
        "Read-only snapshot of the machine KafKaf itself is running on — OS, "
        "Python version, CPU count, and disk free space. Argument is ignored."
    )

    async def run(self, arg: str) -> str:
        total, _used, free = shutil.disk_usage(Path.cwd())
        return (
            f"OS: {platform.system()} {platform.release()}\n"
            f"Python: {platform.python_version()}\n"
            f"CPU cores: {os.cpu_count() or 1}\n"
            f"Disk: {free / _BYTES_IN_GB:.1f} GB free of {total / _BYTES_IN_GB:.1f} GB"
        )
