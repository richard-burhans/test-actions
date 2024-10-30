#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail
set -o posix

project_root="/galaxy"
miniforge_root="$project_root/miniforge3"
repo="conda-forge/miniforge"

if [ ! -e "$project_root" ]; then
    mkdir -m 0755 -p "$project_root"
fi

if [ ! -e "$miniforge_root" ]; then
    ## get tag_name of latest release of miniforge
    tag=$(curl --silent "https://api.github.com/repos/conda-forge/miniforge/releases/latest" \
            | python3 -m json.tool \
            | awk '$1 == "\"tag_name\":" {print $2}' \
            | cut -d\" -f2)

    if [ -z "$tag" ]; then
        echo "error: unable to get latest release of miniforge"
        exit 1
fi
    
    ## download and verity miniforge
    filename="Miniforge3-${tag}-$(uname -s)-$(uname -m).sh"
    url="https://github.com/conda-forge/miniforge/releases/download/$tag/$filename"

    curl --silent --location -o "$project_root/$filename" "$url"
    curl --silent --location -o "$project_root/${filename}.sha256" "${url}.sha256"

    expected_checksum=$(awk '{print $1}' "$project_root/${filename}.sha256")
    actual_checksum=$(openssl dgst -sha256 "$project_root/$filename" | awk '{print $2}')

    if [ "$expected_checksum" != "$actual_checksum" ]; then
        echo "error: checksum mismatch"
        echo "  expected: $expected_checksum"
        echo "  awk '{print \$1}' \"$project_root/${filename}.sha256\""
        echo "    actual: $actual_checksum"
        exit 1
    fi

    ## install miniforge
    bash "$project_root/$filename" -b -p "$miniforge_root"
fi

echo "source \"${miniforge_root}/etc/profile.d/conda.sh\"" > "$project_root/env.bash"
echo "source \"${miniforge_root}/etc/profile.d/mamba.sh\"" >> "$project_root/env.bash"
source "$project_root/env.bash"

nextflow_env_installed=$(conda env list | egrep '^nextflow\b' || true)
echo "nextflow_env_installed=\"$nextflow_env_installed\""
if [ -z "$nextflow_env_installed" ]; then
    mamba create \
        --name nextflow \
        --channel conda-forge \
        --channel bioconda \
        --channel defaults \
        --override-channels \
        --strict-channel-priority \
        --yes \
        git \
        nextflow

    echo "conda activate nextflow" >> "$project_root/env.bash"
fi

conda activate nextflow
if [ ! -e "$project_root/egapx" ]; then
    cd "$project_root"
    git clone https://github.com/ncbi/egapx.git
fi

if [ ! -e "$project_root/.venv" ]; then
    python3 -m venv "$project_root/.venv"
    echo "source \"$project_root/.venv/bin/activate\"" >> "$project_root/env.bash"
fi

source "$project_root/.venv/bin/activate"
pip install --upgrade pip
pip install -r "$project_root/egapx/ui/requirements.txt"

cd egapx
python3 ui/egapx.py ./examples/input_D_farinae_small.yaml -o example_out || true
cd ..

cat > "$project_root/egapx/egapx_config/galaxy.config" <<EOF
docker.enabled = false
env.GP_HOME="/img/gp/bin/"
env.PATH = "/img/gp/bin/:/img/gp/third-party/STAR/bin/Linux_x86_64:\\\$PATH"
EOF

rm -f "$project_root/$filename"{,.sha256}

deactivate
conda deactivate

# patch nextflow
find /galaxy -type f -name nextflow -print0 2>/dev/null |
    while IFS= read -r -d '' pathname; do
        if ! grep -qx 'unset _JAVA_OPTIONS' "$pathname"; then
            sed -i '/unset JAVA_TOOL_OPTIONS/a unset _JAVA_OPTIONS' "$pathname"
            echo "patched $pathname"
        fi
    done
