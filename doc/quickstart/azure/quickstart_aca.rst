=====================================
Azure Container Apps Quickstart
=====================================

.. _azure-aca-quickstart:

Run **Thaum** on **Azure Container Apps** with **GitHub Container Registry (GHCR)**, **OIDC** deploy (``deploy-aca.yml``), **Azure Key Vault** for application secrets, and **Log Analytics** for platform and container logs.

**Golden path:** private deploy repository, **private** GHCR package, machine-user ``GHCR_PULL_*`` on the Container App, Entra **federated credentials** for GitHub Actions—no Azure client secret in GitHub.

Example artifacts (Dockerfile, optional ACR workflow) live under ``azure/github/``.

Microsoft reference for ACA secrets: `Manage secrets in Azure Container Apps <https://learn.microsoft.com/en-us/azure/container-apps/manage-secrets?tabs=azure-cli>`_ (``keyvaultref``, volumes, ``secretref``).

**Naming:** Key Vault secret names use alphanumeric characters and hyphens. Container Apps secret names **must** be lowercase and at most **20 characters**. Use **kebab-case** so names align across Key Vault, ACA secrets, and ``secret:<name>`` in ``thaum.toml``.


.. _azure-aca-requirements:

Requirements for this deployment pattern
==========================================

The keywords **MUST** and **MUST NOT** are interpreted as described in `RFC 2119 <https://www.rfc-editor.org/info/rfc2119>`_. They apply only to repositories that use this Actions + ACA workflow.

- The **deploy repository** (bakes ``thaum.toml`` into the image via ``Dockerfile`` and CI) **MUST** be **private** on the Git host. A **public** deploy repository **MUST NOT** be used for this pattern.
- The **GHCR package** for that image lineage **MUST** be **private**.
- Credentials for ACA to **pull** the package **MUST** use a PAT owned by a **machine user** (`dedicated automation account <https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys#machine-users>`_), not a personal PAT. Store it only as repository secret ``GHCR_PULL_PAT``; **MUST NOT** commit tokens to tracked files.


What you get
============

.. list-table::
   :header-rows: 1
   :class: wrap-table

   * - Aspect
     - Behavior
   * - **Topology**
     - One resource group, one Container Apps **environment** (with Log Analytics), one Container App
   * - **Registry**
     - **GHCR**; CI pushes with ``GITHUB_TOKEN``; ACA pulls with machine-user ``GHCR_PULL_PAT``
   * - **Deploy identity**
     - **OIDC** to Azure—no Entra client secret in GitHub
   * - **App secrets**
     - **Key Vault** + user-assigned managed identity (UAMI) + ``keyvaultref`` on the Container App
   * - **Default database**
     - Bundled PostgreSQL in the image (``THAUM_EXTERNAL_DB`` unset). Ephemeral disk—data can be lost on revision/restart unless you add storage or an external database
   * - **Logging**
     - **Log Analytics workspace** wired to the Container Apps environment (console/system logs)


Prerequisites
=============

- Azure subscription with rights to create resource groups, Log Analytics, Container Apps, Key Vault, managed identities, and to **assign RBAC** and **write** Key Vault secrets for whoever runs provisioning.
- **Bash:** `Azure CLI <https://learn.microsoft.com/cli/azure/install-azure-cli>`_ (``az login``) with the ``containerapp`` extension.
- **PowerShell:** `Az PowerShell modules <https://learn.microsoft.com/powershell/azure/install-azure-powershell>`_ — at least ``Az.Accounts``, ``Az.Resources``, ``Az.Monitor``, ``Az.KeyVault``, ``Az.ManagedServiceIdentity``, ``Az.App``. Sign in with ``Connect-AzAccount``; select subscription with ``Set-AzContext -SubscriptionId ...``.
- `Docker <https://docs.docker.com/get-docker/>`_ for local image build and schema check.
- A **private** GitHub deploy repository (see :ref:`azure-aca-requirements`).

Set these placeholders consistently in every command below:

