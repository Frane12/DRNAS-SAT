#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p bin
"${CXX:-c++}" -std=c++20 -O3 -Wall -Wextra -Wno-misleading-indentation core.cpp -lcrypto -o bin/drnas-core
"${CXX:-c++}" -std=c++17 -O3 -Wall -Wextra -Werror vendor/general/check_rup.cpp -o bin/check-rup
"${CXX:-c++}" -std=c++20 -O2 vendor/unified/unified8_kernel.cpp -o bin/factor-test
