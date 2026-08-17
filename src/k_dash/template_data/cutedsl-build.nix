{ pkgs, buildSpec }:

let
  target = buildSpec.target;
  elements = buildSpec.args.block_size;
  tvmFfiWheel = pkgs.fetchurl {
    url =
      if target.arch == "x86_64" then
        "https://files.pythonhosted.org/packages/73/d7/c4c783ee435a03e2afb5744b6deb99d98ade203ee91c04f81ad7bdb51de1/apache_tvm_ffi-0.1.13.post3-cp313-cp313-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl"
      else if target.arch == "aarch64" then
        "https://files.pythonhosted.org/packages/e0/5e/b6c248b0fc142dc19ed4e44e8a11e1c8e991d7854bc707ec8e40b9482103/apache_tvm_ffi-0.1.13.post3-cp313-cp313-manylinux_2_24_aarch64.manylinux_2_28_aarch64.whl"
      else
        throw "unsupported target architecture: ${target.arch}";
    hash =
      if target.arch == "x86_64" then
        "sha256-2zuMPRja4BxpYtcFKzNf936XswkmPEnskq6iWDb6S5c="
      else
        "sha256-c4InirtWIvJx1Q6XrX/7spcP0MuDa+T3CV+8sRaUFYI=";
  };
  tvmFfi = pkgs.runCommand "apache-tvm-ffi-0.1.13.post3-python313-runtime" {
    nativeBuildInputs = [ pkgs.unzip ];
  } ''
    mkdir -p "$out"
    unzip -q ${tvmFfiWheel} -d "$out"
    test -f "$out/tvm_ffi/lib/libtvm_ffi.so"
  '';
  mkTvmFfiKernel =
    { build, hostCudaDependencies ? [ ] }:
    pkgs.runCommand "k-dash-cutedsl-tvm-ffi-kernel" {
      nativeBuildInputs = [ pkgs.patchelf ];
      dontPatchELF = true;
      dontAutoPatchelf = true;
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
  cutedslModule = pkgs.stdenv.mkDerivation {
    pname = "cutedsl-copy-tvm-ffi";
    version = "1";
    dontUnpack = true;
    dontPatchELF = true;
    dontAutoPatchelf = true;
    NIX_DONT_SET_RPATH = 1;
    buildPhase = ''
      set -eu
      export PYTHONPATH=${tvmFfi}
      ${pkgs.cutePythonEnv}/bin/python ${./.}/src/kernel.py \
        "$PWD/kernel.o" ${target.cc} ${toString elements}
      cute_runtime="$(${pkgs.cutePythonEnv}/bin/python -c \
        'import cutlass.runtime; print(cutlass.runtime.find_runtime_libraries(enable_tvm_ffi=False)[0])')"
      ${pkgs.stdenv.cc}/bin/gcc -shared -o kernel.so kernel.o \
        "$cute_runtime" ${tvmFfi}/tvm_ffi/lib/libtvm_ffi.so
    '';
    installPhase = ''
      mkdir -p "$out"
      cp kernel.so "$out/kernel.so"
    '';
  };
in
assert target.os == "linux";
assert target.cuda == "12.8";
mkTvmFfiKernel {
  hostCudaDependencies = [ "cuda-runtime" "cutedsl-runtime" ];
  build = cutedslModule;
}
