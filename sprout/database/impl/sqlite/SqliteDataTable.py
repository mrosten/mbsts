from sprout.database.impl.sqlite import Sqlite
from box import Box

class SqliteDataTable:
    @staticmethod
    async def _read(table_obj, objid):
        table_name = table_obj.__class__.__name__
        if Sqlite.conn:
             cursor = await Sqlite.conn.execute(f"SELECT * FROM {table_name} WHERE id=?", (objid,))
             row = await cursor.fetchone()
             # We should probably return a loaded object or dict here.
             # Based on AbstractDataTable, we just return for now.
             # The system seems to expect the object to be populated maybe?
             # For 'read', AbstractDataTable returns the result.
             return row
        return None

    @staticmethod
    async def _set(table_obj, objid, **kwargs):
        table_name = table_obj.__class__.__name__
        if Sqlite.conn:
            # parsing kwargs for columns and values
            columns = list(kwargs.keys())
            values = list(kwargs.values())
            
            # Prepare placeholders
            placeholders = ["?"] * len(values)
            
            # We need to handle ID as well.
            # INSERT OR REPLACE INTO table (id, col1, col2) VALUES (?, ?, ?)
            all_columns = ["id"] + columns
            all_values = [objid] + values
            all_placeholders = ["?"] * len(all_values)
            
            query = f"INSERT OR REPLACE INTO {table_name} ({', '.join(all_columns)}) VALUES ({', '.join(all_placeholders)})"
            
            await Sqlite.conn.execute(query, all_values)
            await Sqlite.conn.commit()
            return True
