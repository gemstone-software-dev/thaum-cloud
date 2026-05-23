# Supporting files (Azure + GitHub)

Example assets live under **`azure/github/`** at the repository root. The step-by-step guide is **[doc/quickstart/cloud/azure/README.md](../README.md)**.

| File | Purpose |
|------|---------|
| [Dockerfile.example](../../../../../azure/github/Dockerfile.example) | Pin upstream Thaum image; `COPY` `thaum.toml` → `/etc/thaum/thaum.toml` |
| [deploy.yml.example](../../../../../azure/github/deploy.yml.example) | **Non-default:** build → schema-check → push **ACR** → update Container App ([GHCR path](../README.md) uses `.github/workflows/deploy-aca.yml`) |
| [scripts/keyvault-uri.ps1.example](../../../../../azure/github/scripts/keyvault-uri.ps1.example) | Print Key Vault base URI for `keyvaultref` URIs |
| [scripts/set-keyvault-secret-from-file.ps1.example](../../../../../azure/github/scripts/set-keyvault-secret-from-file.ps1.example) | Set a vault secret from a file |
| [scripts/keyvault-uri.bat.example](../../../../../azure/github/scripts/keyvault-uri.bat.example) | Invoke the URI script from cmd |
| [scripts/set-keyvault-secrets-interactive.ps1.example](../../../../../azure/github/scripts/set-keyvault-secrets-interactive.ps1.example) | Interactive secret upload helper |
| [scripts/set-keyvault-secrets-interactive.sh.example](../../../../../azure/github/scripts/set-keyvault-secrets-interactive.sh.example) | Bash variant |
