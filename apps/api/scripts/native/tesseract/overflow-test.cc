// QA-only native deserializer tests. No student input or model is modified.
#include "include_gunit.h"
#include "network.h"
#include "serialis.h"

#include <cstdint>
#include <limits>
#include <vector>

namespace tesseract {
namespace {

std::vector<char> LayerBytes(NetworkType type, int ni, int no, int weights,
                             int first, int second) {
  std::vector<char> bytes;
  auto byte = [&bytes](uint32_t value) { bytes.push_back(static_cast<char>(value & 255)); };
  auto word = [&byte](int value) {
    const auto bits = static_cast<uint32_t>(value);
    for (int i = 0; i < 4; ++i) byte(bits >> (8 * i));
  };
  byte(type);
  byte(0); // TS_DISABLED
  byte(0); // needs_to_backprop
  word(0); // network_flags
  word(ni);
  word(no);
  word(weights);
  word(0); // empty name
  word(first);
  word(second);
  return bytes;
}

bool AcceptsLayer(NetworkType type, int ni, int no, int weights, int first, int second) {
  auto bytes = LayerBytes(type, ni, no, weights, first, second);
  TFile file;
  if (!file.Open(bytes.data(), bytes.size())) return false;
  Network *network = Network::CreateFromFile(&file);
  const bool accepted = network != nullptr;
  delete network;
  return accepted;
}

TEST(SecurityOverflow, ConvolveRejectsLargeHalves) {
  EXPECT_FALSE(AcceptsLayer(NT_CONVOLVE, 1, 1, 0, std::numeric_limits<int>::max(), 1));
}
TEST(SecurityOverflow, ConvolveRejectsChannelProductOverflow) {
  EXPECT_FALSE(AcceptsLayer(NT_CONVOLVE, std::numeric_limits<int>::max(), 1, 0, 1, 1));
}
TEST(SecurityOverflow, ConvolveRejectsNegativeHalf) {
  EXPECT_FALSE(AcceptsLayer(NT_CONVOLVE, 1, 1, 0, -1, 1));
}
TEST(SecurityOverflow, ConvolveAcceptsValidDimensions) {
  EXPECT_TRUE(AcceptsLayer(NT_CONVOLVE, 2, 18, 0, 1, 1));
}
TEST(SecurityOverflow, ReconfigRejectsScaleProductOverflow) {
  EXPECT_FALSE(AcceptsLayer(NT_RECONFIG, 2, 1, 0, std::numeric_limits<int>::max(),
                           std::numeric_limits<int>::max()));
}
TEST(SecurityOverflow, ReconfigRejectsChannelProductOverflow) {
  EXPECT_FALSE(AcceptsLayer(NT_RECONFIG, std::numeric_limits<int>::max(), 1, 0, 2, 2));
}
TEST(SecurityOverflow, ReconfigRejectsZeroScale) {
  EXPECT_FALSE(AcceptsLayer(NT_RECONFIG, 1, 1, 0, 0, 1));
}
TEST(SecurityOverflow, ReconfigAcceptsValidDimensions) {
  EXPECT_TRUE(AcceptsLayer(NT_RECONFIG, 2, 8, 0, 2, 2));
}
TEST(SecurityOverflow, NetworkRejectsNegativeInputs) {
  EXPECT_FALSE(AcceptsLayer(NT_CONVOLVE, -1, 1, 0, 1, 1));
}
TEST(SecurityOverflow, NetworkRejectsNegativeOutputs) {
  EXPECT_FALSE(AcceptsLayer(NT_CONVOLVE, 1, -1, 0, 1, 1));
}
TEST(SecurityOverflow, NetworkRejectsNegativeWeights) {
  EXPECT_FALSE(AcceptsLayer(NT_CONVOLVE, 1, 1, -1, 1, 1));
}

} // namespace
} // namespace tesseract
