from example_sprout_apps.mailsync import data as db
from example_sprout_apps.mailsync import input_output as io
from example_sprout_apps.mailsync.SM.email_processor import EMailProcessor
from sprout.runtime import scheduler


async def sync_mail():
    mail_count = await io.ic().message_count("INBOX")
    db_mail_height = await db.get_latest_stored_message()
    if mail_count > db_mail_height:
        for msg_id in range(db_mail_height, mail_count + 1):
            sprout_context = f"sync_mail:{msg_id}"
            try:
                msg_string = await io.ic().get_message("INBOX", str(msg_id))

                msm = EMailProcessor(msg_id, msg_string)
                # initial state is 'raw' when triggering transition such as parse_and_store, then that will call hook which
                # ive configured which will parse the msg, and then store it in database. then it will transition to
                # parsed_and_stored
                #
                await scheduler.dispatch_job(msm.parse_and_store()) #parse and store in the background
            except Exception as e:
                print(e)
                continue
