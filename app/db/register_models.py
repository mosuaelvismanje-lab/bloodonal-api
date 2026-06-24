import pkgutil
import importlib
import app

def register_all_models():
    for _, module_name, _ in pkgutil.walk_packages(
        app.__path__,
        app.__name__ + "."
    ):
        if (
            module_name.endswith(".models")
            or ".models." in module_name
        ):
            importlib.import_module(module_name)