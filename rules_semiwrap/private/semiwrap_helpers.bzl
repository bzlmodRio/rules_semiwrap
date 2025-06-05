load("@rules_cc//cc:defs.bzl", "cc_library")
load("@rules_python//python:defs.bzl", "py_binary")
load("@rules_semiwrap_pip_deps//:requirements.bzl", "requirement")

# PUBLISH_CASTERS_DIR = "generated/publish_casters/"
RESOLVE_CASTERS_DIR = "generated/resolve_casters/"
HEADER_DAT_DIR = "generated/header_to_dat/"
DAT_TO_CC_DIR = "generated/dat_to_cc/"
DAT_TO_TMPL_CC_DIR = "generated/dat_to_tmpl_cc/"
DAT_TO_TMPL_HDR_DIR = "generated/dat_to_tmpl_hdr/"
GEN_MODINIT_HDR_DIR = "generated/gen_modinit_hdr/"

def _location_helper(filename):
    return " $(locations " + filename + ")"

def _wrapper():
    return "$(locations @rules_semiwrap//:wrapper) "

def _wrapper_dep():
    return ["@rules_semiwrap//:wrapper"]

def _local_include_root(project_import, include_subpackage):
    return "$(location " + project_import + ")/site-packages/native/" + include_subpackage + "/include"

def publish_casters(
        name,
        project_config,
        caster_name,
        output_json,
        output_pc,
        typecasters_srcs):
    cmd = _wrapper() + " semiwrap.cmd.publish_casters"
    cmd += " $(SRCS) " + caster_name + " $(OUTS)"

    native.genrule(
        name = name,
        srcs = [project_config],
        outs = [output_json, output_pc],
        cmd = cmd,
        tools = _wrapper_dep() + typecasters_srcs,
        visibility = ["//visibility:public"],
    )

def resolve_casters(
        name,
        casters_pkl_file,
        dep_file,
        caster_files = [],
        caster_deps = []):
    cmd = _wrapper() + " semiwrap.cmd.resolve_casters "
    cmd += " $(OUTS)"

    cmd += _location_helper("@rules_semiwrap//:semiwrap_casters")

    resolved_caster_files = []

    deps = []
    for dep, caster_path in caster_deps:
        deps.append(dep)
        cmd += " " + caster_path

    for cfd in caster_files:
        if cfd.startswith(":"):
            resolved_caster_files.append(cfd)
            cmd += _location_helper(cfd)
        else:
            cmd += " " + cfd

    native.genrule(
        name = name,
        srcs = resolved_caster_files + deps,
        outs = [RESOLVE_CASTERS_DIR + casters_pkl_file, RESOLVE_CASTERS_DIR + dep_file],
        cmd = cmd,
        tools = _wrapper_dep() + ["@rules_semiwrap//:semiwrap_casters"],
    )

def gen_libinit(
        name,
        output_file,
        modules):
    cmd = _wrapper() + " semiwrap.cmd.gen_libinit "
    cmd += " $(OUTS) "
    cmd += " ".join(modules)

    native.genrule(
        name = name,
        outs = [output_file],
        cmd = cmd,
        tools = _wrapper_dep(),
    )

def gen_pkgconf(
        name,
        project_file,
        module_pkg_name,
        pkg_name,
        output_file,
        libinit_py,
        install_path):
    cmd = _wrapper() + " semiwrap.cmd.gen_pkgconf "
    cmd += " " + module_pkg_name + " " + pkg_name
    cmd += _location_helper(project_file)
    cmd += " $(OUTS)"
    if libinit_py:
        cmd += " --libinit-py " + libinit_py

    OUT_FILE = install_path + "/" + output_file
    native.genrule(
        name = name,
        outs = [OUT_FILE],
        cmd = cmd,
        tools = _wrapper_dep() + [project_file],
    )

def header_to_dat(
        name,
        casters_pickle,
        include_root,
        class_name,
        yml_file,
        header_location,
        generation_includes = [],
        header_to_dat_deps = [],
        extra_defines = [],
        deps = []):
    # print(class_name)
    cmd = _wrapper() + " semiwrap.cmd.header2dat "
    cmd += "--cpp 202002L "  # TODO
    cmd += class_name
    cmd += _location_helper(yml_file)

    # cmd += _location_helper(header_to_dat_deps)
    cmd += " -I " + include_root

    # TODO TEMP
    for inc in generation_includes:
        cmd += " -I " + inc
    for d in extra_defines:
        cmd += " -D '" + d + "'"
    cmd += " " + header_location

    cmd += " " + include_root
    cmd += _location_helper(RESOLVE_CASTERS_DIR + casters_pickle)
    cmd += " $(OUTS)"
    cmd += " bogus c++20 ccache c++ -- -std=c++20"  # TODO
    native.genrule(
        name = name + "." + class_name,
        srcs = [RESOLVE_CASTERS_DIR + casters_pickle] + deps + header_to_dat_deps,
        outs = [HEADER_DAT_DIR + class_name + ".dat", HEADER_DAT_DIR + class_name + ".d"],
        cmd = cmd,
        tools = _wrapper_dep() + [yml_file],
    )

