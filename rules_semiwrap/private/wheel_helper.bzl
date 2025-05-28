
load("@rules_python//python:packaging.bzl", "py_wheel")
load("@rules_pycross//pycross/private:wheel_library.bzl", "pycross_wheel_library")

def wheel_helper(
    name,
    package_name,
    strip_path_prefixes,
    robotpy_wheel_deps,
    data,
    version,
    visibility,
):

    py_wheel(
        name = "{}-wheel".format(name),
        distribution = package_name,
        platform = select({
            "@bazel_tools//src/conditions:darwin": "win_amd64",
            "@bazel_tools//src/conditions:windows": "macosx_11_0_x86_64",
            "//conditions:default": "manylinux_2_35_x86_64",
        }),
        python_tag = "py3",
        stamp = 1,
        version = version,
        deps = data + [":{}".format(name)],
        strip_path_prefixes = strip_path_prefixes,
    )

    pycross_wheel_library(
        name = "import",
        wheel = "{}-wheel".format(name),
        deps = robotpy_wheel_deps,
        visibility = visibility,
    )
