{ pkgs, buildSpec }:

let
  lib = pkgs.lib;
  target = buildSpec.target;
  blockSize = buildSpec.args.block_size;
  tvmFfiWheel = pkgs.fetchurl {
    url =
      if target.arch == "x86_64" then
        "https://files.pythonhosted.org/packages/df/f3/5ef87404d8ae94d40861fdb82632dcbd8a8172791909033122d104a0328c/apache_tvm_ffi-0.1.13.post3-cp311-cp311-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl"
      else if target.arch == "aarch64" then
        "https://files.pythonhosted.org/packages/23/bd/d1d9de3a32decb4c39c6c3d54522dfc2febcdc7d12664e0f2bb4c79cba83/apache_tvm_ffi-0.1.13.post3-cp311-cp311-manylinux_2_24_aarch64.manylinux_2_28_aarch64.whl"
      else
        throw "unsupported target architecture: ${target.arch}";
    hash =
      if target.arch == "x86_64" then
        "sha256-ssm+bCQiQj0R4Om6KIP4+zWuXVaNMps89d9f7itk0Z8="
      else
        "sha256-piSFJhY2Smexb/kFCaECUSiu4p6EoVJ5lWuPfFJKyDc=";
  };
  tvmFfi = pkgs.runCommand "apache-tvm-ffi-0.1.13.post3-runtime" {
    nativeBuildInputs = [ pkgs.unzip ];
  } ''
    mkdir -p "$out"
    unzip -q ${tvmFfiWheel} -d "$out"
    test -f "$out/tvm_ffi/include/tvm/ffi/tvm_ffi.h"
    test -f "$out/tvm_ffi/lib/libtvm_ffi.so"
  '';
  cudaPackages =
    if builtins.hasAttr "cudaPackages_12_8" pkgs then pkgs.cudaPackages_12_8
    else throw "the locked nixpkgs does not provide cudaPackages_12_8";
  mkTvmFfiKernel =
    { build, hostCudaDependencies ? [ ] }:
    pkgs.runCommand "k-dash-tvm-ffi-kernel" {
      nativeBuildInputs = [ pkgs.patchelf ];
      dontPatchELF = true;
      dontAutoPatchelf = true;
      NIX_DONT_SET_RPATH = 1;
      passthru.kDashHostCudaDependencies = hostCudaDependencies;
    } ''
      set -eu
      test -f ${build}/kernel.so
      test "$(find ${build} -mindepth 1 -maxdepth 1 | wc -l)" -eq 1
      mkdir -p "$out"
      cp ${build}/kernel.so "$out/kernel.so"
      chmod u+w "$out/kernel.so"
      patchelf --remove-rpath "$out/kernel.so"
      chmod 0555 "$out/kernel.so"
    '';
  cudaTvmFfiModule =
    { src, sources, definitions ? { } }:
    let
      cc = target.cc;
      ccNumber = builtins.substring 3 (builtins.stringLength cc - 3) cc;
      sourceArgs = lib.escapeShellArgs (map (relative: "${src}/${relative}") sources);
      defineArgs = lib.escapeShellArgs (
        lib.mapAttrsToList (name: value: "-D${name}=${toString value}") definitions
      );
    in
    assert target.os == "linux";
    assert target.cuda == "12.8";
    pkgs.stdenv.mkDerivation {
      pname = "kernel-tvm-ffi";
      version = "1";
      dontUnpack = true;
      dontPatchELF = true;
      dontAutoPatchelf = true;
      buildPhase = ''
        runHook preBuild
        ${cudaPackages.cuda_nvcc}/bin/nvcc -std=c++17 -O3 --shared --cudart shared \
          -ccbin ${pkgs.stdenv.cc}/bin/g++ \
          -Xcompiler=-fPIC \
          -D_GLIBCXX_USE_CXX11_ABI=1 \
          -Xcompiler=-ffile-prefix-map=${src}=source \
          -Xcompiler=-ffile-prefix-map=${tvmFfi}=tvm_ffi \
          -gencode=arch=compute_${ccNumber},code=${cc} \
          -I${tvmFfi}/tvm_ffi/include \
          -I${cudaPackages.cuda_cudart}/include \
          -I${cudaPackages.cuda_cccl}/include \
          -L${tvmFfi}/tvm_ffi/lib -ltvm_ffi \
          -L${cudaPackages.cuda_cudart}/lib -lcudart \
          ${defineArgs} ${sourceArgs} -o kernel.so
        runHook postBuild
      '';
      installPhase = ''
        mkdir -p "$out"
        cp kernel.so "$out/kernel.so"
      '';
    };
in
mkTvmFfiKernel {
  hostCudaDependencies = [ "cuda-runtime" ];
  build = cudaTvmFfiModule {
    src = ./.;
    sources = [ "src/kernel.cu" ];
    definitions.K_DASH_BLOCK_SIZE = blockSize;
  };
}
