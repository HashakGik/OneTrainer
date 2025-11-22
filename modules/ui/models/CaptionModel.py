from modules.module.Blip2Model import Blip2Model
from modules.module.BlipModel import BlipModel
from modules.module.WDModel import WDModel
from modules.ui.models.SingletonConfigModel import SingletonConfigModel
from modules.util.enum.GenerateCaptionsModel import GenerateCaptionsAction, GenerateCaptionsModel
from modules.util.torch_util import default_device, torch_gc

import torch


class CaptionModel(SingletonConfigModel):
    def __init__(self):
        self.config = {
            "model": GenerateCaptionsModel.BLIP,
            "path": "",
            "caption": "",
            "prefix": "",
            "postfix": "",
            "mode": GenerateCaptionsAction.REPLACE,
            "include_subdirectories": False,
        }

        self.captioning_model = None

    def create_captions(self, progress_fn=None):
        self.__load_captioning_model(self.getState("model"))

        self.captioning_model.caption_folder(
            sample_dir=self.getState("path"),
            initial_caption=self.getState("caption"),
            caption_prefix=self.getState("prefix"),
            caption_postfix=self.getState("postfix"),
            mode=str(self.getState("mode")).lower(),
            include_subdirectories=self.getState("include_subdirectories"),
            progress_callback=self.__wrap_progress(progress_fn),
        )

    def __load_captioning_model(self, model):
        self.captioning_model = None

        if model == GenerateCaptionsModel.BLIP:
            if self.captioning_model is None or not isinstance(self.captioning_model, BlipModel):
                print("loading Blip model, this may take a while")
                self.release_model()
                self.captioning_model = BlipModel(default_device, torch.float16)
        elif model == GenerateCaptionsModel.BLIP2:
            if self.captioning_model is None or not isinstance(self.captioning_model, Blip2Model):
                print("loading Blip2 model, this may take a while")
                self.release_model()
                self.captioning_model = Blip2Model(default_device, torch.float16)
        elif model == GenerateCaptionsModel.WD14_VIT_2:
            if self.captioning_model is None or not isinstance(self.captioning_model, WDModel):
                print("loading WD14_VIT_v2 model, this may take a while")
                self.release_model()
                self.captioning_model = WDModel(default_device, torch.float16)

    def __wrap_progress(self, fn):
        def f(value, max_value):
            if fn is not None:
                fn({"value": value, "max_value": max_value})
        return f

    def release_model(self):
        """Release all models from VRAM"""
        freed = False
        if self.captioning_model is not None:
            self.captioning_model = None
            freed = True
        if freed:
            torch_gc()
