import copy
import fractions
import json
import math
import os
import pathlib
import platform
import random
import threading
import time

from modules.ui.models.SingletonConfigModel import SingletonConfigModel
from modules.ui.models.StateModel import StateModel
from modules.util import concept_stats, path_util
from modules.util.config.ConceptConfig import ConceptConfig
from modules.util.enum.ConceptType import ConceptType
from modules.util.image_util import load_image
from modules.util.path_util import write_json_atomic

from mgds.LoadingPipeline import LoadingPipeline
from mgds.OutputPipelineModule import OutputPipelineModule
from mgds.PipelineModule import PipelineModule
from mgds.pipelineModules.CapitalizeTags import CapitalizeTags
from mgds.pipelineModules.DropTags import DropTags
from mgds.pipelineModules.RandomBrightness import RandomBrightness
from mgds.pipelineModules.RandomCircularMaskShrink import (
    RandomCircularMaskShrink,
)
from mgds.pipelineModules.RandomContrast import RandomContrast
from mgds.pipelineModules.RandomFlip import RandomFlip
from mgds.pipelineModules.RandomHue import RandomHue
from mgds.pipelineModules.RandomMaskRotateCrop import RandomMaskRotateCrop
from mgds.pipelineModules.RandomRotate import RandomRotate
from mgds.pipelineModules.RandomSaturation import RandomSaturation
from mgds.pipelineModules.ShuffleTags import ShuffleTags
from mgds.pipelineModuleTypes.RandomAccessPipelineModule import (
    RandomAccessPipelineModule,
)

import torch
from torchvision.transforms import functional

import huggingface_hub
from PIL import Image


class InputPipelineModule(
    PipelineModule,
    RandomAccessPipelineModule,
):
    def __init__(self, data: dict):
        super().__init__()
        self.data = data

    def length(self) -> int:
        return 1

    def get_inputs(self) -> list[str]:
        return []

    def get_outputs(self) -> list[str]:
        return list(self.data.keys())

    def get_item(self, variation: int, index: int, requested_name: str = None) -> dict:
        return self.data


