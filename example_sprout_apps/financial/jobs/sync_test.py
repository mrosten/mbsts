from mailparser import MailParser

from example_sprout_apps.mailsync import input_output as io
from example_sprout_apps.mailsync import data as db


def default(dict, key, default):
    if key in dict:
        return dict[key]
    return default


async def sync_mail():
    mail_count = await io.ic().message_count("INBOX")
    db_mail_height = await db.get_latest_stored_message()
    for msg_id in range(db_mail_height, mail_count):
        try:
            msg_string = await io.ic().get_message("INBOX", str(msg_id))
            parsed_email: MailParser = await io.ic().parse_message(msg_string)
        except Exception as e:
            print(e)
            continue

        await db.writeEMail(msg_id,
                            body_field=parsed_email.body,
                            date_field=str(parsed_email.date),
                            from_field=parsed_email.headers['Return-Path'],
                            subject_field=parsed_email.headers['Subject'],
                            to_field=default(parsed_email.headers, 'To', None))
