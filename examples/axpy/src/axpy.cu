#include <algorithm>
#include <cstdint>
#include <cuda_runtime.h>
#include <tvm/ffi/extra/c_env_api.h>
#include <tvm/ffi/extra/cuda/device_guard.h>
#include <tvm/ffi/tvm_ffi.h>

#ifndef K_DASH_BLOCK_SIZE
#define K_DASH_BLOCK_SIZE 256
#endif

using namespace tvm;

__global__ void axpy_kernel(float* __restrict__ out,
                            const float* __restrict__ x,
                            const float* __restrict__ y,
                            float alpha,
                            int64_t n) {
  for (int64_t i = static_cast<int64_t>(blockIdx.x) * blockDim.x + threadIdx.x;
       i < n;
       i += static_cast<int64_t>(blockDim.x) * gridDim.x) {
    out[i] = alpha * x[i] + y[i];
  }
}

void axpy(ffi::TensorView out,
          ffi::TensorView const x,
          ffi::TensorView const y,
          float alpha) {
  constexpr DLDataType kFloat32{kDLFloat, 32, 1};
  TVM_FFI_CHECK(out.device().device_type == kDLCUDA, ValueError) << "out must be CUDA";
  TVM_FFI_CHECK(x.device().device_type == kDLCUDA, ValueError) << "x must be CUDA";
  TVM_FFI_CHECK(y.device().device_type == kDLCUDA, ValueError) << "y must be CUDA";
  TVM_FFI_CHECK(out.device().device_id == x.device().device_id &&
                x.device().device_id == y.device().device_id, ValueError) << "device mismatch";
  TVM_FFI_CHECK(out.IsContiguous() && x.IsContiguous() && y.IsContiguous(), ValueError)
      << "all tensors must be contiguous";
  TVM_FFI_CHECK(out.dtype() == kFloat32 && x.dtype() == kFloat32 && y.dtype() == kFloat32,
                TypeError) << "AXPY supports float32";
  TVM_FFI_CHECK(out.numel() == x.numel() && x.numel() == y.numel(), ValueError)
      << "size mismatch";
  if (x.numel() == 0) return;

  ffi::CUDADeviceGuard guard(x.device().device_id);
  auto stream = static_cast<cudaStream_t>(
      TVMFFIEnvGetStream(x.device().device_type, x.device().device_id));
  const int blocks = std::min<int64_t>((x.numel() + K_DASH_BLOCK_SIZE - 1) / K_DASH_BLOCK_SIZE, 4096);
  axpy_kernel<<<blocks, K_DASH_BLOCK_SIZE, 0, stream>>>(
      static_cast<float*>(out.data_ptr()),
      static_cast<const float*>(x.data_ptr()),
      static_cast<const float*>(y.data_ptr()),
      alpha,
      x.numel());
  TVM_FFI_CHECK(cudaGetLastError() == cudaSuccess, RuntimeError) << "AXPY launch failed";
}

TVM_FFI_DLL_EXPORT_TYPED_FUNC(axpy, axpy);
