import inspect

from sprout.database.impl.sqlite import SQL_TYPE_LOOKP


def kvdefault(dict, key, default):
    if key in dict:
        return dict[key]
    return default


def get_property_type_map(clazz) -> dict:
    properties = inspect.getmembers(clazz, lambda o: isinstance(o, property))

    field_type_map = {}
    for prop in properties:
        field_name = prop[0]

        field_type = inspect.signature(
            getattr(getattr(clazz, field_name), "fget"))
        field_type_str = field_type.return_annotation.__name__
        field_type_lookup = SQL_TYPE_LOOKP.get(field_type_str)
        field_type_map[field_name] = field_type_lookup
    return field_type_map