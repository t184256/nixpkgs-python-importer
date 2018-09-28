# nixpkgs-python-importer

## What

An importlib hack that allows `from nixpkgs import somepackage`.

Examples:

    import nixpkgs.scipy.scipy
    from nixpkgs.scipy import scipy
    from nixpkgs.matplotlib.matplotlib import pyplot as plt
    import nixpkgs.matplotlib.matplotlib.pyplot as plt
    from nixpkgs.pillow.PIL import Image


## Why

I am a researcher and I use `python` and `xonsh` interactively a lot.
While I appreciate the purity of Nix, sometimes I really want to violate it
and pull in some dependency into my shell *right now*,
without tearing my session down, editing and rebuilding an environment,
and then recreating my session from history.

A convenient way of spawning a `xonsh` instance with an extra dependency
soothes the nerves a bit, but doesn't really free me from the recreation part.

I started writing a xonsh macro that ended up being a generic Python solution
with a pleasingly nice syntax. I mean, `from nixpkgs.scipy import scipy`.
Ain't that nice?


## How

`importlib` magic

## Try

The quickest way would be

```
nix-shell -p 'python3.withPackages(ps: with ps; [ ( python3.pkgs.buildPythonPackage rec { pname = "nixpkgs"; version="0.2.2"; src = pkgs.python3Packages.fetchPypi { inherit pname version; sha256 = "0gsrd99kkv99jsrh3hckz7ns1zwndi9vvh4465v4gnpz723dd6fj"; }; propagatedBuildInputs = with pkgs.python3Packages; [ pbr pythonix ]; }) ])' --run python
```

then try `from nixpkgs import ` something.
