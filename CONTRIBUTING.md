# Contributors documentation
Check the full contributors (up-to-date) documentation here: https://github.com/ghecko/mandalore-docs

# Wrapper & images (legacy)
- the `main` branch is the stable version. Only Pull Requests are allowed on this branch.
- the `dev` branch is used for active development. This is the bleeding-edge version, but is sometimes not as stable as the `master` (depending on the development cycle).
- the `Mandalore` repository includes the mandalore.py wrapper code base, and features a `mandalore-images` submodule tracking [Mandalore-images](https://github.com/ghecko/mandalore-images).
- changes to the images/dockerfiles/tools/installs must be done on the [Mandalore-images](https://github.com/ghecko/mandalore-images) repo.
- by default, the wrapper pulls the latest pre-built image from the GitHub Container Registry (`ghcr.io/ghecko/mandalore`) for the install and updates
- Automatic image builds are configured as follows
  - `nightly` image is built using the base Dockerfile whenever a commit is made on [Mandalore-images](https://github.com/ghecko/mandalore-images) `dev` branch.
  - `full` image is built using the base Dockerfile whenever a new tag is pushed on [Mandalore-images](https://github.com/ghecko/mandalore-images).
  - `ad`, `osint`, `web` and `light` images are built using specific Dockerfiles whenever a new tag is pushed on [Mandalore-images](https://github.com/ghecko/mandalore-images).
- if you want to locally build your image with your changes, run `mandalore install local`. If you have local changes to the dockerfiles, they won't be overwritten.
- any addition/question/edit/pull request to the wrapper? Feel free to raise issues on this repo, or contribute on the dev branch!
- any addition/question/edit/pull request to the docker images? GOTO [Mandalore-images](https://github.com/ghecko/mandalore-images).

Any other idea that falls outside this scope?
Any question that is left unanswered?
Feel free to reach out, I'll be happy to help and improve things, Mandalore is a community-driven toolkit :rocket:
