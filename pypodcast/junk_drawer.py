from importlib import import_module
import string
import sys


def _cached_import(module_path, class_name):
    # Check whether module is loaded and fully initialized.
    if not (
        (module := sys.modules.get(module_path))
        and (spec := getattr(module, "__spec__", None))
        and getattr(spec, "_initializing", False) is False
    ):
        module = import_module(module_path)
    return getattr(module, class_name)


# Copied from django. Can only handle one attr into the module
# That is, must be `package.module.object`, cannot be `module.object.attr`
def import_string(dotted_path):
    """
    Import a dotted module path and return the attribute/class designated by the
    last name in the path. Raise ImportError if the import failed.
    """
    try:
        module_path, class_name = dotted_path.rsplit(".", 1)
    except ValueError as err:
        raise ImportError("%s doesn't look like a module path" % dotted_path) from err

    try:
        return _cached_import(module_path, class_name)
    except AttributeError as err:
        raise ImportError(
            'Module "%s" does not define a "%s" attribute/class'
            % (module_path, class_name)
        ) from err


class GentleFormatter(string.Formatter):
    pass

def gentle_format(format: str, namespace) -> str:
    """
    Allows formatting with less mappy mappings
    """
    return GentleFormatter().vformat(format, [], namespace)
