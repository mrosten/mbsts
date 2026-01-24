from sprout.configuration import SproutConfiguration
from sprout.log.logger import Logger
from sprout.runtime.instrumented_object import InstrumentedIO

from twilio.rest import Client


class TwilioClient(InstrumentedIO):
    def __init__(self, account_sid, auth_token):
        self.logger = Logger(TwilioClient.__name__)
        self.config = SproutConfiguration().config

        self.client = Client(account_sid, auth_token)

    def getMessages(self, num, n=0, inbound=None):
        messages = self.client.messages.list(limit=n, to=num, from_=inbound)
        return messages
