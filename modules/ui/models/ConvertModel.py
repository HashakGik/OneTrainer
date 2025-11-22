import traceback
from uuid import uuid4

from modules.ui.models.SingletonConfigModel import SingletonConfigModel
from modules.util import create
from modules.util.args.ConvertModelArgs import ConvertModelArgs
from modules.util.enum.TrainingMethod import TrainingMethod
from modules.util.ModelNames import EmbeddingName, ModelNames
from modules.util.torch_util import torch_gc


class ConvertModel(SingletonConfigModel):
    def __init__(self):
        self.config = ConvertModelArgs.default_values()

    def convert_model(self):
        try:
            model_loader = create.create_model_loader(
                model_type=self.getState("model_type"),
                training_method=self.getState("training_method")
            )
            model_saver = create.create_model_saver(
                model_type=self.getState("model_type"),
                training_method=self.getState("training_method")
            )

            print("Loading model " + self.getState("input_name"))
            if self.getState("training_method") in [TrainingMethod.FINE_TUNE]:
                model = model_loader.load(
                    model_type=self.getState("model_type"),
                    model_names=ModelNames(
                        base_model=self.getState("input_name"),
                    ),
                    weight_dtypes=self.config.weight_dtypes(),
                )
            elif self.getState("training_method") in [TrainingMethod.LORA, TrainingMethod.EMBEDDING]:
                model = model_loader.load(
                    model_type=self.getState("model_type"),
                    model_names=ModelNames(
                        lora=self.getState("input_name"),
                        embedding=EmbeddingName(str(uuid4()), self.getState("input_name")),
                    ),
                    weight_dtypes=self.config.weight_dtypes(),
                )
            else:
                raise Exception("could not load model: " + self.getState("input_name"))

            print("Saving model " + self.getState("output_model_destination"))
            model_saver.save(
                model=model,
                model_type=self.getState("model_type"),
                output_model_format=self.getState("output_model_format"),
                output_model_destination=self.getState("output_model_destination"),
                dtype=self.getState("output_dtype").torch_dtype(),
            )
            print("Model converted")
        except Exception:
            traceback.print_exc()
        finally:
            torch_gc()
