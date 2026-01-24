import inspect
import os

import jinja2

from sprout.database import get_package_classes, getFieldTypeMap
from sprout.util import get_property_type_map
from sprout.database.base_object import AbstractDataTable as SproutBaseObject
# from sprout.util import get_package_classes, getFieldTypeMap
from pathlib import Path
# from turbindo.data_objects import Unset

def generate_data_accessors(package, appname):

    # next line retrieves package classes that are subclasses of
    # TurbindoBaseObject, and are not DataModelObject and TurbindoBaseObject.
    classes = get_package_classes(package, ["DataModelObject", "TurbindoBaseObject"], SproutBaseObject)


    # Next line retrieves the jinja
    import turbindo.templates
    path = os.path.abspath(Path(turbindo.templates.__file__).parent.absolute())


    templateLoader = jinja2.FileSystemLoader(searchpath=path)
    templateEnv = jinja2.Environment(loader=templateLoader)

    class_prop_map = {}
    classtypes = {}
    class_type_map = {}


    # extract all column names from classes to list class_prop_map
    for c in classes:
        # pull out fields and types and assign them to classtypes[CLASS]
        # example: def test_case(self) -> str:, create dict {['test_case',
        # 'str'],[etc]}

        classtypes[c.__name__] = get_property_type_map(c)

        # based on whether the members of the class are an instance of
        # 'property' we will grab the first element and
        members = [i[0] for i in inspect.getmembers(c, lambda o: isinstance(o, property))]


        members = [i for i in members if i != 'id']

        # class_prop_map contains all members of a class that are typed with
        # 'property'
        class_prop_map[c.__name__] = members

    def doubleq(sl: list):
        return [f"{o}={o}" for o in sl]

    templateEnv.filters['doubleq'] = doubleq
    TEMPLATE_FILE = "data_accessors.py.j2"
    template = templateEnv.get_template(TEMPLATE_FILE)
    # first thing we appear to be doing here is to take the .j2 file and
    # replacing anything in brackets with our filter's instructions.



    for c, data in classtypes.items():
        entries = []
        for k, v in data.items():
            if k != "id":
                entries.append(f"{k}:{v.__name__}")
        class_type_map[c] = entries

    #     previous generates text looking like table_field_name:
    #     table_field_type I presume, to entries and then to class_type_map[
    #     CLASS]
    # It looks like this is all for class_type_map[CLASS] to contain a list
    # of table field names and types.

    outputText = template.render({
        "appname": appname,
        "package": package,
        "data_objects": classes,
        "class_prop_map": class_prop_map,
        "class_type_map": class_type_map
    })  # this is where to put args to __name__the template renderer

    return outputText
