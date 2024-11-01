ARG EGAPx_TAG=latest
FROM docker.io/ncbi/egapx:${EGAPx_TAG}

# - install OS updates
# - install venv module for python3
# - create symlinks for executables
RUN --mount=type=bind,source=assets,target=/root/bin <<EOF
#!/usr/bin/env bash
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get -y install python3-venv
apt-get -y dist-upgrade
apt-get -y autoremove
apt-get -y clean
rm -rf /var/lib/apt/lists/*
/root/bin/link_bins.bash
EOF

# - install latest release of miniforge
# - create conda env for nextflow
# - install EGAPx runner script
RUN --mount=type=bind,source=assets,target=/root/bin <<EOF
#!/usr/bin/env bash
/root/bin/bootstrap.bash
EOF
