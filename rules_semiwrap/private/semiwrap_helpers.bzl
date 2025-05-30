load("@rules_cc//cc:defs.bzl", "cc_library")

PUBLISH_CASTERS_DIR = "generated/publish_casters/"
RESOLVE_CASTERS_DIR = "generated/resolve_casters/"
GEN_PKGCONF_DIR = "generated/gen_pkgconf/"
HEADER_DAT_DIR = "generated/header_to_dat/"
DAT_TO_CC_DIR = "generated/dat_to_cc/"
DAT_TO_TMPL_CC_DIR = "generated/dat_to_tmpl_cc/"
DAT_TO_TMPL_HDR_DIR = "generated/dat_to_tmpl_hdr/"
DAT_TO_TRAMPOLINE_HDR_DIR = "generated/dat_to_trampoline_hdr/"
GEN_MODINIT_HDR_DIR = "generated/gen_modinit_hdr/"

def _location_helper(filename):
    return " $(locations " + filename + ")"

def _wrapper():
    return "$(locations @rules_semiwrap//:wrapper) "

def _wrapper_dep():
    return ["@rules_semiwrap//:wrapper"]

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
        outs = [PUBLISH_CASTERS_DIR + output_json, PUBLISH_CASTERS_DIR + output_pc],
        cmd = cmd,
        tools = _wrapper_dep() + typecasters_srcs,
        visibility = ["//visibility:public"],
    )

def resolve_casters(
        name,
        casters_pkl_file,
        caster_files,
        dep_file):
    cmd = _wrapper() + " semiwrap.cmd.resolve_casters "
    cmd += " $(OUTS)"

    cmd += _location_helper("@rules_semiwrap//:semiwrap_casters")

    resolved_caster_files = []
    for cfd in caster_files:
        if not cfd.startswith("//"):
            cfd = PUBLISH_CASTERS_DIR + cfd
        resolved_caster_files.append(cfd)
        cmd += _location_helper(cfd)

    native.genrule(
        name = name,
        srcs = resolved_caster_files,
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
        libinit_py):
    cmd = _wrapper() + " semiwrap.cmd.gen_pkgconf "
    cmd += " " + module_pkg_name + " " + pkg_name
    cmd += _location_helper(project_file)
    cmd += " $(OUTS)"
    if libinit_py:
        cmd += " --libinit-py " + libinit_py

    native.genrule(
        name = name,
        outs = [GEN_PKGCONF_DIR + output_file],
        cmd = cmd,
        tools = _wrapper_dep() + [project_file],
    )

def header_to_dat(
        name,
        casters_pickle,
        include_root,
        class_names = [],
        generation_includes = [],
        extra_defines = [],
        deps = []):
    for class_name, yml_file, header_location in class_names:
        # print(class_name)
        cmd = _wrapper() + " semiwrap.cmd.header2dat "
        cmd += "--cpp 202002L "  # TODO
        cmd += class_name
        cmd += _location_helper(yml_file)
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
            srcs = [RESOLVE_CASTERS_DIR + casters_pickle],
            outs = [HEADER_DAT_DIR + class_name + ".dat", HEADER_DAT_DIR + class_name + ".d"],
            cmd = cmd,
            tools = _wrapper_dep() + [yml_file] + deps,
        )

def dat_to_cc(
        name,
        class_names = []):
    for class_name in class_names:
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

def dat_to_tmpl_cpp(name, class_names):
    for base_class_name, specialization, tmp_class_name in class_names:
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
        break

def dat_to_tmpl_hpp(name, class_names):
    for class_name in class_names:
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

def dat_to_trampoline(name, class_names):
    for dat_file, class_name, output_file in class_names:
        cmd = _wrapper() + " semiwrap.cmd.dat2trampoline "

        cmd += _location_helper(HEADER_DAT_DIR + dat_file)
        cmd += "  " + class_name
        cmd += " $(OUTS)"

        native.genrule(
            name = name + "." + output_file,
            outs = [DAT_TO_TRAMPOLINE_HDR_DIR + "trampolines/" + output_file],
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

def make_pyi(name):
    cmd = _wrapper() + " semiwrap.cmd.make_pyi "

def run_header_gen(name, include_root, casters_pickle, header_gen_config, deps = [], generation_includes = [], generation_defines = []):
    temp_yml_files = []

    for header_gen in header_gen_config:
        temp_yml_files.append(header_gen.yml_file)

        header_to_dat(
            name = name + ".header_to_dat",
            casters_pickle = casters_pickle,
            include_root = include_root,
            class_names = [(
                header_gen.class_name,
                header_gen.yml_file,
                header_gen.header_file,
            )],
            deps = deps,
            generation_includes = generation_includes,
            extra_defines = generation_defines,
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
            class_names = [header_gen.class_name],
        )
        generated_cc_files.append(DAT_TO_CC_DIR + header_gen.class_name + ".cpp")

    tmpl_hdrs = []
    for header_gen in header_gen_config:
        if header_gen.tmpl_class_names:
            dat_to_tmpl_hpp(
                name = name + ".dat_to_tmpl_hpp",
                class_names = [header_gen.class_name],
            )
            tmpl_hdrs.append(DAT_TO_TMPL_HDR_DIR + header_gen.class_name + "_tmpl.hpp")

        for tmpl_class_name, specialization in header_gen.tmpl_class_names:
            dat_to_tmpl_cpp(
                name = name + ".dat_to_tmpl_cpp",
                class_names = [(header_gen.class_name, specialization, tmpl_class_name)],
            )
            generated_cc_files.append(DAT_TO_TMPL_CC_DIR + tmpl_class_name + ".cpp")

    trampoline_hdrs = []
    for header_gen in header_gen_config:
        for trampoline_symbol, trampoline_header in header_gen.trampolines:
            dat_to_trampoline(
                name = name + ".dat2trampoline",
                class_names = [(header_gen.class_name + ".dat", trampoline_symbol, trampoline_header)],
            )
            trampoline_hdrs.append(DAT_TO_TRAMPOLINE_HDR_DIR + "trampolines/" + trampoline_header)
    cc_library(
        name = name + ".tmpl_hdrs",
        hdrs = tmpl_hdrs,
        strip_include_prefix = DAT_TO_TMPL_HDR_DIR,
    )
    cc_library(
        name = name + ".trampoline_hdrs",
        hdrs = trampoline_hdrs,
        strip_include_prefix = DAT_TO_TRAMPOLINE_HDR_DIR,
    )

    native.filegroup(
        name = name + ".generated_srcs",
        srcs = generated_cc_files,
        tags = ["manual"],
    )

    native.filegroup(
        name = name + ".header_gen_files",
        srcs = tmpl_hdrs + trampoline_hdrs + generated_cc_files,
        tags = ["manual"],
    )
