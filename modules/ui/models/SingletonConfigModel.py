import copy
import os
import threading
import traceback
from contextlib import contextmanager

from modules.util import path_util

# TODO: Cleanup
# 1) Naming convention is all over the place (camelCase, snake_case, inconsistent visibility __method vs _method vs method)
# 2) Use self._log instead of print/logging.logger/traceback.print_exc()


# Base class for config models. It provides a Singleton interface and a single mutex shared across all the subclasses.
class SingletonConfigModel:
    _instance = None
    config = None
    _frozenConfig = None
    _is_frozen = False
    mutex = threading.RLock() # QBasicMutex and QMutex are both non-reentrant. We need this to allow the same thread to enter the critical region multiple times without deadlocks.
    log_mutex = threading.RLock()

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def log(self, severity, message):
        self.log_mutex.acquire()
        print(f"{severity}: {message}") # TODO: use logging.logger, logging on file, other approach?
        # Proposed severities: "traceback", "error", "warning", "debug", "info"
        # Maybe some of them default to files, others to console, other both?
        self.log_mutex.release()

    # Freezes internal state, forcing getState to read on a copy. setState, instead will still write on the actual data.
    # Note that this does not prevent access from different threads, but since the copy is read-only, this is not a race condition.
    @contextmanager
    def freeze_state(self):
        try:
            try:
                if self.mutex is not None:
                    self.mutex.acquire()
                    self._frozenConfig = copy.deepcopy(self.config)
                    self._is_frozen = True
            finally:
                if self.mutex is not None:
                    self.mutex.release()

            yield
        except Exception:
            traceback.print_exc()
        finally:
            if self.mutex is not None:
                self.mutex.acquire()
                self._frozenConfig = None
                self._is_frozen = False
            if self.mutex is not None:
                self.mutex.release()

    def getState(self, path):
        cfg = self._frozenConfig if self._is_frozen else self.config
        if cfg is not None:
            try:
                if self.mutex is not None and not self._is_frozen:
                    self.mutex.acquire()

                ref = cfg
                if path == "":
                    return ref

                for key in str(path).split("."):
                    if isinstance(ref, list):
                        ref = ref[int(key)]
                    elif isinstance(ref, dict) and key in ref:
                        ref = ref[key]
                    elif hasattr(ref, key):
                        ref = getattr(ref, key)
                    else:
                        print(f"DEBUG: key {key} not found in config")
                        return None
                return ref

            except Exception:
                traceback.print_exc()
            finally:
                if self.mutex is not None and not self._is_frozen:
                    self.mutex.release()


        return None

    def setState(self, path, value):
        if self.config is not None:
            with self.critical_region():
                ref = self.config
                for ptr in str(path).split(".")[:-1]:
                    if isinstance(ref, list):
                        ref = ref[int(ptr)]
                    elif isinstance(ref, dict):
                        ref = ref[ptr]
                    elif hasattr(ref, ptr):
                        ref = getattr(ref, ptr)
                if isinstance(ref, list):
                    ref[int(path.split(".")[-1])] = value
                elif isinstance(ref, dict):
                    ref[path.split(".")[-1]] = value
                elif hasattr(ref, path.split(".")[-1]):
                    setattr(ref, path.split(".")[-1], value)
                else:
                    print(f"DEBUG: key {path} not found in config")

    def load_available_config_names(self, dir="training_presets", include_default=True):
        configs = [("", path_util.canonical_join(dir, "#.json"))] if include_default else []

        if os.path.isdir(dir):
            for path in os.listdir(dir):
                if path != "#.json":
                    path = path_util.canonical_join(dir, path)
                    if path.endswith(".json") and os.path.isfile(path):
                        name = os.path.basename(path)
                        name = os.path.splitext(name)[0]
                        configs.append((name, path))
            configs.sort()

        return configs

    @contextmanager
    def critical_region(self):
        try:
            if self.mutex is not None:
                self.mutex.acquire()
            yield
        except Exception:
            traceback.print_exc()
        finally:
            if self.mutex is not None:
                self.mutex.release()

    # Decorator @atomic for fully-region critical methods.
    def atomic(method):
        def f(self, *args, **kwargs):
            with self.critical_region():
                return method(self, *args, **kwargs)
        return f
