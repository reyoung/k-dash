{
  description = "k-dash AXPY kernel build lock";
  inputs.nixpkgs = {
    url = "tarball+https://codeload.github.com/NixOS/nixpkgs/tar.gz/75f4ba05c63be3f147bcc2f7bd4ba1f029cedcb1";
    flake = false;
  };
  inputs.cuda-nixpkgs = {
    url = "tarball+https://codeload.github.com/NixOS/nixpkgs/tar.gz/b6018f87da91d19d0ab4cf979885689b469cdd41";
    flake = false;
  };
  outputs = { self, nixpkgs, cuda-nixpkgs }: { };
}
