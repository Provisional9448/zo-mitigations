"""Host Linux metrics; percentages may differ from container quota metrics."""

from pathlib import Path
import shutil


class Sampler:
    def __init__(self, disk_path="/", scratch_path="/tmp"):
        self.disk_path, self.scratch_path = disk_path, scratch_path
        self.previous_cpu = None

    def sample(self):
        result = {}
        for key, path in (("disk_pct", self.disk_path), ("tmp_pct", self.scratch_path)):
            try:
                usage = shutil.disk_usage(path)
                result[key] = 100 * usage.used / usage.total
            except (OSError, ZeroDivisionError):
                pass
        try:
            memory = {line.split(":")[0]: int(line.split()[1]) for line in Path("/proc/meminfo").read_text().splitlines()}
            result["ram_pct"] = 100 * (1 - memory["MemAvailable"] / memory["MemTotal"])
        except (OSError, ValueError, KeyError, ZeroDivisionError):
            pass
        try:
            values = [int(v) for v in Path("/proc/stat").read_text().splitlines()[0].split()[1:9]]
            total, idle = sum(values), values[3] + values[4]
            if self.previous_cpu and total > self.previous_cpu[0] and idle >= self.previous_cpu[1]:
                result["cpu_pct"] = max(0, min(100, 100 * (1 - (idle - self.previous_cpu[1]) / (total - self.previous_cpu[0]))))
            self.previous_cpu = (total, idle)
        except (OSError, ValueError, IndexError):
            pass
        return result
