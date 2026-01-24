
class Logger:
    def __init__(self, name):
        self.name = name
    
    def process(self, msg):
        # Based on hello_world main.py: ans1 = logger.process("Hello")
        # assuming it logs and returns something or just logs.
        print(f"[{self.name}] {msg}")
        return f"Processed: {msg}"

# Singleton-like usage in main.py: from sprout.log import logger ??
# main.py does: from sprout.log import logger AND from sprout.log.logger import Logger
# so we need both.

logger = Logger("root")
