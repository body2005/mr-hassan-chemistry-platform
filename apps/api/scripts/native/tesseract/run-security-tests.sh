#!/bin/sh
# REAL compiled library,15 unchanged official regression bodies plus11
# negative/overflow/valid controls. Fail the image build on any failed case.
set -eu
task_source="${1:?compiled source required}"
task_output="${2:?new test output required}"
task_assets="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
test ! -e "$task_output/security-tests.xml"
mkdir -p "$task_output"
cd "$task_source"
test -f .libs/libtesseract.a
task_includes='-I. -Iinclude -Iunittest -Isrc/training/common -Isrc/training/unicharset'
for task_dir in src/*; do
  if test -d "$task_dir"; then task_includes="$task_includes -I$task_dir"; fi
done
g++ -std=c++17 -DHAVE_CONFIG_H -DTESS_COMMON_TRAINING_API= \
  -DTESS_UNICHARSET_TRAINING_API= $task_includes $(pkg-config --cflags lept) \
  unittest/normproto_test.cc unittest/fullyconnected_test.cc \
  unittest/genericvector_test.cc unittest/unicharset_load_test.cc \
  unittest/intproto_test.cc "$task_assets/overflow-test.cc" \
  .libs/libtesseract.a -lgtest_main -lgtest -lgmock -fopenmp -pthread \
  $(pkg-config --libs lept) -o "$task_output/security-tests"
"$task_output/security-tests" --gtest_output="xml:$task_output/security-tests.xml"
