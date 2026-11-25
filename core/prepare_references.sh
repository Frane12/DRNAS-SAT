#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p results/references bin
fetch_source() {
  local name="$1" url="$2" revision="$3"
  if ! test -d "results/references/$name/.git"; then
    git clone --no-checkout "$url" "results/references/$name"
  fi
  git -C "results/references/$name" checkout --detach "$revision"
}
fetch_source kissat https://github.com/arminbiere/kissat.git 77bc7ea68afe80751a67df8561357f193e160fb1
(cd results/references/kissat && ./configure && make -j2)
cp results/references/kissat/build/kissat bin/kissat
fetch_source cadical https://github.com/arminbiere/cadical.git 14593f819cb242082b127396218bd60889409737
(cd results/references/cadical && ./configure && make -j2)
cp results/references/cadical/build/cadical bin/cadical
fetch_source drat-trim https://github.com/marijnheule/drat-trim.git 2e3b2dc0ecf938addbd779d42877b6ed69d9a985
cc -O2 results/references/drat-trim/drat-trim.c -o bin/drat-trim
c++ -std=c++20 -O3 vendor/fusion/native.cpp -o bin/fusion1
c++ -std=c++20 -O3 vendor/general/general14.cpp -o bin/general14
git fetch --depth 1 origin 15b4c071644a393a9eb6f3ff181cb0f6b5a2a16b
mkdir -p results/references/unified3
git -C .. archive 15b4c071644a393a9eb6f3ff181cb0f6b5a2a16b research/toolbox20_native src research/pcmax_capacity research/math4 | tar -x -C results/references/unified3
c++ -std=c++20 -O3 results/references/unified3/research/toolbox20_native/unified3.cpp -lcrypto -o bin/unified3
