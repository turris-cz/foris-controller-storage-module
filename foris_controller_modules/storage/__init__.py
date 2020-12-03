import logging

from foris_controller.module_base import BaseModule
from foris_controller.handler_base import wrap_required_functions


class StorageModule(BaseModule):
    logger = logging.getLogger(__name__)

    def action_get_settings(self, data):
        """ Get storage settings

        Deprecated function, kept for compatibility with Foris
        Use get_state() in new code
        """
        return self.handler.get_settings()

    def action_get_state(self, data):
        """ Get storage state """
        res = self.handler.get_state()
        del res["old_uuid"]
        return res

    def action_update_srv(self, data):
        """ Update settings for /srv mountpoint """
        return self.handler.update_srv(data)

    def action_get_drives(self, data):
        return self.handler.get_drives()

    def action_prepare_srv_drive(self, data):
        return self.handler.prepare_srv_drive(data)

    def action_update_settings(self, data):
        return self.handler.update_settings(data)


@wrap_required_functions(
    [
        "get_settings",
        "get_state",
        "update_srv",
        "get_drives",
        "prepare_srv_drive",
        "update_settings"
    ]
)
class Handler(object):
    pass
