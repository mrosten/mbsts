import argparse
import asyncio

from example_sprout_apps.financial.financial import FinancialApp
from sprout.log import logger
from sprout.log.logger import Logger

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    sprout_context = "CLI"

    logger = Logger('main')
    parser.add_argument("--tests", help="run the testsuite", action="store_true", default=False)
    # parser.add_argument("--test_suite", help="specify test suite", action="store_example apptrue", default=False)
    parser.add_argument("--test_case", help="specify test case from suite", action="store_true", default=False)
    parser.add_argument("--run_app", help="run application", action="store_true", default=False)

    args = parser.parse_args()
    if args.tests:
        app_loop = asyncio.new_event_loop()
        if args.test_suite:
            if args.test_case:
                pass
            else:
                pass
        else:
            from sprout.test import system as test_system

            results: list = app_loop.run_until_complete(test_system.run_tests(app_loop))
            for r in results:
                print(r)
    elif args.run_app:
        app_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(app_loop)
        app_inst = FinancialApp()
        app_loop.run_until_complete(app_inst.start())
        app_loop.run_forever()

    ans1 = logger.process("Hello")
    print(ans1)
