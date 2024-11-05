#!/usr/bin/env bash

set -e

#---------------------------------------------------------------------------------------------------
this_dir=$(dirname $(readlink -f "$0"))

if ! [[ -d "${PWD}/.git" ]] || ! [[ -f "${PWD}/pyproject.toml" ]]; then
    echo "ERROR: This script expects to be executed from the regio source directory." >&2
    exit 1
fi

#-------------------------------------------------------------------------------
spec_dir="${this_dir}/spec"
build_dir="${this_dir}/build"
c_dir="${build_dir}/c"
py_dir="${build_dir}/py"

top="${spec_dir}/i2c_top.yaml"
ir="${build_dir}/ir.yaml"

rm -rf "${build_dir}"
mkdir -p "${build_dir}"

#-------------------------------------------------------------------------------
echo "===> Setting up poetry"
poetry install -vv --all-extras
poetry run -- pip3 list

#-------------------------------------------------------------------------------
echo "===> Elaborating the top-level YAML ${top}"
poetry run -- regio-elaborate -f top -i "${spec_dir}" -o "${ir}" "${top}"

#-------------------------------------------------------------------------------
echo "===> Generating C language header files in ${c_dir}"
mkdir -p "${c_dir}"
poetry run -- regio-generate -f top --recursive -g c -o "${c_dir}" "${ir}"

#-------------------------------------------------------------------------------
echo "===> Generating Python library files in ${py_dir}"
mkdir -p "${py_dir}"
poetry run -- regio-generate -f top --recursive -g py -o "${py_dir}" "${ir}"

echo "===> Installing generated Python library"
py_install="${build_dir}/py-install"
cat <<_EOF >"${py_install}"
#!/usr/bin/env bash
set -e
pushd "\$1/python"
poetry install -vv --all-extras
popd
_EOF
chmod +x "${py_install}"

poetry run -- "${py_install}" "${py_dir}"
poetry run -- pip3 list
