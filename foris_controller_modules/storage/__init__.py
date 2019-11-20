import logging

from foris_controller.module_base import BaseModule
from foris_controller.handler_base import wrap_required_functions


class StorageModule(BaseModule):
    logger = logging.getLogger(__name__)

    def action_get_settings(self, data):
        return self.handler.get_settings()

    def action_get_state(self, data):
        return self.handler.get_state()

    def action_update_srv(self, data):
        return self.handler.update_srv(data)

    def action_get_drives(self, data):
        return self.handler.get_drives()

    def action_prepare_srv_drive(self, data):
        return self.handler.prepare_srv_drive(data)

    def action_configure_nextcloud(self, data):
        return self.handler.configure_nextcloud(data)


@wrap_required_functions(
    [
        "get_settings",
        "get_state",
        "configure_nextcloud",
        "update_srv",
        "get_drives",
        "prepare_srv_drive",
    ]
)
class Handler(object):
    pass
