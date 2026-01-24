import asyncio
import inspect
from os import listdir
from os.path import isfile, join
from pathlib import Path

import sprout
from sprout.database.objects.data_objects import TestResults


def get_package_classes(data_class_package, excluded_classes:list, base_object):
    data_classes_found = []
    try:
        # refToPackage = importlib.import_module(thePackage)

        # if ('__init__.py' in str(refToPackage)):
        #     raise Exception('must pass package', 'error')

        mypath = Path(data_class_package.__file__).parent

        onlyfiles = [f for f in listdir(mypath) if isfile(join(mypath, f))]
        #
        # for x in onlyfiles:
        #     module = importlib.import_module(x)
        #     for name, obj in inspect.getmembers(module, inspect.isclass):
        #         print (obj)

        package_items = dir(data_class_package)

        for package_item in package_items:
            if (not package_item.startswith('__')):
                pkg_attr = getattr(data_class_package, package_item)
                if (inspect.isclass(pkg_attr) and
                        issubclass(pkg_attr, base_object) and
                        (not pkg_attr.__name__ in excluded_classes)):
                    data_classes_found.append(pkg_attr)

                # refToSubElements = importlib.import_module(thePackage + "." + anElement)

                # try:
                #     subElementsInFile = dir(refToSubElements)
                #     for aSubElement in subElementsInFile:
                #         aRefToSubElement = getattr(refToSubElements, aSubElement)
                #
                #         if(inspect.isclass(aRefToSubElement) and issubclass(aRefToSubElement, underBaseClass)):
                #             if (not aRefToSubElement.__name__ in str(toExcludeStringList)):
                #
                #                 listOfClassesToReturn.append(aRefToSubElement)
                #                 print(aRefToSubElement.__name__)
                #
                # except Exception as inst:
                #     print(inst)
                # print(dir(refToSubElements))
    except Exception as e:
        print(e)

    return data_classes_found


def generate_data_accessors(package, appname):
    classes = get_package_classes(package, ["MetaData", "TurbindoBaseObject"], sprout.database.base_object.AbstractDataTable)
    print(classes)


#     i'm receiving a package path to search out and to return classes that are in this package
#     I will find the code for this search in the data_objects.py where I have the same search happening


async def getTestResults(id) -> TestResults:
    return await TestResults(id).async_init()


async def setTestResults(id, **kwargs):
    {
        "question": 5,

    }

# await setTestResults('1234', question=5, result=True)
#     "update testresults where id=1234 "

# thing = await getTestResults(1234)
# print(thing.question)
