import orjson as json

from pathlib import Path

pretty_print_json = False


def read_json(path):
    return json.loads(Path(path).read_bytes())


def orjson_default(obj):
    if hasattr(obj, "to_dict"):
        return obj.to_dict()

    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def write_json(json_dict, path, pretty_print=False):
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    options = json.OPT_NON_STR_KEYS | json.OPT_PASSTHROUGH_DATACLASS

    if pretty_print_json or pretty_print:
        options |= json.OPT_INDENT_2

    file_path.write_bytes(json.dumps(json_dict, default=orjson_default, option=options))
