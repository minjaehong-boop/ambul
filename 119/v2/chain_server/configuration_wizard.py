"""Configuration wizard - reads config from YAML/JSON/env variables."""

import json
import logging
import os
from dataclasses import _MISSING_TYPE, dataclass
from typing import Any, Callable, Dict, List, Optional, TextIO, Tuple, Union

import yaml
from dataclass_wizard import JSONWizard, LoadMeta, YAMLWizard, errors, fromdict, json_field
from dataclass_wizard.models import JSONField
from dataclass_wizard.utils.string_conv import to_camel_case

configclass = dataclass(frozen=True)
ENV_BASE = "APP"
_LOGGER = logging.getLogger(__name__)


def configfield(name: str, *, env: bool = True, help_txt: str = "", **kwargs: Any) -> JSONField:
    if not isinstance(name, str):
        raise TypeError("Provided name must be a string.")
    json_name = to_camel_case(name)
    meta = kwargs.get("metadata", {})
    meta["env"] = env
    meta["help"] = help_txt
    kwargs["metadata"] = meta
    return json_field(json_name, **kwargs)


class ConfigWizard(JSONWizard, YAMLWizard):  # type: ignore[misc]

    @classmethod
    def envvars(
        cls, env_parent: Optional[str] = None, json_parent: Optional[Tuple[str, ...]] = None,
    ) -> List[Tuple[str, Tuple[str, ...], type]]:
        if not env_parent:
            env_parent = ""
        if not json_parent:
            json_parent = ()
        output = []
        for _, val in cls.__dataclass_fields__.items():
            jsonname = val.json.keys[0]
            envname = jsonname.upper()
            full_envname = f"{ENV_BASE}{env_parent}_{envname}"
            is_embedded_config = hasattr(val.type, "envvars")
            if is_embedded_config:
                new_env_parent = f"{env_parent}_{envname}"
                new_json_parent = json_parent + (jsonname,)
                output += val.type.envvars(env_parent=new_env_parent, json_parent=new_json_parent)
            elif val.metadata.get("env", True):
                output += [(full_envname, json_parent + (jsonname,), val.type)]
        return output

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConfigWizard":
        if not data:
            data = {}
        if not isinstance(data, dict):
            raise RuntimeError("Configuration data is not a dictionary.")
        for envvar in cls.envvars():
            var_name, conf_path, var_type = envvar
            var_value = os.environ.get(var_name)
            if var_value:
                var_value = _try_json_load(var_value)
                _update_dict(data, conf_path, var_value)
        LoadMeta(key_transform="CAMEL").bind_to(cls)
        return fromdict(cls, data)  # type: ignore[no-any-return]

    @classmethod
    def from_file(cls, filepath: str) -> Optional["ConfigWizard"]:
        try:
            file = open(filepath, encoding="utf-8")
        except (FileNotFoundError, PermissionError):
            file = None
        if not file:
            return cls.from_dict({})

        try:
            data = _read_json_or_yaml(file)
        except ValueError:
            data = None
        finally:
            file.close()

        if data:
            try:
                return cls.from_dict(data)
            except (errors.MissingFields, errors.ParseError):
                return None
        return cls.from_dict({})


def _read_json_or_yaml(stream: TextIO) -> Dict[str, Any]:
    if not stream.seekable():
        raise ValueError("The provided stream must be seekable.")
    try:
        data = json.loads(stream.read())
        return data
    except ValueError:
        stream.seek(0)
    try:
        data = yaml.safe_load(stream.read())
        return data
    except (yaml.error.YAMLError, ValueError) as err:
        raise ValueError(str(err))


def _try_json_load(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _update_dict(data: Dict[str, Any], path: Tuple[str, ...], value: Any) -> None:
    end = len(path)
    target = data
    for idx, key in enumerate(path, 1):
        if idx == end:
            if not target.get(key):
                target[key] = value
            return
        if not target.get(key):
            target[key] = {}
        if not isinstance(target.get(key), dict):
            return
        target = target.get(key)  # type: ignore[assignment]
