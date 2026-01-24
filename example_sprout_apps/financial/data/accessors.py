# CODE GENERATED -- FILE DO NOT MODIFY

from example_sprout_apps.mailsync.data.classes import EMail, HttpLog
from sprout.database.objects import SPECIAL_TYPES


async def readEMail(id) -> EMail:
    return await EMail(id).read()


async def writeEMail(id, body_field: str = SPECIAL_TYPES.NOT_SET, date_field: str = SPECIAL_TYPES.NOT_SET,
                     from_field: str = SPECIAL_TYPES.NOT_SET, headers: list = SPECIAL_TYPES.NOT_SET,
                     subject_field: str = SPECIAL_TYPES.NOT_SET, to_field: str = SPECIAL_TYPES.NOT_SET) -> EMail:
    return await EMail(id).set(body_field=body_field, date_field=date_field, from_field=from_field, headers=headers,
                               subject_field=subject_field, to_field=to_field)


async def readHttpLog(id) -> HttpLog:
    return await HttpLog(id).read()


async def writeHttpLog(id, args: list = SPECIAL_TYPES.NOT_SET, body: dict = SPECIAL_TYPES.NOT_SET,
                       remote: str = SPECIAL_TYPES.NOT_SET, time: int = SPECIAL_TYPES.NOT_SET) -> HttpLog:
    return await HttpLog(id).set(args=args, body=body, remote=remote, time=time)
