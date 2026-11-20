# Contributors documentation
Check the full contributors (up-to-date) documentation here: https://ghecko.github.io/mandalore-docs/community/contributors.html

# Wrapper & images
- the `main` branch is the stable version. Changes are made in feature branches and merged through Pull Requests.
- the `Mandalore` repository includes the mandalore.py wrapper code base, and features a `mandalore-images` submodule tracking [Mandalore-images](https://github.com/ghecko/mandalore-images).
- changes to the images/dockerfiles/tools/installs must be done on the [Mandalore-images](https://github.com/ghecko/mandalore-images) repo.
- by default, the wrapper pulls the latest pre-built image from the GitHub Container Registry (`ghcr.io/ghecko/mandalore`) for the install and updates
- images are built with the `Makefile` of [Mandalore-images](https://github.com/ghecko/mandalore-images) and pushed manually to the GitHub Container Registry (there is no automatic image build pipeline).
- if you want to locally build your image with your changes, run `mandalore install local`. If you have local changes to the dockerfiles, they won't be overwritten.
- any addition/question/edit/pull request to the wrapper? Feel free to raise issues on this repo, or open a pull request on the main branch!
- any addition/question/edit/pull request to the docker images? GOTO [Mandalore-images](https://github.com/ghecko/mandalore-images).

Any other idea that falls outside this scope?
Any question that is left unanswered?
Feel free to reach out, I'll be happy to help and improve things, Mandalore is a community-driven toolkit :rocket:
