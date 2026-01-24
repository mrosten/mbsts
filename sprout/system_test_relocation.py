import asyncio
import inspect

# from sprout.test.suites import async_object_test
from sprout.database import base_object

import importlib

from sprout.test.base_test import BaseTest



async def run_tests(loop, suite='*', case='*'):
    basetestsuite = "sprout.test.suites"
    based_module=importlib.import_module(basetestsuite)
    contents = dir(based_module)
    print(contents)

    basedPackage = "sprout.database"
    suiteBased = importlib.import_module(basedPackage)
    contentsBased = dir(suiteBased)
    print(contentsBased)

    suits = importlib.import_module(basetestsuite)

    for name in contents:
        if not name.startswith("__"):
            whattoimport = basetestsuite + "." + name
            subsuits = importlib.import_module(basetestsuite + "." + name)
            subcontents = dir(subsuits)
            for subname in subcontents:
                element = getattr(subsuits, subname)
                if (inspect.isclass(element)):
                    # Retrieve Classes and check if they are implementing BaseTest
                    if issubclass(element, BaseTest):
                        # This class implements BaseTest
                        # Now this class can be instantiated and the functions run.CREATE
                        instantiatedClass = element()
                        subElements = dir(instantiatedClass)
                        for subElement in subElements:
                            # inspect.iscoroutinefunction(handle):
                            if ((not subElement.startswith(
                                    "_")) and subElement != 'invoke_testcase' and subElement != 'run_all_testcases'):
                                referenceToRoutine = getattr(instantiatedClass, subElement)
                                isAsyncObject = inspect.iscoroutinefunction(referenceToRoutine)
                                if (isAsyncObject):
                                    await referenceToRoutine(loop)



app_loop = asyncio.new_event_loop()
# app_loop.run_until_complete(async_object_test.AsyncObjectTest.test_io(app_loop))
app_loop.run_until_complete(run_tests(app_loop))
from sprout import main
