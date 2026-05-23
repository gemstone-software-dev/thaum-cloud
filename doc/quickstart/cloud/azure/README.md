# Azure Container Apps + GitHub Actions (GHCR)

Opinionated guide: run **Thaum** on **Azure Container Apps** with **GitHub Container Registry (GHCR)**, **OIDC** deploy ([`.github/workflows/deploy-aca.yml`](../../../../.github/workflows/deploy-aca.yml)), **Azure Key Vault** for application secrets, and **Log Analytics** for platform and container logs.

**Golden path:** private deploy repo, **private** GHCR package, machine-user **`GHCR_PULL_*`** on the Container App, Entra **federated credentials** for Actions—no Azure client secret in GitHub.

Example artifacts (Dockerfile, optional ACR workflow) live under [**azure/github/**](../../../../azure/github/) ([index](github/README.md)).

Other entry points:

- [Repository root README](../../../../README.md) (image tags, adopt pattern)
- [Cloud deployment quickstarts](../../README.md)
- [Example `thaum.toml`](../../../../thaum.toml) in this template

Microsoft docs for ACA secrets:

- [Manage secrets in Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/manage-secrets?tabs=azure-cli) (`keyvaultref`, volumes, `secretref`)

Naming rules: Key Vault secret names use alphanumeric and hyphens. **Container Apps** secret names must be **lowercase**, at most [**20 characters**](https://learn.microsoft.com/en-us/cli/azure/containerapp/secret?view=azure-cli-latest#az-containerapp-secret-set). Examples below use **kebab-case** so names align across Key Vault, ACA secrets, and `secret:<name>` in `thaum.toml`.

---

## Requirements for this deployment pattern (RFC keywords)

The keywords **MUST** and **MUST NOT** below are interpreted as described in [RFC 2119](https://www.rfc-editor.org/info/rfc2119). They apply **only** to repositories that use this Actions + ACA workflow; they do **not** describe every way to install or run Thaum.

- **Deploy repository** (the repo that **bakes** Thaum configuration into an image—a **`Dockerfile`**, **`thaum.toml`** in-layer, CI, and infra like this template) **MUST** be **private** on the Git host. Organizational configuration ships inside the container; mistaken sensitive values in tracked files remain in **`git` history**. A **public** deploy repository **MUST NOT** be used for this pattern.
- For that image lineage, the **GHCR package** **MUST** be **private** so pulls require authenticated access.
- Credentials that allow **Azure Container Apps** to **pull** that package **MUST** use a PAT owned by a **machine user** ([dedicated automation account](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys#machine-users)), **not** a personal PAT tied to whoever triggered the workflow. Store it **only** as repository secret **`GHCR_PULL_PAT`**; **MUST NOT** commit tokens into tracked files.

Elsewhere, lowercase “must”, “may”, and similar words are ordinary guidance unless they refer back to these requirements.

---

## What you get

| Aspect | Behavior |
|--------|----------|
| **Topology** | One resource group, one Container Apps **environment** (with Log Analytics), one Container App |
| **Registry** | **GHCR**; CI pushes with `GITHUB_TOKEN` ([workflow](../../../../.github/workflows/deploy-aca.yml)); ACA pulls with machine user **`GHCR_PULL_PAT`** |
| **Deploy identity** | **OIDC** to Azure—no Entra client secret in GitHub |
| **App secrets** | **Key Vault** + user-assigned managed identity + `keyvaultref` on the Container App |
| **Default database** | Bundled PostgreSQL in the image (`THAUM_EXTERNAL_DB` unset). Ephemeral disk—data can be lost on revision/restart unless you add storage or external DB |
| **Logging** | **Log Analytics workspace** wired to the Container Apps environment (console/system logs)—no Application Insights in this guide |

---

## Prerequisites

- Azure subscription; rights to create resource groups, Log Analytics, Container Apps, Key Vault, managed identities, and **assign RBAC** (and **write** Key Vault secrets for whoever runs the provisioning commands).
- **Bash:** [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) (`az login`) with `containerapp` extension for Container Apps and Key Vault commands.
- **PowerShell:** [Az PowerShell modules](https://learn.microsoft.com/powershell/azure/install-azure-powershell) — at least **`Az.Accounts`**, **`Az.Resources`**, **`Az.Monitor`** (Operational Insights), **`Az.KeyVault`**, **`Az.ManagedServiceIdentity`**, **`Az.App`**. Sign in with `Connect-AzAccount` and select subscription with `Set-AzContext -SubscriptionId ...`.
- [Docker](https://docs.docker.com/get-docker/) for local image build / schema check.
- A **GitHub** deploy repository (see [Requirements](#requirements-for-this-deployment-pattern-rfc-keywords)).

Set common placeholders (adjust everywhere below):

| Placeholder | Meaning |
|-------------|---------|
| `SUBSCRIPTION_ID` | Azure subscription GUID |
| `LOCATION` | Region (e.g. `eastus`) |
| `RESOURCE_GROUP` / `RG` | Resource group name |
| `WORKSPACE` | Log Analytics workspace name (e.g. `thaum-logs`) |
| `ENVIRONMENT` | Container Apps environment name (e.g. `thaum-env`) |
| `APP_NAME` | Container App name |
| `VAULT_NAME` | Key Vault name (globally unique) |
| `OWNER` / `REPO` | GitHub repo `owner/repo` |

---

## 1. Resource providers, resource group, Log Analytics, Container Apps environment

Register providers and create the resource group.

### Bash (`az`)

```bash
az account set --subscription "SUBSCRIPTION_ID"

az extension add --name containerapp --upgrade 2>/dev/null || true

az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights
az provider register --namespace Microsoft.KeyVault
# Optional: wait until Registered
az provider show --namespace Microsoft.KeyVault --query registrationState -o tsv

az group create --name "$RESOURCE_GROUP" --location "$LOCATION"
```

Create a **Log Analytics workspace**, then a Container Apps **environment** that sends logs to it (`--logs-workspace-id` is the workspace **ARM resource ID**).

```bash
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
```

### PowerShell (`Az`)

```powershell
Set-AzContext -Subscription "SUBSCRIPTION_ID"

Register-AzResourceProvider -ProviderNamespace Microsoft.App
Register-AzResourceProvider -ProviderNamespace Microsoft.OperationalInsights
Register-AzResourceProvider -ProviderNamespace Microsoft.KeyVault

New-AzResourceGroup -Name $RESOURCE_GROUP -Location $LOCATION

New-AzOperationalInsightsWorkspace -ResourceGroupName $RESOURCE_GROUP `
  -Name $WORKSPACE -Location $LOCATION | Out-Null

$customerId = (Get-AzOperationalInsightsWorkspace -ResourceGroupName $RESOURCE_GROUP -Name $WORKSPACE).CustomerId
$sharedKey = (Get-AzOperationalInsightsWorkspaceSharedKey -ResourceGroupName $RESOURCE_GROUP -Name $WORKSPACE).PrimarySharedKey

New-AzContainerAppManagedEnv -Name $ENVIRONMENT -ResourceGroupName $RESOURCE_GROUP -Location $LOCATION `
  -AppLogConfigurationDestination "log-analytics" `
  -LogAnalyticConfigurationCustomerId $customerId `
  -LogAnalyticConfigurationSharedKey $sharedKey
```

---

## 2. Key Vault, operator access, and user-assigned managed identity (UAMI)

Store Thaum credential **values** in **Key Vault**. The Container App resolves them at runtime via **`keyvaultref`** and a **user-assigned** managed identity ([Microsoft note](https://learn.microsoft.com/en-us/azure/container-apps/manage-secrets?tabs=azure-cli) on UAMI vs system-assigned during create).

### Bash (`az`)

```bash
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
```

Create the UAMI and grant **Key Vault Secrets User** on the vault:

```bash
UAMI_ID=$(az identity create --name "thaum-aca-secrets" --resource-group "$RESOURCE_GROUP" --location "$LOCATION" --query id -o tsv)
UAMI_PRINCIPAL=$(az identity show --ids "$UAMI_ID" --query principalId -o tsv)

az role assignment create \
  --role "Key Vault Secrets User" \
  --assignee-object-id "$UAMI_PRINCIPAL" \
  --assignee-principal-type ServicePrincipal \
  --scope "$KV_ID"
```

### PowerShell (`Az`)

```powershell
New-AzKeyVault -Name $VAULT_NAME -ResourceGroupName $RESOURCE_GROUP -Location $LOCATION

$kv = Get-AzKeyVault -VaultName $VAULT_NAME -ResourceGroupName $RESOURCE_GROUP
$ctx = Get-AzContext
$myObjId = (Get-AzADUser -UserPrincipalName $ctx.Account.Id).Id

New-AzRoleAssignment -ObjectId $myObjId -RoleDefinitionName "Key Vault Secrets Officer" -Scope $kv.ResourceId

$raw = Get-Content -Raw "./webex-token-database.txt"
$sec = ConvertTo-SecureString $raw -AsPlainText -Force
Set-AzKeyVaultSecret -VaultName $VAULT_NAME -Name "webex-token-database" -SecretValue $sec

$uami = New-AzUserAssignedIdentity -ResourceGroupName $RESOURCE_GROUP -Name "thaum-aca-secrets" -Location $LOCATION
$UAMI_ID = $uami.Id
$uamiPrincipal = $uami.PrincipalId

New-AzRoleAssignment -ObjectId $uamiPrincipal -RoleDefinitionName "Key Vault Secrets User" -Scope $kv.ResourceId
```

**`keyvaultref` URI:** `https://<vault>.vault.azure.net/secrets/<name>` (latest) or append `/<version-id>` to pin. Optional helper: [`azure/github/scripts/keyvault-uri.ps1.example`](../../../../azure/github/scripts/keyvault-uri.ps1.example).

---

## 3. Container App: placeholder, UAMI, Key Vault secrets, Thaum image, private GHCR

**Private GHCR** and **`keyvaultref`** together drive this **split** flow: create the app on a **public** placeholder image, attach UAMI, define ACA secrets pointing at Key Vault, then **one** update for the real Thaum image, port **5165**, volume mount, env, and registry credentials.

### 3.1 Create app and attach UAMI

Get the managed environment resource ID for `az containerapp create` / `New-AzContainerApp`:

**Bash**

```bash
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
```

**PowerShell**

```powershell
$envId = (Get-AzContainerAppManagedEnv -ResourceGroupName $RESOURCE_GROUP -Name $ENVIRONMENT).Id
$placeholder = "mcr.microsoft.com/azuredocs/aci-helloworld:latest"

New-AzContainerApp -Name $APP_NAME -ResourceGroupName $RESOURCE_GROUP `
  -ManagedEnvironmentId $envId -Image $placeholder `
  -IngressExternal -TargetPort 80

Update-AzContainerApp -Name $APP_NAME -ResourceGroupName $RESOURCE_GROUP `
  -IdentityType "UserAssigned" -UserAssignedIdentity @($UAMI_ID)
```

If `New-AzContainerApp` / `Update-AzContainerApp` parameters differ in your `Az.App` version, use the Bash `az containerapp` block in a shell; the ARM result is the same.

### 3.2 Application secrets (`keyvaultref`) and volume mount

**Azure CLI (bash or PowerShell)** — recommended for `keyvaultref` quoting across CLI versions:

```bash
SECRET_URI="https://${VAULT_NAME}.vault.azure.net/secrets/webex-token-database"

az containerapp secret set \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --secrets "webex-token-database=keyvaultref:${SECRET_URI},identityref:${UAMI_ID}"
```

Repeat the secret definition for each credential (add space-separated `--secrets "name=..."` pairs as needed).

Mount secrets under **`/run/secrets`**, set **`THAUM_CREDS_DIR`** so the [official Thaum `entrypoint.sh`](https://github.com/gemstone-software-dev/Thaum/blob/main/docker/entrypoint.sh) can copy files for user `thaum` ([Manage secrets — volume mount](https://learn.microsoft.com/en-us/azure/container-apps/manage-secrets?tabs=azure-cli#mounting-secrets-in-a-volume)).

**Ingress target port:** `az containerapp update` does **not** take **`--target-port`**. After switching from the placeholder (port 80) to Thaum (5165), run a separate **[`az containerapp ingress update`](https://learn.microsoft.com/en-us/cli/azure/containerapp/ingress?view=azure-cli-latest#az-containerapp-ingress-update)** (or ensure **`--target-port`** is set on the initial `create` / [`ingress enable`](https://learn.microsoft.com/en-us/cli/azure/containerapp/ingress?view=azure-cli-latest#az-containerapp-ingress-enable) step for new apps).

```bash
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
```

**PowerShell:** Run the same two `az containerapp …` invocations from above (recommended), or use your `Az.App` version’s ingress update surface (`Get-Help Update-AzContainerApp`, or `Get-Command *ContainerApp*Ingress*`) to set **Target port** to **5165** after `Update-AzContainerApp` for image, registry, and env/volume flags—**do not** pass target port on `Update-AzContainerApp` if the CLI rejects it.

For **bootstrap** only, you may run `secret set` before this update and temporarily keep the placeholder image/port; the final revision should use Thaum on **5165** (`ingress update` as above).

**`thaum.toml`:** use `secret:webex-token-database` (matching the ACA secret name). See [File vs env secrets](#file-mounted-secrets-vs-environment-variable-secrets).

### 3.3 CI registry credentials vs ACA pull secret

The PAT in the command above is the **machine user** **`read:packages`** token (same **class** as **`GHCR_PULL_PAT`** in GitHub Actions). After CI is enabled, **`deploy_aca`** runs [`az containerapp registry set`](https://learn.microsoft.com/en-us/cli/azure/containerapp/registry#az-containerapp-registry-set) each time so ACA pull credentials stay aligned with the repo secret—see [GitHub repository secrets](#github-repository-secrets).

---

## 4. Logging (Log Analytics)

With the environment wired to a workspace ([section 1](#1-resource-providers-resource-group-log-analytics-container-apps-environment)), **stdout/stderr** and platform diagnostics are available in **Log Analytics**.

**Stream (quick check)**

```bash
az containerapp logs show -g "$RESOURCE_GROUP" -n "$APP_NAME" --follow
```

In the Azure portal: Container App → **Log stream**, or **Logs** to run queries against the workspace.

**Example query** (table name can vary; start from *Container Apps* diagnostic tables in the workspace):

```kusto
ContainerAppConsoleLogs_CL
| where ContainerAppName_s == "APP_NAME"
| sort by TimeGenerated desc
| take 100
```

If `ContainerAppConsoleLogs_CL` is empty, open the workspace → **Logs** → schema browser and pick the **ContainerApp** console table present in your subscription.

---

## 5. Health checks

Thaum exposes:

- `GET /health` — liveness  
- `GET /ready` — database readiness  

Point Container Apps probes at **`/ready`** (or `/health`) on port **5165**.

---

## 6. Configuration and Dockerfile

1. Start from this repo’s [`thaum.toml`](../../../../thaum.toml) or upstream examples, and keep only what your org needs.  
2. Set **`[server].base_url`** to the app FQDN, or omit it and rely on **`WEBSITE_HOSTNAME`** / **`THAUM_BASE_URL`** at runtime.  
3. Save as **`thaum.toml`** in the deploy repo; the Dockerfile should **`COPY`** it to **`/etc/thaum/thaum.toml`**.  
4. Use [`azure/github/Dockerfile.example`](../../../../azure/github/Dockerfile.example): pin **`FROM`** to a digest or tag; do not rely on `:latest` alone.

Keep secrets out of Git—use **`secret:<name>`** with the volume mount, or **`env:VAR`** if you bind secrets with **`secretref:`** (see below).

### `THAUM_BASE_URL` in CI

[`deploy-aca.yml`](../../../../.github/workflows/deploy-aca.yml) sets **`WEBSITE_HOSTNAME`** only for the schema-check container. For **`base_url`** resolution in real CI overrides, see **`thaum_config_check.py`** help text (`THAUM_BASE_URL`).

---

## File-mounted secrets vs environment variable secrets

**Files (`--secret-volume-mount "/run/secrets"`)** — Each ACA secret appears as a file; TOML uses **`secret:<name>`**. Matches systemd-style **`secret:`** and keeps values out of the process environment.

**Environment (`secretref:`)** — Omit the volume mount; on update use **`--set-env-vars "VARNAME=secretref:aca-secret-name"`**. In TOML use **`env:VARNAME`**. Anything that dumps the environment can expose values.

Pick one style per secret and stay consistent.

---

## GitHub Actions workflow ([`deploy-aca.yml`](../../../../.github/workflows/deploy-aca.yml))

Two jobs:

| Job | Purpose |
|-----|---------|
| **`build_push`** | Build Dockerfile, **`--schema-check`**, push image to **GHCR** (`GITHUB_TOKEN`, `packages: write`). No Azure credentials. |
| **`deploy_aca`** | **OIDC** login, **`az containerapp registry set`** (GHCR + machine user), **`az containerapp update`** to the commit SHA tag. |

If the schema check fails, nothing is pushed and ACA is not updated.

**Triggers** (confirm in the YAML if this drifts): `workflow_dispatch` with optional **Deploy to Azure Container Apps**; **`push` to `main`** may be commented out—enable it if every merge should deploy.

### Schema check (same as CI locally)

```bash
docker build -t thaum-local:test .

docker run --rm \
  --workdir /app \
  --entrypoint python \
  -e WEBSITE_HOSTNAME=schema-check.ci.local \
  thaum-local:test \
  scripts/python/thaum_config_check.py --schema-check -c /etc/thaum/thaum.toml
```

### GitHub Actions basics

Workflow **`permissions`** scope **`GITHUB_TOKEN`**. Azure uses **`azure/login`** with **`AZURE_*`** secrets—not the GitHub token.

### Tokens: `GITHUB_TOKEN` vs PAT

| Scenario | Credential | Notes |
|----------|------------|--------|
| CI pushes to GHCR | `GITHUB_TOKEN` | Requires `packages: write` in the workflow |
| Org blocks token push | PAT + workflow change | `write:packages` |
| ACA pulls **private** GHCR | **`GHCR_PULL_PAT`** + **`GHCR_PULL_USERNAME`** | Machine user, **`read:packages`** only |

Further reading: [Managing PATs](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens), [credential types](https://docs.github.com/en/organizations/managing-programmatic-access-to-your-organization/github-credential-types), [machine users](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys#machine-users).

### GitHub repository secrets

**Settings → Secrets and variables → Actions → Secrets**

| Secret | Purpose |
|--------|---------|
| `AZURE_CLIENT_ID` | Entra app **application (client) ID** for OIDC |
| `AZURE_TENANT_ID` | Tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Subscription ID |
| `GHCR_PULL_PAT` | Machine user PAT **`read:packages`** for **`az containerapp registry set`** |

### GitHub repository variables

**Variables**

| Variable | Required | Purpose |
|----------|----------|---------|
| `AZURE_RESOURCE_GROUP` | Yes | Resource group of the Container App |
| `AZURE_CONTAINERAPP_NAME` | Yes | App name |
| `GHCR_PULL_USERNAME` | Yes for **`deploy_aca`** | Machine user login for registry `--username` |
| `GHCR_IMAGE` | No | Full image **without tag**; default `ghcr.io/<lower(owner/repo)>` |

---

## Azure OIDC (federated identity)

Trust GitHub Actions so **`azure/login`** receives tokens without an Entra client secret.

### Portal (summary)

1. Entra ID → App registration → note **Application (client) ID** → **`AZURE_CLIENT_ID`**.  
2. **Certificates & secrets → Federated credentials** → Add:  
   - **Issuer:** `https://token.actions.githubusercontent.com`  
   - **Subject:** e.g. `repo:OWNER/REPO:ref:refs/heads/main` (must match how you trigger **`deploy_aca`**)  
   - **Audience:** `api://AzureADTokenExchange`  
3. Grant the app’s service principal rights on the RG (below).

Tutorials: [Microsoft — GitHub OIDC](https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure), [GitHub Docs](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-azure).

### Bash (`az`)

```bash
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
```

Use **`repo:OWNER/REPO:environment:NAME`** if you bind federated credentials to a GitHub Environment.

### PowerShell (`Az.Resources`)

```powershell
$app = New-AzADApplication -DisplayName "gha-thaum-deploy"
New-AzADServicePrincipal -ApplicationId $app.AppId
$CLIENT_ID = $app.AppId

New-AzADAppFederatedCredential `
  -ApplicationObjectId $app.Id `
  -Issuer "https://token.actions.githubusercontent.com" `
  -Subject "repo:OWNER/REPO:ref:refs/heads/main" `
  -Audience "api://AzureADTokenExchange" `
  -Name "github-main"
```

Copy **`CLIENT_ID`** → **`AZURE_CLIENT_ID`**; tenant and subscription → **`AZURE_TENANT_ID`**, **`AZURE_SUBSCRIPTION_ID`**.

---

## Azure role assignment (deploy principal)

The automation principal needs permission for **`az containerapp update`** and **`az containerapp registry set`**.

**Bash**

```bash
az role assignment create \
  --assignee "$CLIENT_ID" \
  --role Contributor \
  --scope "/subscriptions/SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP"
```

**PowerShell**

```powershell
$rgScope = "/subscriptions/SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP"
$deploySp = Get-AzADServicePrincipal -ApplicationId $CLIENT_ID
New-AzRoleAssignment -ObjectId $deploySp.Id -RoleDefinitionName "Contributor" -Scope $rgScope
```

Prefer a narrower custom role if policy requires; **`Contributor`** on the RG is a common starting point.

**Sanity checks**

```bash
az containerapp show -g "$RESOURCE_GROUP" -n "$APP_NAME" -o table
az containerapp revision list -g "$RESOURCE_GROUP" -n "$APP_NAME" -o table
```

---

## GHCR package visibility

Keep the GHCR package **private**. **`GHCR_PULL_PAT`** / **`GHCR_PULL_USERNAME`** must be set before **`deploy_aca`**. Leave **`packages: write`** enabled on the workflow for pushes.

---

## First-time validation

1. Configure GitHub secrets and variables (including machine-user **`GHCR_PULL_*`**).  
2. Finish federated credential + RBAC.  
3. Run **Actions → Schema check and deploy to Azure Container Apps** (enable deploy if using `workflow_dispatch`).  
4. Confirm: schema check passed, GHCR push OK, **`az containerapp update`** OK, provisioning **Succeeded**, revisions expected.  
5. Verify GHCR SHA tag exists; ACA revision shows the new image.  
6. Confirm logs appear in Log Analytics / **Log stream**.

---

## Optional: external managed Postgres

1. Provision managed Postgres and a database/user for Thaum.  
2. Set **`THAUM_EXTERNAL_DB=true`** on the Container App.  
3. Set **`[server.database].db_url`** in `thaum.toml`; supply passwords via Key Vault + **`secret:`** / **`env:`**.  
4. Redeploy. The container runs **Gunicorn only** (no bundled Postgres); see the upstream [**Dockerfile**](https://github.com/gemstone-software-dev/Thaum/blob/main/Dockerfile) and **`docker/entrypoint.sh`** in the Thaum repository.

---

## Appendix: ACR + alternate workflow (not the default)

This repo’s default CI path is **GHCR** + **`deploy-aca.yml`**. To use **Azure Container Registry** instead, provision an ACR, adapt registry credentials on the Container App, and use an ACR-oriented pipeline such as [`azure/github/deploy.yml.example`](../../../../azure/github/deploy.yml.example) (build → schema-check → push ACR → update)— aligned with Microsoft’s [ACR-remote tutorial](https://learn.microsoft.com/en-us/azure/container-apps/tutorial-code-to-cloud?tabs=bash%2Ccsharp&pivots=acr-remote). Application secrets remain in Key Vault as in [section 2](#2-key-vault-operator-access-and-user-assigned-managed-identity-uami)–[3](#3-container-app-placeholder-uami-key-vault-secrets-thaum-image-private-ghcr).
