import functools

import asyncssh

import example_sprout_apps

from example_sprout_apps.mailsync import input_output as io
from example_sprout_apps.mailsync.jobs.sync_mail import sync_mail
from sprout.app import SproutApp
from sprout.configuration import SproutConfiguration
from sprout.database import initialize_database, run_database_updates
from sprout.server.ssh import CustomSSHServerImpl, handle_ssh_conn
from example_sprout_apps.mailsync.data import classes as mail_classes


async def start_ssh_server():
    await asyncssh.create_server(CustomSSHServerImpl, '', 8022, server_host_keys=['../../id_ed25519'],
                                 process_factory=handle_ssh_conn)


from sprout.runtime import scheduler

from example_sprout_apps.mailsync.data import classes as mail_classes


async def test(thing):
    print(thing)


class MailSyncApp(SproutApp):
    def __init__(self):
        self.config = SproutConfiguration().config
        super().__init__()

    async def start(self):
        sprout_context = "MailSyncApp:start"

        await io.setup()
        await initialize_database(self.config, self.config.db.sqlite.storage_file, mail_classes)
        await run_database_updates(yaml_file=self.config.db.sqlite.updates_file)
        await scheduler.SchedulerState.setup()
        await scheduler.setup_scheduler(self.config.cron.schedule, example_sprout_apps.mailsync.jobs.sync_mail)
        await start_ssh_server()


