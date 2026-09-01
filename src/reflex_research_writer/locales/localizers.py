import yaml
from typing import Any, List, Tuple
from importlib import resources
import reflex_research_writer.locales as locales


DEFAULT_LANGUAGE = "en"


def _load_yaml_file(file_name: str):
    # Construct the resource path within the project package
    resource_path = resources.files(locales).joinpath(file_name)

    # Read text directly (Python 3.9+)
    content = resource_path.read_text(encoding="utf-8")
    return yaml.safe_load(content)


class MessageLocalizer:
    def __init__(self, language: str):
        _messages_obj = _load_yaml_file("messages.yaml")

        self._available_languages = _messages_obj.keys()

        self._language = (
            language
            if language in _messages_obj
            else DEFAULT_LANGUAGE
        )

        self._messages = _messages_obj[self._language]


    def get(self, key: str, phase: str, **kwargs: Any,) -> str:
        text = self._messages[key][phase]
        return text.format(**kwargs)


    @property
    def available_languages(self)-> List[str]:
        return self._available_languages




class UIStringLocalizer:
    def __init__(self, language: str):
        _ui_strings_obj = _load_yaml_file("ui_strings.yaml")

        self._available_languages = _ui_strings_obj.keys()

        self._language = (
            language
            if language in _ui_strings_obj
            else DEFAULT_LANGUAGE
        )

        self._ui_strings = _ui_strings_obj[self._language]


    def get(self, key: str)-> str:
        return self._ui_strings.get(key, key)


    def target_language_name(self, code: str) -> str:
        return self._ui_strings["target.languages"][code]


    def languages_list(self) -> List[Tuple[str, str]]:
        return [
            (name, code)
            for code, name in self._ui_strings.get("languages", {}).items()
        ]


    @property
    def available_languages(self)-> List[str]:
        return self._available_languages


    @property
    def current_language(self) -> str:
        return self._language