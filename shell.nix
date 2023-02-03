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
with pkgs;
mkShell {
  packages = [
    pipreqs
    (python3.withPackages
      python-packages)
  ];
}
