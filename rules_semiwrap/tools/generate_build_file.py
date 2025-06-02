
from semiwrap.autowrap.buffer import RenderBuffer
from semiwrap.pyproject import PyProject
from semiwrap.config.autowrap_yml import AutowrapConfigYaml
from semiwrap.config.pyproject_toml import ExtensionModuleConfig, TypeCasterConfig
from semiwrap.pkgconf_cache import PkgconfCache
import pathlib
import collections
import typing as T
import re
import argparse
import logging

import toposort

def _split_ns(name: str) -> T.Tuple[str, str]:
    ns = ""
    idx = name.rfind("::")
    if idx != -1:
        ns = name[:idx]
        name = name[idx + 2 :]
    return ns, name



def resolve_dependency(dependencies, root_package):
    resolved = set()
    header_paths = set()
    # logging.error("-----------------")
    for d in dependencies:
        # logging.error("---", d)
        if "native" in d:
            bazel_dep = f"//subprojects/{d}"
            base_lib = re.search("robotpy-native-(.*)", d)[1]
            # logging.error(base_lib)
            header_paths.add(f'_local_include_root("//subprojects/robotpy-native-{root_package}:import", "{root_package}")')
        elif "casters" in d:
            continue
        else:
            bazel_dep = f"//subprojects/robotpy-{d}"
            header_paths.add(f"$(location //subprojects/robotpy-native-{root_package}:import)/site-packages/native/{root_package}/include")
        resolved.add(bazel_dep)

    # logging.error(resolved)
    # logging.error(header_paths)
    # logging.error("-----------------")


    if header_paths:
        header_paths_str = "[\n            "
        header_paths_str += ",\n            ".join(f'{x}' for x in sorted(header_paths))
        header_paths_str += ",\n        ]"
    else:
        header_paths = "[]"


    return resolved, header_paths_str


import os
def hack_pkgconfig(depends, pkgcfgs):
    # logging.error("))))))))))))))))))))))))))")
    # logging.error(pkgcfgs)
    
    pkg_config_paths = os.environ.get('PKG_CONFIG_PATH', '').split(os.pathsep)

    # logging.error("PACKAGE CONFIG HACKS")
    if pkgcfgs:
        for pc in pkgcfgs:
            # logging.error(pc.parent)
            # logging.error(pc.parent.exists())
            # logging.error(pc.parent.absolute())
            # logging.error(os.path.exists(pc.parent))
            pkg_config_paths.append(str(pc.parent))
    # logging.error("/PACKAGE CONFIG HACKS")
        
    os.environ["PKG_CONFIG_PATH"] = os.pathsep.join(pkg_config_paths)
    # raise
    # for d in depends:
    #     if "casters" in d:
    #         continue
    #     else:
    #         raise Exception(d)
    # pass


