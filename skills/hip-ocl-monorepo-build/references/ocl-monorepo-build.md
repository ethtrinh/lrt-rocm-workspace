# OCL monorepo build-010426-191020

**Pages**: 1-3

---

**📄 Source: PDF Page 1**

HIP/OCL monorepo build
ROCr Build
HIP Build
OCL build
Related articles
Please refer to 
rocm-systems/CONTRIBUTING.md at develop · ROCm/rocm-systems  for all
the information on rocm-systems repository migration and guidelines.
Refer to github config settings before starting your development 
ROCr Build
HIP Build
Building hip on AMD
Github config settings
1
cd rocr-runtime/build
2
cmake .. -DCMAKE_PREFIX_PATH=/opt/rocm -
DCMAKE_INSTALL_PREFIX=$PWD/install
3
make -j4 
4
make -j4 install
1
export HIP_DIR="$(readlink -f hip)"
2
export CLR_DIR="$(readlink -f clr)"
3
export HIPTESTS_DIR="$(readlink -f hip-tests)"
4
export ROCM_PATH=/opt/rocm
5
6
cd "$CLR_DIR"
7
mkdir -p build; cd build
8
cmake -DHIP_COMMON_DIR=$HIP_DIR -DCMAKE_PREFIX_PATH="/opt/rocm/" -
DCMAKE_INSTALL_PREFIX=$PWD/install -DCLR_BUILD_HIP=ON -

---

---

**📄 Source: PDF Page 2**

build hip-tests on AMD using the locally built hip
Unit tests:
Stress tests:
build hip-tests on AMD using the locally built hip
Create a pull request, first by creating a private branch 
Opening the PR
Tests and CI - Use this in a PR comment to trigger the PSDB job.
OCL build
Rebase:
DCLR_BUILD_OCL=OFF -DHIP_PLATFORM=amd -DCMAKE_BUILD_TYPE=Debug ..
9
make -j$(nproc)
10
make install
11
12
1
cd "$HIPTESTS_DIR"
2
mkdir -p build; cd build
3
export ROCM_PATH=/opt/rocm
4
cmake ../catch -DHIP_PLATFORM=amd -
DCMAKE_PREFIX_PATH=$CLR_DIR/build/install -DCMAKE_BUILD_TYPE=Debug -
DCMAKE_CXX_COMPILER=amdclang++ -DCMAKE_C_COMPILER=amdclang -
DCMAKE_HIP_COMPILER=amdclang++ -DOFFLOAD_ARCH_STR="--offload-
arch=gfx1201"
5
make build_tests -j$(nproc)
1
cd "$HIPTESTS_DIR"
2
mkdir -p build; cd build
3
export ROCM_PATH=/opt/rocm
4
cmake ../catch -DHIP_PLATFORM=amd -
DCMAKE_PREFIX_PATH=$CLR_DIR/build/install -DCMAKE_BUILD_TYPE=Debug -
DCMAKE_CXX_COMPILER=amdclang++ -DCMAKE_C_COMPILER=amdclang -
DCMAKE_HIP_COMPILER=amdclang++ -DOFFLOAD_ARCH_STR="--offload-
arch=gfx1201" -DBUILD_STRESS_TESTS=ON
5
make stress_test -j$(nproc)
1
git checkout -b users/<github-username>/<branch-name> 
1
git push origin branch-name-like-above
1
/AzurePipelines run rocm-ci-caller
1
cd "$CLR_DIR"
2
mkdir -p build; cd build
3
cmake -DCMAKE_PREFIX_PATH="/opt/rocm/" -DCLR_BUILD_HIP=OFF -
DCLR_BUILD_OCL=ON -DBUILD_TESTS=ON ..
4
make -j$(nproc)
5
1
git checkout <dev_branch>

### Code Examples

```unknown
users/<github-username>/<branch-name>
```

---

---

**📄 Source: PDF Page 3**

Troubleshooting:
1. We need to run below package everytime we change ROCM to fix below error.
sudo apt install rocm-llvm-dev
2. install python package to fix below CppHeaderParser error:
sudo apt install python3 python3-pip
pip3 install --break-system-packages CppHeaderParser
Related articles
2
git remote update
3
git merge origin/develop
1
CMake Error at hipamd/src/CMakeLists.txt:185 (find_package):
2
Could not find a package configuration file provided by "LLVM" with
any of
3
the following names:
4
5
LLVMConfig.cmake
6
llvm-config.cmake
7
8
Add the installation prefix of "LLVM" to CMAKE_PREFIX_PATH or set
9
"LLVM_DIR" to a directory containing one of the above files.  If
"LLVM"
10
provides a separate development package or SDK, be sure it has been
11
installed.
1
ModuleNotFoundError: No module named 'CppHeaderParser'
2
CMake Error at hipamd/src/CMakeLists.txt:227 (message):
3
The "CppHeaderParser" Python3 package is not installed.
Please install it using the following command: "pip3 install
CppHeaderParser"
Building HIP via Github Emu and creating commits

---

