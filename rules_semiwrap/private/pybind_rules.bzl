load("@pybind11_bazel//:build_defs.bzl", "pybind_extension", "pybind_library")
load("@rules_pycross//pycross/private:wheel_library.bzl", "pycross_wheel_library")
load("@rules_python//python:defs.bzl", "py_library")
load("@rules_python//python:packaging.bzl", "py_wheel", "py_package")

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
        srcs = generated_srcs + extra_srcs,
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
        srcs = entry_point,
        deps = [":{}_pybind_library".format(name)] + semiwrap_header,
        visibility = ["//visibility:private"],
        target_compatible_with = select({
            "//conditions:default": [],
        }),
        copts = copts + select({
            "@bazel_tools//src/conditions:darwin": [
            ],
            "@bazel_tools//src/conditions:linux_x86_64": [
                "-Wno-unused-parameter",
            ],
            "@bazel_tools//src/conditions:windows": [
            ],
        }),
    )

def robotpy_library(
        name,
        package_name,
        strip_path_prefixes,
        version,
        data = [],
        deps = [],
        robotpy_wheel_deps = [],
        visibility = None,
        **kwargs):
    if deps:
        fail()

    py_library(
        name = name,
        visibility = None,
        data = data,
        deps = robotpy_wheel_deps,
        **kwargs
    )

    print(name  )
    if name == "hal":
        native.filegroup(
            name = "ahhhhh",
            srcs = [":hal/wpihal.pc".format(name)]
        )
    elif name == "wpimath":
        native.filegroup(
            name = "ahhhhh",
            srcs = [
                ":{}/{}.pc".format(name, name),
                ":wpimath/filter/wpimath_filter.pc".format(name),
                ":wpimath/geometry/wpimath_geometry.pc".format(name),
                ":wpimath/spline/wpimath_spline.pc".format(name),
            ]
        )
    else:
        native.filegroup(
            name = "ahhhhh",
            srcs = [":{}/{}.pc".format(name, name)]
        )
    

    # py_package(
    #     name = "ahhhhhhh",
    #     # Only include these Python packages.
    #     # packages = ["examples.wheel"],
    #     deps = [":{}/{}.pc".format(name, name)],
    # )

    py_wheel(
        name = "{}-wheel".format(name),
        distribution = package_name,
        platform = select({
            "@bazel_tools//src/conditions:darwin": "macosx_11_0_x86_64",
            "@bazel_tools//src/conditions:windows": "win_amd64",
            "//conditions:default": "manylinux_2_35_x86_64",
        }),
        python_tag = "py3",
        stamp = 1,
        version = version,
        deps = data + [":{}".format(name), ] + [":ahhhhh"],
        # data = ,
        strip_path_prefixes = strip_path_prefixes,
    )

    pycross_wheel_library(
        name = "_import",
        wheel = "{}-wheel".format(name),
        deps = robotpy_wheel_deps,
        visibility = visibility,
        tags = ["manual"],
    )

    native.alias(
        name = "import",
        actual = select({
            "@bazel_tools//src/conditions:windows": name,
            "//conditions:default": "_import",
        }),
        visibility = visibility,
    )
