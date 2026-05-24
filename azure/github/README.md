# Supporting files (Azure + GitHub)

Example assets for the **[Azure Container Apps quickstart](https://gemstone-software-dev.github.io/thaum-cloud/quickstart/azure/quickstart_aca.html)**.

| File | Purpose |
|------|---------|
| [Dockerfile.example](Dockerfile.example) | Pin upstream Thaum image; `COPY` `thaum.toml` → `/etc/thaum/thaum.toml` |
| [deploy.yml.example](deploy.yml.example) | **Non-default:** build → schema-check → push **ACR** → update Container App ([GHCR path](https://gemstone-software-dev.github.io/thaum-cloud/quickstart/azure/quickstart_aca.html) uses repo root `.github/workflows/deploy-aca.yml`) |
| [scripts/keyvault-uri.ps1.example](scripts/keyvault-uri.ps1.example) | Print Key Vault base URI for `keyvaultref` URIs |
| [scripts/set-keyvault-secret-from-file.ps1.example](scripts/set-keyvault-secret-from-file.ps1.example) | Set a vault secret from a file |
| [scripts/keyvault-uri.bat.example](scripts/keyvault-uri.bat.example) | Invoke the URI script from cmd |
| [scripts/set-keyvault-secrets-interactive.ps1.example](scripts/set-keyvault-secrets-interactive.ps1.example) | Interactive secret upload helper |
| [scripts/set-keyvault-secrets-interactive.sh.example](scripts/set-keyvault-secrets-interactive.sh.example) | Bash variant |
