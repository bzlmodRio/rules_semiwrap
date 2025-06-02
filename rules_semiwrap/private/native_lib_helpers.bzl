load("@rules_pycross//pycross/private:wheel_library.bzl", "pycross_wheel_library")
load("@rules_python//python:defs.bzl", "py_library")
load("@rules_python//python:packaging.bzl", "py_package", "py_wheel")
load("//rules_semiwrap/private:copy_native_file.bzl", "copy_native_file")
load("//rules_semiwrap/private:hatch_nativelib_helpers.bzl", "gen_libinit")
load("@aspect_bazel_lib//lib:copy_to_directory.bzl", "copy_to_directory")

def create_native_library(
        name,
        lib_name,
        headers,
        headers_external_repositories,
        package_name,
        shared_library,
        module_dependencies,
        strip_pkg_prefix,
        version,
        deps = [],
        visibility = ["//visibility:public"]):
    if deps:
        fail("Don't use deps directly")

    copy_to_directory(
        name = "{}.copy_headers".format(name),
        srcs = [headers],
        include_external_repositories = headers_external_repositories,
        out = "native/{}/include".format(lib_name),
        root_paths = [""],
        exclude_srcs_patterns = ["**/BUILD.bazel", "WORKSPACE"],
        verbose=False,
    )

    gen_libinit(
        name = "{}.gen_lib_init".format(name),
        lib_name = lib_name,
        modules = module_dependencies,
        output_file = "native/{}/_init_{}.py".format(lib_name, package_name.replace("-", "_")),
    )

    native.genrule(
        name = "{}.gen_pc".format(name),
        outs = ["native/{}/{}.pc".format(lib_name, package_name)],
        srcs = [":pyproject.toml"],
        cmd = '$(locations @rules_semiwrap//rules_semiwrap/private:render_native_pc) --output_file=$(OUTS) --project_file=$(location :pyproject.toml)',
        tools = ["@rules_semiwrap//rules_semiwrap/private:render_native_pc"],
        visibility = ["//visibility:public"],
    )

    copy_native_file(
        name = lib_name,
        base_path = "native/{}/".format(lib_name),
        library = shared_library,
    )
    py_library(
        name = package_name,
        srcs = ["{}.gen_lib_init".format(name)],
        data = [":{}.copy_lib".format(lib_name), "{}.copy_headers".format(name), "{}.gen_pc".format(name)],
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
