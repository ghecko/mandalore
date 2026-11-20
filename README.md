> Mandalore is a community-driven hacking environment, powerful and yet simple enough to be used by anyone in day to day engagements. Mandalore is the best solution to deploy powerful hacking environments securely, easily, professionally.
> Mandalore is a fork of [**Exegol**](https://github.com/ThePorgs/Exegol), started from version 4.3.12 (the GPLv3 code base, before the licence change of Exegol 5). It will always remain free, continuing the original philosophy with a focus on usability, extensibility, and community contribution. Credits for the original project go to the Exegol authors and contributors.
> Mandalore fits pentesters, CTF players, bug bounty hunters, researchers, beginners and advanced users, defenders, from stylish macOS users and corporate Windows pros to UNIX-like power users.

# Getting started

You can refer to the [Mandalore documentation](https://ghecko.github.io/mandalore-docs/).

## Project structure

Below are some bullet points to better understand how Mandalore works
- This repository ([Mandalore](https://github.com/ghecko/mandalore)) contains the code for the Python wrapper. It's the entrypoint of the Mandalore project. The wrapper can be installed from sources, using PyPI.
- The [Mandalore-images](https://github.com/ghecko/mandalore-images) repo is loaded as a submodule. It includes all necessary assets to build Docker images. Notabene: the images are pre-built and published on the [GitHub Container Registry](https://github.com/ghecko/mandalore/pkgs/container/mandalore) (`ghcr.io/ghecko/mandalore`).
- The [Mandalore-resources](https://github.com/ghecko/mandalore-resources) repo is loaded as a submodule. It includes all resources mentioned previously (LinPEAS, WinPEAS, LinEnum, PrivescCheck, SysinternalsSuite, mimikatz, Rubeus, PowerSploit and many more.).
- The [Mandalore-docs](https://github.com/ghecko/mandalore-docs) repo for the documentation, destined for users as well as developpers and contributors.