def dat_to_cc(
        name,
        class_name):
    dat_file = HEADER_DAT_DIR + class_name + ".dat"
    cmd = _wrapper() + " semiwrap.cmd.dat2cpp "
    cmd += _location_helper(dat_file)
    cmd += " $(OUTS)"
    native.genrule(
        name = name + "." + class_name,
        outs = [DAT_TO_CC_DIR + class_name + ".cpp"],
        cmd = cmd,
        tools = _wrapper_dep() + [dat_file],
    )

def dat_to_tmpl_cpp(name, base_class_name, specialization, tmp_class_name):
    cmd = _wrapper() + " semiwrap.cmd.dat2tmplcpp "
    cmd += _location_helper(HEADER_DAT_DIR + base_class_name + ".dat")
    cmd += " " + specialization
    cmd += " $(OUTS)"
    native.genrule(
        name = name + "." + tmp_class_name,
        outs = [DAT_TO_TMPL_CC_DIR + tmp_class_name + ".cpp"],
        cmd = cmd,
        tools = _wrapper_dep() + [HEADER_DAT_DIR + base_class_name + ".dat"],
    )

def dat_to_tmpl_hpp(name, class_name):
    dat_file = HEADER_DAT_DIR + class_name + ".dat"

    # print(dat_file)
    cmd = _wrapper() + " semiwrap.cmd.dat2tmplhpp "
    cmd += _location_helper(dat_file)
    cmd += " $(OUTS)"
    native.genrule(
        name = name + "." + class_name,
        outs = [DAT_TO_TMPL_HDR_DIR + class_name + "_tmpl.hpp"],
        cmd = cmd,
        tools = _wrapper_dep() + [dat_file],
    )

def dat_to_trampoline(name, dat_file, class_name, output_file):
    cmd = _wrapper() + " semiwrap.cmd.dat2trampoline "

    cmd += _location_helper(HEADER_DAT_DIR + dat_file)
    cmd += "  " + class_name
    cmd += " $(OUTS)"

    native.genrule(
        name = name + "." + output_file,
        outs = [output_file],
        cmd = cmd,
        tools = _wrapper_dep() + [HEADER_DAT_DIR + dat_file],
    )

def gen_modinit_hpp(
        name,
        libname,
        input_dats,
        output_file):
    input_dats = [HEADER_DAT_DIR + x + ".dat" for x in input_dats]

    cmd = _wrapper() + " semiwrap.cmd.gen_modinit_hpp "
    cmd += " " + libname
    cmd += " $(OUTS)"
    for input_dat in input_dats:
        cmd += _location_helper(input_dat)

    native.genrule(
        name = name + ".gen",
        outs = [GEN_MODINIT_HDR_DIR + output_file],
        cmd = cmd,
        tools = _wrapper_dep() + input_dats,
    )
    cc_library(
        name = name,
        hdrs = [GEN_MODINIT_HDR_DIR + output_file],
        strip_include_prefix = GEN_MODINIT_HDR_DIR,
    )

def make_pyi(name, extension_library, interface_files, init_pkgcfgs, extension_package, install_path, python_deps, init_packages, local_extension_deps = []):
    outs = []

    init_file = init_packages[0] + "/__init__.py"

    cmd = "$(locations " + name + ".gen_wrapper" + ") "
    cmd += " --install_path={}".format(install_path)
    cmd += " --extension_package={}".format(extension_package)
    cmd += " --output_files $(OUTS)"
    for of in interface_files:
        outs.append(install_path + "/" + of)

    cmd += " --remapping_args "
    for init_package in init_packages:
        cmd += " {} $(location {})".format(init_package.replace("/", "."), init_package + "/__init__.py")
    for init_pkgcfg in init_pkgcfgs:
        cmd += " {} $(location {})".format(init_pkgcfg[:-3].replace("/", "."), init_pkgcfg)
    for extension_path, extension_dep in local_extension_deps:
        cmd += " {} $(location {})".format(extension_path.replace("/", "."), extension_dep)
    cmd += " {} $(location {})".format(extension_package, extension_library)

    py_binary(
        name = name + ".gen_wrapper",
        srcs = ["@rules_semiwrap//rules_semiwrap/private:make_pyi_wrapper.py"],
        main = "make_pyi_wrapper.py",
        deps = [requirement("semiwrap")] + python_deps,
    )

    native.genrule(
        name = name,
        srcs = init_pkgcfgs + [x[1] for x in local_extension_deps] + [extension_library] + [init_package + "/__init__.py" for init_package in init_packages],
        outs = outs,
        cmd = cmd,
        tools = [name + ".gen_wrapper"],
    )

