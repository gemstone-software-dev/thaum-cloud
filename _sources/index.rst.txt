Thaum Cloud
===========

**Thaum Cloud** is a **template deploy repository** for running `Thaum <https://github.com/gemstone-software-dev/Thaum>`_ on public-cloud platforms where organizational configuration should be **baked into the container image** rather than mounted at runtime.

A **Dockerfile** copies ``thaum.toml`` (and any bundled assets) into the image. **GitHub Actions** builds that image, runs a blocking **schema check**, pushes to a container registry, and—depending on the cloud quickstart—can update an **existing** deployment target. Cloud-specific provisioning (environments, secrets stores, identity) lives in the **quickstart guides** below; this repository ships an **Azure Container Apps** example today, with room for additional clouds.


Who this is for
---------------

Use this pattern when you want Thaum configuration and delivery **separate from** the upstream Thaum source tree: pin a base image version in the Dockerfile, keep org-specific settings in your own repository, and use CI as the path from commit to registry (and optional deploy).

Each quickstart documents what the included workflows **assume already exists** (for example, a named Container App) versus what you provision with CLI or your platform team.


Public template, private production
------------------------------------

For real organizational deployments, maintain your config and CI in a **private** GitHub repository. Deploy repos bake organizational configuration into the image; mistaken sensitive values can land in **git** history, and **revert** does not erase prior commits.

Treat **this public copy** as documentation and starting content only. Production deploys **must not** rely on this repository as their long-lived canonical remote unless you knowingly accept those risks—**fork** or copy into a **private** repo under your organization instead.

The Azure quickstart states formal requirements (RFC-style **MUST** / **MUST NOT**) for private repos, private registry packages, and machine-user tokens: :ref:`azure-aca-requirements`.


Adopt this template
-------------------

Pick one starting path:

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - Approach
     - Typical use
   * - **Fork**
     - Easier comparisons and occasional merges from this template; GitHub keeps a visible “forked from” relationship.
   * - **`git archive` or source download + new repo**
     - Unpack without the template’s ``.git`` history and run ``git init`` (push to your private remote); no fork metadata, fully detached copy if you prefer that posture.

After you have **your own** repo: edit ``thaum.toml``, adjust the Dockerfile ``FROM`` line to your desired Thaum image tag or digest, and add any extra assets the Dockerfile should ``COPY``.


CI and release discipline
-------------------------

Example workflows validate configuration with ``--schema-check``, build and push an image, and optionally run a deploy job against infrastructure that **already exists**. Trigger behavior varies by workflow file; the stock Azure example (``.github/workflows/deploy-aca.yml``) supports:

- **`workflow_dispatch`** — manual runs; deploy is typically gated behind a run form option.
- **`push` to `main`** — often **commented out** in the template; uncomment when you want merges to ``main`` to drive builds (and, with default conditions, deploys).

Verify the workflow file in your fork if behavior drifts from this summary.


Recommended Git workflow when ``push`` to ``main`` is enabled
-------------------------------------------------------------

Many organizations treat **``main``** as the branch whose pushes **build**, push to the registry, and—with default workflow conditions—**update the live deployment** on every merge. They avoid committing small ``thaum.toml`` or asset tweaks directly to ``main`` on every save, because each push would consume CI minutes and advance the live image unintentionally.

A common pattern:

1. Keep a **long-lived branch** for day-to-day config work—often named ``update``, ``config``, or similar (the name is up to your team).
2. **Commit** configuration and Dockerfile changes there as often as you like.
3. When you are ready to ship, open a **pull request** (or otherwise review) and **merge into ``main``**. That merge is the deliberate boundary that triggers the ``push`` to ``main`` workflow.

Optional hardening: protect ``main`` in GitHub so direct pushes are disallowed and changes land only via PR, matching the boundary above.

This workflow is **optional** and **independent** of tracking the public example template (no ``upstream`` merge required). If you rely only on ``workflow_dispatch``, use PRs for review if you want, but remember that **running** the workflow is still a separate step unless you enable ``push``.


Repository layout
-----------------

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - Path
     - Purpose
   * - ``Dockerfile``
     - Base Thaum image + copy ``thaum.toml`` (and bundled assets) into the image
   * - ``thaum.toml``
     - Deployment configuration baked at ``/etc/thaum/thaum.toml``
   * - ``doc/``
     - Sphinx documentation (this site) and cloud quickstarts
   * - ``.github/workflows/``
     - Example CI (Azure ACA in this template)
   * - ``incident_prompt_card.j2``, ``static/``
     - Example assets referenced from ``thaum.toml`` / Dockerfile


Quickstarts
-----------

Cloud-specific golden paths (provisioning, secrets, registry pull identity, logging) are in the guides below. Start with the Azure guide for the workflow files included in this template.


.. toctree::
   :maxdepth: 2
   :caption: Quickstarts

   quickstart/azure/quickstart_aca
