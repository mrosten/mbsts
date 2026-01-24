from example_sprout_apps.smssync import data as db
from example_sprout_apps.smssync import input_output as io
from example_sprout_apps.smssync.SM.sms_processor import SMSProcessor
from sprout.runtime import scheduler


from twilio.rest import Client

import fileinput
import argparse
import sys
import json
import os
from twilio.rest import Client


account_sid = os.environ["twilio_account_sid"]
auth_token = os.environ["twilio_auth_token"]

client = Client(account_sid, auth_token)

# messages = client.messages.list(limit=0, to='+16468450948', from_=None)
#
# for m in messages:
#     print(m.body)

def getMessages(num, n=0, inbound=None):
    messages = client.messages.list(limit=n, to=num, from_=inbound)
    return messages

async def sync_sms():
    # account_sid = os.environ["twilio_account_sid"]
    # auth_token = os.environ["twilio_auth_token"]
    try:
    # client = Client(account_sid, auth_token)
        messages = client.messages.list(limit=0, to='+16468450948', from_=None)

        # await scheduler.dispatch_job(msm.parse_and_store()) #parse and store in the background

    except Exception as e:
        print(e)
# msgs = getMessages('+16468450948', n=10, inbound=None)

    for m in messages:

        msm = SMSProcessor(m.sid, m.body)
        # print(m.body)
        await scheduler.dispatch_job(msm.parse_and_store()) #parse and store in the background

# print(messages)

#
    # mail_count = await io.ic().message_count("INBOX")
    # db_mail_height = await db.get_latest_stored_message()
    # if mail_count > db_mail_height:
    #     for msg_id in range(db_mail_height, mail_count + 1):
    #         sprout_context = f"sync_mail:{msg_id}"
    #         try:
    #             msg_string = await io.ic().get_message("INBOX", str(msg_id))
    #
    #             msm = EMailProcessor(msg_id, msg_string)
    #             # initial state is 'raw' when triggering transition such as parse_and_store, then that will call hook which
    #             # ive configured which will parse the msg, and then store it in database. then it will transition to
    #             # parsed_and_stored
    #             #
    #             await scheduler.dispatch_job(msm.parse_and_store()) #parse and store in the background
    #         except Exception as e:
    #             print(e)
    #             continue
