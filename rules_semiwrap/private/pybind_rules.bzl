load("@pybind11_bazel//:build_defs.bzl", "pybind_extension", "pybind_library")
load("@rules_pycross//pycross/private:wheel_library.bzl", "pycross_wheel_library")
load("@rules_python//python:defs.bzl", "py_library")
load("@rules_python//python:packaging.bzl", "py_wheel")
# load("@aspect_bazel_lib//lib:copy_to_directory.bzl", "copy_to_directory")

def create_pybind_library(
        name,
        extension_name = None,
        generated_srcs = [],
        extra_hdrs = [],
        extra_srcs = [],
        entry_point = [],
        deps = [],
        semiwrap_header = [],
        copts = [],
        includes = [],
        local_defines = []):
    # srcs = [DAT_TO_CC_DIR + src + ".cpp" for src in dat_to_cc_srcs]
    pybind_library(
        name = "{}_pybind_library".format(name),
        hdrs = extra_hdrs,
        copts = copts + select({
            "@bazel_tools//src/conditions:darwin": [
                "-Wno-deprecated-declarations",
                "-Wno-overloaded-virtual",
                "-Wno-pessimizing-move",
            ],
            "@bazel_tools//src/conditions:linux_x86_64": [
                "-Wno-attributes",
                "-Wno-unused-value",
                "-Wno-deprecated",
                "-Wno-deprecated-declarations",
                "-Wno-unused-parameter",
                "-Wno-redundant-move",
                "-Wno-unused-but-set-variable",
                "-Wno-unused-variable",
                "-Wno-pessimizing-move",
            ],
            "@bazel_tools//src/conditions:windows": [
            ],
        }),
        deps = deps + [
            "@rules_semiwrap//:semiwrap_headers",
        ],
        includes = includes,
        visibility = ["//visibility:public"],
        local_defines = local_defines,
    )

    extension_name = extension_name or "_{}".format(name)
    pybind_extension(
        name = extension_name,
        srcs = generated_srcs + extra_srcs + entry_point,
        deps = [":{}_pybind_library".format(name)] + semiwrap_header,
        visibility = ["//visibility:private"],
        target_compatible_with = select({
            "//conditions:default": [],
        }),
        copts = copts + select({
            "@bazel_tools//src/conditions:darwin": [
                "-Wno-deprecated-declarations",
                "-Wno-overloaded-virtual",
                "-Wno-pessimizing-move",
            ],
            "@bazel_tools//src/conditions:linux_x86_64": [
                "-Wno-attributes",
                "-Wno-unused-value",
                "-Wno-deprecated",
                "-Wno-deprecated-declarations",
                "-Wno-unused-parameter",
                "-Wno-redundant-move",
                "-Wno-unused-but-set-variable",
                "-Wno-unused-variable",
                "-Wno-pessimizing-move",
            ],
            "@bazel_tools//src/conditions:windows": [
            ],
        }),
        local_defines = local_defines,
    )

def robotpy_library(
        name,
        package_name,
        strip_path_prefixes,
        version,
        data = [],
        deps = [],
        robotpy_wheel_deps = [],
        entry_points = {},
        package_python_tag = "cp311",
        package_abi = "cp311",
        package_summary = None,
        package_project_urls = None,
        package_author_email = None,
        package_requires = None,
        visibility = None,
        **kwargs):
    if deps:
        fail()

    if package_summary == None:
        fail()

    # if package_project_urls == None:
    #     fail()
    if package_author_email == None:
        fail()
    if package_author_email == None:
        fail()
    if package_requires == None:
        fail()

    py_library(
        name = name,
        visibility = visibility,
        data = data,
        deps = robotpy_wheel_deps,
        **kwargs
    )

    py_wheel(
        name = "{}-wheel".format(name),
        distribution = package_name,
        platform = select({
            "@bazel_tools//src/conditions:darwin": "macosx_11_0_x86_64",
            "@bazel_tools//src/conditions:windows": "win_amd64",
            "//conditions:default": "manylinux_2_35_x86_64",
        }),
        python_tag = package_python_tag,
        abi = package_abi,
        stamp = 1,
        version = version,
        summary = package_summary,
        project_urls = package_project_urls,
        author_email = package_author_email,
        deps = data + [":{}".format(name)],
        requires = package_requires,
        # deps = data + [":{}".format(name)] + ["{}.copy_headers".format(name)],
        # data = ,
        strip_path_prefixes = strip_path_prefixes,
        entry_points = entry_points,
    )

    pycross_wheel_library(
        name = "_import",
        wheel = "{}-wheel".format(name),
        deps = robotpy_wheel_deps,
        visibility = visibility,
        tags = ["manual"],
    )

    # TODO
    native.alias(
        name = "import",
        actual = "_import",
        visibility = visibility,
        tags = ["manual"],
    )
