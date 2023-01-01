{ pkgs ? import <nixpkgs> { } }:
with pkgs;
mkShell {
  packages = [
    python3
  ];
}
