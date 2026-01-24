from sprout import database as db


async def get_latest_stored_message() -> int:
    query = "select MAX(id) from EMail"
    row, names = await db.select_from_table(query)

    if row[0] is None:
        return 1
    else:
        return row[0]
