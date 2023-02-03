{ pkgs ? import <nixpkgs> { } }:
let
  python-packages = p: with p; [
    pandas
    tkinter
    qrcode
    jinja2
    autopep8
    python-frontmatter
  ];
in
pkgs.mkShell {
  packages = [
    (pkgs.python3.withPackages
      python-packages)
  ];
}
