import copy
import json
import os

from modules.ui.models.SingletonConfigModel import SingletonConfigModel
from modules.ui.models.StateModel import StateModel
from modules.util import path_util
from modules.util.config.SampleConfig import SampleConfig
from modules.util.path_util import write_json_atomic


class SampleModel(SingletonConfigModel):
    def __init__(self):
        self.config = []

    def __len__(self):
        return len(self.config)

    @SingletonConfigModel.atomic
    def get_default_sample(self):
        return SampleConfig.default_values().to_dict()

    @SingletonConfigModel.atomic
    def create_new_sample(self):
        smp_cfg = SampleConfig.default_values()
        self.config.append(smp_cfg)

    @SingletonConfigModel.atomic
    def clone_sample(self, idx):
        new_element = copy.deepcopy(self.config[idx])
        self.config.append(new_element)

    @SingletonConfigModel.atomic
    def delete_sample(self, idx):
        self.config.pop(idx)

    @SingletonConfigModel.atomic
    def toggle_samples(self):
        some_enabled = self.some_samples_enabled()

        for smp in self.config:
            smp.enabled = not some_enabled

    @SingletonConfigModel.atomic
    def some_samples_enabled(self):
        out = False
        for smp in self.config:
            out |= smp.enabled
        return out

    @SingletonConfigModel.atomic
    def save_config(self, path="training_samples"):
        if not os.path.exists(path):
            os.mkdir(path)

        config_path = StateModel.instance().getState("sample_definition_file_name")
        write_json_atomic(config_path, [element.to_dict() for element in self.config])

    @SingletonConfigModel.atomic
    def load_config(self, filename, path="training_samples"):
        if not os.path.exists(path):
            os.mkdir(path)

        if filename == "":
            filename = "samples"

        config_file = path_util.canonical_join(path, f"{filename}.json")
        StateModel.instance().setState("sample_definition_file_name", config_file)

        self.config = []

        if os.path.exists(config_file):
            with open(config_file, "r") as f:
                loaded_config_json = json.load(f)
                for element_json in loaded_config_json:
                    element = SampleConfig.default_values().from_dict(element_json)
                    self.config.append(element)
