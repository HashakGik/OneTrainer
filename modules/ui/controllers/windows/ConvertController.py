from modules.ui.controllers.BaseController import BaseController
from modules.ui.models.ConvertModel import ConvertModel
from modules.ui.utils.WorkerPool import WorkerPool
from modules.util.enum.DataType import DataType
from modules.util.enum.ModelFormat import ModelFormat
from modules.util.enum.ModelType import ModelType
from modules.util.enum.TrainingMethod import TrainingMethod

from PySide6.QtCore import QCoreApplication as QCA
from PySide6.QtCore import Slot


class ConvertController(BaseController):
    def __init__(self, loader, parent=None):
        super().__init__(loader, "modules/ui/views/windows/convert.ui", name=None, parent=parent)

    ###FSM###

    def _connectUIBehavior(self):
        self._connectFileDialog(self.ui.inputBtn, self.ui.inputLed, is_dir=False, save=False,
                               title=QCA.translate("dialog_window", "Open Input model"),
                               filters=QCA.translate("filetype_filters", "Safetensors (*.safetensors);;Diffusers (model_index.json);;Checkpoints (*.ckpt, *.pt, *.bin);;All Files (*.*)"))
        self._connectFileDialog(self.ui.outputBtn, self.ui.outputLed, is_dir=False, save=True,
                               title=QCA.translate("dialog_window", "Save Output model"),
                               filters=QCA.translate("filetype_filters", "Safetensors (*.safetensors);;Diffusers (model_index.json)"))

        state_ui_connections = {
            "model_type": "modelTypeCmb",
            "training_method": "trainingMethodCmb",
            "input_name": "inputLed",
            "output_model_destination": "outputLed",
            "output_model_format": "outputFormatCmb",
            "output_dtype": "outputDTypeCmb",
        }

        self._connectStateUI(state_ui_connections, ConvertModel.instance(), update_after_connect=True)

        self._connect(self.ui.convertBtn.clicked, self.__startConvert())

    def _loadPresets(self):
        for e in ModelType.enabled_values(context="convert_window"):
            self.ui.modelTypeCmb.addItem(e.pretty_print(), userData=e)

        for e in TrainingMethod.enabled_values(context="convert_window"):
            self.ui.trainingMethodCmb.addItem(e.pretty_print(), userData=e)

        for e in DataType.enabled_values(context="convert_window"):
            self.ui.outputDTypeCmb.addItem(e.pretty_print(), userData=e)

        for e in ModelFormat.enabled_values(context="convert_window"):
            self.ui.outputFormatCmb.addItem(e.pretty_print(), userData=e)


    ###Reactions###

    def __startConvert(self):
        @Slot()
        def f():
            worker, name = WorkerPool.instance().createNamed(self.__convert(), "convert_model")
            if worker is not None:
                worker.connectCallbacks(init_fn=self.__enableButton(False), result_fn=None, finished_fn=self.__enableButton(True),
                               errored_fn=self.__enableButton(True), aborted_fn=self.__enableButton(True))
                WorkerPool.instance().start(name)
        return f

    def __enableButton(self, enabled):
        @Slot()
        def f():
            self.ui.convertBtn.setEnabled(enabled)
        return f

    ###Utils###

    def __convert(self):
        def f():
            return ConvertModel.instance().convert_model()

        return f
