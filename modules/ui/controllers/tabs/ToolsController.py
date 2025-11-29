from modules.ui.controllers.BaseController import BaseController
from modules.ui.controllers.windows.BulkCaptionController import BulkCaptionController
from modules.ui.controllers.windows.BulkImageController import BulkImageController
from modules.ui.controllers.windows.CaptionController import CaptionController
from modules.ui.controllers.windows.ConvertController import ConvertController
from modules.ui.controllers.windows.DatasetController import DatasetController
from modules.ui.controllers.windows.MaskController import MaskController
from modules.ui.controllers.windows.ProfileController import ProfileController
from modules.ui.controllers.windows.SampleController import SampleController
from modules.ui.controllers.windows.VideoController import VideoController

from PySide6.QtCore import QCoreApplication as QCA


class ToolsController(BaseController):
    def __init__(self, loader, parent=None):
        super().__init__(loader, "modules/ui/views/tabs/tools.ui", name=QCA.translate("main_window_tabs", "Tools"), parent=parent)

    ###FSM###

    def _setup(self):

        self.children = {"dataset": DatasetController(self.loader, parent=None),
                         "caption": CaptionController(self.loader, parent=None),
                         "mask": MaskController(self.loader, parent=None),
                         "image": BulkImageController(self.loader, parent=None),
                         "bulk_caption": BulkCaptionController(self.loader, parent=None),
                        "video": VideoController(self.loader, parent=None),
                        "convert": ConvertController(self.loader, parent=None),
                        "sample": SampleController(self.loader, parent=None),
                        "profile": ProfileController(self.loader, parent=None)}

    def _connectUIBehavior(self):
        self._connect(self.ui.datasetBtn.clicked, lambda: self.__open("dataset"))
        self._connect(self.ui.imageBtn.clicked, lambda: self.__open("image"))
        self._connect(self.ui.maskBtn.clicked, lambda: self.__open("mask"))
        self._connect(self.ui.captionBtn.clicked, lambda: self.__open("caption"))
        self._connect(self.ui.bulkCaptionBtn.clicked, lambda: self.__open("bulk_caption"))
        self._connect(self.ui.videoBtn.clicked, lambda: self.__open("video"))
        self._connect(self.ui.convertBtn.clicked, lambda: self.__open("convert"))
        self._connect(self.ui.samplingBtn.clicked, lambda: self.__open("sample"))
        self._connect(self.ui.profilingBtn.clicked, lambda: self.__open("profile"))

    ###Utils###

    def __open(self, window):
        if self.children[window].ui.isHidden():
            self._openWindow(self.children[window], fixed_size=window != "dataset")
        else:
            self.children[window].ui.activateWindow()
