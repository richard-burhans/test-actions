ARG BUILD_SRC
FROM $BUILD_SRC
# install OS updates
RUN DEBIAN_FRONTEND=noninteractive /bin/bash -c "apt-get update && apt-get upgrade -u -y && apt-get dist-upgrade -y && apt-get autoremove -y && apt-get autoclean -y"
# install pyvenv-3 binary for python3
RUN DEBIAN_FRONTEND=noninteractive /bin/bash -c "apt-get install -y python3-venv"
COPY assets/link_bins.bash /root/
RUN DEBIAN_FRONTEND=noninteractive /bin/bash -c "/root/link_bins.bash && rm /root/link_bins.bash"
COPY assets/bootstrap.bash /root/
RUN DEBIAN_FRONTEND=noninteractive /bin/bash -c "/root/bootstrap.bash && rm /root/bootstrap.bash"
