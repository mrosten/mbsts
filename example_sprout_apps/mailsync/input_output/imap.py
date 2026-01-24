from mailparser import MailParser
from sprout.configuration import SproutConfiguration
from sprout.log.logger import Logger
from sprout.runtime.instrumented_object import InstrumentedIO

import mailparser
import imaplib


class ImapClient(InstrumentedIO):
    def __init__(self):
        self.logger = Logger(ImapClient.__name__)
        self.config = SproutConfiguration().config
        self.imap = imaplib.IMAP4_SSL(self.config.io.imap.server, port=self.config.io.imap.port)

        self.imap.login(self.config.io.imap.user, self.config.io.imap.password)

    def get_message(self, mailbox, message_id):
        sprout_context = f"{message_id}"

        status, data = self.imap.select(mailbox)
        self.logger.log("will fetch message")
        status, msgstruct = self.imap.fetch(message_id, "(RFC822)")
        self.logger.log("done fetch message")
        a, b = msgstruct
        rfc822str = a[1].decode('utf-8')
        return rfc822str

    def message_count(self, mailbox):
        status, data = self.imap.select(mailbox)
        return int(data[0])

    def list_messages(self, mailbox, directory=None, filter=None, limit=None, start=None):
        pass

    def parse_message(self, raw_mail: str) -> MailParser:
        return mailparser.parse_from_string(raw_mail)
