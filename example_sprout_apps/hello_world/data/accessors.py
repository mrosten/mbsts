from example_sprout_apps.hello_world.data.classes import HttpLog


async def setHttpLog(id, **kwargs):
    httpLogInst = HttpLog(id)


    indic = await httpLogInst.set(**kwargs)


    return indic

async def getHttpLog(id, **kwargs):
    httpLogInst = HttpLog()

    indic = await httpLogInst.read(id, 'HTTPLog', **kwargs)

    return indic