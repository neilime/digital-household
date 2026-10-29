FROM debian:trixie-slim@sha256:f6b08b09a05725f9431502d3b5714f5c4576e82c1a84fa1debe0c24a7e0c3ec4

# The Proxmox repository authenticates packages through its signed APT index.
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl openssh-client openssh-server python3 python3-venv xorriso && \
    curl --fail --silent --show-error https://enterprise.proxmox.com/debian/proxmox-release-trixie.gpg \
      -o /usr/share/keyrings/proxmox-release-trixie.gpg && \
    echo '1bcd2d5bab556076c9ea756a84fe2b7445b13f4ef6e97b2e412b68778377ba6d  /usr/share/keyrings/proxmox-release-trixie.gpg' | sha256sum --check && \
    printf '%s\n' 'deb [signed-by=/usr/share/keyrings/proxmox-release-trixie.gpg] http://download.proxmox.com/debian/pve trixie pve-no-subscription' \
      > /etc/apt/sources.list.d/proxmox.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends proxmox-auto-install-assistant=9.2.8 && \
    rm -rf /var/lib/apt/lists/*

COPY docker/tooling/requirements.txt /opt/tooling/requirements.txt
ARG UID=1000
ARG GID=1000
RUN python3 -m venv /opt/tooling/venv && \
    /opt/tooling/venv/bin/pip install --no-cache-dir -r /opt/tooling/requirements.txt && \
    groupadd --gid "${GID}" tooling && \
    useradd --create-home --uid "${UID}" --gid "${GID}" tooling

ENV PATH="/opt/tooling/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    ANSIBLE_CONFIG=/workspace/ansible/ansible.cfg \
    ANSIBLE_HOME=/tmp/ansible
WORKDIR /workspace
USER tooling
HEALTHCHECK --interval=5m --timeout=10s CMD ["proxmox-auto-install-assistant", "--version"]
CMD ["bash"]
