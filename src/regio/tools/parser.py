#---------------------------------------------------------------------------------------------------
__all__ = (
    'dump',
    'load',
)

import pathlib
import sys
import yaml

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
    def __init__(self, *pargs, include_dirs=(), **kargs):
        super().__init__(*pargs, **kargs)
        self._include_dirs = include_dirs

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

    def construct_custom_include(self, node):
        # Use the default method for parsing the included file's path.
        path = pathlib.Path(str(self.construct_scalar(node)))

        # Search for the included file within the provided include directories.
        for inc_dir in self._include_dirs:
            inc_path = (inc_dir / path).resolve()
            if inc_path.exists():
                path = inc_path
                break
        else:
            include_dirs = ', '.join(self._include_dirs)
            raise yaml.MarkedYAMLError(None, None,
                f'Failed to find included file "{path}" in search directories: {include_dirs}',
                node.start_mark)

        # Create an empty mapping for the node. This is needed to support anchors.
        data = CustomDict()
        data.___metadata___ = MetaData(node)
        yield data

        # Recursively load the included file.
        with path.open('r') as stream:
            inc_data = load(stream, self._include_dirs)

        if not isinstance(inc_data, dict):
            raise yaml.MarkedYAMLError(None, None,
                f'Root of included file "{path}" must be specified as a mapping, '
                f'not a {type(inc_data)}', node.start_mark)
        data.update(inc_data)

Loader.add_constructor('tag:yaml.org,2002:map', Loader.construct_custom_dict)
Loader.add_constructor('tag:yaml.org,2002:seq', Loader.construct_custom_list)
Loader.add_constructor('!include', Loader.construct_custom_include)

#---------------------------------------------------------------------------------------------------
class Dumper(yaml.Dumper):
    def represent_custom_dict(self, data):
        return self.represent_dict(data) # Dump as normal mapping.

    def represent_custom_list(self, data):
        return self.represent_list(data) # Dump as normal list.

Dumper.add_representer(CustomDict, Dumper.represent_custom_dict)
Dumper.add_representer(CustomList, Dumper.represent_custom_list)

#---------------------------------------------------------------------------------------------------
def load(stream, include_dirs=()):
    loader = Loader(stream, include_dirs=include_dirs)
    try:
        return loader.get_single_data()
    finally:
        loader.dispose()

#---------------------------------------------------------------------------------------------------
def dump(data, stream):
    yaml.dump(data, stream, Dumper=Dumper)
