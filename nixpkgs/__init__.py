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
import nix
import glob
import importlib
import os
import subprocess
import functools
import sys


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
        store_paths = nix.eval("""
          with import <nixpkgs> {}; let
            getClosure = drv: let
              propagated = if (lib.hasAttr "propagatedBuildInputs" drv) then
                (builtins.filter (x: x != null) drv.propagatedBuildInputs)
                else [];
            in lib.foldl (acc: v: acc ++ getClosure v) [ drv ] propagated;
          in builtins.map (drv: "${drv}") (lib.unique (getClosure python3%sPackages.%s))
        """ % (sys.version_info.minor, module_name))

        # Build/download path
        cmd = ['nix-store', '--realise', '--quiet', store_paths[0]]
        subprocess.run(cmd, stdout=subprocess.PIPE, check=True)

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
    def __init__(self, name):
        self.__name__ = name

    def __repr__(self):
        return ''.join((
            '<nixpkgs.NixPackage [',
            ', '.join('\'%s\'' % attr for attr in dir(self) if not attr.startswith('_')),
            ']>',
        ))

    __path__ = []


class FromExtraPathsLoader:
    def __init__(self, extra_paths):
        self.extra_paths = extra_paths

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

            if f.endswith('.py'):
                yield f.rstrip('.py')

            if f.endswith('.egg'):
                yield f.split('-')[0]

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
                    # Insert as both eg PIL and nixpkgs.pillow.PIL
                    # The python module system assumes that a module will be
                    # available under the exact imported path
                    #
                    # We also want to make it available as `import PIL`
                    sys.modules[python_mod_path] = mod
                    sys.modules[name] = mod
        finally:
                sys.path = old_path


sys.meta_path.append(NixpkgsFinder())
