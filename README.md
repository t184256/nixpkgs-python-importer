# nixpkgs-python-importer

## What

An importlib hack that allows `from nixpkgs import somepackage`.

Examples:

    import nixpkgs.scipy
    from nixpkgs import scipy
    from nixpkgs.matplotlib import pyplot as plt
    import nixpkgs.matplotlib.pyplot as plt


## Why

I am a researcher and I uses `python` and `xonsh` interactively a lot.
While I appreciate the purity of Nix, sometimes I really want to violate it
and pull in some dependency into my shell *right now*,
without tearing my session down, editing and rebuilding an environment,
and then recreating my session from history.

A convenient way of spawning a `xonsh` instant with an extra dependency
soothes the nerves a bit, but doesn't really free me from the recreation part.

I started writing a xonsh macro that ended up being a generic Python solution
with a pleasingly nice syntax. I mean, `from nixpkgs import scipy`.
Ain't that nice?


## How

`importlib` magic

## Try

TODO
