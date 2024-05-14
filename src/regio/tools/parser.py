#---------------------------------------------------------------------------------------------------
__all__ = (
    'dump',
    'load',
)

import yaml
import yamlinclude

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

#---------------------------------------------------------------------------------------------------
def load(stream, include_dir=None):
    if include_dir is not None:
        yamlinclude.YamlIncludeConstructor.add_to_loader_class(
            loader_class=Loader, base_dir=include_dir)
    return yaml.load(stream, Loader=Loader)

#---------------------------------------------------------------------------------------------------
def dump(data, stream):
    yaml.dump(data, stream, Dumper=Dumper)
