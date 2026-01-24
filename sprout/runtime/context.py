
class IOContext:
    def __init__(self):
        self.loop = None
        self.pool = None
    
    def init(self, loop, pool):
        self.loop = loop
        self.pool = pool
        self.services = {}

    async def register(self, clazz):
        # Assuming register instantiates the class or stores it.
        # hello_world passes a class ExampleHTTPClient
        instance = clazz()
        self.services[clazz.__name__] = instance
        # If the service has async init, maybe call it?
        # For now just store it.
        return instance


io_context = IOContext()
