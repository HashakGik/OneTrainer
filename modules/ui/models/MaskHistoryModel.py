from modules.ui.models.SingletonConfigModel import SingletonConfigModel
from modules.util.config.BaseConfig import BaseConfig

import cv2
import numpy as np

# TODO: Sometimes it seems it won't save/load correctly from disk.

class MaskHistoryConfig(BaseConfig):
    buffer: list
    ptr: int
    current_mask: np.ndarray
    original_mask: np.ndarray
    width: int
    height: int


    @staticmethod
    def default_values():
        data = []

        # name, default value, data type, nullable
        data.append(("buffer", [], list, False))
        data.append(("ptr", 0, int, False))
        data.append(("original_mask", None, np.ndarray, True))
        data.append(("current_mask", None, np.ndarray, True))
        data.append(("width", 0, int, False))
        data.append(("height", 0, int, False))

        return MaskHistoryConfig(data)

class MaskHistoryModel(SingletonConfigModel):
    def __init__(self):
        super().__init__(MaskHistoryConfig.default_values())
        self.draw = None

    def loadMask(self, mask):
        with self.critical_region_write():
            self.config.buffer = []
            self.config.ptr = 0
            self.config.original_mask = mask
            self.config.current_mask = mask.copy()
            self.config.width, self.config.height = mask.shape

    def __pack(self, mask):
        # Encodes np.bool into np.uint8 (flattened and zero-padded at the end).
        w, h = mask.shape
        return np.packbits(mask.astype(np.bool)), w, h

    def __unpack(self, mask, w, h):
        # Unpack np.uint8 into np.bool, remove zero-padding at the end, and reshape.
        return np.unpackbits(mask)[:w * h].reshape((w, h)).astype(np.uint8).copy()

    def undo(self):
        with self.critical_region_write():
            if self.config.ptr > 0:
                self.config.ptr -= 1
                self.config.current_mask = self.__unpack(self.config.buffer[self.config.ptr], self.config.width, self.config.height)

    def redo(self):
        with self.critical_region_write():
            if self.config.ptr < len(self.config.buffer) - 1:
                self.config.ptr += 1
                self.config.current_mask = self.__unpack(self.config.buffer[self.config.ptr], self.config.width, self.config.height)

    def commit(self):
        with self.critical_region_write():
            if self.config.current_mask is not None:
                if self.config.ptr < len(self.config.buffer) - 1:
                    self.config.buffer = self.config.buffer[:self.config.ptr + 1] # Invalidate the future before adding a new state.

                self.config.ptr = len(self.config.buffer)
                packed, _, _ = self.__pack(self.config.current_mask)
                self.config.buffer.append(packed)

    def clearHistory(self):
        with self.critical_region_write():
            self.config.buffer = []
            self.config.ptr = 0
            self.config.current_mask = self.config.original_mask.copy()

    def reset(self):
        with self.critical_region_write():
            self.commit() # Commit previous state.
            self.config.current_mask = np.ones_like(self.config.current_mask)
            self.commit() # Commit empty mask.


    def fill(self, x, y, color):
        with self.critical_region_write():
            if self.config.current_mask is not None:
                cv2.floodFill(self.config.current_mask, None, (x, y), color)

    def paintStroke(self, x0, y0, x1, y1, radius, color, commit=False):
        # TODO: this should be protected from race conditions, however, locking every single stroke is noticeably slow.
        # The solution may be to acquire the lock during mouse pressed and release it during commit, but can introduce bugs and violates encapsulation.
        if self.config.current_mask is not None:
            # Draw line between points
            line_width = 2 * radius + 1
            cv2.line(self.config.current_mask, (x0, y0), (x1, y1), color, line_width)

            # Draw circle at start point
            cv2.circle(self.config.current_mask, (x0, y0), radius, color, -1)

            # Draw circle at end point if different from start
            if (x0, y0) != (x1, y1):
                cv2.circle(self.config.current_mask, (x1, y1), radius, color, -1)

            if commit:
                self.commit()
