import logging

from foris_controller.handler_base import BaseOpenwrtHandler
from foris_controller.utils import logger_wrapper

from foris_controller_backends.storage import SettingsUci, DriveManager, SoftwareManager

from .. import Handler

logger = logging.getLogger(__name__)


class OpenwrtStorageHandler(Handler, BaseOpenwrtHandler):

    settings = SettingsUci()
    drives = DriveManager()
    software = SoftwareManager()

    @logger_wrapper(logger)
    def get_settings(self):
        return self.settings.get_srv()

    @logger_wrapper(logger)
    def get_state(self):
        return self.settings.get_state()

    @logger_wrapper(logger)
    def get_drives(self):
        return self.drives.get_drives()

    @logger_wrapper(logger)
    def update_srv(self, srv):
        return self.settings.update_srv(srv)

    @logger_wrapper(logger)
    def update_raid(self, srv):
        return self.settings.update_raid(srv)

    @logger_wrapper(logger)
    def prepare_srv_drive(self, srv):
        return self.drives.prepare_srv_drive(srv)

    @logger_wrapper(logger)
    def update_settings(self, srv):
        return self.settings.update_srv(srv)

    @logger_wrapper(logger)
    def configure_nextcloud(self, credentials):
        return self.software.configure_nextcloud(credentials)
