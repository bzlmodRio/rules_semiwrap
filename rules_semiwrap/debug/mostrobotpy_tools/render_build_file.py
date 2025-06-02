import pathlib
import dataclasses
from semiwrap.makeplan import (
    TypeCasterConfig,
    BuildTarget,
    Entrypoint,
    LocalDependency,
    ExtensionModule,
    CppMacroValue,
    InputFile,
    OutputFile,
    BuildTargetOutput,
    ExtensionModule,
    ExtensionModuleConfig,
    PlanError,
    Depfile,
    makeplan,
)
import typing as T
from semiwrap.autowrap.buffer import RenderBuffer
from semiwrap.pyproject import PyProject
from semiwrap.pkgconf_cache import PkgconfCache
from semiwrap.casters import PKGCONF_CASTER_EXT
from semiwrap.config.autowrap_yml import AutowrapConfigYaml
import collections
import sysconfig
import os

import toposort


@dataclasses.dataclass(frozen=True)
class HeaderGenInfo:
    class_name: str
    yml_file: InputFile
    header_input: str
    hdr_tmpls: T.List[T.Tuple[str, str]] = dataclasses.field(default_factory=list)
    trampolines: T.List[T.Tuple[str, str]] = dataclasses.field(default_factory=list)


@dataclasses.dataclass(frozen=True)
class Dat2HeaderConfig:
    class_name: str
    yml_file: InputFile
    header_input: str
    header_root: str
    all_type_casters: BuildTarget
    output_file: OutputFile
    dep_file: Depfile
    include_directories: T.List[T.Union[str, pathlib.Path]]
    extra_defines: T.List[str]

    @staticmethod
    def from_item(item):
        arg_idx = 0
        include_directories = []
        extra_defines = []
        while True:
            if item.args[arg_idx] == "-I":
                include_directories.append(item.args[arg_idx + 1])
                arg_idx += 2
            else:
                break
        while True:
            if item.args[arg_idx] == "-D":
                extra_defines.append(item.args[arg_idx + 1])
                arg_idx += 2
            else:
                break
        while True:
            if item.args[arg_idx] == "-I":
                include_directories.append(item.args[arg_idx + 1])
                arg_idx += 2
            else:
                break
        if item.args[arg_idx] == "--cpp":
            arg_idx += 2
        print(len(item.args[arg_idx:]))
        if len(item.args[arg_idx:]) != 8:
            print("*********************************")
            for i, arg in enumerate(item.args):
                print(i, i - arg_idx, arg)
                print("-------------------------------")
            print("*********************************")
        assert 8 == len(item.args[arg_idx:])

        return Dat2HeaderConfig(
            class_name=item.args[arg_idx + 0],
            yml_file=item.args[arg_idx + 1],
            header_input=item.args[arg_idx + 2],
            header_root=item.args[arg_idx + 3],
            all_type_casters="",
            output_file=item.args[arg_idx + 5],
            dep_file=item.args[arg_idx + 6],
            include_directories=include_directories,
            extra_defines=extra_defines,
        )


def amalgamate_includes(dat2hdrs: T.List[Dat2HeaderConfig]):
    include_directories = set()
    for dat2hdr in dat2hdrs:
        config = Dat2HeaderConfig.from_item(dat2hdr)
        for inc in config.include_directories:
            if "site-packages/semiwrap" in str(inc):
                continue
            if "site-packages/native" in str(inc):
                lib = inc.parent.name
                inc = f"external/bzlmodrio-allwpilib~~setup_bzlmodrio_allwpilib_cpp_dependencies~bazelrio_edu_wpi_first_{lib}_{lib}-cpp_headers"
            if "python3.10" in str(inc):
                continue
            include_directories.add(str(inc))

    return sorted(str(x) for x in include_directories)


def amalgamate_defines(dat2hdrs: T.List[Dat2HeaderConfig]):
    extra_defines = set()
    for dat2hdr in dat2hdrs:
        config = Dat2HeaderConfig.from_item(dat2hdr)
        for define in config.extra_defines:
            extra_defines.add(str(define))

    print(extra_defines)
    return sorted(str(x) for x in extra_defines)