+---------------------+----------------------------------------------------------+
| Placeholder         | Meaning                                                  |
+=====================+==========================================================+
| ``SUBSCRIPTION_ID`` | Azure subscription GUID                                  |
+---------------------+----------------------------------------------------------+
| ``LOCATION``        | Region (e.g. ``eastus``)                                 |
+---------------------+----------------------------------------------------------+
| ``RESOURCE_GROUP``  | Resource group name (``RG`` in some examples)            |
+---------------------+----------------------------------------------------------+
| ``WORKSPACE``       | Log Analytics workspace name (e.g. ``thaum-logs``)       |
+---------------------+----------------------------------------------------------+
| ``ENVIRONMENT``     | Container Apps environment name (e.g. ``thaum-env``)     |
+---------------------+----------------------------------------------------------+
| ``APP_NAME``        | Container App name                                       |
+---------------------+----------------------------------------------------------+
| ``VAULT_NAME``      | Key Vault name (globally unique)                         |
+---------------------+----------------------------------------------------------+
| ``OWNER`` / ``REPO`` | GitHub repository ``owner/repo``                        |
+---------------------+----------------------------------------------------------+


.. _azure-aca-step1:

Step 1 — Resource group, Log Analytics, Container Apps environment
==================================================================

Register resource providers and create the resource group.

.. tab-set::
   :sync-group: aca-shell

   .. tab-item:: Bash
      :sync: bash

      .. code-block:: bash

         az account set --subscription "SUBSCRIPTION_ID"

         az extension add --name containerapp --upgrade 2>/dev/null || true

         az provider register --namespace Microsoft.App
         az provider register --namespace Microsoft.OperationalInsights
         az provider register --namespace Microsoft.KeyVault
         # Optional: wait until Registered
         az provider show --namespace Microsoft.KeyVault --query registrationState -o tsv

         az group create --name "$RESOURCE_GROUP" --location "$LOCATION"

   .. tab-item:: PowerShell
      :sync: powershell

      .. code-block:: powershell

         Set-AzContext -Subscription "SUBSCRIPTION_ID"

         Register-AzResourceProvider -ProviderNamespace Microsoft.App
         Register-AzResourceProvider -ProviderNamespace Microsoft.OperationalInsights
         Register-AzResourceProvider -ProviderNamespace Microsoft.KeyVault

         New-AzResourceGroup -Name $RESOURCE_GROUP -Location $LOCATION


Create a **Log Analytics workspace**, then a Container Apps **environment** that sends logs to it (``--logs-workspace-id`` is the workspace **ARM resource ID**).

