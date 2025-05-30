load("@rules_pycross//pycross/private:wheel_library.bzl", "pycross_wheel_library")
load("@rules_python//python:defs.bzl", "py_library")
load("@rules_python//python:packaging.bzl", "py_package", "py_wheel")
load("//rules_semiwrap/private:copy_native_file.bzl", "copy_native_file")
load("//rules_semiwrap/private:hatch_nativelib_helpers.bzl", "gen_libinit")

def create_native_library(
        name,
        lib_name,
        package_name,
        shared_library,
        module_dependencies,
        strip_pkg_prefix,
        version,
        deps = [],
        visibility = ["//visibility:public"]):
    if deps:
        fail("Don't use deps directly")

    gen_libinit(
        name = "{}.gen_lib_init".format(name),
        lib_name = lib_name,
        modules = module_dependencies,
        output_file = "native/{}/_init_{}.py".format(lib_name, package_name.replace("-", "_")),
    )

    copy_native_file(
        name = lib_name,
        base_path = "native/{}/".format(lib_name),
        library = shared_library,
    )
    py_library(
        name = package_name,
        srcs = ["{}.gen_lib_init".format(name)],
        data = [":{}.copy_lib".format(lib_name)],
        imports = ["."],
        visibility = visibility,
    )

    py_package(
        name = "{}-pkg".format(package_name),
        deps = [":{}".format(package_name)],
    )

    py_wheel(
        name = "{}-wheel".format(package_name),
        distribution = package_name,
        platform = select({
            "@bazel_tools//src/conditions:darwin": "macosx_11_0_x86_64",
            "@bazel_tools//src/conditions:windows": "win_amd64",
            "//conditions:default": "manylinux_2_35_x86_64",
        }),
        python_tag = "py3",
        stamp = 1,
        version = version,
        deps = [":{}-pkg".format(package_name)],
        strip_path_prefixes = strip_pkg_prefix,
    )

    pycross_wheel_library(
        name = "import",
        wheel = "{}-wheel".format(package_name),
        visibility = visibility,
    )
