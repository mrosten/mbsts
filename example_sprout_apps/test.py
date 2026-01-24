import sprout.database.base_object

from sprout.database.data_accessors import generate_data_accessors, get_package_classes

pc = get_package_classes("example_sprout_apps.hello_world.data.classes", "DataTable", sprout.database.base_object.DataTable)