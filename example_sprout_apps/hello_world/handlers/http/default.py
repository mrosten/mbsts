from aiohttp.web_request import Request
from sprout.log.logger import Logger
from aiohttp import web

from example_sprout_apps.hello_world import input_output


async def default_http_handler(request: Request):
    _context = "default_http_handler"
    logger = Logger("http handler")
    logger.log(f"got request from {request.remote}")
    data1 = await input_output.hc().httpGetSync("http://icanhazip.com/")
    data2 = await input_output.hc().httpGetAsync("http://icanhazip.com/")

    return web.Response(text="hello http req1: " + data1 + " req2: " + data2)
