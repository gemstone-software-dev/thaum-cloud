FROM ghcr.io/gemstone-software-dev/thaum:0.7.0a3

# Ensure config directory exists and ownership aligns with runtime UID/GID 1000.
RUN mkdir -p /etc/thaum && chown 1000:1000 /etc/thaum

# Copy local config into the image with explicit ownership and readable perms.
COPY --chown=1000:1000 --chmod=0644 thaum.toml /etc/thaum/thaum.toml
COPY --chown=1000:1000 --chmod=0644 incident_prompt_card.j2 /etc/thaum/incident_prompt_card.j2
COPY --chown=1000:1000 --chmod=0644 static/Thaum_wizard_cgi.jpg /app/static/Thaum_wizard_cgi.jpg
