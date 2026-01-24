# CODE GENERATED -- FILE DO NOT MODIFY

from example_sprout_apps.smssync.data.classes import SMS
from sprout.database.objects import SPECIAL_TYPES


async def readSMS(id) -> SMS:
    return await SMS(id).read()


async def writeSMS(id,
                   body_field: str = SPECIAL_TYPES.NOT_SET,
                   date_field: str = SPECIAL_TYPES.NOT_SET,
                   from_field: str = SPECIAL_TYPES.NOT_SET,
                   to_field: str = SPECIAL_TYPES.NOT_SET) -> SMS:
    return await SMS(id).set(
        body_field=body_field,
        date_field=date_field,
        from_field=from_field,
        to_field=to_field)

#
# async def readSMS(id) -> SMS:
#     return await SMS(id).read()

#
# async def writeSMS(
#         id,
#         body_field:TEXT=SPECIAL_TYPES.NOT_SET,
#         date_field:TEXT=SPECIAL_TYPES.NOT_SET,
#         from_field:TEXT=SPECIAL_TYPES.NOT_SET,
#         headers:TEXT=SPECIAL_TYPES.NOT_SET,
#         subject_field:TEXT=SPECIAL_TYPES.NOT_SET,
#         to_field:TEXT=SPECIAL_TYPES.NOT_SET) -> SMS:
#     return await SMS(id).set(
#         body_field=body_field,
#         date_field=date_field,
#         from_field=from_field,
#         headers=headers,
#         subject_field=subject_field,
#         to_field=to_field)
