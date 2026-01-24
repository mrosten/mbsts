import argparse
import asyncio

import sprout.database
from sprout.log.logger import Logger
from sprout.database import generate_data_accessors
from sprout.log.logger import Logger

# Purpose of this file is to run tests determined by parameters given to app
# at runtime.

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    _context = "CLI"
    logger = Logger('main')

    parser.add_argument("--tests", help="run the testsuite", action="store_true", default=False)
    parser.add_argument("--test_suite", help="specify test suite", type=str, default=False)
    parser.add_argument("--test_case", help="specify test case from suite", type=str, default=False)
    parser.add_argument("--generate_accessors", help="specify test case from suite", type=str, default=False)

    args = parser.parse_args()

    if args.tests:
        app_loop = asyncio.new_event_loop()
        if args.test_suite:
            if args.test_case:
                from sprout.test import system as test_system

                results: list = app_loop.run_until_complete(
                    test_system.run_tests(app_loop, args.test_suite, args.test_case))
            else:
                from sprout.test import system as test_system

                results: list = app_loop.run_until_complete(test_system.run_tests(app_loop, args.test_suite))
                if args.test_suite == 'databasetests':
                    from sprout.test import system as test_system
                    from sprout.test.suites.databasetests import DatabaseTest

                    results: list = app_loop.run_until_complete(
                        test_system.run_tests(app_loop, DatabaseTest, args.test_suite))
        else:
            from sprout.test import system as test_system

            results: list = app_loop.run_until_complete(test_system.run_tests(app_loop))
    elif args.generate_accessors:
        app_loop = asyncio.new_event_loop()
        results: list = app_loop.run_until_complete(generate_data_accessors(args.generate_accessors))
        print(results)
