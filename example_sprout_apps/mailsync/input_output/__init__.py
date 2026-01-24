from example_sprout_apps.mailsync.input_output.imap import ImapClient
from sprout.runtime.context import io_context

async def setup():
    await io_context.register(ImapClient)

def ic() -> ImapClient:
        return io_context.lookup(ImapClient)

