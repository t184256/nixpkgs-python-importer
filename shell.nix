with import <nixpkgs> {};

mkShell {
  buildInputs = [
    (python3.withPackages(ps: with ps; [
      pythonix
      flake8
      jedi
      epc
    ]))
  ];
}
