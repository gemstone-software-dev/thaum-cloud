# Thaum Cloud

Template **deploy repository** for [**Thaum**](https://github.com/gemstone-software-dev/Thaum): bake `thaum.toml` and related assets into a container image with a **Dockerfile**, then use **GitHub Actions** to build, schema-check, push to a registry, and optionally deploy to an existing cloud target.

This public repo is a **starting point and documentation** for that pattern. The included example targets **Azure Container Apps**; other clouds are planned in the docs tree.

## Documentation

**Full guide (introduction, security posture, Git workflow, quickstarts):**

**https://gemstone-software-dev.github.io/thaum-cloud/**

Build locally from the repo root:

```bash
pip install -r doc/sphinx_config/requirements.txt
make -C doc/sphinx_config html
# open doc/_build/html/index.html
```

Publish to GitHub Pages: run the **Publish documentation** workflow (see [.github/workflows/publish-docs.yml](.github/workflows/publish-docs.yml)), then enable Pages from the `gh-pages` branch.

## Quick start

1. **Fork** this repo or copy it into a **private** repository under your organization (see the docs site—do not use a public deploy repo for production).
2. Edit [thaum.toml](thaum.toml) and [Dockerfile](Dockerfile) (`FROM` image tag, extra `COPY` assets).
3. Follow the **[Azure Container Apps quickstart](https://gemstone-software-dev.github.io/thaum-cloud/quickstart/azure/quickstart_aca.html)** to provision Azure resources, configure Actions secrets/variables, and run [.github/workflows/deploy-aca.yml](.github/workflows/deploy-aca.yml).

Source for the quickstart also lives under [doc/quickstart/azure/quickstart_aca.rst](doc/quickstart/azure/quickstart_aca.rst) and [doc/quickstart/cloud/azure/](doc/quickstart/cloud/azure/).

## Repository layout

| Path | Purpose |
|------|---------|
| [Dockerfile](Dockerfile) | Base Thaum image + baked config |
| [thaum.toml](thaum.toml) | Example deployment config |
| [doc/](doc/) | Sphinx docs and cloud quickstarts |
| [.github/workflows/](.github/workflows/) | Example CI (Azure ACA) |
