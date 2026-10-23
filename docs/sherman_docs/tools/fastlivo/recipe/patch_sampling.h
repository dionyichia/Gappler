#pragma once

#include <cstdint>
#include <limits>

namespace fast_livo_sampling
{
// Quantized center coordinates, not the unsnapped floating-point projection.
// Include both bilinear neighbours and the +/- one-scale gradient stencil.
inline bool patchSamplingInBounds(int u, int v, int patch_size, int scale, int width, int height)
{
  if (patch_size <= 0 || scale <= 0 || width <= 0 || height <= 0) return false;
  // The existing sampler forms its linear byte offsets with int arithmetic.
  if (std::int64_t(width) * height > std::numeric_limits<int>::max()) return false;
  const std::int64_t half = patch_size / 2;
  const std::int64_t lower = (half + 1) * scale;
  const std::int64_t upper = (std::int64_t(patch_size) - half + 1) * scale;
  return std::int64_t(u) >= lower && std::int64_t(v) >= lower &&
         std::int64_t(u) + upper < width && std::int64_t(v) + upper < height;
}
}  // namespace fast_livo_sampling