def write_library(
    generated_info_buffer,
    build_file_buffer,
    item,
    publish_casters,
    resolve_casters_item,
    gen_libinit,
    gen_pkgconf,
    gen_modinit_hpp,
    casters_pickle_file,
    header2dats,
    dat2cpps,
    dat2tmplcpps,
    dat2tmplhpps,
    dat2trampolines,
):
    lib_name = item.name

    depends = em_deps_to_extension_deps(calculate_extension_dependencies(item))

    build_file_buffer.write_trim(
        f"""   
{lib_name}_extension(
    DEFAULT_INCLUDE_ROOT = DEFAULT_INCLUDE_ROOT,
    entry_point = ["{lib_name}/src/main.cpp"],
    deps = {depends},
)
"""
    )

    # write_extension_module(build_file_buffer, item, write_deps=True)

    configs = {}

    for header2dat in header2dats:
        config = Dat2HeaderConfig.from_item(header2dat)
        configs[config.class_name] = HeaderGenInfo(
            class_name=config.class_name,
            yml_file=config.yml_file,
            header_input=config.header_input,
        )

    for dat2tmplcpp in dat2tmplcpps:
        config = Dat2HeaderConfig.from_item(dat2tmplcpp.args[0])
        class_name = config.class_name
        specialization_name = dat2tmplcpp.args[-2]
        output_file = dat2tmplcpp.args[-1].name[:-4]
        configs[class_name].hdr_tmpls.append((output_file, specialization_name))

    for dat2trampoline in dat2trampolines:
        config = Dat2HeaderConfig.from_item(dat2trampoline.args[0])
        class_name = config.class_name
        configs[config.class_name].trampolines.append(
            (dat2trampoline.args[-2], dat2trampoline.args[-1].name)
        )

    generated_info_buffer.writeln(
        f"""\ndef {lib_name}_extension(entry_point, deps, DEFAULT_INCLUDE_ROOT, header_to_dat_deps, extension_name = None, extra_hdrs = [], extra_srcs = [], includes = []):"""
    )

    with generated_info_buffer.indent(4):

        generated_info_buffer.writeln(f"{lib_name.upper()}_HEADER_GEN = [")
        with generated_info_buffer.indent(4):
            for class_name, config in configs.items():
                newline_indent = "\n                    "
                trimed_header = str(config.header_input)
                trimed_header = trimed_header[trimed_header.find("include") + 7 :]
                header_templates = (
                    newline_indent
                    + newline_indent.join(
                        f'("{x[0]}", "{x[1]}"),' for x in config.hdr_tmpls
                    )
                    + newline_indent
                    if config.hdr_tmpls
                    else ""
                )
                trampolines = (
                    newline_indent
                    + newline_indent.join(
                        f'("{x[0]}", "{x[1]}"),' for x in config.trampolines
                    )
                    + newline_indent[:-4]
                    if config.trampolines
                    else ""
                )
                generated_info_buffer.write_trim(
                    f"""struct(
                class_name = "{config.class_name}",
                yml_file = "{config.yml_file.path}",
                header_file = DEFAULT_INCLUDE_ROOT + "{trimed_header}",
                tmpl_class_names = [{header_templates}],
                trampolines = [{trampolines}],
            ),"""
                )
        generated_info_buffer.writeln(f"]")

        write_resolve_casters(generated_info_buffer, lib_name, resolve_casters_item)

        gen_lib_init_files = f", ".join(f'"{x}"' for x in gen_libinit.args[1:])

        all_includes = amalgamate_includes(header2dats)
        all_defines = amalgamate_defines(header2dats)
        generation_includes = ",\n                    ".join(
            f'"{x}"' for x in all_includes
        )

        generated_info_buffer.write_trim(
            f"""
            gen_libinit(
                name = "{lib_name}.gen_lib_init",
                output_file = "{gen_libinit.install_path}/{gen_libinit.args[0].name}",
                modules = [{gen_lib_init_files}],
            )

            gen_pkgconf(
                name = "{lib_name}.gen_pkgconf",
                libinit_py = "{gen_pkgconf.args[-1]}",
                module_pkg_name = "{gen_pkgconf.args[0]}",
                output_file = "{gen_pkgconf.args[3].name}",
                pkg_name = "{gen_pkgconf.args[1]}",
                project_file = "pyproject.toml",
            )

            gen_modinit_hpp(
                name = "{lib_name}.gen_modinit_hpp",
                input_dats = [x.class_name for x in {lib_name.upper()}_HEADER_GEN],
                libname = "{gen_modinit_hpp.args[0]}",
                output_file = "{gen_modinit_hpp.args[1].name}",
            )
            
            run_header_gen(
                name = "{lib_name}",
                casters_pickle = "{lib_name}.casters.pkl",
                header_gen_config = {lib_name.upper()}_HEADER_GEN,
                include_root = DEFAULT_INCLUDE_ROOT,
                deps = header_to_dat_deps,
                generation_includes = [
                    {generation_includes}],
                generation_defines = {all_defines},
            )
            
            native.filegroup(
                name = "{lib_name}.generated_files",
                srcs = [
                    "{lib_name}.gen_modinit_hpp.gen",
                    "{lib_name}.header_gen_files",
                    "{lib_name}.gen_pkgconf",
                    "{lib_name}.gen_lib_init",
                ],
            )
            """
        )


