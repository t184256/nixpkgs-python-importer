# nixpkgs-python-importer

## What

An importlib hack that allows `from nixpkgs.pythonpackagename import modulename`.

Examples:

    from nixpkgs.scipy import scipy
    import nixpkgs.scipy.scipy
    from nixpkgs.matplotlib.matplotlib import pyplot as plt
    import nixpkgs.matplotlib.matplotlib.pyplot as plt
    from nixpkgs.pillow.PIL import Image


## Why

I used to be a researcher who used `python` and `xonsh` interactively a lot.
While I appreciate the purity of Nix, sometimes I really want to violate it
and pull in some dependency into my shell *right now*,
without tearing my session down, editing and rebuilding an environment,
and then recreating my session from history.

A convenient way of spawning a `xonsh` instance with an extra dependency
soothes the nerves a bit, but doesn't really free me from the recreation part.

I started writing a `xonsh` macro that ended up being a generic Python solution
with a pleasingly nice syntax. I mean, `from nixpkgs.scipy import scipy`.
Ain't that nice?


## How

`importlib` magic


## Try

The quickest way to try it would be (on a recent NixOS):

```
nix run '(import <nixpkgs> {}).python3.withPackages(ps:[ps.nixpkgs])' -c python
```
then try `from nixpkgs.pbr import pbr` (or any other package).


If that doesn't work, you may also try your luck with unstable nixpkgs:

```
nix run -f channel:nixos-unstable '(import <nixpkgs> {}).python3.withPackages(ps:[ps.nixpkgs])' -c python
```
