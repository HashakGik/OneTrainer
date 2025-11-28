from enum import Enum


class BaseEnum(Enum):
    def __str__(self):
        return self.value

    def pretty_print(self):
        # TODO: do we want this method to use translatable strings? If so, how to avoid introducing an undesirable QT dependency in modules.util.enum?
        return self.value.replace("_", " ").title()

    @staticmethod
    def is_enabled(value, context=None):
        return True

    @classmethod
    def enabled_values(cls, context=None):
        return [v for v in cls if cls.is_enabled(v, context)]