class ConceptModel(SingletonConfigModel):
    def __init__(self):
        self.config = []
        self.cancel_scan_flag = threading.Event()

    @SingletonConfigModel.atomic
    def __len__(self):
        return len(self.config)

    @SingletonConfigModel.atomic
    def get_random_seed(self):
        return ConceptConfig.default_values().seed

    @SingletonConfigModel.atomic
    def get_concept_name(self, idx):
        name = self.config[idx].name
        path = self.config[idx].path

        if name is not None and name != "":
            return name
        elif path is not None and path != "":
            return os.path.basename(path)
        else:
            return ""

    @SingletonConfigModel.atomic
    def toggle_concepts(self):
        some_enabled = self.some_concepts_enabled()

        for c in self.config:
            c.enabled = not some_enabled

    @SingletonConfigModel.atomic
    def get_filtered_concepts(self, query="", type=ConceptType.ALL, show_disabled=True):
        filtered_concepts = []
        for c in self.config:
            if show_disabled or c.enabled:
                if type == ConceptType.ALL or c.type == type:
                    if query == "" or query.strip() in c.name:
                        filtered_concepts.append(c)

        return filtered_concepts


    @SingletonConfigModel.atomic
    def some_concepts_enabled(self):
        out = False
        for c in self.config:
            out |= c.enabled
        return out

    @SingletonConfigModel.atomic
    def create_new_concept(self):
        con_cfg = ConceptConfig.default_values()
        self.config.append(con_cfg)

    @SingletonConfigModel.atomic
    def clone_concept(self, idx):
        new_element = copy.deepcopy(self.config[idx])
        self.config.append(new_element)

    @SingletonConfigModel.atomic
    def delete_concept(self, idx):
        self.config.pop(idx)

    @SingletonConfigModel.atomic
    def save_config(self, path="training_concepts"):
        if not os.path.exists(path):
            os.mkdir(path)

        config_path = StateModel.instance().getState("concept_file_name") # IMPORTANT! The mutex is shared because it is defined in the base class, this must be called before the lock!

        write_json_atomic(config_path, [element.to_dict() for element in self.config])

    @SingletonConfigModel.atomic
    def load_config(self, filename, path="training_concepts"):
        if not os.path.exists(path):
            os.mkdir(path)

        if filename == "":
            filename = "concepts"

        config_file = path_util.canonical_join(path, f"{filename}.json")
        StateModel.instance().setState("concept_file_name", config_file)

        self.config = []

        if os.path.exists(config_file):

            with open(config_file, "r") as f:
                loaded_config_json = json.load(f)
                for element_json in loaded_config_json:
                    element = ConceptConfig.default_values().from_dict(element_json)
                    self.config.append(element)

    @staticmethod
    def get_concept_path(path):
        if os.path.isdir(path):
            return path
        try:
            # don't download, only check if available locally:
            return huggingface_hub.snapshot_download(repo_id=path, repo_type="dataset", local_files_only=True)
        except Exception:
            return None

    @SingletonConfigModel.atomic
    def get_preview_icon(self, idx):
        preview_path = "resources/icons/icon.png"
        glob_pattern = "**/*.*" if self.getState(f"{idx}.include_subdirectories") else "*.*"

        concept_path = self.get_concept_path(self.getState(f"{idx}.path"))
        if concept_path:
            for path in pathlib.Path(concept_path).glob(glob_pattern):
                extension = os.path.splitext(path)[1]
                if path.is_file() and path_util.is_supported_image_extension(extension) \
                        and not path.name.endswith("-masklabel.png") and not path.name.endswith("-condlabel.png"):
                    preview_path = path_util.canonical_join(concept_path, path)
                    break

        image = load_image(preview_path, convert_mode="RGBA")
        size = min(image.width, image.height)
        image = image.crop((
            (image.width - size) // 2,
            (image.height - size) // 2,
            (image.width - size) // 2 + size,
            (image.height - size) // 2 + size,
        ))
        image = image.resize((150, 150), Image.Resampling.BILINEAR)
        return image

    def download_dataset(self, idx):
        # Exception handled by WorkerPool.
        huggingface_hub.login(token=StateModel.instance().getState("secrets.huggingface_token"), new_session=False)
        huggingface_hub.snapshot_download(repo_id=self.getState(f"{idx}.path"), repo_type="dataset")


    def get_preview_prompt(self, filename, show_augmentations):
        empty_msg = "[Empty prompt]"
        try:
            with open(filename, "r") as f:
                if show_augmentations:
                    lines = [line.strip() for line in f if line.strip()]
                    return random.choice(lines) if lines else empty_msg
                content = f.read().strip()
                return content if content else empty_msg
        except FileNotFoundError:
            return "File not found, please check the path"
        except IsADirectoryError:
            return "[Provided path is a directory, please correct the caption path]"
        except PermissionError:
            if platform.system() == "Windows":
                return "[Permission denied, please check the file permissions or Windows Defender settings]"
            else:
                return "[Permission denied, please check the file permissions]"
        except UnicodeDecodeError:
            return "[Invalid file encoding. This should not happen, please report this issue]"

    def get_concept_stats(self, idx, advanced_checks, wait_time=60):
        path = self.getState(f"{idx}.path")
        include_subdirectories = self.getState(f"{idx}.include_subdirectories")
        if not os.path.isdir(path):
            print(f"Unable to get statistics for invalid concept path: {path}")
            return
        start_time = time.perf_counter()
        self.cancel_scan_flag.clear()

        concept_path = self.get_concept_path(path)

        if not concept_path:
            print(f"Unable to get statistics for invalid concept path: {path}")
            return
        subfolders = [concept_path]

        stats_dict = concept_stats.init_concept_stats(advanced_checks)
        for path in subfolders:
            if self.cancel_scan_flag.is_set() or time.perf_counter() - start_time > wait_time:
                break
            stats_dict = concept_stats.folder_scan(path, stats_dict, advanced_checks, self.getState(idx), start_time, wait_time, self.cancel_scan_flag)
            if include_subdirectories and not self.cancel_scan_flag.is_set():     #add all subfolders of current directory to for loop
                subfolders.extend([f for f in os.scandir(path) if f.is_dir()])

            self.setState(f"{idx}.concept_stats", stats_dict)
        self.cancel_scan_flag.clear()

    def pretty_print_stats(self, idx):
        concept_stats = self.getState(f"{idx}.concept_stats")
        formatted_stats = {}

        if len(concept_stats) == 0:
            for k in ["file_size", "processing_time", "dir_count", "image_count", "image_count_mask", "image_count_caption",
                      "video_count", "video_count_caption", "mask_count", "mask_count_unpaired", "caption_count",
                      "unpaired_captions", "max_pixels", "avg_pixels", "min_pixels", "length_max", "length_avg",
                      "length_min", "fps_max", "fps_avg", "fps_min", "caption_max", "caption_avg", "caption_min", "small_bucket"
                      ]:
                formatted_stats[k] = "-"
            formatted_stats["aspect_buckets"] = {}
            return formatted_stats

        # File size.
        formatted_stats["file_size"] = str(int(concept_stats["file_size"] / 1048576)) + " MB"
        formatted_stats["processing_time"] = str(round(concept_stats["processing_time"], 2)) + " s"

        # Directory count.
        formatted_stats["dir_count"] = concept_stats["directory_count"]

        # Image count.
        formatted_stats["image_count"] = concept_stats["image_count"]
        formatted_stats["image_count_mask"] = concept_stats["image_with_mask_count"]
        formatted_stats["image_count_caption"] = concept_stats["image_with_caption_count"]

        # Video count.
        formatted_stats["video_count"] = concept_stats["video_count"]
        formatted_stats["video_count_caption"] = concept_stats["video_with_caption_count"]

        # Mask count.
        formatted_stats["mask_count"] = concept_stats["mask_count"]
        formatted_stats["mask_count_unpaired"] = concept_stats["unpaired_masks"]

        # Caption count.
        if concept_stats["subcaption_count"] > 0:
            formatted_stats["caption_count"] = f'{concept_stats["caption_count"]} ({concept_stats["subcaption_count"]})'
        else:
            formatted_stats["caption_count"] = concept_stats["caption_count"]
        formatted_stats["unpaired_captions"] = concept_stats["unpaired_captions"]

        # Resolution info.
        max_pixels = concept_stats["max_pixels"]
        avg_pixels = concept_stats["avg_pixels"]
        min_pixels = concept_stats["min_pixels"]

        if any(isinstance(x, str) for x in [max_pixels, avg_pixels, min_pixels]) or concept_stats["image_count"] == 0:  # will be str if adv stats were not taken
            formatted_stats["max_pixels"] = "-"
            formatted_stats["avg_pixels"] = "-"
            formatted_stats["min_pixels"] = "-"
        else:
            # formatted as (#pixels/1000000) MP, width x height, \n filename
            formatted_stats["max_pixels"] = f'{str(round(max_pixels[0] / 1000000, 2))} MP, {max_pixels[2]}\n{max_pixels[1]}'
            formatted_stats["avg_pixels"] = f'{str(round(avg_pixels / 1000000, 2))} MP, ~{int(math.sqrt(avg_pixels))}w x {int(math.sqrt(avg_pixels))}h'
            formatted_stats["min_pixels"] = f'{str(round(min_pixels[0] / 1000000, 2))} MP, {min_pixels[2]}\n{min_pixels[1]}'

        # Video length and fps info.
        max_length = concept_stats["max_length"]
        avg_length = concept_stats["avg_length"]
        min_length = concept_stats["min_length"]
        max_fps = concept_stats["max_fps"]
        avg_fps = concept_stats["avg_fps"]
        min_fps = concept_stats["min_fps"]

        if any(isinstance(x, str) for x in [max_length, avg_length, min_length]) or concept_stats["video_count"] == 0:  # will be str if adv stats were not taken
            formatted_stats["length_max"] = "-"
            formatted_stats["length_avg"] = "-"
            formatted_stats["length_min"] = "-"
            formatted_stats["fps_max"] = "-"
            formatted_stats["fps_avg"] = "-"
            formatted_stats["fps_min"] = "-"
        else:
            # formatted as (#frames) frames \n filename
            formatted_stats["length_max"] = f'{int(max_length[0])} frames\n{max_length[1]}'
            formatted_stats["length_avg"] = f'{int(avg_length)} frames'
            formatted_stats["length_min"] = f'{int(min_length[0])} frames\n{min_length[1]}'
            # formatted as (#fps) fps \n filename
            formatted_stats["fps_max"] = f'{int(max_fps[0])} fps\n{max_fps[1]}'
            formatted_stats["fps_avg"] = f'{int(avg_fps)} fps'
            formatted_stats["fps_min"] = f'{int(min_fps[0])} fps\n{min_fps[1]}'

        # Caption info.
        max_caption_length = concept_stats["max_caption_length"]
        avg_caption_length = concept_stats["avg_caption_length"]
        min_caption_length = concept_stats["min_caption_length"]

        if any(isinstance(x, str) for x in [max_caption_length, avg_caption_length, min_caption_length]) or concept_stats["caption_count"] == 0:  # will be str if adv stats were not taken
            formatted_stats["caption_max"] = "-"
            formatted_stats["caption_avg"] = "-"
            formatted_stats["caption_min"] = "-"
        else:
            # formatted as (#chars) chars, (#words) words, \n filename
            formatted_stats["caption_max"] = f'{max_caption_length[0]} chars, {max_caption_length[2]} words\n{max_caption_length[1]}'
            formatted_stats["caption_avg"] = f'{int(avg_caption_length[0])} chars, {int(avg_caption_length[1])} words'
            formatted_stats["caption_min"] = f'{min_caption_length[0]} chars, {min_caption_length[2]} words\n{min_caption_length[1]}'

        # Aspect bucketing.
        aspect_buckets = concept_stats["aspect_buckets"]
        formatted_stats["aspect_buckets"] = aspect_buckets

        if len(aspect_buckets) != 0 and max(
                val for val in aspect_buckets.values()) > 0:  # check aspect_bucket data exists and is not all zero
            min_val = min(val for val in aspect_buckets.values() if val > 0)  # smallest nonzero values
            if max(val for val in
                   aspect_buckets.values()) > min_val:  # check if any buckets larger than min_val exist - if all images are same aspect then there won't be
                min_val2 = min(
                    val for val in aspect_buckets.values() if (val > 0 and val != min_val))  # second smallest bucket
            else:
                min_val2 = min_val  # if no second smallest bucket exists set to min_val
            min_aspect_buckets = {key: val for key, val in aspect_buckets.items() if val in (min_val, min_val2)}
            min_bucket_str = ""
            for key, val in min_aspect_buckets.items():
                min_bucket_str += f'aspect {self.decimal_to_aspect_ratio(key)} : {val} img\n'
            min_bucket_str.strip()

            formatted_stats["small_bucket"] = min_bucket_str
        else:
            formatted_stats["small_bucket"] = "-"


        return formatted_stats



    def decimal_to_aspect_ratio(self, value):
        #find closest fraction to decimal aspect value and convert to a:b format
        aspect_fraction = fractions.Fraction(value).limit_denominator(16)
        aspect_string = f'{aspect_fraction.denominator}:{aspect_fraction.numerator}'
        return aspect_string

    @SingletonConfigModel.atomic
    def getImage(self, idx, image_id, show_augmentations=False):
        preview_image_path = "resources/icons/icon.png"
        file_index = -1
        glob_pattern = "**/*.*" if self.getState(f"{idx}.include_subdirectories") else "*.*"

        concept_path = self.get_concept_path(self.getState(f"{idx}.path"))
        if concept_path:
            for path in pathlib.Path(concept_path).glob(glob_pattern):
                extension = os.path.splitext(path)[1]
                if path.is_file() and path_util.is_supported_image_extension(extension) \
                        and not path.name.endswith("-masklabel.png") and not path.name.endswith("-condlabel.png"):
                    preview_image_path = path_util.canonical_join(concept_path, path)
                    file_index += 1
                    if file_index == image_id:
                        break

        image = load_image(preview_image_path, 'RGB')
        image_tensor = functional.to_tensor(image)

        splitext = os.path.splitext(preview_image_path)
        preview_mask_path = path_util.canonical_join(splitext[0] + "-masklabel.png")
        if not os.path.isfile(preview_mask_path):
            preview_mask_path = None

        if preview_mask_path:
            mask = Image.open(preview_mask_path).convert("L")
            mask_tensor = functional.to_tensor(mask)
        else:
            mask_tensor = torch.ones((1, image_tensor.shape[1], image_tensor.shape[2]))

        source = self.getState(f"{idx}.text.prompt_source")
        preview_p = pathlib.Path(preview_image_path)
        if source == "filename":
            prompt_output = preview_p.stem or "[Empty prompt]"
        else:
            file_map = {
                "sample": preview_p.with_suffix(".txt"),
                "concept": pathlib.Path(self.getState(f"{idx}.text.prompt_path")) if self.getState(f"{idx}.text.prompt_path") else None,
            }
            file_path = file_map.get(source)
            prompt_output = self.get_preview_prompt(str(file_path), show_augmentations) if file_path else "[Empty prompt]"

        modules = []
        if show_augmentations:
            input_module = InputPipelineModule({
                'true': True,
                'image': image_tensor,
                'mask': mask_tensor,
                'enable_random_flip': self.getState(f"{idx}.image.enable_random_flip"),
                'enable_fixed_flip': self.getState(f"{idx}.image.enable_fixed_flip"),
                'enable_random_rotate': self.getState(f"{idx}.image.enable_random_rotate"),
                'enable_fixed_rotate': self.getState(f"{idx}.image.enable_fixed_rotate"),
                'random_rotate_max_angle': self.getState(f"{idx}.image.random_rotate_max_angle"),
                'enable_random_brightness': self.getState(f"{idx}.image.enable_random_brightness"),
                'enable_fixed_brightness': self.getState(f"{idx}.image.enable_fixed_brightness"),
                'random_brightness_max_strength': self.getState(f"{idx}.image.random_brightness_max_strength"),
                'enable_random_contrast': self.getState(f"{idx}.image.enable_random_contrast"),
                'enable_fixed_contrast': self.getState(f"{idx}.image.enable_fixed_contrast"),
                'random_contrast_max_strength': self.getState(f"{idx}.image.random_contrast_max_strength"),
                'enable_random_saturation': self.getState(f"{idx}.image.enable_random_saturation"),
                'enable_fixed_saturation': self.getState(f"{idx}.image.enable_fixed_saturation"),
                'random_saturation_max_strength': self.getState(f"{idx}.image.random_saturation_max_strength"),
                'enable_random_hue': self.getState(f"{idx}.image.enable_random_hue"),
                'enable_fixed_hue': self.getState(f"{idx}.image.enable_fixed_hue"),
                'random_hue_max_strength': self.getState(f"{idx}.image.random_hue_max_strength"),
                'enable_random_circular_mask_shrink': self.getState(f"{idx}.image.enable_random_circular_mask_shrink"),
                'enable_random_mask_rotate_crop': self.getState(f"{idx}.image.enable_random_mask_rotate_crop"),

                'prompt': prompt_output,
                'tag_dropout_enable': self.getState(f"{idx}.text.tag_dropout_enable"),
                'tag_dropout_probability': self.getState(f"{idx}.text.tag_dropout_probability"),
                'tag_dropout_mode': self.getState(f"{idx}.text.tag_dropout_mode"),
                'tag_dropout_special_tags': self.getState(f"{idx}.text.tag_dropout_special_tags"),
                'tag_dropout_special_tags_mode': self.getState(f"{idx}.text.tag_dropout_special_tags_mode"),
                'tag_delimiter': self.getState(f"{idx}.text.tag_delimiter"),
                'keep_tags_count': self.getState(f"{idx}.text.keep_tags_count"),
                'tag_dropout_special_tags_regex': self.getState(f"{idx}.text.tag_dropout_special_tags_regex"),
                'caps_randomize_enable': self.getState(f"{idx}.text.caps_randomize_enable"),
                'caps_randomize_probability': self.getState(f"{idx}.text.caps_randomize_probability"),
                'caps_randomize_mode': self.getState(f"{idx}.text.caps_randomize_mode"),
                'caps_randomize_lowercase': self.getState(f"{idx}.text.caps_randomize_lowercase"),
                'enable_tag_shuffling': self.getState(f"{idx}.text.enable_tag_shuffling"),
            })

            circular_mask_shrink = RandomCircularMaskShrink(mask_name='mask', shrink_probability=1.0,
                                                            shrink_factor_min=0.2, shrink_factor_max=1.0,
                                                            enabled_in_name='enable_random_circular_mask_shrink')
            random_mask_rotate_crop = RandomMaskRotateCrop(mask_name='mask', additional_names=['image'], min_size=512,
                                                           min_padding_percent=10, max_padding_percent=30,
                                                           max_rotate_angle=20,
                                                           enabled_in_name='enable_random_mask_rotate_crop')
            random_flip = RandomFlip(names=['image', 'mask'], enabled_in_name='enable_random_flip',
                                     fixed_enabled_in_name='enable_fixed_flip')
            random_rotate = RandomRotate(names=['image', 'mask'], enabled_in_name='enable_random_rotate',
                                         fixed_enabled_in_name='enable_fixed_rotate',
                                         max_angle_in_name='random_rotate_max_angle')
            random_brightness = RandomBrightness(names=['image'], enabled_in_name='enable_random_brightness',
                                                 fixed_enabled_in_name='enable_fixed_brightness',
                                                 max_strength_in_name='random_brightness_max_strength')
            random_contrast = RandomContrast(names=['image'], enabled_in_name='enable_random_contrast',
                                             fixed_enabled_in_name='enable_fixed_contrast',
                                             max_strength_in_name='random_contrast_max_strength')
            random_saturation = RandomSaturation(names=['image'], enabled_in_name='enable_random_saturation',
                                                 fixed_enabled_in_name='enable_fixed_saturation',
                                                 max_strength_in_name='random_saturation_max_strength')
            random_hue = RandomHue(names=['image'], enabled_in_name='enable_random_hue',
                                   fixed_enabled_in_name='enable_fixed_hue',
                                   max_strength_in_name='random_hue_max_strength')
            drop_tags = DropTags(text_in_name='prompt', enabled_in_name='tag_dropout_enable',
                                 probability_in_name='tag_dropout_probability', dropout_mode_in_name='tag_dropout_mode',
                                 special_tags_in_name='tag_dropout_special_tags',
                                 special_tag_mode_in_name='tag_dropout_special_tags_mode',
                                 delimiter_in_name='tag_delimiter',
                                 keep_tags_count_in_name='keep_tags_count', text_out_name='prompt',
                                 regex_enabled_in_name='tag_dropout_special_tags_regex')
            caps_randomize = CapitalizeTags(text_in_name='prompt', enabled_in_name='caps_randomize_enable',
                                            probability_in_name='caps_randomize_probability',
                                            capitalize_mode_in_name='caps_randomize_mode',
                                            delimiter_in_name='tag_delimiter',
                                            convert_lowercase_in_name='caps_randomize_lowercase',
                                            text_out_name='prompt')
            shuffle_tags = ShuffleTags(text_in_name='prompt', enabled_in_name='enable_tag_shuffling',
                                       delimiter_in_name='tag_delimiter', keep_tags_count_in_name='keep_tags_count',
                                       text_out_name='prompt')
            output_module = OutputPipelineModule(['image', 'mask', 'prompt'])

            modules = [
                input_module,
                circular_mask_shrink,
                random_mask_rotate_crop,
                random_flip,
                random_rotate,
                random_brightness,
                random_contrast,
                random_saturation,
                random_hue,
                drop_tags,
                caps_randomize,
                shuffle_tags,
                output_module,
            ]

            pipeline = LoadingPipeline(
                device=torch.device('cpu'),
                modules=modules,
                batch_size=1,
                seed=random.randint(0, 2 ** 30),
                state=None,
                initial_epoch=0,
                initial_index=0,
            )

            data = pipeline.__next__()
            image_tensor = data['image']
            mask_tensor = data['mask']
            prompt_output = data['prompt']

        filename_output = os.path.basename(preview_image_path)

        mask_tensor = torch.clamp(mask_tensor, 0.3, 1)
        image_tensor = image_tensor * mask_tensor

        image = functional.to_pil_image(image_tensor)

        image.thumbnail((300, 300))

        return image, filename_output, prompt_output
