import aiohttp
import requests as requests
from sprout.runtime.instrumented_object import InstrumentedIO

class ExampleHTTPClient(InstrumentedIO):
    async def httpGetAsync(self, url) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                return await resp.text()

    def httpGetSync(self, url) -> str:
        return requests.get(url).text