def run_header_gen(name, casters_pickle, trampoline_subpath, header_gen_config, deps = [], generation_includes = [], generation_defines = [], header_to_dat_deps = [], local_native_libraries = []):
    temp_yml_files = []

    generation_includes = list(generation_includes)
    header_to_dat_deps = list(header_to_dat_deps)

    if header_to_dat_deps:
        fail()

    if generation_includes and not (("wpimath" not in name) or ("cscore" not in name)):
        fail()

    for project_label, include_subpackage in local_native_libraries:
        header_to_dat_deps.append(project_label)
        generation_includes.append(_local_include_root(project_label, include_subpackage))

    # print(generation_includes)
    # print(header_to_dat_deps)

    for header_gen in header_gen_config:
        temp_yml_files.append(header_gen.yml_file)

        header_to_dat(
            name = name + ".header_to_dat",
            casters_pickle = casters_pickle,
            include_root = header_gen.header_root,
            class_name = header_gen.class_name,
            yml_file = header_gen.yml_file,
            header_location = header_gen.header_file,
            deps = deps,
            generation_includes = generation_includes,
            extra_defines = generation_defines,
            header_to_dat_deps = header_to_dat_deps,
        )

    native.filegroup(
        name = name + ".yml_files",
        srcs = temp_yml_files,
        tags = ["manual"],
    )

    generated_cc_files = []
    for header_gen in header_gen_config:
        dat_to_cc(
            name = name + ".dat_to_cc",
            class_name = header_gen.class_name,
        )
        generated_cc_files.append(DAT_TO_CC_DIR + header_gen.class_name + ".cpp")

    tmpl_hdrs = []
    for header_gen in header_gen_config:
        if header_gen.tmpl_class_names:
            dat_to_tmpl_hpp(
                name = name + ".dat_to_tmpl_hpp",
                class_name = header_gen.class_name,
            )
            tmpl_hdrs.append(DAT_TO_TMPL_HDR_DIR + header_gen.class_name + "_tmpl.hpp")

        for tmpl_class_name, specialization in header_gen.tmpl_class_names:
            dat_to_tmpl_cpp(
                name = name + ".dat_to_tmpl_cpp",
                base_class_name = header_gen.class_name,
                specialization = specialization,
                tmp_class_name = tmpl_class_name,
            )
            generated_cc_files.append(DAT_TO_TMPL_CC_DIR + tmpl_class_name + ".cpp")

    trampoline_hdrs = []
    for header_gen in header_gen_config:
        for trampoline_symbol, trampoline_header in header_gen.trampolines:
            output_path = trampoline_subpath + "/trampolines/" + trampoline_header
            dat_to_trampoline(
                name = name + ".dat2trampoline",
                dat_file = header_gen.class_name + ".dat",
                class_name = trampoline_symbol,
                output_file = output_path,
            )
            trampoline_hdrs.append(output_path)
    cc_library(
        name = name + ".tmpl_hdrs",
        hdrs = tmpl_hdrs,
        strip_include_prefix = DAT_TO_TMPL_HDR_DIR,
    )
    cc_library(
        name = name + ".trampoline_hdrs",
        hdrs = trampoline_hdrs,
        strip_include_prefix = trampoline_subpath,
    )

    native.filegroup(
        name = name + ".generated_srcs",
        srcs = generated_cc_files,
        tags = ["manual"],
    )

    native.filegroup(
        name = name + ".trampoline_hdr_files",
        srcs = trampoline_hdrs,
        tags = ["manual"],
    )

    native.filegroup(
        name = name + ".header_gen_files",
        srcs = tmpl_hdrs + trampoline_hdrs + generated_cc_files,
        tags = ["manual"],
    )