.. tab-set::
   :sync-group: aca-shell

   .. tab-item:: Bash
      :sync: bash

      .. code-block:: bash

         az monitor log-analytics workspace create \
           --resource-group "$RESOURCE_GROUP" \
           --workspace-name "$WORKSPACE" \
           --location "$LOCATION"

         LOG_ANALYTICS_ID=$(az monitor log-analytics workspace show \
           --resource-group "$RESOURCE_GROUP" \
           --workspace-name "$WORKSPACE" \
           --query id -o tsv)

         az containerapp env create \
           --name "$ENVIRONMENT" \
           --resource-group "$RESOURCE_GROUP" \
           --location "$LOCATION" \
           --logs-workspace-id "$LOG_ANALYTICS_ID"

   .. tab-item:: PowerShell
      :sync: powershell

      .. code-block:: powershell

         New-AzOperationalInsightsWorkspace -ResourceGroupName $RESOURCE_GROUP `
           -Name $WORKSPACE -Location $LOCATION | Out-Null

         $customerId = (Get-AzOperationalInsightsWorkspace `
           -ResourceGroupName $RESOURCE_GROUP -Name $WORKSPACE).CustomerId
         $sharedKey = (Get-AzOperationalInsightsWorkspaceSharedKey `
           -ResourceGroupName $RESOURCE_GROUP -Name $WORKSPACE).PrimarySharedKey

         New-AzContainerAppManagedEnv -Name $ENVIRONMENT `
           -ResourceGroupName $RESOURCE_GROUP -Location $LOCATION `
           -AppLogConfigurationDestination "log-analytics" `
           -LogAnalyticConfigurationCustomerId $customerId `
           -LogAnalyticConfigurationSharedKey $sharedKey


.. _azure-aca-keyvault-uami:

Step 2 — Key Vault and user-assigned managed identity
=====================================================

Store Thaum credential **values** in **Key Vault**. The Container App resolves them at runtime via ``keyvaultref`` and a **user-assigned** managed identity (UAMI). Microsoft recommends UAMI over system-assigned identity when attaching during or after create.

Grant operator access and create secrets
----------------------------------------

.. tab-set::
   :sync-group: aca-shell

   .. tab-item:: Bash
      :sync: bash

      .. code-block:: bash

         az keyvault create --name "$VAULT_NAME" --resource-group "$RESOURCE_GROUP" --location "$LOCATION"

         KV_ID=$(az keyvault show --name "$VAULT_NAME" --resource-group "$RESOURCE_GROUP" --query id -o tsv)
         MY_OID=$(az ad signed-in-user show --query id -o tsv)

         az role assignment create \
           --role "Key Vault Secrets Officer" \
           --assignee-object-id "$MY_OID" \
           --assignee-principal-type User \
           --scope "$KV_ID"

         # Prefer --file to avoid secrets on the command line; delete the file after use
         az keyvault secret set --vault-name "$VAULT_NAME" --name webex-token-database --file ./webex-token-database.txt

   .. tab-item:: PowerShell
      :sync: powershell

      .. code-block:: powershell

         New-AzKeyVault -Name $VAULT_NAME -ResourceGroupName $RESOURCE_GROUP -Location $LOCATION

         $kv = Get-AzKeyVault -VaultName $VAULT_NAME -ResourceGroupName $RESOURCE_GROUP
         $ctx = Get-AzContext
         $myObjId = (Get-AzADUser -UserPrincipalName $ctx.Account.Id).Id

         New-AzRoleAssignment -ObjectId $myObjId `
           -RoleDefinitionName "Key Vault Secrets Officer" -Scope $kv.ResourceId

         $raw = Get-Content -Raw "./webex-token-database.txt"
         $sec = ConvertTo-SecureString $raw -AsPlainText -Force
         Set-AzKeyVaultSecret -VaultName $VAULT_NAME -Name "webex-token-database" -SecretValue $sec


Create the UAMI and grant **Key Vault Secrets User** on the vault:

.. tab-set::
   :sync-group: aca-shell

   .. tab-item:: Bash
      :sync: bash

      .. code-block:: bash

         UAMI_ID=$(az identity create --name "thaum-aca-secrets" \
           --resource-group "$RESOURCE_GROUP" --location "$LOCATION" --query id -o tsv)
         UAMI_PRINCIPAL=$(az identity show --ids "$UAMI_ID" --query principalId -o tsv)

         az role assignment create \
           --role "Key Vault Secrets User" \
           --assignee-object-id "$UAMI_PRINCIPAL" \
           --assignee-principal-type ServicePrincipal \
           --scope "$KV_ID"

   .. tab-item:: PowerShell
      :sync: powershell

      .. code-block:: powershell

         $uami = New-AzUserAssignedIdentity -ResourceGroupName $RESOURCE_GROUP `
           -Name "thaum-aca-secrets" -Location $LOCATION
         $UAMI_ID = $uami.Id
         $uamiPrincipal = $uami.PrincipalId

         New-AzRoleAssignment -ObjectId $uamiPrincipal `
           -RoleDefinitionName "Key Vault Secrets User" -Scope $kv.ResourceId


.. note::

   **``keyvaultref`` URI:** ``https://<vault>.vault.azure.net/secrets/<name>`` (latest) or append ``/<version-id>`` to pin a version. Optional helper: ``azure/github/scripts/keyvault-uri.ps1.example``.


.. _azure-aca-container-app:

Step 3 — Container App (placeholder → secrets → Thaum image)
============================================================

**Private GHCR** and ``keyvaultref`` require a **split** flow:

1. Create the app on a **public placeholder** image.
2. Attach the UAMI.
3. Define ACA secrets pointing at Key Vault.
4. Update to the real Thaum image, registry credentials, volume mount, and environment variables.
5. Update ingress to port **5165** (separate from ``containerapp update``).

3.1 — Placeholder image and UAMI
---------------------------------

Resolve the managed environment resource ID, then create the app and assign identity.

.. tab-set::
   :sync-group: aca-shell

   .. tab-item:: Bash
      :sync: bash

      .. code-block:: bash

         ENV_ID=$(az containerapp env show -g "$RESOURCE_GROUP" -n "$ENVIRONMENT" --query id -o tsv)
         PLACEHOLDER="mcr.microsoft.com/azuredocs/aci-helloworld:latest"

         az containerapp create \
           --name "$APP_NAME" \
           --resource-group "$RESOURCE_GROUP" \
           --environment "$ENV_ID" \
           --image "$PLACEHOLDER" \
           --ingress external \
           --target-port 80

         az containerapp identity assign \
           --name "$APP_NAME" \
           --resource-group "$RESOURCE_GROUP" \
           --user-assigned "$UAMI_ID"

   .. tab-item:: PowerShell
      :sync: powershell

      .. code-block:: powershell

         $envId = (Get-AzContainerAppManagedEnv `
           -ResourceGroupName $RESOURCE_GROUP -Name $ENVIRONMENT).Id
         $placeholder = "mcr.microsoft.com/azuredocs/aci-helloworld:latest"

         New-AzContainerApp -Name $APP_NAME -ResourceGroupName $RESOURCE_GROUP `
           -ManagedEnvironmentId $envId -Image $placeholder `
           -IngressExternal -TargetPort 80

         Update-AzContainerApp -Name $APP_NAME -ResourceGroupName $RESOURCE_GROUP `
           -IdentityType "UserAssigned" -UserAssignedIdentity @($UAMI_ID)

.. tip::

   If ``New-AzContainerApp`` / ``Update-AzContainerApp`` parameters differ in your ``Az.App`` version, run the Bash ``az containerapp`` block; the ARM result is the same.


3.2 — Application secrets (``keyvaultref``)
--------------------------------------------

Use **Azure CLI** for ``keyvaultref`` quoting (works from Bash or PowerShell):

.. code-block:: bash

   SECRET_URI="https://${VAULT_NAME}.vault.azure.net/secrets/webex-token-database"

   az containerapp secret set \
     --name "$APP_NAME" \
     --resource-group "$RESOURCE_GROUP" \
     --secrets "webex-token-database=keyvaultref:${SECRET_URI},identityref:${UAMI_ID}"

Repeat with additional space-separated ``--secrets "name=..."`` pairs for each credential.

In ``thaum.toml``, reference ``secret:webex-token-database`` (matching the ACA secret name). See :ref:`azure-aca-file-vs-env-secrets`.


3.3 — Real image, volume mount, registry, ingress
-------------------------------------------------

Mount secrets under ``/run/secrets`` and set ``THAUM_CREDS_DIR`` so the Thaum ``entrypoint.sh`` can copy files for user ``thaum``.

.. important::

   ``az containerapp update`` does **not** accept ``--target-port``. After switching from the placeholder (port 80) to Thaum (5165), run ``az containerapp ingress update`` separately.

.. tab-set::
   :sync-group: aca-shell

   .. tab-item:: Bash
      :sync: bash

      .. code-block:: bash

         IMAGE="ghcr.io/your-org/your-repo:your-tag"

         az containerapp update \
           --name "$APP_NAME" \
           --resource-group "$RESOURCE_GROUP" \
           --image "$IMAGE" \
           --registry-server ghcr.io \
           --registry-username "MACHINE_USER_LOGIN" \
           --registry-password "MACHINE_USER_READ_PACKAGES_PAT" \
           --secret-volume-mount "/run/secrets" \
           --set-env-vars "THAUM_CREDS_DIR=/tmp/thaum-creds"

         az containerapp ingress update \
           --name "$APP_NAME" \
           --resource-group "$RESOURCE_GROUP" \
           --target-port 5165

   .. tab-item:: PowerShell
      :sync: powershell

      Run the same ``az containerapp update`` and ``az containerapp ingress update`` commands from the Bash tab (recommended). Alternatively, use your ``Az.App`` version’s ingress surface (``Get-Help Update-AzContainerApp``, ``Get-Command *ContainerApp*Ingress*``) to set **target port** to **5165** after updating image, registry, and env/volume flags—do not pass target port on ``Update-AzContainerApp`` if the cmdlet rejects it.

For bootstrap only, you may run ``secret set`` before this update and temporarily keep the placeholder image and port 80; the final revision must use Thaum on **5165**.


3.4 — CI registry credentials vs ACA pull secret
------------------------------------------------

The PAT in ``containerapp update`` is the machine-user ``read:packages`` token (same class as ``GHCR_PULL_PAT`` in GitHub Actions). After CI is enabled, the ``deploy_aca`` job runs ``az containerapp registry set`` on each deploy so ACA pull credentials stay aligned with the repository secret—see :ref:`azure-aca-github-secrets`.


.. _azure-aca-logging:

Step 4 — Logging and validation
===============================

With the environment wired to Log Analytics in :ref:`azure-aca-step1`, **stdout/stderr** and platform diagnostics flow to the workspace.

Stream logs (quick check)
-------------------------

.. code-block:: bash

   az containerapp logs show -g "$RESOURCE_GROUP" -n "$APP_NAME" --follow

In the Azure portal: Container App → **Log stream**, or **Logs** to query the workspace.

Example Kusto query (table name can vary by subscription):

.. code-block:: kusto

   ContainerAppConsoleLogs_CL
   | where ContainerAppName_s == "APP_NAME"
   | sort by TimeGenerated desc
   | take 100

If ``ContainerAppConsoleLogs_CL`` is empty, open the workspace → **Logs** → schema browser and select the **ContainerApp** console table present in your subscription.

Sanity checks
-------------

.. code-block:: bash

   az containerapp show -g "$RESOURCE_GROUP" -n "$APP_NAME" -o table
   az containerapp revision list -g "$RESOURCE_GROUP" -n "$APP_NAME" -o table


Health checks
=============

Thaum exposes:

- ``GET /health`` — liveness
- ``GET /ready`` — database readiness

Point Container Apps probes at ``/ready`` (or ``/health``) on port **5165**.


Configuration and Dockerfile
============================

1. Start from the template ``thaum.toml`` or upstream examples; keep only what your organization needs.
2. Set ``[server].base_url`` to the app FQDN, or omit it and rely on ``WEBSITE_HOSTNAME`` / ``THAUM_BASE_URL`` at runtime.
3. Save as ``thaum.toml`` in the deploy repository; the Dockerfile must ``COPY`` it to ``/etc/thaum/thaum.toml``.
4. Use ``azure/github/Dockerfile.example``: pin ``FROM`` to a digest or tag; do not rely on ``:latest`` alone.

Keep secrets out of Git—use ``secret:<name>`` with the volume mount, or ``env:VAR`` if you bind secrets with ``secretref:`` (see below).

Schema check (local, same as CI)
--------------------------------

.. code-block:: bash

   docker build -t thaum-local:test .

   docker run --rm \
     --workdir /app \
     --entrypoint python \
     -e WEBSITE_HOSTNAME=schema-check.ci.local \
     thaum-local:test \
     scripts/python/thaum_config_check.py --schema-check -c /etc/thaum/thaum.toml


.. _azure-aca-file-vs-env-secrets:

File-mounted secrets vs environment variable secrets
====================================================

**Files** (``--secret-volume-mount "/run/secrets"``)
   Each ACA secret appears as a file; TOML uses ``secret:<name>``. Matches systemd-style ``secret:`` and keeps values out of the process environment.

**Environment** (``secretref:``)
   Omit the volume mount; on update use ``--set-env-vars "VARNAME=secretref:aca-secret-name"``. In TOML use ``env:VARNAME``. Anything that dumps the environment can expose values.

Pick one style per secret and stay consistent.


.. _azure-aca-github-secrets:

GitHub Actions workflow
=======================

Two jobs in ``deploy-aca.yml``:

.. list-table::
   :header-rows: 1
   :widths: 18 62

   * - Job
     - Purpose
   * - ``build_push``
     - Build Dockerfile, ``--schema-check``, push to **GHCR** (``GITHUB_TOKEN``, ``packages: write``). No Azure credentials.
   * - ``deploy_aca``
     - **OIDC** login, ``az containerapp registry set``, ``az containerapp update`` to the commit SHA tag

If the schema check fails, nothing is pushed and ACA is not updated.

**Triggers:** confirm in the YAML; ``workflow_dispatch`` is typical; ``push`` to ``main`` may be commented out—enable it if every merge should deploy.

Tokens: ``GITHUB_TOKEN`` vs PAT
-------------------------------

.. list-table::
   :header-rows: 1
   :widths: 28 18 34

   * - Scenario
     - Credential
     - Notes
   * - CI pushes to GHCR
     - ``GITHUB_TOKEN``
     - Requires ``packages: write`` in workflow
   * - Org blocks token push
     - PAT + workflow change
     - ``write:packages``
   * - ACA pulls **private** GHCR
     - ``GHCR_PULL_PAT`` + ``GHCR_PULL_USERNAME``
     - Machine user, ``read:packages`` only

Repository secrets (**Settings → Secrets and variables → Actions → Secrets**)
-------------------------------------------------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 28 52

   * - Secret
     - Purpose
   * - ``AZURE_CLIENT_ID``
     - Entra app **application (client) ID** for OIDC
   * - ``AZURE_TENANT_ID``
     - Tenant ID
   * - ``AZURE_SUBSCRIPTION_ID``
     - Subscription ID
   * - ``GHCR_PULL_PAT``
     - Machine user PAT ``read:packages`` for ``az containerapp registry set``

Repository variables (**Variables**)
------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 28 12 50

   * - Variable
     - Required
     - Purpose
   * - ``AZURE_RESOURCE_GROUP``
     - Yes
     - Resource group of the Container App
   * - ``AZURE_CONTAINERAPP_NAME``
     - Yes
     - Container App name
   * - ``GHCR_PULL_USERNAME``
     - Yes for ``deploy_aca``
     - Machine user login for registry ``--username``
   * - ``GHCR_IMAGE``
     - No
     - Full image **without tag**; default ``ghcr.io/<lower(owner/repo)>``


.. _azure-aca-oidc:

Azure OIDC (federated identity)
===============================

Trust GitHub Actions so ``azure/login`` receives tokens without an Entra client secret.

Portal (summary)
----------------

1. Entra ID → App registration → note **Application (client) ID** → ``AZURE_CLIENT_ID``.
2. **Certificates & secrets → Federated credentials** → Add:

   - **Issuer:** ``https://token.actions.githubusercontent.com``
   - **Subject:** e.g. ``repo:OWNER/REPO:ref:refs/heads/main`` (must match how you trigger ``deploy_aca``)
   - **Audience:** ``api://AzureADTokenExchange``

3. Grant the app’s service principal rights on the resource group (below).

Tutorials: `Microsoft — GitHub OIDC <https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure>`_, `GitHub Docs <https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-azure>`_.

CLI provisioning
----------------

.. tab-set::
   :sync-group: aca-shell

   .. tab-item:: Bash
      :sync: bash

      .. code-block:: bash

         APP_DISPLAY_NAME="gha-thaum-deploy"
         CLIENT_ID=$(az ad app create --display-name "$APP_DISPLAY_NAME" --query appId -o tsv)
         APP_OBJECT_ID=$(az ad app show --id "$CLIENT_ID" --query id -o tsv)

         az ad sp create --id "$CLIENT_ID"

         SUBJECT="repo:OWNER/REPO:ref:refs/heads/main"

         az ad app federated-credential create \
           --id "$APP_OBJECT_ID" \
           --parameters "{
             \"name\": \"github-main\",
             \"issuer\": \"https://token.actions.githubusercontent.com\",
             \"subject\": \"$SUBJECT\",
             \"audiences\": [\"api://AzureADTokenExchange\"]
           }"

   .. tab-item:: PowerShell
      :sync: powershell

      .. code-block:: powershell

         $app = New-AzADApplication -DisplayName "gha-thaum-deploy"
         New-AzADServicePrincipal -ApplicationId $app.AppId
         $CLIENT_ID = $app.AppId

         New-AzADAppFederatedCredential `
           -ApplicationObjectId $app.Id `
           -Issuer "https://token.actions.githubusercontent.com" `
           -Subject "repo:OWNER/REPO:ref:refs/heads/main" `
           -Audience "api://AzureADTokenExchange" `
           -Name "github-main"

Use ``repo:OWNER/REPO:environment:NAME`` if federated credentials bind to a GitHub Environment.

Copy ``CLIENT_ID`` → ``AZURE_CLIENT_ID``; tenant and subscription → ``AZURE_TENANT_ID``, ``AZURE_SUBSCRIPTION_ID``.


Azure role assignment (deploy principal)
========================================

The automation principal needs permission for ``az containerapp update`` and ``az containerapp registry set``.

.. tab-set::
   :sync-group: aca-shell

   .. tab-item:: Bash
      :sync: bash

      .. code-block:: bash

         az role assignment create \
           --assignee "$CLIENT_ID" \
           --role Contributor \
           --scope "/subscriptions/SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP"

   .. tab-item:: PowerShell
      :sync: powershell

      .. code-block:: powershell

         $rgScope = "/subscriptions/SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP"
         $deploySp = Get-AzADServicePrincipal -ApplicationId $CLIENT_ID
         New-AzRoleAssignment -ObjectId $deploySp.Id -RoleDefinitionName "Contributor" -Scope $rgScope

Prefer a narrower custom role if policy requires; **Contributor** on the resource group is a common starting point.


GHCR package visibility
=======================

Keep the GHCR package **private**. Set ``GHCR_PULL_PAT`` and ``GHCR_PULL_USERNAME`` before ``deploy_aca``. Leave ``packages: write`` enabled on the workflow for pushes.


First-time validation
=====================

1. Configure GitHub secrets and variables (including machine-user ``GHCR_PULL_*``).
2. Finish federated credential and RBAC (:ref:`azure-aca-oidc`).
3. Run **Actions → Schema check and deploy to Azure Container Apps** (enable deploy if using ``workflow_dispatch``).
4. Confirm: schema check passed, GHCR push OK, ``az containerapp update`` OK, provisioning **Succeeded**, revisions as expected.
5. Verify the GHCR SHA tag exists; the ACA revision shows the new image.
6. Confirm logs in Log Analytics / **Log stream** (:ref:`azure-aca-logging`).


Optional — external managed Postgres
====================================

1. Provision managed Postgres and a database/user for Thaum.
2. Set ``THAUM_EXTERNAL_DB=true`` on the Container App.
3. Set ``[server.database].db_url`` in ``thaum.toml``; supply passwords via Key Vault + ``secret:`` / ``env:``.
4. Redeploy. The container runs **Gunicorn only** (no bundled Postgres).


Appendix — ACR alternate workflow (not the default)
===================================================

The default CI path is **GHCR** + ``deploy-aca.yml``. To use **Azure Container Registry** instead, provision an ACR, adapt registry credentials on the Container App, and use an ACR-oriented pipeline such as ``azure/github/deploy.yml.example`` (build → schema-check → push ACR → update), aligned with Microsoft’s `tutorial <https://learn.microsoft.com/en-us/azure/container-apps/tutorial-code-to-cloud?tabs=bash%2Ccsharp&pivots=acr-remote>`_. Application secrets remain in Key Vault as in :ref:`azure-aca-keyvault-uami` and :ref:`azure-aca-container-app`.
