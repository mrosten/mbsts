import json
import os

from mailparser import MailParser
from transitions import Machine
import random

from transitions.extensions import AsyncMachine

from sprout.configuration import SproutConfiguration
from sprout.log.logger import Logger
from sprout.util import kvdefault
from example_sprout_apps.smssync import data as db
from example_sprout_apps.smssync import input_output as io


class SMSProcessor(object):
    states = ['raw', 'parsed_and_stored', 'archived']

    def __init__(self, sms_id, body):
        self.sms_id = sms_id
        self.body = body
        self.logger = Logger(f'{SMSProcessor.__name__}')
        self.config = SproutConfiguration().config

        self.machine = AsyncMachine(model=self, states=SMSProcessor.states, initial='raw')

        self.machine.add_transition(trigger='parse_and_store',
                                    source='raw',
                                    dest='parsed_and_stored',
                                    before="do_parse",
                                    after=["do_store", 'archive'])

        self.machine.add_transition(trigger='archive',
                                    source='parsed_and_stored',
                                    dest='archived',
                                    before="do_archive")

    async def do_parse(self):
        sprout_context = f"{self.sms_id}"
        self.logger.log("do_parse")
        # self.parsed_email: MailParser = await io.ic().parse_message(self.body)

    async def do_archive(self):
        path = self.config.app.archive_path
        assert os.path.isdir(path)
        open(f'{path}/{self.sms_id}.mail','w').write(self.body)

    async def do_store(self):
        sprout_context = f"{self.sms_id}"
        self.logger.log("do_store")
        await db.writeEMail(self.email_id,
                            body_field=self.parsed_email.body,
                            headers=self.parsed_email.headers_json,
                            date_field=str(self.parsed_email.date),
                            from_field=self.parsed_email.headers['Return-Path'],
                            subject_field=self.parsed_email.headers['Subject'],
                            to_field=kvdefault(self.parsed_email.headers, 'To', None))
        mail = await db.readEMail(self.email_id)
        self.logger.log(f"message {mail.id} processed from {mail.from_field}")
