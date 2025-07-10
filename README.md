> Mandalore is a community-driven hacking environment, powerful and yet simple enough to be used by anyone in day to day engagements. Mandalore is the best solution to deploy powerful hacking environments securely, easily, professionally.
> Mandalore is a fork of **Exegol** before version 5 and will always remain free, continuing the original philosophy with a focus on usability, extensibility, and community contribution.
> Mandalore fits pentesters, CTF players, bug bounty hunters, researchers, beginners and advanced users, defenders, from stylish macOS users and corporate Windows pros to UNIX-like power users.

# Getting started

You can refer to the [Mandalore documentation](https://mandalore.readthedocs.io/en/latest/getting-started/install.html).

> Full documentation homepage: https://mandalore.rtfd.io/.

## Project structure

Below are some bullet points to better understand how Mandalore works
- This repository ([Mandalore](https://github.com/ghecko/mandalore)) contains the code for the Python wrapper. It's the entrypoint of the Mandalore project. The wrapper can be installed from sources, using pipy.
- The [Mandalore-images](https://github.com/ghecko/mandalore-images) repo is loaded as a submodule. It includes all necessary assets to build Docker images. Notabene: the image are already built and offered on [the official Dockerhub registry](N/A).
- The [Mandalore-resources](https://github.com/ghecko/mandalore-resources) repo is loaded as a submodule. It includes all resources mentioned previously (LinPEAS, WinPEAS, LinEnum, PrivescCheck, SysinternalsSuite, mimikatz, Rubeus, PowerSploit and many more.).
- The [Mandalore-docs](https://github.com/ghecko/mandalore-docs) repo for the documentation, destined for users as well as developpers and contributors.
