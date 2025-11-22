from modules.ui.controllers.BaseController import BaseController
from modules.ui.models.VideoModel import VideoModel
from modules.ui.utils.WorkerPool import WorkerPool

from PySide6.QtCore import QCoreApplication as QCA
from PySide6.QtCore import Slot


class VideoController(BaseController):
    def __init__(self, loader, parent=None):
        super().__init__(loader, "modules/ui/views/windows/video.ui", name=None, parent=parent)

    ###FSM###

    def _connectUIBehavior(self):
        self._connectFileDialog(self.ui.linkListBtn, self.ui.linkListLed, is_dir=False, save=False,
                           title=QCA.translate("dialog_window", "Open Link list"),
                           filters=QCA.translate("filetype_filters",
                                                 "Text (*.txt)"))
        self._connectFileDialog(self.ui.singleVideo1Btn, self.ui.singleVideo1Led, is_dir=False, save=False,
                               title=QCA.translate("dialog_window", "Open Video"),
                               filters=QCA.translate("filetype_filters",
                                                     "Video (*.m4v, *.wmv, *.mp4, *.avi, *.webm)"))
        self._connectFileDialog(self.ui.singleVideo2Btn, self.ui.singleVideo2Led, is_dir=False, save=False,
                               title=QCA.translate("dialog_window", "Open Video"),
                               filters=QCA.translate("filetype_filters",
                                                     "Video (*.m4v, *.wmv, *.mp4, *.avi, *.webm)"))

        self._connectFileDialog(self.ui.directory1Btn, self.ui.directory1Led, is_dir=True, save=False,
                               title=QCA.translate("dialog_window", "Open Video directory"))
        self._connectFileDialog(self.ui.directory2Btn, self.ui.directory2Led, is_dir=True, save=False,
                               title=QCA.translate("dialog_window", "Open Video directory"))

        self._connectFileDialog(self.ui.output1Btn, self.ui.output1Led, is_dir=True, save=True,
                               title=QCA.translate("dialog_window", "Save Video directory"))
        self._connectFileDialog(self.ui.output2Btn, self.ui.output2Led, is_dir=True, save=True,
                               title=QCA.translate("dialog_window", "Save Video directory"))
        self._connectFileDialog(self.ui.output3Btn, self.ui.output3Led, is_dir=True, save=True,
                               title=QCA.translate("dialog_window", "Save Video directory"))

        self._connect(self.ui.infoBtn.clicked, lambda: self._openUrl("https://github.com/yt-dlp/yt-dlp?tab=readme-ov-file#usage-and-options"))

        state_ui_connections = {
            "clips.single_video": "singleVideo1Led",
            "clips.range_start": "timeRangeStart1Led",
            "clips.range_end": "timeRangeStop1Led",
            "clips.directory": "directory1Led",
            "clips.output": "output1Led",
            "clips.output_to_subdirectories": "outputSubdirectories1Cbx",
            "clips.split_at_cuts": "splitCutsCbx",
            "clips.max_length": "maxLengthSbx",
            "clips.fps": "fpsSbx",
            "clips.remove_borders": "removeBorders1Cbx",
            "clips.crop_variation": "cropVariation1Sbx",

            "images.single_video": "singleVideo2Led",
            "images.range_start": "timeRangeStart2",
            "images.range_end": "timeRangeStop2",
            "images.directory": "directory2Led",
            "images.output": "output2Led",
            "images.output_to_subdirectories": "outputSubdirectories2Cbx",
            "images.capture_rate": "imagesSecSbx",
            "images.blur_removal": "blurRemovalSbx",
            "images.remove_borders": "removeBorders2Cbx",
            "images.crop_variation": "cropVariation2Sbx",

            "download.single_link": "singleLinkLed",
            "download.link_list": "linkListLed",
            "download.output": "output3Led",
            "download.additional_args": "additionalArgsTed",
        }
        self._connectStateUI(state_ui_connections, VideoModel.instance(), update_after_connect=True)


        self._connect(self.ui.extractSingle1Btn.clicked, self.__startClipSingle())
        self._connect(self.ui.extractDirectory1Btn.clicked, self.__startClipDirectory())
        self._connect(self.ui.extractSingle2Btn.clicked, self.__startImageSingle())
        self._connect(self.ui.extractDirectory2Btn.clicked, self.__startImageDirectory())
        self._connect(self.ui.downloadLinkBtn.clicked, self.__startDownloadLink())
        self._connect(self.ui.downloadListBtn.clicked, self.__startDownloadList())

        self.__enableButtons(True)()


    ###Reactions###

    def __enableButtons(self, enabled):
        @Slot()
        def f():
            self.ui.extractSingle1Btn.setEnabled(enabled)
            self.ui.extractDirectory1Btn.setEnabled(enabled)
            self.ui.extractSingle2Btn.setEnabled(enabled)
            self.ui.extractDirectory2Btn.setEnabled(enabled)
            self.ui.downloadLinkBtn.setEnabled(enabled)
            self.ui.downloadListBtn.setEnabled(enabled)
        return f

    def __startClipSingle(self):
        @Slot()
        def f():
            worker, name = WorkerPool.instance().createNamed(self.__extractClip(), "video_processing", batch_mode=False)
            if worker is not None:
                worker.connectCallbacks(init_fn=self.__enableButtons(False), result_fn=None, finished_fn=self.__enableButtons(True),
                               errored_fn=self.__enableButtons(True), aborted_fn=self.__enableButtons(True))
                WorkerPool.instance().start(name)
        return f

    def __startClipDirectory(self):
        @Slot()
        def f():
            worker, name = WorkerPool.instance().createNamed(self.__extractClip(), "video_processing", batch_mode=True)
            if worker is not None:
                worker.connectCallbacks(init_fn=self.__enableButtons(False), result_fn=None, finished_fn=self.__enableButtons(True),
                               errored_fn=self.__enableButtons(True), aborted_fn=self.__enableButtons(True))
                WorkerPool.instance().start(name)
        return f

    def __startImageSingle(self):
        @Slot()
        def f():
            worker, name = WorkerPool.instance().createNamed(self.__extractImage(), "video_processing", batch_mode=False)
            if worker is not None:
                worker.connectCallbacks(init_fn=self.__enableButtons(False), result_fn=None, finished_fn=self.__enableButtons(True),
                               errored_fn=self.__enableButtons(True), aborted_fn=self.__enableButtons(True))
                WorkerPool.instance().start(name)
        return f

    def __startImageDirectory(self):
        @Slot()
        def f():
            worker, name = WorkerPool.instance().createNamed(self.__extractImage(), "video_processing", batch_mode=True)
            if worker is not None:
                worker.connectCallbacks(init_fn=self.__enableButtons(False), result_fn=None, finished_fn=self.__enableButtons(True),
                               errored_fn=self.__enableButtons(True), aborted_fn=self.__enableButtons(True))
                WorkerPool.instance().start(name)
        return f

    def __startDownloadLink(self):
        @Slot()
        def f():
            worker, name = WorkerPool.instance().createNamed(self.__download(), "video_processing", batch_mode=False)
            if worker is not None:
                worker.connectCallbacks(init_fn=self.__enableButtons(False), result_fn=None, finished_fn=self.__enableButtons(True),
                               errored_fn=self.__enableButtons(True), aborted_fn=self.__enableButtons(True))
                WorkerPool.instance().start(name)
        return f

    def __startDownloadList(self):
        @Slot()
        def f():
            worker, name = WorkerPool.instance().createNamed(self.__download(), "video_processing", batch_mode=True)
            if worker is not None:
                worker.connectCallbacks(init_fn=self.__enableButtons(False), result_fn=None, finished_fn=self.__enableButtons(True),
                               errored_fn=self.__enableButtons(True), aborted_fn=self.__enableButtons(True))
                WorkerPool.instance().start(name)
        return f

    ###Utils###

    def __extractClip(self):
        def f(batch_mode):
            return VideoModel.instance().extract_clips_multi(batch_mode)

        return f

    def __extractImage(self):
        def f(batch_mode):
            return VideoModel.instance().extract_images_multi(batch_mode)

        return f


    def __download(self):
        def f(batch_mode):
            return VideoModel.instance().download_multi(batch_mode)

        return f