def write_resolve_casters(generated_file_buffer, lib_name, item):
    casters_pickle_file = item.args[0].name
    dep_file = item.args[1].name
    maybe_caster_file = None
    last_arg = item.args[-1]

    caster_files = []
    for cf in item.args[3:]:
        if isinstance(cf, pathlib.Path):
            cf = str(cf)
            if (
                cf
                == "/home/pjreiniger/git/robotpy/mostrobotpy/.venv/lib/python3.10/site-packages/wpiutil/wpiutil-casters.pybind11.json"
            ):
                cf = "//subprojects/robotpy-wpiutil:generated/publish_casters/wpiutil-casters.pybind11.json"
            elif (
                cf
                == "/home/pjreiniger/git/robotpy/mostrobotpy/.venv/lib/python3.10/site-packages/wpimath/wpimath-casters.pybind11.json"
            ):
                cf = "//subprojects/robotpy-wpimath:generated/publish_casters/wpimath-casters.pybind11.json"
        elif isinstance(cf, BuildTargetOutput):
            cf = cf.target.args[-2].name
            # cf =
        else:
            print("UNKNOWN CASTER FILE", type(cf))

        if cf not in caster_files:
            caster_files.append(cf)

    generated_file_buffer.write_trim(
        f"""
        resolve_casters(
            name = "{lib_name}.resolve_casters",
            caster_files = [{", ".join(f'"{x}"' for x in caster_files)}],
            casters_pkl_file = "{casters_pickle_file}",
            dep_file = "{dep_file}",
        )
    """
    )
    generated_file_buffer.writeln()


def calculate_extension_dependencies(item):
    depends = []

    def calculate_deps(dependency):
        for d in dependency:
            if isinstance(d, LocalDependency):
                # print("*" * 80)
                # print(d)
                # print("*" * 80)
                calculate_deps(d.depends)
                depends.append(d.name)
            elif isinstance(d, str):
                if d == "semiwrap":
                    continue
                depends.append(d)
            else:
                print(d)
                raise

    calculate_deps(item.depends)
    print("--AA--", depends)

    return depends


def write_extension_module(buffer, item):
    buffer.write_trim(
        f"""
    create_pybind_library(
        name = "{item.name}",
        entry_point = entry_point,
        extension_name = extension_name,
        generated_srcs = [":{item.name}.generated_srcs"],
        semiwrap_header = [":{item.name}.gen_modinit_hpp"],
        deps = deps + [
            ":{item.name}.tmpl_hdrs",
            ":{item.name}.trampoline_hdrs",
        ],
        extra_hdrs = extra_hdrs,
        extra_srcs = extra_srcs,
        includes = includes,
    )
    """
    )


def em_deps_to_extension_deps(dependencies):
    output = []
    for dep in dependencies:
        if "native" in dep:
            lib_name = dep[len("robotpy-native-") :]
            output.append(f"@bzlmodrio-allwpilib//libraries/cpp/{lib_name}:shared")
        else:
            output.append(f"//subprojects/robotpy-{dep}:{dep}_pybind_library")
    return output


def em_deps_to_python_deps(dependencies):
    output = []
    for dep in dependencies:
        if "native" in dep:
            output.append(f"//subprojects/{dep}")
        else:
            output.append(f"//subprojects/robotpy-{dep}:{dep}")
    return output


