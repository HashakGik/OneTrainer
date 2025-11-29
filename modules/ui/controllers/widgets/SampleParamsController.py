from modules.ui.controllers.BaseController import BaseController
from modules.util.enum.NoiseScheduler import NoiseScheduler

import PySide6.QtGui as QtGui
import PySide6.QtWidgets as QtW
from PySide6.QtCore import QCoreApplication as QCA
from PySide6.QtCore import QObject, Slot


class SampleParamsController(BaseController):
    idx = 0
    def __init__(self, loader, model_instance, read_signal=None, write_signal=None, parent=None):
        self.model_instance = model_instance
        self.read_signal = read_signal
        self.write_signal = write_signal
        self.idx = None

        super().__init__(loader, "modules/ui/views/widgets/sampling_params.ui", invalidate_once=False, name=None, parent=parent)

    ###FSM###

    def _connectUIBehavior(self):
        self._connectFileDialog(self.ui.imagePathBtn, self.ui.imagePathLed, is_dir=False, save=False,
                            title=QCA.translate("dialog_window", "Open Base Image"),
                               filters=QCA.translate("filetype_filters", "Image (*.jpg *.jpeg *.tif *.png *.webp)"))
        self._connectFileDialog(self.ui.maskPathBtn, self.ui.maskPathLed, is_dir=False, save=False,
                               title=QCA.translate("dialog_window", "Open Mask Image"),
                               filters=QCA.translate("filetype_filters",
                                                     "Image (*.jpg *.jpeg *.tif *.png *.webp)"))

        self.dynamic_state_ui_connections = {
            "prompt": "promptLed",
            "negative_prompt": "negativePromptLed",
            "width": "widthSbx",
            "height": "heightSbx",
            "frames": "framesSbx",
            "length": "lengthSbx",
            "seed": "seedLed",
            "random_seed": "randomSeedCbx",
            "cfg_scale": "cfgSbx",
            "diffusion_steps": "stepsSbx",
            "noise_scheduler": "samplerCmb",
            "sample_inpainting": "inpaintingCbx",
            "base_image_path": "imagePathLed",
            "mask_image_path": "maskPathLed",
        }

        # Since data should be read/write based on parent widget's signals, operations are performed in bulk, rather than connecting each ui element individually.
        if self.read_signal is not None: # If we have a dynamic connection, we connect the signal to the update.
            self._connect(self.read_signal, self.__readControls())
        if self.write_signal is not None: # If we have a dynamic connection, we connect the signal to the update.
            self._connect(self.write_signal, self.__writeControls())

    def _loadPresets(self):
        for e in NoiseScheduler.enabled_values():
            self.ui.samplerCmb.addItem(e.pretty_print(), userData=e)

    def _connectInputValidation(self):
        # We use regular expressions, instead of QIntValidator, to avoid hitting the maximum value.
        self.ui.seedLed.setValidator(QtGui.QRegularExpressionValidator(r"-1|0|[1-9]\d*", self.ui))

    ###Reactions###

    def __readControls(self):
        def f(idx=None):
            self.idx = idx
            if idx is None:
                data = self.model_instance.bulk_read(*self.dynamic_state_ui_connections, as_dict=True)
            else:
                data = self.model_instance.bulk_read(*[f"{self.idx}.{k}" for k in self.dynamic_state_ui_connections], as_dict=True)

            for k, v in self.dynamic_state_ui_connections.items():
                if self.idx is not None:
                    k = f"{self.idx}.{k}"

                wdg = self.ui.findChild(QObject, v)
                if data[k] is not None:
                    if isinstance(wdg, QtW.QCheckBox):
                        wdg.setChecked(data[k])
                    elif isinstance(wdg, QtW.QComboBox):
                        i = wdg.findData(data[k])
                        if i != -1:
                            wdg.setCurrentIndex(i)
                    elif isinstance(wdg, (QtW.QSpinBox, QtW.QDoubleSpinBox)):
                        wdg.setValue(float(data[k]))
                    elif isinstance(wdg, QtW.QLineEdit):
                        wdg.setText(str(data[k]))

        return f

    def __writeControls(self):
        @Slot()
        def f():
            data = {}
            for k, v in self.dynamic_state_ui_connections.items():
                if self.idx is not None:
                    k = f"{self.idx}.{k}"

                wdg = self.ui.findChild(QObject, v)
                if isinstance(wdg, QtW.QCheckBox):
                    data[k] = wdg.isChecked()
                elif isinstance(wdg, QtW.QComboBox):
                    data[k] = wdg.currentData()
                elif isinstance(wdg, (QtW.QSpinBox, QtW.QDoubleSpinBox)):
                    data[k] = wdg.value()
                elif isinstance(wdg, QtW.QLineEdit):
                    data[k] = wdg.text()


            self.model_instance.bulk_write(data)
        return f
