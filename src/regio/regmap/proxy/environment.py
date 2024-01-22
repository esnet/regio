#---------------------------------------------------------------------------------------------------
__all__ = ()

import code
import collections
import importlib, importlib.util
import pathlib
import re
import sys

import click, click.shell_completion

from . import proxy, variable

PROXY_TYPES = (proxy.Proxy, variable.Variable)

#---------------------------------------------------------------------------------------------------
class EnvironmentVariable:
    def __init__(self, name, *pargs, **kargs):
        super().__init__(*pargs, **kargs)

        self._name = name
        self._proxies = collections.OrderedDict()

    def __dir__(self):
        return [name for name in vars(self) if not name.startswith('_')]

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if isinstance(value, PROXY_TYPES) and value not in self._proxies.values():
            kargs = value.___context___.kargs
            kargs['qualbase'] = (
                self._name + '.' + name, # qualstem
                value.___node___.qualname, # qualroot
                len(value.___node___.path), # qualstart
            )
            self._proxies[name] = value

    def __delattr__(self, name):
        value = getattr(self, name, None)
        super().__delattr__(name)
        if name in self._proxies:
            del value.___context___.kargs['qualbase']
            del self._proxies[name]

#---------------------------------------------------------------------------------------------------
class Environment:
    def __init__(self, *pargs, **kargs):
        super().__init__(*pargs, **kargs)

        # Create an anonymous module. The module's attribute dictionary is used as a namespace for
        # globals and locals during the execution of Python expressions, statements and interactive
        # shells. The idea is to quanrantine any dynamic code from being able to access the internal
        # namespaces in which the environment is embedded.
        # TODO: Look into sub-classing types.ModuleType via a custom loader for namespace control.
        spec = importlib.machinery.ModuleSpec('__proxy_environment__', None)
        self._mod = importlib.util.module_from_spec(spec)
        self._namespace = vars(self._mod)
        self._variables = collections.OrderedDict()

    def new_variable(self, name):
        if name in self._variables:
            raise NameError(f'The "{name}" environment variable already exists.')

        var = EnvironmentVariable(name)
        self._variables[name] = var
        self._namespace[name] = var

        return var

    def __enter__(self):
        self.start()

        # Allow caller to bind the object in a 'with X() as x' statement.
        return self

    def __exit__(self, *pargs):
        self.stop()

        # Don't suppress exceptions. Pass along to the caller.
        return False

    def start(self):
        # Start all proxies in the environment's namespace.
        for v in self._variables.values():
            for p in v._proxies.values():
                proxy.start_io(p)

    def stop(self):
        # Stop all proxies in the environment's namespace.
        for v in reversed(self._variables.values()):
            for p in reversed(v._proxies.values()):
                proxy.stop_io(p)

    def dump(self, paths):
        if paths:
            # Break up the selected paths into their components.
            paths = [p.split('.') for p in paths]
        else:
            # Select all proxies attached to the environment variables.
            paths = [[vn, pn] for vn, v in self._variables.items() for pn in v._proxies]

        # Perform a verbose dump of the selected proxies.
        with self:
            for names in paths:
                # Lookup the object.
                obj = self._mod
                while names:
                    obj = getattr(obj, names.pop(0))

                # Display the object.
                if isinstance(obj, proxy.Proxy):
                    obj = obj(...)
                print(obj)

    def eval(self, expressions):
        with self:
            for expr in expressions:
                # Compile the string into a code object. This is needed because the builtin eval()
                # can only handle expressions when passed a string, but can deal with statements
                # when passed a code object. The choice to use eval() instead of exec() is due to
                # eval() returning a result, where as exec() always returns None.
                # https://docs.python.org/3/library/functions.html#eval
                # https://docs.python.org/3/library/functions.html#compile
                try:
                    # The string is a pure expression.
                    co = compile(expr, '<string>', 'eval')
                except SyntaxError:
                    # The string contains statements.
                    co = compile(expr, '<string>', 'exec')

                # Run the code object within the environment's namespace.
                result = eval(co, self._namespace)
                if result is not None:
                    print(result)

    def script(self, path, argv):
        if not isinstance(path, pathlib.Path):
            path = pathlib.Path(path)

        if not path.exists:
            raise FileNotFoundError(str(path))

        # Update the environment's namespace for execution of the script.
        ns = self._namespace
        bkup = {
            '__name__': {'new': '__main__'},
            '__file__': {'new': str(path)},
        }
        for k, v in bkup.items():
            try:
                value = ns[k]
            except KeyError:
                ...
            else:
                v['old'] = value
            ns[k] = v['new']

        # Swap out the command line arguments and module search path.
        sargv, sys.argv = sys.argv, list(argv)
        spath, sys.path = sys.path, [path.parent.absolute(), *sys.path]

        # Compile the script into a code object.
        with path.open('r') as fo:
            co = compile(fo.read(), '<script>', 'exec')

        # Execute the compiled script.
        with self:
            exec(co, ns)

        # Restore the environment.
        sys.argv = sargv
        sys.path = spath

        for k, v in bkup.items():
            try:
                value = v['old']
            except KeyError:
                del ns[k]
            else:
                ns[k] = value

    def python_shell(self):
        # Create the shell or re-use the previously cached one. This allows maintaining state
        # between invocations.
        try:
            shell = self._python_shell
        except AttributeError:
            # Setup the terminal behaviour (module automatically installs input handlers).
            import readline

            shell = code.InteractiveConsole(locals=self._namespace)
            self._python_shell = shell

        # Run the interactive shell.
        with self:
            shell.interact()

    def ipython_shell(self):
        try:
            import IPython
        except ImportError:
            raise NotImplementedError('Missing IPython module.')

        # Create the shell or re-use the previously cached one. This allows maintaining state
        # between invocations.
        try:
            shell = self._ipython_shell
        except AttributeError:
            shell = IPython.terminal.embed.InteractiveShellEmbed()
            self._ipython_shell = shell

        # Run the interactive shell.
        with self:
            shell(local_ns=self._namespace, module=self._mod)

    def ptpython_shell(self):
        try:
            import ptpython
        except ImportError:
            raise NotImplementedError('Missing ptpython module.')

        # Create the shell or re-use the previously cached one. This allows maintaining state
        # between invocations.
        try:
            shell = self._ptpython_shell
        except AttributeError:
            shell = ptpython.repl.PythonRepl(
                get_globals=lambda: self._namespace,
                get_locals=lambda: self._namespace)
            self._ptpython_shell = shell

        # Run the interactive shell.
        with self:
            shell.run()

    def ptipython_shell(self):
        try:
            import ptpython.ipython as ptipython
        except ImportError:
            raise NotImplementedError('Missing ptpython and/or IPython module(s).')

        try:
            shell = self._ptipython_shell
        except AttributeError:
            shell = ptipython.InteractiveShellEmbed()
            self._ptipython_shell = shell

        # Run the interactive shell.
        with self:
            shell(local_ns=self._namespace, module=self._mod)

