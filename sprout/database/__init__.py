import inspect
import os
from pathlib import Path

import aiosqlite
import jinja2
import yaml
from aiosqlite import Cursor
from jinja2 import Template

import sprout.database.base_object
import sprout.templates
from sprout.database.impl.sqlite import Sqlite
from sprout.database.base_object import AbstractDataTable
from sprout.database.data_accessors import get_package_classes
from sprout.database.impl.sqlite.SqliteDataTable import SqliteDataTable
from sprout.database.objects.data_objects import TestResults, MetaData
from sprout.util import get_property_type_map

schema_version = 2


def create_table_def(clazz):
    if not issubclass(clazz, AbstractDataTable):
        raise Exception(f"{clazz.__name__} does not extendAbstractDataTable")
    field_type_map = get_property_type_map(clazz)
    field_type_map.pop('id')

    create_table_template = Template(
        """
        CREATE TABLE IF NOT EXISTS   {{ table_name }}   ( 
        {% for name, type in fields.items() -%} 
        {{ name }} {{type}},
        {% endfor -%} 
        id TEXT
        );
        """
    )

    rendered_string = create_table_template.render(table_name=clazz.__name__, fields=field_type_map)

    return rendered_string


async def create_connection(db_file):
    """ create a database connection to the SQLite database
        specified by db_file
    :param db_file: database file
    :return: Connection object or None
    """
    try:
        conn = await aiosqlite.connect(db_file)
        return conn
    except aiosqlite.Error as e:
        print(e)

    return None


async def create_table(create_table_sql):
    """ create a table from the create_table_sql statement
    :param conn: Connection object
    :param create_table_sql: a CREATE TABLE statement
    :return:
    """
    cursor = await Sqlite.conn.execute(create_table_sql)
    await Sqlite.conn.commit()
    return cursor


async def insert_into_table(sql_insert_statement, *params) -> Cursor:
    cursor = await Sqlite.conn.execute(sql_insert_statement, *params)
    await Sqlite.conn.commit()
    return cursor


async def execute_sql_statement(sql_statement, *params):
    # this fn only supports single statements
    assert sql_statement.count(';') < 2
    cursor = await Sqlite.conn.execute(sql_statement, *params)
    await Sqlite.conn.commit()
    return cursor


async def get_columns_from_table(sql_select):
    cursor = await Sqlite.conn.execute(sql_select)
    names = list(map(lambda x: x[0], cursor.description))
    return names


# @todo
async def issue_query_result_single(sql_statement):
    pass


async def issue_query_result_iterator(sql_statement):
    pass


async def select_from_table(sql_select, id=None):
    if id is None:
        params = []
    else:
        params = [id]
    cursor = await Sqlite.conn.execute(sql_select, params)

    # following line creates a list which is taken from the output of map function taking 1st element of x
    names = list(map(lambda x: x[0], cursor.description))
    row = await cursor.fetchone()

    selected_row = row

    while row is not None:
        row = await cursor.fetchone()
        if (row is not None):
            selected_row = row

    return (selected_row, names)


async def run_schema_updates(yamlfile):
    sql_select_max_version = """ SELECT max(databaseVersion ) FROM MetaData """
    max_ver_row, names = await select_from_table(sql_select_max_version)

    if (max_ver_row is not None):
        if (max_ver_row[0] is not None):
            max_ver_from_db = int(max_ver_row[0])
        else:
            max_ver_from_db = 0
    else:
        # We do not have access to table and we can not execute any updates -- fatal error
        max_ver_from_db = 0

    with open(yamlfile) as f:
        updatesDoc = yaml.load_all(f, Loader=yaml.FullLoader)

        master_update_sql_statement_TMPL = Template(
            "INSERT INTO MetaData (databaseVersion) VALUES({{db_version}})")

        async def do_update(sqlStatement):
            versFromFile = int(theUpdateNumber)
            if (versFromFile > max_ver_from_db):
                # update database with sql query from file
                sql_statement_to_execute = sqlStatement
                await execute_sql_statement(sql_statement_to_execute)

                # add updated version to database
                master_update_sql_statement = master_update_sql_statement_TMPL.render(
                    db_version=versFromFile)
                await execute_sql_statement(
                    master_update_sql_statement)

        for doc in updatesDoc:
            for theUpdateNumber, entry in doc.items():
                if type(entry) is list:
                    for sqlStatement in entry:
                        await do_update(sqlStatement)
                else:
                    await do_update(entry)


async def generate_data_accessors(thePackage):
    package_classes = get_package_classes(thePackage, "DataTable",
                                          AbstractDataTable)
    path = os.path.abspath(Path(sprout.templates.__file__).parent.absolute())
    template_loader = jinja2.FileSystemLoader(searchpath=path)
    template_enviorn = jinja2.Environment(loader=template_loader)

    class_prop_map = {}
    classtypes = {}
    class_type_map = {}

    for clazz in package_classes:
        classtypes[clazz.__name__] = get_property_type_map(clazz)

        members = [i[0] for i in
                   inspect.getmembers(clazz, lambda o: isinstance(o, property))]

        members = [i for i in members if i != 'id']
        class_prop_map[clazz.__name__] = members

    def doubleq(sl: list):
        return [f"{o}={o}" for o in sl]

    template_enviorn.filters['doubleq'] = doubleq
    TEMPLATE_FILE = "data_accessors.py.j2"
    template = template_enviorn.get_template(TEMPLATE_FILE)

    for clazz, data in classtypes.items():
        entries = []
        for k, v in data.items():
            if k != "id":
                entries.append(f"{k}:{v}")
        class_type_map[clazz] = entries

    accessor_python_code = template.render({
        "data_objects": package_classes,
        "class_type_map": class_type_map,
        "class_prop_map": class_prop_map,
    })

    return accessor_python_code


async def run_database_updates(yaml_file):
    await run_schema_updates(yaml_file)


async def initialize_metadata():
    await execute_sql_statement(create_table_def(MetaData))

    try:
        result = await select_from_table("select * from MetaData")
    except Exception as e:
        pass
        # await create_table(create_table_def(MetaData))

    # result = await select_from_table("select * from MetaData")

    if result is None:
        result = await insert_into_table("insert into MetaData (databaseVersion) values (1)")
        print(result)


async def initialize_database_sqlite(database, data_class_package):
    Sqlite.conn = await create_connection(database)

    await initialize_metadata()

    print(await generate_data_accessors(data_class_package))

    package_classes = get_package_classes(data_class_package, ["DataTable", "AbstractDataTable"],
                                          sprout.database.base_object.AbstractDataTable)

    sql_statements = []

    if package_classes.__len__() == 0:
        raise Exception("no data classes found")
    else:
        for cls in package_classes:
            sql_statements.append(create_table_def(cls))
        if (sql_statements.__len__() > 0):
            for statement in sql_statements:
                await create_table(statement)


async def initialize_database(config, disk_path, data_class_package):
    if config.db.driver == 'sqlite':
        base_object.AbstractDataTable.DATABASE_IMPL = SqliteDataTable
        return await initialize_database_sqlite(disk_path, data_class_package)