def render_build_file(project_dir):
    plans = makeplan(project_dir)

    dat2trampolines = []
    header2dats = []
    dat2cpps = []
    dat2tmplhpps = []
    dat2tmplcpps = []
    publish_casters = None
    resolve_casters = None
    gen_libinit = None
    gen_pkgconf = None
    gen_modinit_hpp = None

    lib_counter = 0

    extension_modules = []

    build_file_buffer = RenderBuffer()
    build_file_buffer.write_trim(
        """load("//bazel_scripts:copy_native_file.bzl", "copy_extension_library", "copy_native_file")
load("//bazel_scripts:semiwrap_helpers.bzl", "dat_to_cc", "dat_to_tmpl_hpp", "gen_libinit", "gen_modinit_hpp", "gen_pkgconf", "make_pyi", "dat_to_trampoline", "gen_pkgconf", "header_to_dat", "publish_casters", "publish_casters",  "resolve_casters", "dat_to_tmpl_cpp", "run_header_gen")
load("//bazel_scripts:pybind_rules.bzl", "create_pybind_library", "pybind_python_library")
load("//subprojects/robotpy-wpiutil:generated_build_info.bzl", "publish_library_casters", "wpiutil_extension")


load("@pybind11_bazel//:build_defs.bzl", "pybind_extension", "pybind_library")

DEFAULT_INCLUDE_ROOT = "external/bzlmodrio-allwpilib~~setup_bzlmodrio_allwpilib_cpp_dependencies~bazelrio_edu_wpi_first_wpiutil_wpiutil-cpp_headers"
"""
    )

    generated_info_buffer = RenderBuffer()
    generated_info_buffer.write_trim(
        """load("//bazel_scripts:pybind_rules.bzl", "create_pybind_library")
load("//bazel_scripts:semiwrap_helpers.bzl", "gen_libinit", "gen_modinit_hpp", "gen_pkgconf", "publish_casters", "resolve_casters", "run_header_gen")
"""
    )

    for item in plans:
        # if isinstance(item, BuildTarget):
        #     print(item.command)
        # else:
        #     print(type(item))

        if isinstance(item, BuildTarget):
            if item.command == "dat2trampoline":
                dat2trampolines.append(item)
            elif item.command == "header2dat":
                header2dats.append(item)
                pass
            elif item.command == "dat2cpp":
                dat2cpps.append(item)
                pass
            elif item.command == "dat2tmplcpp":
                dat2tmplcpps.append(item)
                pass
            elif item.command == "dat2tmplhpp":
                dat2tmplhpps.append(item)
            elif item.command == "publish-casters":
                build_file_buffer.write_trim(
                    """
                    publish_library_casters(
                        typecasters_srcs = glob([
                            "wpiutil/src/type_casters/**",
                            "wpiutil/src/wpistruct/**",
                        ]),
                    )"""
                )
                build_file_buffer.writeln()
                if publish_casters is not None:
                    raise
                publish_casters = item
            elif item.command == "resolve-casters":
                if resolve_casters is not None:
                    raise
                resolve_casters = item
            elif item.command == "gen-libinit-py":
                if gen_libinit is not None:
                    raise
                gen_libinit = item
            elif item.command == "gen-pkgconf":
                if gen_pkgconf is not None:
                    raise
                gen_pkgconf = item
            elif item.command == "gen-modinit-hpp":
                if gen_modinit_hpp is not None:
                    raise
                gen_modinit_hpp = item
            elif item.command == "make-pyi":
                build_file_buffer.write_trim(
                    f"""
                    make_pyi(
                        name = "make_pyi{lib_counter}",
                    )
                """
                )
            else:
                print(f"Unknown command {item.command}")
        elif isinstance(item, CppMacroValue):
            print("Ignoring macro thing")
        elif isinstance(item, LocalDependency):
            pass
        elif isinstance(item, ExtensionModule):
            extension_modules.append(item)
            write_library(
                generated_info_buffer,
                build_file_buffer,
                item,
                publish_casters,
                resolve_casters,
                gen_libinit,
                gen_pkgconf,
                gen_modinit_hpp,
                None,
                header2dats,
                dat2cpps,
                dat2tmplcpps,
                dat2tmplhpps,
                dat2trampolines,
            )

            with generated_info_buffer.indent(4):
                write_extension_module(generated_info_buffer, item)

            casters_pickle_file = None
            header2dats = []
            dat2cpps = []
            dat2tmplcpps = []
            dat2tmplhpps = []
            dat2trampolines = []
            resolve_casters = None
            gen_libinit = None
            gen_pkgconf = None
            gen_modinit_hpp = None
            lib_counter += 1
            pass
        else:
            print(type(item))

    data_deps = []
    deps = set()
    for em in extension_modules:
        # print(em)
        build_file_buffer.write_trim(
            f"""
    copy_extension_library(
        name = "copy_{em.name}",
        extension = "_{em.name}",
        output_directory = "{em.install_path}/",
    )"""
        )
        data_deps.append(f":copy_{em.name}")
        deps.update(calculate_extension_dependencies(em))
    deps = em_deps_to_python_deps(deps)

    build_file_buffer.write_trim(
        f"""
pybind_python_library(
    name = "wpiutil",
    srcs = glob(["wpiutil/**/*.py"]),
    data = {data_deps},
    imports = ["."],
    visibility = ["//visibility:public"],
    deps = {deps}
)
"""
    )

    if publish_casters:
        generated_info_buffer.writeln()
        generated_info_buffer.write_trim(
            f"""
            def publish_library_casters(typecasters_srcs):
                publish_casters(
                    name = "publish_casters",
                    caster_name = "{publish_casters.args[1]}",
                    output_json = "{publish_casters.args[2].name}",
                    output_pc = "{publish_casters.args[3].name}",
                    project_config = "pyproject.toml",
                    typecasters_srcs = typecasters_srcs,
                )

        """
        )

    build_file_buffer.write_trim(
        f"""
        filegroup(
            name = "generated_files",
            srcs = [
        """
    )
    for em in extension_modules:
        build_file_buffer.writeln(f'"{em.name}.generated_files",')

    build_file_buffer.write_trim(
        f"""
        ],
        visibility = ["//visibility:public"],
    )
    """
    )

    with open(project_dir / "BUILD.bazel", "w") as f:
        f.write(build_file_buffer.getvalue())

    print(project_dir)
    with open(project_dir / "generated_build_info.bzl", "w") as f:
        f.write(generated_info_buffer.getvalue())


