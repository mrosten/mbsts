import functools

import asyncssh

import example_sprout_apps

from example_sprout_apps.mailsync import input_output as io
from example_sprout_apps.mailsync.jobs.sync_mail import sync_mail
from example_sprout_apps.smssync.jobs.sync_sms import sync_sms

from sprout.app import SproutApp
from sprout.configuration import SproutConfiguration
from sprout.database import initialize_database, run_database_updates
from sprout.server.ssh import CustomSSHServerImpl, handle_ssh_conn
from example_sprout_apps.mailsync.data import classes as mail_classes

from sprout.runtime import scheduler
from example_sprout_apps.smssync.data import classes as sms_classes



async def test(thing):
    print(thing)


class SMSSyncApp(SproutApp):
    def __init__(self):
        self.config = SproutConfiguration().config
        super().__init__()

    async def start(self):
        sprout_context = "SMSSyncApp:start"

        await io.setup()
        await initialize_database(self.config, self.config.db.sqlite.storage_file, sms_classes)
        await run_database_updates(yaml_file=self.config.db.sqlite.updates_file)
        await scheduler.SchedulerState.setup()
        # await scheduler.setup_scheduler(self.config.cron.schedule, example_sprout_apps.mailsync.jobs.sync_mail)
        await scheduler.setup_scheduler(self.config.cron.schedule, example_sprout_apps.smssync.jobs.sync_sms)