#---------------------------------------------------------------------------------------------------
class ClickEnvironment(Environment):
    NAME_RE = r'(?P<name>[a-zA-Z_][a-zA-Z0-9_]*)'
    SUBS_RE = r'(?P<subs>(\[((\d+|(\d*:\d*(:\d*)?)),)*(\d+|(\d*:\d*(:\d*)?))\])*?)'
    PART_RE = r'(?P<suffix>' + NAME_RE + SUBS_RE + r')'
    PARTIAL_RE = re.compile(r'^(?P<stem>.*?)' + PART_RE + r'$')
    PATH_RE = re.compile(r'^(?P<stem>.*?)' + PART_RE + r'\.?$')

    def __init__(self, parent, *pargs, **kargs):
        super().__init__(*pargs, **kargs)

        self.in_completion = False
        self._add_click_commands(parent)

    @staticmethod
    def main_options(main):
        options = (
            click.option(
                '--verbose',
                help='Display using verbose configuration.',
                is_flag=True,
                default=False,
            ),
            click.option(
                '--abspath',
                help='Include all components when displaying regmap object paths. Default behaviour'
                     ' is to print paths relative to the selected object.',
                is_flag=True,
                default=False,
            ),
            click.option(
                '--formatter',
                help='Select the format of displayed output.',
                type=click.Choice(tuple(sorted(variable.FORMATTERS))),
                default='table',
            ),
            click.option(
                '--path-sort',
                help='Sort displayed output by object path. Default is to sort by offset.',
                is_flag=True,
                default=False,
            ),
            click.option(
                '--ignore-access',
                help='Ignore access permissions on registers and fields when displaying output.',
                is_flag=True,
                default=False,
            ),
            click.option(
                '--hex-grouping',
                help='Display hexadecimal values with an "_" separating every group of 4 digits.',
                is_flag=True,
                default=False,
            ),
            click.option(
                '--bits-grouping',
                help='Display bits values with an "_" separating every group of 4 digits.',
                is_flag=True,
                default=False,
            ),
            click.option(
                '--show-column-layout',
                help='Display the default column layout used by the table formatter.',
                is_flag=True,
                default=False,
            ),
            click.option(
                '--column-layout',
                help='Specify a custom column layout to be used by the table formatter.',
            ),
        )

        for opt in reversed(options):
            main = opt(main)
        return main

    def process_options(self, kargs):
        kargs = dict(kargs)
        if kargs['column_layout'] is None:
            del kargs['column_layout']
        return kargs

    def _complete(self, incomplete):
        # Extract the last path component on which completion is being attempted.
        parts = []
        match = self.PARTIAL_RE.match(incomplete)
        if match is not None:
            stem = match['stem']
            name = match['name']
            subs = match['subs']
            if subs:
                parts.append((name, subs))
                partial_name = ''
            else:
                partial_name = name
        else:
            stem = incomplete
            partial_name = ''

        # Extract the path components leading up to the completion being attempted.
        while True:
            match = self.PATH_RE.match(stem)
            if match is None:
                break

            stem = match['stem']
            parts.append((match['name'], match['subs']))

        # Perform the path lookup to find the namespace to query for the completion.
        obj = self._mod
        for name, subs in reversed(parts):
            try:
                obj = getattr(obj, name)
            except AttributeError:
                return []

            for _ in range(subs.count('[')):
                try:
                    # The index doesn't matter for completion, just need an object in order to
                    # continue the chain of lookups.
                    obj = obj[0]
                except IndexError:
                    return []

        # Build up the list of matches for the completion.
        matches = [name for name in dir(obj) if name[:2] != '__' and name.startswith(partial_name)]
        if matches:
            if len(matches) == 1 and len(dir(getattr(obj, matches[0]))) > 0:
                matches.append(matches[0] + '.')

            nstrip = len(partial_name)
            matches = [incomplete + m[nstrip:] for m in matches]
        return [click.shell_completion.CompletionItem(m) for m in matches]

    def _path_complete(self, ctx, param, incomplete):
        # Run the main command to load the regmap and insert variables into the environment.
        main = ctx.find_root()
        kargs = dict(main.params)
        kargs['test_io'] = 'zero'

        self.in_completion = True
        main.invoke(main.command, **kargs) # TODO: can flag be passed via kargs instead?
        self.in_completion = False

        return self._complete(incomplete)

    def _add_click_commands(self, parent):
        @parent.command()
        @click.argument('object-paths', nargs=-1, shell_complete=self._path_complete)
        def dump(object_paths):
            '''
            Read and display selected sub-tree(s) from loaded register map specifications. Without
            any object path arguments, the top-level of all loaded register maps will be displayed.
            '''
            self.dump(object_paths)

        @parent.command()
        @click.argument('expressions', nargs=-1, shell_complete=self._path_complete)
        def eval(expressions):
            '''
            Evaluate a sequence of Python expressions within the context of the loaded register
            map specifications and display the result of each.
            '''
            self.eval(expressions)

        @parent.command()
        @click.argument('path', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
        @click.argument('arguments', nargs=-1)
        def script(path, arguments):
            '''
            Execute a Python script within the context of the loaded register map specifications.
            '''
            self.script(path, arguments)

        @parent.group()
        def shell():
            '''
            Enter various interactive Python shells executed within the context of the loaded
            register map specifications.
            '''

        @shell.command()
        def python():
            '''
            Enter the standard Python shell.
            '''
            self.python_shell()

        @shell.command()
        def ipython():
            '''
            Enter the IPython shell.
            '''
            self.ipython_shell()

        @shell.command()
        def ptpython():
            '''
            Enter the Prompt Toolkit shell.
            '''
            self.ptpython_shell()

        @shell.command()
        def ptipython():
            '''
            Enter the Prompt Toolkit IPython shell.
            '''
            self.ptipython_shell()

        @parent.group()
        def completions():
            '''
            Generate shell completion scripts.
            '''

        @completions.command()
        @click.pass_context
        def bash(ctx):
            # TODO: Update help strings with commands to setup completion in current shell.
            # https://click.palletsprojects.com/en/8.1.x/shell-completion/
            '''
            Generate a completion script for the Bourne Again SHell.
            '''
            self._print_completion(ctx, 'bash')

        @completions.command()
        @click.pass_context
        def fish(ctx):
            '''
            Generate a completion script for the Friendly Interactive SHell.
            '''
            self._print_completion(ctx, 'fish')

        @completions.command()
        @click.pass_context
        def zsh(ctx):
            '''
            Generate a Z SHell completion script.
            '''
            self._print_completion(ctx, 'zsh')

    def _print_completion(self, ctx, shell):
        prog = ctx.find_root().info_name
        var = prog.replace('-', '_').upper()

        # https://click.palletsprojects.com/en/8.1.x/shell-completion/#enabling-completion
        import subprocess
        output = subprocess.run(
            (shell, '-c', f'_{var}_COMPLETE={shell}_source {prog}'),
            stdout=subprocess.PIPE,
        )
        click.echo(output.stdout.decode())
