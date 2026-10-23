#pragma once
#include <cmath>

namespace fast_livo_geometry {
// Pixel bounds alone cannot distinguish front-facing and behind-camera points.
inline bool inFrontOfCamera(double x, double y, double z) {
  return std::isfinite(x) && std::isfinite(y) && std::isfinite(z) && z > 0.0;
}
}  // namespace fast_livo_geometry
