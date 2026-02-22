import orjson as json

from pathlib import Path

pretty_print_json = False


def read_json(path):
    return json.loads(Path(path).read_bytes())


def write_json(json_dict, path, pretty_print=False):
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    options = json.OPT_NON_STR_KEYS

    if pretty_print_json or pretty_print:
        options |= json.OPT_INDENT_2

    file_path.write_bytes(json.dumps(json_dict, option=options))
