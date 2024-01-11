#---------------------------------------------------------------------------------------------------
__all__ = ()

import code
import collections
import importlib, importlib.util
import pathlib
import sys

try:
    import click
except ImportError:
    click = None

try:
    import IPython
except ImportError:
    IPython = None

_ptipython = None
try:
    import ptpython as _ptpython
except ImportError:
    _ptpython = None
else:
    if IPython is not None:
        import ptpython.ipython as _ptipython

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
            value.___context___.kargs['qualname_base'] = (
                self._name + '.' + name, len(value.___node___.path))
            self._proxies[name] = value

    def __delattr__(self, name):
        value = getattr(self, name, None)
        super().__delattr__(name)
        if name in self._proxies:
            del value.___context___.kargs['qualname_base']
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

    def dump(self):
        # Perform a verbose dump of all proxies.
        with self:
            for vn, v in self._variables.items():
                for pn, p in v._proxies.items():
                    print(p(...))

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
        if IPython is None:
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
        if _ptpython is None:
            raise NotImplementedError('Missing ptpython module.')

        # Create the shell or re-use the previously cached one. This allows maintaining state
        # between invocations.
        try:
            shell = self._ptpython_shell
        except AttributeError:
            shell = _ptpython.repl.PythonRepl(
                get_globals=lambda: self._namespace,
                get_locals=lambda: self._namespace)
            self._ptpython_shell = shell

        # Run the interactive shell.
        with self:
            shell.run()

    def ptipython_shell(self):
        if _ptipython is None:
            raise NotImplementedError('Missing ptpython and/or IPython module(s).')

        try:
            shell = self._ptipython_shell
        except AttributeError:
            shell = _ptipython.InteractiveShellEmbed()
            self._ptipython_shell = shell

        # Run the interactive shell.
        with self:
            shell(local_ns=self._namespace, module=self._mod)

#---------------------------------------------------------------------------------------------------
class ClickEnvironment(Environment):
    def __init__(self, parent, *pargs, **kargs):
        super().__init__(*pargs, **kargs)

        if click is None:
            raise NotImplementedError('Missing click module.')
        self._add_click_commands(parent)

    def _add_click_commands(self, parent):
        @parent.command()
        def dump():
            '''
            Read and display all registers from all register map specifications.
            '''
            self.dump()

        @parent.command()
        @click.argument('expressions', nargs=-1)
        def eval(expressions):
            '''
            Evaluate a sequence of Python expressions within the context of the loaded register
            map specifications and display the result of each.
            '''
            self.eval(expressions)

        @parent.command()
        @click.argument('path')
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

        if IPython is not None:
            @shell.command()
            def ipython():
                '''
                Enter the IPython shell.
                '''
                self.ipython_shell()

        if _ptpython is not None:
            @shell.command()
            def ptpython():
                '''
                Enter the Prompt Toolkit shell.
                '''
                self.ptpython_shell()

        if _ptipython is not None:
            @shell.command()
            def ptipython():
                '''
                Enter the Prompt Toolkit IPython shell.
                '''
                self.ptipython_shell()
