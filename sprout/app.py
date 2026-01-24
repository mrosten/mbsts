import asyncio
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor

from sprout.runtime.context import io_context


class SproutApp(ABC):

    def __init__(self, loop=asyncio.new_event_loop()):
        self.start_time = time.monotonic()
        self.loop = loop
        self.pool = ThreadPoolExecutor()
        io_context.init(self.loop, self.pool)


    @abstractmethod
    async def start(self):
        pass
