#---------------------------------------------------------------------------------------------------
__all__ = (
    'dump',
    'load',
)

import sys
import yaml
import yamlinclude

#---------------------------------------------------------------------------------------------------
class MetaData:
    def __init__(self, node):
        self.path = node.start_mark.name
        self.line = node.start_mark.line + 1
        self.column = node.start_mark.column

    def __str__(self):
        return f'path: {self.path}, line: {self.line}, column: {self.column}'

#---------------------------------------------------------------------------------------------------
# These types are created to allow attaching extra attributes to parsed data objects. They must
# behave exactly as the builtin types they extend.
class CustomDict(dict): ...
class CustomList(list): ...

#---------------------------------------------------------------------------------------------------
class Loader(yaml.SafeLoader):
    def construct_custom_dict(self, node):
        # Create an empty mapping for the node. This is needed to support anchors.
        data = CustomDict()
        data.___metadata___ = MetaData(node)
        yield data

        # Use the default method for filling in the mapping key:value pairs.
        data.update(self.construct_mapping(node))

    def construct_custom_list(self, node):
        # Create an empty list for the node. This is needed to support anchors.
        data = CustomList()
        data.___metadata___ = MetaData(node)
        yield data

        # Use the default method for filling in the list items.
        data.extend(self.construct_sequence(node))

Loader.add_constructor('tag:yaml.org,2002:map', Loader.construct_custom_dict)
Loader.add_constructor('tag:yaml.org,2002:seq', Loader.construct_custom_list)

#---------------------------------------------------------------------------------------------------
class Dumper(yaml.Dumper):
    def represent_custom_dict(self, data):
        return self.represent_dict(data) # Dump as normal mapping.

    def represent_custom_list(self, data):
        return self.represent_list(data) # Dump as normal list.

Dumper.add_representer(CustomDict, Dumper.represent_custom_dict)
Dumper.add_representer(CustomList, Dumper.represent_custom_list)

#---------------------------------------------------------------------------------------------------
def load(stream, include_dir=None):
    if include_dir is not None:
        yamlinclude.YamlIncludeConstructor.add_to_loader_class(
            loader_class=Loader, base_dir=include_dir)
    return yaml.load(stream, Loader=Loader)

#---------------------------------------------------------------------------------------------------
def dump(data, stream):
    yaml.dump(data, stream, Dumper=Dumper)
