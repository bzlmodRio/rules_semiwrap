import argparse
import pathlib


def generate_files(project_dir: pathlib.Path):
    project_name = project_dir.name

    with open(project_dir / "MODULE.bazel", 'w') as f:
        f.write(f"""bazel_dep(name = "rules_python", version = "1.0.0")
bazel_dep(name = "pybind11_bazel", version = "2.13.6")
bazel_dep(name = "rules_cc", version = "0.0.17")
bazel_dep(name = "platforms", version = "0.0.10")
bazel_dep(name = "aspect_bazel_lib", version = "2.16.0")
bazel_dep(name = "rules_pycross", version = "0.7.1")
bazel_dep(name = "caseyduquettesc_rules_python_pytest", version = "1.1.1", repo_name = "rules_python_pytest")
bazel_dep(name = "bzlmodrio-allwpilib", version = "")
bazel_dep(name = "rules_semiwrap", version = "")

local_path_override(
    module_name = "rules_semiwrap",
    path = "../rules_semiwrap",
)

archive_override(
    module_name = "pybind11_bazel",
    integrity = "sha256-iwRj1wuX2pDS6t6DqiCfhIXisv4y+7CvxSJtZoSAzGw=",
    patch_strip = 1,
    patches = [
        "//:0001-Patch-to-robotpy-version.patch",
    ],
    strip_prefix = "pybind11_bazel-2b6082a4d9d163a52299718113fa41e4b7978db5",
    urls = ["https://github.com/pybind/pybind11_bazel/archive/2b6082a4d9d163a52299718113fa41e4b7978db5.tar.gz"],
)

python = use_extension(
    "@rules_python//python/extensions:python.bzl",
    "python",
    dev_dependency = True,
)
python.toolchain(
    ignore_root_user_error = True,
    is_default = True,
    python_version = "3.10",
)

pip = use_extension("@rules_python//python/extensions:pip.bzl", "pip")
pip.parse(
    hub_name = "{project_name.replace("-", "_")}_pip_deps",
    python_version = "3.10",
    requirements_lock = "//:requirements_lock.txt",
)
use_repo(pip, "{project_name.replace("-", "_")}_pip_deps")
""")

    with open(project_dir / "BUILD.bazel", 'w') as f:
        f.write("""load("@rules_python//python:pip.bzl", "compile_pip_requirements")

# bazel run //:requirements.update / bazel test //:requirements_test
compile_pip_requirements(
    name = "requirements",
    extra_args = ["--allow-unsafe"],
    requirements_in = "pyproject.toml",
    requirements_txt = "requirements_lock.txt",
    requirements_windows = "requirements_windows.txt",
)

""")

    with open(project_dir / ".bazelversion", 'w') as f:
        f.write("7.3.1\n")
        
    with open(project_dir / ".bazelrc", 'w') as f:
        f.write("""try-import %workspace%/.bazel_auth.rc
try-import %workspace%/user.bazelrc

test --test_output=errors
test --test_verbose_timeout_warnings


common --registry=https://raw.githubusercontent.com/pjreiniger/bazel-central-registry/bzlmodrio/


common --enable_platform_specific_config

build -c=opt

build:linux   --copt=-std=c++20
build:macos   --copt=-std=c++20

build:windows --copt=/std:c++20
build:windows --copt=/Zc:__cplusplus
build:windows --copt=/Zc:preprocessor
build:windows --copt=/utf-8
""")

    with open(project_dir / "WORKSPACE", 'w') as f:
        f.write("\n")

    with open(project_dir / "tests/BUILD.bazel", 'w') as f:
        f.write("\n")

    with open(project_dir / "requirements.txt", 'w') as f:
        f.write("\n")

    with open(project_dir / "requirements_lock.txt", 'w') as f:
        f.write("\n")

def main():

    project_dir = pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/robotpy-rev")

    generate_files(project_dir)


if __name__ == "__main__":
    # python3 -m rules_semiwrap.tools.bazelify_project
    main()