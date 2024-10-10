#!/usr/bin/env bash

set -e

#---------------------------------------------------------------------------------------------------
this_dir=$(dirname $(readlink -f "$0"))

if ! [[ -d "${PWD}/.git" ]] || ! [[ -f "${PWD}/pyproject.toml" ]]; then
    echo "ERROR: This script expects to be executed from the regio source directory." >&2
    exit 1
fi

#---------------------------------------------------------------------------------------------------
mmap_file='regio-protocol-test.none.bar0.bin'
rm -f "${mmap_file}"

dump_mmap_file() {
    echo '================================================================================'
    echo "==> hexdump of ${mmap_file}"
    hexdump -C "${mmap_file}"
    echo '================================================================================'
}

#---------------------------------------------------------------------------------------------------
args=()
args+=('-p none')
args+=('-b all')
args+=('-t mmap')
args+=('--no-protocol-override')
args+=('--indirect')

cmd="regio-protocol-test ${args[@]}"

#---------------------------------------------------------------------------------------------------
# TODO: The following should be converted to a regio script.

echo '===> Display of initial state'
poetry run -- ${cmd} dump dev0.bar0
dump_mmap_file

echo '===> Modification of single view'
poetry run -- ${cmd} eval \
    sv=dev0.bar0.single_view \
    sv.first=1 \
    sv.second=2 \
    sv.third=3

echo '===> Display of single view'
poetry run -- ${cmd} dump dev0.bar0
dump_mmap_file

echo '===> Modification of nested view'
poetry run -- ${cmd} eval \
    nv=dev0.bar0.nested_view \
    nv0=nv.view_0 \
    nv1=nv.view_1 \
    nv0.first=0x11 \
    nv0.second=0x12 \
    nv0.third=0x13 \
    nv1.first=0x14 \
    nv1.second=0x15 \
    nv1.third=0x16

echo '===> Display of nested view'
poetry run -- ${cmd} dump dev0.bar0
dump_mmap_file

echo '===> Modification of bus view'
poetry run -- ${cmd} eval \
    bv=dev0.bar0.bus_view \
    bv0=bv.view_0 \
    bv1=bv.view_1 \
    bv0.first=0x21 \
    bv0.second=0x22 \
    bv0.third=0x23 \
    bv1.first=0x24 \
    bv1.second=0x25 \
    bv1.third=0x26

echo '===> Display of bus view'
poetry run -- ${cmd} dump dev0.bar0
dump_mmap_file

echo '===> Modification of transparent views'
for ((i=0; i<2; i++)); do
    base=$((3 + i))
    poetry run -- ${cmd} eval \
        tv=dev0.bar0.transparent_view_${i} \
        tv.first=0x${base}1 \
        tv.second=0x${base}2 \
        tv.third=0x${base}3
done

echo '===> Display of transparent views'
poetry run -- ${cmd} dump dev0.bar0
dump_mmap_file
