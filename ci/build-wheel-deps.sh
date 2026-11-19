#!/usr/bin/env bash
set -euo pipefail

prefix=${G2C_DIR:?Set G2C_DIR to the wheel dependency prefix}
workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT

case "$(uname -s)" in
    Linux) rpath='$ORIGIN'; checksum_command=(sha256sum) ;;
    Darwin) rpath='@loader_path'; checksum_command=(shasum -a 256) ;;
    *) exit 1 ;;
esac

build_dependency() {
    local name=$1 url=$2 checksum=$3 license=$4
    shift 4
    local source="$workdir/$name"
    mkdir -p "$source"
    curl --fail --silent --show-error --location --retry 3 "$url" -o "$source.tar.gz"
    printf '%s  %s\n' "$checksum" "$source.tar.gz" | "${checksum_command[@]}" --check
    tar -xzf "$source.tar.gz" -C "$source" --strip-components=1
    cmake -S "$source" -B "$source/build" \
        -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$prefix" \
        -DCMAKE_INSTALL_LIBDIR=lib -DCMAKE_PREFIX_PATH="$prefix" \
        -DCMAKE_INSTALL_RPATH="$rpath" -DBUILD_TESTING=OFF \
        -DBUILD_SHARED_LIBS=ON -DBUILD_STATIC_LIBS=OFF "$@"
    cmake --build "$source/build" --parallel 2
    cmake --install "$source/build"
    install -m 644 "$source/$license" "$prefix/share/grib2io-licenses/$name.txt"
}

mkdir -p "$prefix/share/grib2io-licenses"
build_dependency openjpeg https://codeload.github.com/uclouvain/openjpeg/tar.gz/refs/tags/v2.5.4 \
    a695fbe19c0165f295a8531b1e4e855cd94d0875d2f88ec4b61080677e27188a LICENSE -DBUILD_CODEC=OFF
build_dependency libpng https://codeload.github.com/pnggroup/libpng/tar.gz/refs/tags/v1.6.54 \
    ba7efce137409079989df4667706c339bebfbb10e9f413474718012a13c8cd4c LICENSE \
    -DPNG_STATIC=OFF -DPNG_TESTS=OFF -DPNG_TOOLS=OFF -DPNG_FRAMEWORK=OFF
build_dependency libaec https://gitlab.dkrz.de/k202009/libaec/-/archive/v1.1.4/libaec-v1.1.4.tar.gz \
    b910e47d526ecbfb802ba6cdc6d262420f6ca436e87edfb57a32966f5148f762 LICENSE.txt
build_dependency nceplibs-g2c https://codeload.github.com/NOAA-EMC/NCEPLIBS-g2c/tar.gz/refs/tags/v1.8.0 \
    4ce9f5a7cb0950699fe08ebc5a463ab4d09ef550c050391a319308a2494f971f LICENSE.md \
    -DUSE_Jasper=OFF -DUSE_OpenJPEG=ON -DUSE_PNG=ON -DUSE_AEC=ON -DUTILS=OFF