class Generator:
    def __init__(self, project_file, pkgcfgs: T.List[pathlib.Path]):
        self.output_buffer = RenderBuffer()
        self.project_root = project_file.parent
        self.pyproject = PyProject(project_file)
        self.pkgcfgs = pkgcfgs
        
        self.local_caster_targets: T.Dict[str, BuildTargetOutput] = {}
        
        self.pkgcache = PkgconfCache()

        self.output_buffer.write_trim("""load("@rules_semiwrap//:defs.bzl", "create_pybind_library")
load("@rules_semiwrap//rules_semiwrap/private:semiwrap_helpers.bzl", "gen_libinit", "gen_modinit_hpp", "gen_pkgconf", "publish_casters", "resolve_casters", "run_header_gen")
load("@rules_semiwrap//:defs.bzl", "copy_extension_library", "make_pyi", "robotpy_library")

def _local_include_root(project_import, include_subpackage):
    return "$(location " + project_import + ")/site-packages/native/" + include_subpackage + "/include"
""")    
        self.output_buffer.writeln()

    def _sorted_extension_modules(self):
        # sort extension modules by dependencies, that way modules can depend on other modules
        # also declared in pyproject.toml without needing to worry about ordering in the file
        by_name = {}
        to_sort: T.Dict[str, T.Set[str]] = {}

        for package_name, extension in self.pyproject.project.extension_modules.items():
            if extension.ignore:
                continue

            name = extension.name or package_name.replace(".", "_")
            by_name[name] = (package_name, extension)

            deps = to_sort.setdefault(name, set())
            for dep in extension.wraps:
                deps.add(dep)
            for dep in extension.depends:
                deps.add(dep)

        for name in toposort.toposort_flatten(to_sort, sort=True):
            data = by_name.get(name)
            if data:
                yield data

    
    def _process_trampolines_str(self, ayml: AutowrapConfigYaml) -> str:
        trampolines = []
        
        for name, ctx in ayml.classes.items():
            if ctx.ignore:
                continue

            # if ctx.subpackage:
            #     subpackages.add(ctx.subpackage)

            cls_ns, cls_name = _split_ns(name)
            cls_ns = cls_ns.replace(":", "_")

            trampolines.append((name, f"{cls_ns}__{cls_name}.hpp"))
        
        output = "["
        if trampolines:
            # output += "\n            "
            output += "\n                            "
            output += ",\n                            ".join(f'("{t[0]}", "{t[1]}")' for t in trampolines)
            output += ",\n                        "
            # for trampoline in trampolines:
            #     output += f'("{trampoline[0]}", "{trampoline[1]}"), '


        output += "]"
        return output


    def _process_tmpl_str(self, yml: str, ayml: AutowrapConfigYaml) -> str:
        templates = []
        
        for i, (name, tctx) in enumerate(ayml.templates.items(), start=1):
            templates.append((f"{yml}_tmpl{i}", f"{name}"))
        
        output = "["
        if templates:
            output += "\n                            "
            output += ",\n                            ".join(f'("{t[0]}", "{t[1]}")' for t in templates)
            output += ",\n                        "


        output += "]"
        return output


    def _prepare_dependency_paths(
        self, depends: T.List[str], extension: ExtensionModuleConfig
    ):
        search_path: T.List[pathlib.Path] = []
        include_directories_uniq: T.Dict[pathlib.Path, bool] = {}
        caster_json_file: T.List[T.Union[BuildTargetOutput, pathlib.Path]] = []
        libinit_modules: T.List[str] = []

        # Add semiwrap default type casters
        # caster_json_file.append(self.semiwrap_type_caster_path)

        hack_pkgconfig(depends, self.pkgcfgs)

        for dep in depends:
            entry = self.pkgcache.get(dep)
            include_directories_uniq.update(
                dict.fromkeys(entry.full_include_path, True)
            )

            # extend the search path if the dependency is in 'wraps'
            if dep in extension.wraps:
                print("DJFSLDKJFKL")
                print(dep)
                print(entry.include_path)
                search_path.extend(entry.include_path)

            self._locate_type_caster_json(dep, caster_json_file)

            if entry.libinit_py:
                libinit_modules.append(entry.libinit_py)

        return search_path, include_directories_uniq, caster_json_file, libinit_modules


    def _locate_type_caster_json(
        self,
        depname: str,
        caster_json_file,
    ):
        checked = set()
        to_check = collections.deque([depname])
        while to_check:
            name = to_check.popleft()
            checked.add(name)

            entry = self.pkgcache.get(name)

            if name in self.local_caster_targets:
                caster_json_file.append(self.local_caster_targets[name])
            else:
                tc = entry.type_casters_path
                if tc and tc not in caster_json_file:
                    # print("--ff--", tc)
                    # print(os.environ)
                    tc = str(tc).replace(
                        "/home/pjreiniger/git/robotpy/robotpy_monorepo/rules_semiwrap/.venv/lib/python3.10/site-packages/wpiutil/wpiutil-casters.pybind11.json", 
                        "//subprojects/robotpy-wpiutil:generated/publish_casters/wpiutil-casters.pybind11.json")
                    tc = str(tc).replace(
                        "/home/pjreiniger/git/robotpy/robotpy_monorepo/rules_semiwrap/.venv/lib/python3.10/site-packages/wpimath/wpimath-casters.pybind11.json", 
                        "//subprojects/robotpy-wpimath:generated/publish_casters/wpimath-casters.pybind11.json"
                    )
                    caster_json_file.append(tc)

            for req in entry.requires:
                if req not in checked:
                    to_check.append(req)

    def _process_headers(
        self, 
        package_name,
        extension: ExtensionModuleConfig, 
        yaml_path: pathlib.Path):

        # TODO
        search_path = []
        # if extension.name == "wpiutil":
        #     search_path.append(pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/bazel-mostrobotpy/external/bzlmodrio-allwpilib~~setup_bzlmodrio_allwpilib_cpp_dependencies~bazelrio_edu_wpi_first_wpiutil_wpiutil-cpp_headers"))
        #     search_path.append(pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/subprojects/robotpy-wpiutil/wpiutil/"))
        # elif extension.name == "wpinet":
        #     search_path.append(pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/bazel-mostrobotpy/external/bzlmodrio-allwpilib~~setup_bzlmodrio_allwpilib_cpp_dependencies~bazelrio_edu_wpi_first_wpinet_wpinet-cpp_headers"))
        # elif extension.name == "ntcore":
        #     search_path.append(pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/bazel-mostrobotpy/external/bzlmodrio-allwpilib~~setup_bzlmodrio_allwpilib_cpp_dependencies~bazelrio_edu_wpi_first_ntcore_ntcore-cpp_headers"))
        # elif "wpimath" in extension.name:
        #     search_path.append(pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/bazel-mostrobotpy/external/bzlmodrio-allwpilib~~setup_bzlmodrio_allwpilib_cpp_dependencies~bazelrio_edu_wpi_first_wpimath_wpimath-cpp_headers"))
        #     search_path.append(pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/subprojects/robotpy-wpimath/wpimath/"))
        # elif "hal" in extension.name:
        #     search_path.append(pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/bazel-mostrobotpy/external/bzlmodrio-allwpilib~~setup_bzlmodrio_allwpilib_cpp_dependencies~bazelrio_edu_wpi_first_hal_hal-cpp_headers"))
        # elif "apriltag" in extension.name:
        #     search_path.append(pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/bazel-mostrobotpy/external/bzlmodrio-allwpilib~~setup_bzlmodrio_allwpilib_cpp_dependencies~bazelrio_edu_wpi_first_apriltag_apriltag-cpp_headers"))
        # elif "wpilib" in extension.name:
        #     search_path.append(pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/bazel-mostrobotpy/external/bzlmodrio-allwpilib~~setup_bzlmodrio_allwpilib_cpp_dependencies~bazelrio_edu_wpi_first_wpilibc_wpilibc-cpp_headers"))
        #     search_path.append(pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/subprojects/robotpy-wpilib/wpilib/src"))
        # elif "cscore" in extension.name:
        #     search_path.append(pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/bazel-mostrobotpy/external/bzlmodrio-allwpilib~~setup_bzlmodrio_allwpilib_cpp_dependencies~bazelrio_edu_wpi_first_cscore_cscore-cpp_headers"))
        #     search_path.append(pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/bazel-mostrobotpy/external/bzlmodrio-allwpilib~~setup_bzlmodrio_allwpilib_cpp_dependencies~bazelrio_edu_wpi_first_cameraserver_cameraserver-cpp_headers"))
        # elif "xrp" in extension.name:
        #     search_path.append(pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/bazel-mostrobotpy/external/bzlmodrio-allwpilib~~setup_bzlmodrio_allwpilib_cpp_dependencies~bazelrio_edu_wpi_first_xrpvendordep_xrpvendordep-cpp_headers"))
        # elif "romi" in extension.name:
        #     search_path.append(pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/bazel-mostrobotpy/external/bzlmodrio-allwpilib~~setup_bzlmodrio_allwpilib_cpp_dependencies~bazelrio_edu_wpi_first_romivendordep_romivendordep-cpp_headers"))
        # else:
        #     raise Exception(extension.name)
        # TODO

        # print("Original search path...")
        # print("\n".join(str(x) for x in search_path))
        # print("Original search path...")
        
        depends = self.pyproject.get_extension_deps(extension)
        ignored_depends = []
        for d in depends:
            if "casters" in d:
                ignored_depends.append(d)

        for id in ignored_depends:
            depends.remove(id)
        

        # extra_generation_hdrs_str = ""
        # if extra_generation_hdrs:
        #     extra_generation_hdrs_str += " + ["
        #     extra_generation_hdrs_str += ",".join(f'"{x}"' for x in extra_generation_hdrs)
        #     extra_generation_hdrs_str += "]"

        # Search path for wrapping is dictated by package_path and wraps
        search_path, include_directories_uniq, caster_json_file, libinit_modules = (
            self._prepare_dependency_paths(depends, extension)
        )
        if extension.name == "wpiutil":
            search_path.append(pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/subprojects/robotpy-wpiutil/wpiutil/"))
        elif "wpilib" in extension.name:
            search_path.append(pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/subprojects/robotpy-wpilib/wpilib/src"))
        elif "cscore" in extension.name:
            search_path.append(pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/bazel-mostrobotpy/external/bzlmodrio-allwpilib~~setup_bzlmodrio_allwpilib_cpp_dependencies~bazelrio_edu_wpi_first_cscore_cscore-cpp_headers"))
            search_path.append(pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/bazel-mostrobotpy/external/bzlmodrio-allwpilib~~setup_bzlmodrio_allwpilib_cpp_dependencies~bazelrio_edu_wpi_first_cameraserver_cameraserver-cpp_headers"))

        print("New search paths...")
        print("\n".join(str(x) for x in search_path))
        print("---")

        extra_hdrs = []

        root_package = package_name.split(".")[0]

        with self.output_buffer.indent(4):
            self.output_buffer.writeln(f"{extension.name.upper()}_HEADER_GEN = [")

            with self.output_buffer.indent(4):
                for yml, hdr in self.pyproject.get_extension_headers(extension):
                    yml_input = yaml_path / f"{yml}.yml"

                    ayml = AutowrapConfigYaml.from_file(self.project_root / yml_input)

                    tmpl_class_names = self._process_tmpl_str(yml, ayml)
                    trampolines = self._process_trampolines_str(ayml)
                    # Every class gets a trampoline file, but some just have #error in them
                    for name, ctx in ayml.classes.items():
                        if ctx.ignore:
                            continue
                        cls_ns, cls_name = _split_ns(name)
                        cls_ns = cls_ns.replace(":", "_")

                    h_input, h_root = self._locate_header(hdr, search_path)
                    if "site-packages" in str(h_root):
                        header_root = f'_local_include_root("//subprojects/robotpy-native-{root_package}:import", "{root_package}")'
                    # if str(h_root).startswith("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/bazel-mostrobotpy"):
                    #     header_root = f"$(location //subprojects/robotpy-native-{root_package}:import)/site-packages/native/{root_package}/include"
                    #     # header_root = str(h_root)[len("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/bazel-mostrobotpy/"):]
                    elif str(h_root).startswith("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy"):
                        header_root = '"' + str(h_root)[len("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/"):] +  '"'
                        extra_hdrs.append(package_name.split(".")[0] / h_input.relative_to(h_root))
                    else:
                        header_root = h_input

                    print(header_root)
                    print(h_input)
                    print(h_root)
                    header_suffix = h_input.relative_to(h_root)

                    self.output_buffer.write_trim(f"""
                    struct(
                        class_name = "{yml}",
                        yml_file = "{yml_input}",
                        header_root = {header_root},
                        header_file = {header_root} + "/{h_input.relative_to(h_root)}",
                        tmpl_class_names = {tmpl_class_names},
                        trampolines = {trampolines},
                    ),""")



            self.output_buffer.writeln("]")
            # self.output_buffer.writeln("\n")

        return extra_hdrs

    def _write_extension_data(self, package_name: str, extension: ExtensionModuleConfig, extra_generation_hdrs):
        depends = self.pyproject.get_extension_deps(extension)
        ignored_depends = []
        for d in depends:
            if "casters" in d:
                ignored_depends.append(d)

        for id in ignored_depends:
            depends.remove(id)
        

        extra_generation_hdrs_str = ""
        if extra_generation_hdrs:
            extra_generation_hdrs_str += " + ["
            extra_generation_hdrs_str += ",".join(f'"{x}"' for x in extra_generation_hdrs)
            extra_generation_hdrs_str += "]"

        # Search path for wrapping is dictated by package_path and wraps
        search_path, include_directories_uniq, caster_json_file, libinit_modules = (
            self._prepare_dependency_paths(depends, extension)
        )

        root_package = package_name.split('.')[0]

        bazel_deps, bazel_header_paths = resolve_dependency(depends, root_package)

        libinit_modules = "[" + ", ".join(f'"{x}"' for x in libinit_modules) + "]"
        caster_json_file = "[" + ", ".join(f'"{x}"' for x in sorted(set(caster_json_file))) + "]"
        print(caster_json_file)
        # raise

        with self.output_buffer.indent(4):
            package_path_elems = package_name.split(".")
            parent_package = ".".join(package_path_elems[:-1])
            module_name = package_path_elems[-1]
            package_path = pathlib.Path(*package_path_elems[:-1])
            
            libinit = extension.libinit or f"_init_{module_name}"
            
            package_init_py = package_path / "__init__.py"
            self.output_buffer.write_trim(f"""
    resolve_casters(
        name = "{extension.name}.resolve_casters",
        caster_files = {caster_json_file},
        casters_pkl_file = "{extension.name}.casters.pkl",
        dep_file = "{extension.name}.casters.d",
    )

    gen_libinit(
        name = "{extension.name}.gen_lib_init",
        output_file = "{package_path}/{libinit}.py",
        modules = {libinit_modules},
    )

    gen_pkgconf(
        name = "{extension.name}.gen_pkgconf",
        libinit_py = "{parent_package}.{libinit}",
        module_pkg_name = "{package_name}",
        output_file = "{extension.name}.pc",
        pkg_name = "{extension.name}",
        project_file = "pyproject.toml",
    )

    gen_modinit_hpp(
        name = "{extension.name}.gen_modinit_hpp",
        input_dats = [x.class_name for x in {extension.name.upper()}_HEADER_GEN],
        libname = "{module_name}",
        output_file = "semiwrap_init.{package_name}.hpp",
    )

    run_header_gen(
        name = "{extension.name}",
        casters_pickle = "{extension.name}.casters.pkl",
        header_gen_config = {extension.name.upper()}_HEADER_GEN,
        deps = header_to_dat_deps{extra_generation_hdrs_str},
        header_to_dat_deps = ["//subprojects/robotpy-native-{root_package}:import"],
        generation_includes = {bazel_header_paths},
    )

    native.filegroup(
        name = "{extension.name}.generated_files",
        srcs = [
            "{extension.name}.gen_modinit_hpp.gen",
            "{extension.name}.header_gen_files",
            "{extension.name}.gen_pkgconf",
            "{extension.name}.gen_lib_init",
        ],
        tags = ["manual"],
    )
    create_pybind_library(
        name = "{extension.name}",
        entry_point = entry_point,
        extension_name = extension_name,
        generated_srcs = [":{extension.name}.generated_srcs"],
        semiwrap_header = [":{extension.name}.gen_modinit_hpp"],
        deps = deps + [
            ":{extension.name}.tmpl_hdrs",
            ":{extension.name}.trampoline_hdrs",
        ],
        extra_hdrs = extra_hdrs,
        extra_srcs = extra_srcs,
        includes = includes,
    )""")

    def _process_extension_module(self, extension: ExtensionModuleConfig):
        self.output_buffer.writeln(f"""def {extension.name}_extension(entry_point, deps, header_to_dat_deps, extension_name = None, extra_hdrs = [], extra_srcs = [], includes = []):""")


    def _locate_header(self, hdr: str, search_path: T.List[pathlib.Path]):
        phdr = pathlib.PurePosixPath(hdr)
        for p in search_path:
            h_path = p / phdr
            if h_path.exists():
                # We should return this as an InputFile, but inputs must be relative to the
                # project root, which may not be the case on windows. Incremental build should
                # still work, because the header is included in a depfile
                return h_path, p
        raise FileNotFoundError(
            f"cannot locate {phdr} in {', '.join(map(str, search_path))}"
        )

    def generate(self, output_file: pathlib.Path):
        for name, caster_cfg in self.pyproject.project.export_type_casters.items():
            # dep = self.pkgcache.add_local(
            #     name=name,
            #     includes=[self.project_root / inc for inc in caster_cfg.includedir],
            #     requires=caster_cfg.requires,
            # )

            self.local_caster_targets[name] = f"{name}.pybind11.json"


        for package_name, extension in self._sorted_extension_modules():
            self._process_extension_module(extension)
            
            if extension.yaml_path is None:
                yaml_path = pathlib.Path("semiwrap")
            else:
                yaml_path = pathlib.Path(pathlib.PurePosixPath(extension.yaml_path))
            extra_generation_hdrs = self._process_headers(package_name, extension, yaml_path)
            self._write_extension_data(package_name, extension, extra_generation_hdrs)

            varname = extension.name or package_name.replace(".", "_")
            self.pkgcache.add_local(
                name=varname,
                includes=[],
                requires=[],
                # libinit_py=libinit_module,
            )

        
        for name, caster_cfg in self.pyproject.project.export_type_casters.items():            
            self.output_buffer.writeln()
            self.output_buffer.write_trim(f"""
            def publish_library_casters(typecasters_srcs):
                publish_casters(
                    name = "publish_casters",
                    caster_name = "{name}",
                    output_json = "{name}.pybind11.json",
                    output_pc = "{name}.pc",
                    project_config = "pyproject.toml",
                    typecasters_srcs = typecasters_srcs,
                )
            """)

        self.output_buffer.write_trim(f"""
        def move_extension_modules():
        """)
        all_extension_names = []
        for package_name, extension in self.pyproject.project.extension_modules.items():
            if extension.ignore:
                continue

            with self.output_buffer.indent(4):
                self.output_buffer.write_trim(f"""
                copy_extension_library(
                    name = "copy_{extension.name}",
                    extension = "_wpiutil",
                    output_directory = "wpiutil/",
                )
                """)

            all_extension_names.append(extension.name)

        copy_extension_text = "[\n        " + "\n        ".join(f'":copy_{x}",' for x in all_extension_names) + "\n    ]"
        self.output_buffer.writeln(f"    return {copy_extension_text}")

        libinit_files_text = "[\n        " + "\n            ".join(f'"{x}/_init__{x}.py",' for x in all_extension_names) + "\n    ]"
        print(libinit_files_text)
        self.output_buffer.writeln(f"""def libinit_files():\n    return {libinit_files_text}""")
        

            

        
        with open(output_file, 'w') as f:
            f.write(self.output_buffer.getvalue())

def generate_build_info(project_file: pathlib.Path, output_file: pathlib.Path, pkgcfgs: T.List[pathlib.Path]):
    generator = Generator(project_file, pkgcfgs)
    generator.generate(output_file)
    



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project_file", type=pathlib.Path, required=True)
    parser.add_argument("--output_file", type=pathlib.Path, required=True)
    parser.add_argument("--pkgcfgs", type=pathlib.Path, nargs="+")
    # parser.add_argument("ip", type=str, help="IP address to connect to")
    args = parser.parse_args()
    # print(args)
    # raise
    # project_files = [
    #     # pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/subprojects/pyntcore/pyproject.toml"),
    #     # pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/subprojects/robotpy-apriltag/pyproject.toml"),
    #     # pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/subprojects/robotpy-cscore/pyproject.toml"),
    #     # pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/subprojects/robotpy-hal/pyproject.toml"),
    #     # pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/subprojects/robotpy-halsim-ds-socket/pyproject.toml"),
    #     # pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/subprojects/robotpy-halsim-gui/pyproject.toml"),
    #     # pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/subprojects/robotpy-halsim-ws/pyproject.toml"),
    #     # pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/subprojects/robotpy-romi/pyproject.toml"),
    #     # pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/subprojects/robotpy-wpilib/pyproject.toml"),
    #     # pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/subprojects/robotpy-wpimath/pyproject.toml"),
    #     # # # pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/subprojects/robotpy-wpimath/tests/cpp/pyproject.toml"),
    #     # pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/subprojects/robotpy-wpinet/pyproject.toml"),
    #     pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/subprojects/robotpy-wpiutil/pyproject.toml"),
    #     # # pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/subprojects/robotpy-wpiutil/tests/cpp/pyproject.toml"),
    #     # pathlib.Path("/home/pjreiniger/git/robotpy/robotpy_monorepo/mostrobotpy/subprojects/robotpy-xrp/pyproject.toml"),
    # ]

    # for project_file in project_files:
    #     print(f"Running for {project_file}")

    for pc in args.pkgcfgs:
        if not os.path.exists(pc):
            raise Exception(f"Package config {pc} does not exist")

    generate_build_info(args.project_file, args.output_file, args.pkgcfgs)



if __name__ == "__main__":
    main()