# Copyright (c) 2018 Alexander Sosedkin <monk@unboiled.info>
# Distributed under the terms of the MIT License, see below:

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

'''
An importlib hack that allows `from nixpkgs import somepackage`.
Examples:
    import nixpkgs.scipy
    from nixpkgs import scipy
    from nixpkgs.matplotlib import pyplot as plt
    import nixpkgs.matplotlib.pyplot as plt
It works by instantiating the required derivations with 'nix-build',
temporarily monkey-patching the sys.path and importing them.
'''

import functools
import glob
import hashlib
import importlib
import os
import site
import sys

import nix


@functools.lru_cache()
def try_nixpkgs(topmost_name):
    '''
    Try to instantiate python3?Packages.<name>.
    While we're at it, find and also return all the dependencies.
    '''
    try:
        assert sys.version_info.major == 3
        # Instantiate python3Packages.<name>
        # Returns a list of store paths where the first one is the module path
        module_name = topmost_name
        attr_path = "python3%sPackages.%s" % (
            sys.version_info.minor,
            module_name
        )
        store_paths = nix.eval("""
          with import <nixpkgs> {}; let
            getClosure = drv: let
              propagated = if (lib.hasAttr "propagatedBuildInputs" drv) then
                (builtins.filter (x: x != null) drv.propagatedBuildInputs)
                else [];
            in lib.foldl (acc: v: acc ++ getClosure v) [ drv ] propagated;
          in builtins.map (drv: "${drv}") (lib.unique (getClosure %s))
        """ % attr_path)

        # Build/download path
        if not os.path.exists(store_paths[0]):
            # Abuse IFD to realise store path
            # Try to import a file that will never exist
            dummy_file = hashlib.sha1(attr_path.encode()).hexdigest()
            try:
                nix.eval("""
                  with import <nixpkgs> {};
                  import "${%s}/%s.nix"
                """ % (attr_path, dummy_file))
            except nix.NixError as ex:
                # This is expected.
                # What really matters now is whether the store path exists.
                # If it does, the realization was a success.
                # Otherwise, it's likely a missing/misspelt derivation name
                if not os.path.exists(store_paths[0]):
                    raise ex

        # Guess sys.path-usable subpaths from them (and flatten the list)
        return sum((
            glob.glob(os.path.join(p, 'lib', 'py*', '*-packages'))
            for p in store_paths
        ), [])

    except Exception as e:
        raise ImportError(e)


class NixpkgsFinder:
    def find_module(self, module_name, package_path):
        '''
        Checks if python3Packages.<name> exists on `import nixpkgs.<name>...`.
        On success, return a Loader that will make sure to use required paths.
        '''
        if module_name.startswith('nixpkgs.'):
            try_name = module_name.split('.')[1]
            required_paths = try_nixpkgs(try_name)
            if required_paths:
                return FromExtraPathsLoader(required_paths)


class NixPackage:
    """
    Returned in place of an actual module
    Used to supply a namespace for all python modules in a nix package
    """
    def __init__(self, name, doc=None):
        self.__name__ = name
        if doc is not None:
            self.__doc__ = doc

    def __repr__(self):
        return ''.join((
            '<nixpkgs.NixPackage [',
            ', '.join('\'%s\'' % attr
                      for attr in dir(self)
                      if not attr.startswith('_')),
            ']>',
        ))

    __path__ = []


class FromExtraPathsLoader:
    def __init__(self, extra_paths):
        self.extra_paths = []
        for path in extra_paths:
            self._add_path(path)

    def _add_path(self, path):
        # The simple way is to
        self.extra_paths.append(path)
        # The roadblock is that paths can contain .pth files,
        # that should be parsed and processed too:
        # https://docs.python.org/3/library/site.html
        # While the format is simple enough, let's not reinvent the wheel,
        # but pile up another hacky hack and reuse site.addsitedir.
        old_path, sys.path = sys.path, sys.path[:]
        site.addsitedir(path)  # resolves .pth files, adds them to sys.path
        sys_path_delta = [p for p in sys.path if p not in old_path]
        sys.path = old_path
        self.extra_paths.extend(sys_path_delta)

    def _filter_modules(self):
        base_path = self.extra_paths[0]
        for f in os.listdir(base_path):
            if any((
                    f.startswith('.'),
                    f == '__pycache__',
                    f.endswith('.dist-info'))):
                continue

            full_path = os.path.join(base_path, f)
            if os.path.isdir(full_path):
                yield f
                continue

            if f.endswith('.egg'):
                yield f.split('-')[0]

            root, ext = os.path.splitext(f)
            if ext in ('.py', '.so'):
                yield root

    def load_module(self, name):
        '''
        Imports <name> while temporarily extending sys.path.
        '''
        module_path = name.split('.')
        python_mod = module_path[2::]

        # Create a root dummy module (NixPackage) so nested imports
        # `from nixpkgs.pillow import PIL` will work
        old_path, sys.path = sys.path, sys.path + self.extra_paths
        try:
            if not python_mod:
                pkg = NixPackage(name)
                for module_name in self._filter_modules():
                    mod = importlib.import_module(module_name)
                    setattr(pkg, module_name, mod)
                    sys.modules[name] = pkg
            else:
                try:
                    python_mod_path = '.'.join(python_mod)
                    mod = importlib.import_module(python_mod_path)
                except (ImportError, ModuleNotFoundError):
                    pass
                else:
                    # The python module system assumes that a module will be
                    # available under the exact imported path
                    sys.modules[name] = mod
        finally:
                sys.path = old_path


def init_module():
    """
    Initialise module

    This creates completions with docstrings for all derivations in the python package set
    """

    attr_path = "python3%sPackages" % sys.version_info.minor
    expr = """
      with import <nixpkgs> {}; let
        drvAttrs = lib.filterAttrs (k: v: (builtins.tryEval v).success && builtins.typeOf v == "set") %s;
        meta = builtins.mapAttrs (k: v: if builtins.hasAttr "meta" v then v.meta else {}) drvAttrs;
      in builtins.mapAttrs (k: v: if builtins.hasAttr "description" v then v.description else "") meta
    """ % attr_path

    g = globals()
    for attr, desc in nix.eval(expr).items():
        if attr not in g:
            g[attr] = NixPackage(attr, doc=desc)


sys.meta_path.append(NixpkgsFinder())
