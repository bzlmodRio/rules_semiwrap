load("@aspect_bazel_lib//lib:copy_to_directory.bzl", "copy_to_directory")
load("@rules_pycross//pycross/private:wheel_library.bzl", "pycross_wheel_library")
load("@rules_python//python:defs.bzl", "py_library")
load("@rules_python//python:packaging.bzl", "py_package", "py_wheel")
load("//rules_semiwrap/private:copy_native_file.bzl", "copy_native_file")
load("//rules_semiwrap/private:hatch_nativelib_helpers.bzl", "generate_native_lib_files")

def create_native_library(
        name,
        lib_name,
        headers,
        headers_external_repositories,
        package_name,
        shared_library,
        strip_pkg_prefix,
        version,
        deps = [],
        local_pc_file_info = [],
        pc_dep_files = [],
        pc_dep_deps = [],
        entry_points = {},
        package_summary = None,
        package_project_urls = None,
        package_author_email = None,
        package_requires = None,
        visibility = ["//visibility:public"]):
    if deps:
        fail("Don't use deps directly")

    # if module_dependencies:
    #     fail()

    if package_summary == None:
        fail()

    # if package_requires == None:
    #     fail()

    if local_pc_file_info:
        if pc_dep_files or pc_dep_deps:
            fail()

    copy_to_directory(
        name = "{}.copy_headers".format(name),
        srcs = [headers],
        include_external_repositories = headers_external_repositories,
        out = "native/{}/include".format(lib_name),
        root_paths = [""],
        exclude_srcs_patterns = ["**/BUILD.bazel", "WORKSPACE"],
        verbose = False,
    )

    libinit_file = "native/{}/_init_{}.py".format(lib_name, package_name.replace("-", "_"))
    pc_file = "native/{}/{}.pc".format(lib_name, package_name)

    pc_dep_files_ = list(pc_dep_files)
    pc_dep_deps_ = list(pc_dep_deps)

    for d, pcfiles in local_pc_file_info:
        pc_dep_deps_.append(d)
        pc_dep_files_.extend(pcfiles)


    generate_native_lib_files(
        name = "{}.generate_native_files".format(name),
        pc_dep_files = pc_dep_files_,
        pc_dep_deps = pc_dep_deps_,
        libinit_file = libinit_file,
        pc_file = pc_file,
        pyproject_toml = "pyproject.toml",
    )

    # TODO hacked
    hal_lib_name = lib_name
    if lib_name == "wpihal":
        hal_lib_name = "wpiHal"
    elif lib_name == "wpilib":
        hal_lib_name = "wpilibc"
    elif lib_name == "romi":
        hal_lib_name = "romiVendordep"
    elif lib_name == "xrp":
        hal_lib_name = "xrpVendordep"

    copy_native_file(
        name = hal_lib_name,
        base_path = "native/{}/".format(lib_name),
        library = shared_library,
    )
    py_library(
        name = package_name,
        srcs = [libinit_file],
        data = [":{}.copy_lib".format(hal_lib_name), "{}.copy_headers".format(name), pc_file],
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
        entry_points = entry_points,
        summary = package_summary,
        project_urls = package_project_urls,
        author_email = package_author_email,
        requires = package_requires,
    )

    pycross_wheel_library(
        name = "import",
        wheel = "{}-wheel".format(package_name),
        visibility = visibility,
    )