def main():
    project_files = [
        # pathlib.Path("/home/pjreiniger/git/robotpy/mostrobotpy/subprojects/pyntcore/pyproject.toml"),
        # pathlib.Path("/home/pjreiniger/git/robotpy/mostrobotpy/subprojects/robotpy-apriltag/pyproject.toml"),
        # pathlib.Path("/home/pjreiniger/git/robotpy/mostrobotpy/subprojects/robotpy-cscore/pyproject.toml"),
        # pathlib.Path("/home/pjreiniger/git/robotpy/mostrobotpy/subprojects/robotpy-hal/pyproject.toml"),
        # pathlib.Path("/home/pjreiniger/git/robotpy/mostrobotpy/subprojects/robotpy-halsim-ds-socket/pyproject.toml"),
        # pathlib.Path("/home/pjreiniger/git/robotpy/mostrobotpy/subprojects/robotpy-halsim-gui/pyproject.toml"),
        # pathlib.Path("/home/pjreiniger/git/robotpy/mostrobotpy/subprojects/robotpy-halsim-ws/pyproject.toml"),
        # pathlib.Path("/home/pjreiniger/git/robotpy/mostrobotpy/subprojects/robotpy-romi/pyproject.toml"),
        # pathlib.Path("/home/pjreiniger/git/robotpy/mostrobotpy/subprojects/robotpy-wpilib/pyproject.toml"),
        # pathlib.Path("/home/pjreiniger/git/robotpy/mostrobotpy/subprojects/robotpy-wpimath/pyproject.toml"),
        # pathlib.Path("/home/pjreiniger/git/robotpy/mostrobotpy/subprojects/robotpy-wpimath/tests/cpp/pyproject.toml"),
        # pathlib.Path("/home/pjreiniger/git/robotpy/mostrobotpy/subprojects/robotpy-wpinet/pyproject.toml"),
        # pathlib.Path("/home/pjreiniger/git/robotpy/mostrobotpy/subprojects/robotpy-wpiutil/pyproject.toml"),
        # pathlib.Path("/home/pjreiniger/git/robotpy/mostrobotpy/subprojects/robotpy-wpiutil/tests/cpp/pyproject.toml"),
        # pathlib.Path("/home/pjreiniger/git/robotpy/mostrobotpy/subprojects/robotpy-xrp/pyproject.toml"),
    ]

    for project_file in project_files:
        print(f"Running for {project_file}")
        render_build_file(project_file.parent)


if __name__ == "__main__":
    main()
