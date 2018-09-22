# Copyright (c) 2018 Alexander Sosedkin <monk@unboiled.info>
# Distributed under the terms of the MIT License, see below:

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
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

import glob
import importlib
import os
import subprocess
import sys


def try_nixpkgs(topmost_name):
    '''
    Try to instantiate python3?Packages.<name>.
    While we're at it, find and also return all the dependencies.
    '''
    try:
        # Determine python version and the attribute
        assert sys.version_info.major == 3
        a = 'python3{}Packages.{}'.format(sys.version_info.minor, topmost_name)

        # Instantiate python3?Packages.<name> attribute
        cmd = ['nix-build', '--no-out-link', '<nixpkgs>', '-A', a]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, check=True)
        derivation_path = result.stdout.decode().rstrip()

        # List all the requisite paths: we'll need them to import our module
        cmd = ['nix-store', '--query', '--requisites', derivation_path]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, check=True)
        deps_derivation_paths = result.stdout.decode().split()

        # Guess sys.path-usable subpaths from them (and flatten the list)
        python_paths = [glob.glob(os.path.join(p, 'lib', 'py*', '*-packages'))
                        for p in [derivation_path] + deps_derivation_paths]
        return sum(python_paths, [])
    except Exception as ex:
        print(ex)  # We're not trying too hard here, do we?


class NixpkgsFinder:
    def find_module(self, module_name, package_path):
        '''
        Checks if python3Packages.<name> exists on `import nixpkgs.<name>...`.
        On success, return a Loader that will make sure to use required paths.
        '''
        if module_name.startswith('nixpkgs.'):
            try_name = module_name.split('.')[1]
            required_paths = try_nixpkgs(try_name)
            if required_paths is not None:  # maybe we can load it, let's try
                return FromExtraPathsLoader(required_paths,
                                            pseudo_namespace='nixpkgs')


class FromExtraPathsLoader:
    def __init__(self, extra_paths, pseudo_namespace=None):
        self.extra_paths = extra_paths
        self.pseudo_namespace = pseudo_namespace

    def load_module(self, name):
        '''
        Imports <name> while temporarily extending sys.path.
        If a pseudo_namespace is specified, and <pseudo_namespace>.<name> is
        requested, simply <name> will be imported as <pseudo_namespace>.<name>.
        '''
        prefix = self.pseudo_namespace + '.' if self.pseudo_namespace else ''
        module_name = name[len(prefix):] if name.startswith(prefix) else name

        old_path, sys.path = sys.path, sys.path + self.extra_paths
        sys.modules[name] = importlib.import_module(module_name)
        sys.path = old_path


sys.meta_path.append(NixpkgsFinder())
