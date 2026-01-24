from example_sprout_apps.hello_world.input_output.http import ExampleHTTPClient
from example_sprout_apps.hello_world.input_output.http import ExampleHTTPClient
from sprout.runtime.context import io_context

async def setup():
    await io_context.register(ExampleHTTPClient)

def hc() -> ExampleHTTPClient:
        return io_context.lookup(ExampleHTTPClient)

