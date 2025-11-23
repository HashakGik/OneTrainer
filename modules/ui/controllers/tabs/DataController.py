from modules.ui.controllers.BaseController import BaseController

from PySide6.QtCore import QCoreApplication as QCA
from PySide6.QtCore import Slot


class DataController(BaseController):
    state_ui_connections = {
        "aspect_ratio_bucketing": "aspectBucketingCbx",
        "latent_caching": "latentCachingCbx",
        "clear_cache_before_training": "clearCacheCbx"
    }

    def __init__(self, loader, parent=None):
        super().__init__(loader, "modules/ui/views/tabs/data.ui", name=QCA.translate("main_window_tabs", "Data"), parent=parent)

    ###FSM###

    def _connectUIBehavior(self):
        self._connect(self.ui.latentCachingCbx.toggled, self.__updateCaching(), update_after_connect=True, initial_args=[self.ui.latentCachingCbx.isChecked()])

    ###Reactions###

    def __updateCaching(self):
        @Slot(bool)
        def f(enabled):
            self.ui.clearCacheCbx.setEnabled(enabled)
        return f
