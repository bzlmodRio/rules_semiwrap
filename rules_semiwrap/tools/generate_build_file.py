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
import tomli

import toposort


class BazelExtensionModule:
    def __init__(self, package_name: str, extension: ExtensionModuleConfig):
        self.name = extension.name
        self.header_configs = []

        self.package_name = package_name
        self.package_path_elems = package_name.split(".")
        self.parent_package = ".".join(self.package_path_elems[:-1])
        self.module_name = self.package_path_elems[-1]
        self.package_path = pathlib.Path(*self.package_path_elems[:-1])
        self.varname = extension.name or package_name.replace(".", "_")
        self.subpackage_name = "/".join(package_name.split(".")[:-1])

        self.local_headers = []
        self.caster_deps = []
        self.caster_files = []
        self.libinit_py = None

    def add_header(self, root_package, yml, hdr, ayml, yml_input, h_input, h_root):
        templates = []
        for i, (name, tctx) in enumerate(ayml.templates.items(), start=1):
            templates.append((f"{yml}_tmpl{i}", f"{name}"))
            
        trampolines = []

        for name, ctx in ayml.classes.items():
            if ctx.ignore:
                continue

            cls_ns, cls_name = _split_ns(name)
            cls_ns = cls_ns.replace(":", "_")

            trampolines.append((name, f"{cls_ns}__{cls_name}.hpp"))
        
        # TODO hack
        if root_package == "hal":
            root_package = "wpihal"

        if "site-packages" in str(h_root):
            if root_package == "robotpy_apriltag":
                root_package = "apriltag"
            header_root = f'resolve_include_root("//subprojects/robotpy-native-{root_package}", "{root_package}")'
        else:
            header_root = f'"{h_root}"'
            self.local_headers.append(root_package / h_input.relative_to(h_root))
        header_suffix = h_input.relative_to(h_root)
        

        self.header_configs.append(dict(
            yml = yml,
            yml_input = yml_input,
            header_root = header_root,
            header_file = header_root + f' + "/{header_suffix}"',
            trampolines = trampolines,
            templates = templates,
        ))

    def set_caster_json_file(self, caster_json_file):
        # if caster_json_file:
        for cjf in caster_json_file:
            if cjf.startswith("resolve_caster_file"):
                self.caster_deps.append(cjf)
            else:
                self.caster_files.append(f'"{cjf}"')

    def set_depends(self, dependencies):
        self.header_paths = set()
        for d in dependencies:
            if "native" in d:
                base_lib = re.search("robotpy-native-(.*)", d)[1]
                self.header_paths.add(f'local_native_libraries_helper("{base_lib}")')
            elif "casters" in d:
                continue
            else:
                self.header_paths.add(f'local_native_libraries_helper("{d}")')
        print(self.header_paths)
        # raise

    def set_subpackages(self, subpackages):
        self.pyi_files = []
        if subpackages:
            self.pyi_files = ["__init__.pyi"]
            self.pyi_install_path = f"{self.package_path}/{self.module_name}"
            for sp in subpackages:
                self.pyi_files.append(sp + ".pyi")

        else:
            self.pyi_install_path = f"{self.package_path}"
            self.pyi_files = [self.package_name.split(".")[-1] + ".pyi"]



def _split_ns(name: str) -> T.Tuple[str, str]:
    ns = ""
    idx = name.rfind("::")
    if idx != -1:
        ns = name[:idx]
        name = name[idx + 2 :]
    return ns, name


def resolve_dependency(dependencies, root_package):
    header_paths = set()
    for d in dependencies:
        if "native" in d:
            base_lib = re.search("robotpy-native-(.*)", d)[1]
            header_paths.add(f'local_native_libraries_helper("{base_lib}")')
        elif "casters" in d:
            continue
        else:
            header_paths.add(f'local_native_libraries_helper("{d}")')

    if header_paths:
        header_paths_str = "[\n            "
        header_paths_str += ",\n            ".join(f"{x}" for x in sorted(header_paths))
        header_paths_str += ",\n        ]"
    else:
        header_paths_str = "[]"

    return header_paths_str


import os


def hack_pkgconfig(depends, pkgcfgs):

    pkg_config_paths = os.environ.get("PKG_CONFIG_PATH", "").split(os.pathsep)

    if pkgcfgs:
        for pc in pkgcfgs:
            pkg_config_paths.append(str(pc.parent))

    os.environ["PKG_CONFIG_PATH"] = os.pathsep.join(pkg_config_paths)


class _BuildPlanner:
    def __init__(self, project_root: pathlib.Path, pkgcfgs: T.List[pathlib.Path]):
        self.output_buffer = RenderBuffer()
        self.project_root = project_root
        self.pyproject = PyProject(project_root / "pyproject.toml")
        self.pkgcache = PkgconfCache()
        self.pkgcfgs = pkgcfgs

        self.local_caster_targets: T.Dict[str, BuildTargetOutput] = {}

        self.extension_modules: List[BazelExtensionModule] = []

    def generate(self, output_file: pathlib.Path):
        projectcfg = self.pyproject.project
        for name, caster_cfg in projectcfg.export_type_casters.items():
            self._process_export_type_caster(name, caster_cfg)

        for package_name, extension in self._sorted_extension_modules():
            try:
                self._process_extension_module(package_name, extension)
            except Exception as e:
                raise Exception(f"{package_name} failed") from e

        for name, caster_install_path in self.local_caster_targets.items():
            self.output_buffer.writeln()
            self.output_buffer.write_trim(
                f"""
            def publish_library_casters(typecasters_srcs):
                publish_casters(
                    name = "publish_casters",
                    caster_name = "{name}",
                    output_json = "{caster_install_path}/{name}.pybind11.json",
                    output_pc = "{caster_install_path}/{name}.pc",
                    project_config = "pyproject.toml",
                    typecasters_srcs = typecasters_srcs,
                )
            """
            )

        self.output_buffer.writeln()
        self.output_buffer.write_trim(
            f"""
        def get_generated_data_files():
        """
        )
        all_extension_names = []
        for package_name, extension in self.pyproject.project.extension_modules.items():
            if extension.ignore:
                continue

            package_path_elems = package_name.split(".")
            package_path = pathlib.Path(*package_path_elems[:-1])
            module_name = package_path_elems[-1]

            with self.output_buffer.indent(4):
                self.output_buffer.write_trim(
                    f"""
                copy_extension_library(
                    name = "copy_{extension.name}",
                    extension = "{module_name}",
                    output_directory = "{package_path}/",
                )
                """
                )

            all_extension_names.append(
                ("/".join(package_path_elems[:-1]), extension.name, module_name)
            )

        self.output_buffer.writeln()
        with self.output_buffer.indent(4):
            self.output_buffer.write_trim(
                f"""
                native.filegroup(
                    name = "{package_path_elems[0]}.generated_data_files",
                    srcs = [
            """
            )

            for (
                package_name,
                extension,
            ) in self.pyproject.project.extension_modules.items():
                if extension.ignore:
                    continue
                package_path_elems = package_name.split(".")
                package_path = pathlib.Path(*package_path_elems[:-1])
                module_name = package_path_elems[-1]
                self.output_buffer.writeln(
                    f'        "{package_path}/{extension.name}.pc",'
                )
            for caster_name, caster_install_path in self.local_caster_targets.items():
                self.output_buffer.writeln(
                    f'        "{caster_install_path}/{caster_name}.pc",'
                )
                self.output_buffer.writeln(
                    f'        "{caster_install_path}/{caster_name}.pybind11.json",'
                )
            self.output_buffer.writeln("    ],\n)")

        copy_extension_text = (
            f'[\n        ":{package_path_elems[0]}.generated_data_files",\n        '
            + "\n        ".join(f'":copy_{x}",' for _, x, z in all_extension_names)
        )
        copy_extension_text += "\n        " + "\n        ".join(
            f'":{x}.trampoline_hdr_files",' for _, x, z in all_extension_names
        )
        copy_extension_text += "\n    ]"

        self.output_buffer.writeln()
        self.output_buffer.writeln(f"    return {copy_extension_text}")

        libinit_files_text = (
            "[\n        "
            + "\n        ".join(
                f'"{x}/_init_{z}.py",' for (x, y, z) in all_extension_names
            )
            + "\n    ]"
        )
        self.output_buffer.writeln()
        self.output_buffer.writeln(
            f"""def libinit_files():\n    return {libinit_files_text}"""
        )

        # extension_modules = [BazelExtensionModule(name = "wpiutil")]

        print(os.getcwd())
        import jinja2
        from jinja2 import Environment, PackageLoader, select_autoescape
        from jinja2 import Environment, BaseLoader
        # templateLoader = jinja2.FileSystemLoader(searchpath="external/rules_semiwrap~/rules_semiwrap/tools")
        # templateEnv = jinja2.Environment(loader=templateLoader)
        # env = Environment(
        #     loader=PackageLoader("tools"),
        #     autoescape=select_autoescape()
        # )/home/pjreiniger/git/robotpy/robotpy_monorepo/rules_semiwrap/rules_semiwrap/tools/generated_build_info.bzl.jinja2
        template = Environment(loader=BaseLoader).from_string(BUILD_FILE_TEMPLATE)

        print("----")
        print(self.pyproject.root)
        print(self.pyproject.package_root)
        print(self.pyproject)
        print(type(self.pyproject))
        with open(self.pyproject.root / "pyproject.toml", "rb") as fp:
            raw_config = tomli.load(fp)
        print(raw_config)

        print("----")
        for key in raw_config:
            print(key, raw_config[key])
        
        with open(output_file, "w") as f:
            f.write(template.render(
                extension_modules=self.extension_modules, 
                local_caster_targets=self.local_caster_targets,
                top_level_name = raw_config["project"]["name"].replace("robotpy-", ""),
                raw_project_config = raw_config["project"],
                # project_name = raw_config["project"]["name"],
                # summary = raw_config["project"]["description"],
                # dependencies = raw_config["project"]["dependencies"],
                # urls = raw_config["project"]["dependencies"],
                ))

    def _process_export_type_caster(self, name: str, caster_cfg: TypeCasterConfig):
        dep = self.pkgcache.add_local(
            name=name,
            includes=[self.project_root / inc for inc in caster_cfg.includedir],
            requires=[],  # caster_cfg.requires,
        )

        # The .pc file cannot be used in the build, but the data file must be, so
        # store it so it can be used elsewhere
        self.local_caster_targets[name] = caster_cfg.pypackage

    def _sorted_extension_modules(
        self,
    ) -> T.Generator[T.Tuple[str, ExtensionModuleConfig], None, None]:
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

    def _process_extension_module(
        self, package_name: str, extension: ExtensionModuleConfig
    ):
        bazel_extension_module = BazelExtensionModule(package_name, extension)
        self.extension_modules.append(bazel_extension_module)
        self._write_extension_function_header(extension)

        package_path_elems = package_name.split(".")
        parent_package = ".".join(package_path_elems[:-1])
        module_name = package_path_elems[-1]
        package_path = pathlib.Path(*package_path_elems[:-1])
        varname = extension.name or package_name.replace(".", "_")

        # Detect the location of the package in the source tree
        package_init_py = self.pyproject.package_root / package_path / "__init__.py"

        depends = self.pyproject.get_extension_deps(extension)

        bazel_extension_module.set_depends(depends)
        bazel_header_paths = resolve_dependency(depends, package_path_elems[0])

        hack_pkgconfig(depends, self.pkgcfgs)

        # Search path for wrapping is dictated by package_path and wraps
        search_path, include_directories_uniq, caster_json_file, libinit_modules = (
            self._prepare_dependency_paths(depends, extension)
        )

        if extension.name == "wpiutil":
            search_path.append(pathlib.Path("subprojects/robotpy-wpiutil/wpiutil/"))
        elif "wpilib" in extension.name:
            search_path.append(pathlib.Path("subprojects/robotpy-wpilib/wpilib/src"))
        elif "cscore" in extension.name:
            search_path.append(
                pathlib.Path(
                    "bazel-mostrobotpy/external/bzlmodrio-allwpilib~~setup_bzlmodrio_allwpilib_cpp_dependencies~bazelrio_edu_wpi_first_cscore_cscore-cpp_headers"
                )
            )
            search_path.append(
                pathlib.Path(
                    "bazel-mostrobotpy/external/bzlmodrio-allwpilib~~setup_bzlmodrio_allwpilib_cpp_dependencies~bazelrio_edu_wpi_first_cameraserver_cameraserver-cpp_headers"
                )
            )

        includes = [
            self.project_root / pathlib.PurePosixPath(inc) for inc in extension.includes
        ]
        search_path.extend(includes)
        for inc in includes:
            include_directories_uniq[inc] = True

        all_type_casters = None

        #
        # Generate init.py for loading dependencies
        #

        libinit_module = None
        if libinit_modules:
            libinit_py = extension.libinit or f"_init_{module_name}.py"
            libinit_module = f"{parent_package}.{libinit_py}"[:-3]
            bazel_extension_module.libinit_py = libinit_py

        #
        # Process the headers
        #

        # Find and load the yaml
        if extension.yaml_path is None:
            yaml_path = pathlib.Path("semiwrap")
        else:
            yaml_path = pathlib.Path(pathlib.PurePosixPath(extension.yaml_path))

        datfiles, module_sources, subpackages, local_hdrs = self._process_headers(
            bazel_extension_module,
            extension,
            package_path,
            yaml_path,
            include_directories_uniq.keys(),
            search_path,
            all_type_casters,
        )
        bazel_extension_module.set_subpackages(subpackages)

        cached_dep = self.pkgcache.add_local(
            name=varname,
            includes=[*includes, self.pyproject.package_root / package_path],
            requires=depends,
            libinit_py=libinit_module,
        )

        bazel_extension_module.libinit_modules = libinit_modules
        bazel_extension_module.libinit_py = libinit_py
        bazel_extension_module.set_caster_json_file(caster_json_file)

        self._write_extension_function_footer(
            extension,
            caster_json_file,
            bazel_header_paths,
            local_hdrs,
            libinit_modules,
            libinit_py,
            package_name,
            parent_package,
            module_name,
            package_path,
            subpackages,
        )

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

        return trampolines

    def _process_tmpl_str(self, yml: str, ayml: AutowrapConfigYaml) -> str:
        templates = []

        for i, (name, tctx) in enumerate(ayml.templates.items(), start=1):
            templates.append((f"{yml}_tmpl{i}", f"{name}"))

        # output = "["
        # if templates:
        #     output += "\n                            "
        #     output += ",\n                            ".join(f'("{t[0]}", "{t[1]}")' for t in templates)
        #     output += ",\n                        "

        # output += "]"
        return templates

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
                caster_json_file.append(
                    ":"
                    + self.local_caster_targets[name]
                    + "/"
                    + name
                    + ".pybind11.json"
                )
            else:
                tc = entry.type_casters_path
                if tc and tc not in caster_json_file:
                    resolve_str = f'resolve_caster_file("{entry.name}")'
                    if resolve_str not in caster_json_file:
                        caster_json_file.append(resolve_str)

            for req in entry.requires:
                if req not in checked:
                    to_check.append(req)

    def _prepare_dependency_paths(
        self, depends: T.List[str], extension: ExtensionModuleConfig
    ):
        search_path: T.List[pathlib.Path] = []
        include_directories_uniq: T.Dict[pathlib.Path, bool] = {}
        caster_json_file: T.List[T.Union[BuildTargetOutput, pathlib.Path]] = []
        libinit_modules: T.List[str] = []

        # Add semiwrap default type casters
        # caster_json_file.append(self.semiwrap_type_caster_path)

        for dep in depends:
            entry = self.pkgcache.get(dep)
            include_directories_uniq.update(
                dict.fromkeys(entry.full_include_path, True)
            )

            # extend the search path if the dependency is in 'wraps'
            if dep in extension.wraps:
                search_path.extend(entry.include_path)

            self._locate_type_caster_json(dep, caster_json_file)

            if entry.libinit_py:
                libinit_modules.append(entry.libinit_py)

        return search_path, include_directories_uniq, caster_json_file, libinit_modules

    def _process_headers(
        self,
        bazel_extension_module: BazelExtensionModule,
        extension: ExtensionModuleConfig,
        package_path: pathlib.Path,
        yaml_path: pathlib.Path,
        include_directories_uniq: T.Iterable[pathlib.Path],
        search_path: T.List[pathlib.Path],
        all_type_casters,
    ):

        datfiles: T.List[BuildTarget] = []
        module_sources: T.List[BuildTarget] = []
        subpackages: T.Set[str] = set()
        define_args = []
        local_hdrs = []

        root_package = package_path.parts[0]

        for yml, hdr in self.pyproject.get_extension_headers(extension):
            yml_input = yaml_path / f"{yml}.yml"

            ayml = AutowrapConfigYaml.from_file(self.project_root / yml_input)

            h_input, h_root = self._locate_header(hdr, search_path)

            bazel_extension_module.add_header(
                root_package, yml, hdr, ayml, yml_input, h_input, h_root
            )

            local_hdrs.extend(
                self._write_header_gen_struct(
                    root_package, yml, hdr, ayml, yml_input, h_input, h_root
                )
            )
            
            # Detect subpackages
            for f in ayml.functions.values():
                if f.ignore:
                    continue
                if f.subpackage:
                    subpackages.add(f.subpackage)
                for f in f.overloads.values():
                    if f.subpackage:
                        subpackages.add(f.subpackage)

            for e in ayml.enums.values():
                if e.ignore:
                    continue
                if e.subpackage:
                    subpackages.add(e.subpackage)

            for name, ctx in ayml.classes.items():
                if ctx.ignore:
                    continue

                if ctx.subpackage:
                    subpackages.add(ctx.subpackage)

            if ayml.templates:
                for i, (name, tctx) in enumerate(ayml.templates.items(), start=1):
                    if tctx.subpackage:
                        subpackages.add(tctx.subpackage)

        return datfiles, module_sources, subpackages, local_hdrs

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

    def _write_extension_function_header(self, extension):
        self.output_buffer.writeln()
        self.output_buffer.writeln(
            f"""def {extension.name}_extension(entry_point, deps, header_to_dat_deps, extension_name = None, extra_hdrs = [], extra_srcs = [], includes = []):"""
        )
        self.output_buffer.writeln(f"    {extension.name.upper()}_HEADER_GEN = [")

    def _write_extension_function_footer(
        self,
        extension,
        caster_json_file,
        bazel_header_paths,
        local_hdrs,
        libinit_modules,
        libinit_py,
        package_name,
        parent_package,
        module_name,
        package_path,
        subpackages,
    ):
        # caster_json_file = []
        # libinit_modules = []
        # package_path = ""
        # parent_package = ""
        # libinit = ""
        # package_name = ""
        # module_name = ""
        extra_generation_hdrs_str = ""
        root_package = ""

        subpackage_name = "/".join(package_name.split(".")[:-1])

        package_path_elems = package_name.split(".")
        module_name = package_path_elems[-1]

        libinit_modules_str = "[" + ", ".join(f'"{x}"' for x in libinit_modules) + "]"
        if local_hdrs:
            extra_generation_hdrs_str = (
                " + [" + ",".join(f'"{x}"' for x in local_hdrs) + "]"
            )

        caster_files_str = ""
        caster_deps_str = ""
        # if caster_json_file:
        for cjf in caster_json_file:
            if cjf.startswith("resolve_caster_file"):
                caster_deps_str += cjf + ", "
            else:
                caster_files_str += f'"{cjf}"'

        if caster_files_str:
            caster_files_str = f"\n        caster_files = [{caster_files_str}],"
        if caster_deps_str:
            caster_deps_str = f"\n        caster_deps = [{caster_deps_str[:-2]}],"

        with self.output_buffer.indent(4):
            self.output_buffer.write_trim(
                f"""
    ]

    resolve_casters(
        name = "{extension.name}.resolve_casters",{caster_files_str}{caster_deps_str}
        casters_pkl_file = "{extension.name}.casters.pkl",
        dep_file = "{extension.name}.casters.d",
    )

    gen_libinit(
        name = "{extension.name}.gen_lib_init",
        output_file = "{package_path}/{libinit_py}",
        modules = {libinit_modules_str},
    )

    gen_pkgconf(
        name = "{extension.name}.gen_pkgconf",
        libinit_py = "{parent_package}.{libinit_py[:-3]}",
        module_pkg_name = "{package_name}",
        output_file = "{extension.name}.pc",
        pkg_name = "{extension.name}",
        install_path = "{package_path}",
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
        trampoline_subpath = "{subpackage_name}",
        deps = header_to_dat_deps{extra_generation_hdrs_str},
        local_native_libraries = {bazel_header_paths},
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
            print(subpackages)
            if subpackages:
                pyi_files = ["__init__.pyi"]
                for sp in subpackages:
                    pyi_files.append(sp + ".pyi")

            else:
                pyi_files = [package_name.split(".")[-1] + ".pyi"]

            pyi_str = "[\n            " + ",\n            ".join(f'"{x}"' for x in pyi_files) + "\n        ]"


            # print(subpackages)
            # print(package_name.split("."))
            # raise

            self.output_buffer.write_trim(
                f"""


    make_pyi(
        name = "{extension.name}.make_pyi",
        extension_package = "{extension.name}.{module_name}",
        interface_files = {pyi_str},
        init_pkgcfgs = ["{extension.name}/_init_{module_name}.py"],
        install_path = "{package_path}/{module_name}",
        extension_library = "copy_{extension.name}",
        init_packages = ["{extension.name}"],
        python_deps = [
            "//subprojects/robotpy-native-wpinet:import",
            "//subprojects/robotpy-wpiutil:import",
        ],
    )"""
            )

    def _write_header_gen_struct(
        self, root_package, yml, hdr, ayml, yml_input, h_input, h_root
    ):
        tmpl_class_names = self._process_tmpl_str(yml, ayml)
        trampolines = self._process_trampolines_str(ayml)

        local_hdrs = []

        # TODO hack
        if root_package == "hal":
            root_package = "wpihal"

        if "site-packages" in str(h_root):
            if root_package == "robotpy_apriltag":
                root_package = "apriltag"
            header_root = f'resolve_include_root("//subprojects/robotpy-native-{root_package}", "{root_package}")'
        else:
            header_root = f'"{h_root}"'
            local_hdrs.append(root_package / h_input.relative_to(h_root))

        header_suffix = h_input.relative_to(h_root)

        with self.output_buffer.indent(8):
            self.output_buffer.write_trim(
                f"""
            struct(
                class_name = "{yml}",
                yml_file = "{yml_input}",
                header_root = {header_root},
                header_file = {header_root} + "/{header_suffix}",
            """
            )
            if tmpl_class_names:
                self.output_buffer.writeln("    tmpl_class_names = [")
                with self.output_buffer.indent(4):
                    for tmpl in tmpl_class_names:
                        with self.output_buffer.indent(4):
                            self.output_buffer.writeln(f'("{tmpl[0]}", "{tmpl[1]}"),')
                self.output_buffer.writeln("    ],")
            else:
                self.output_buffer.writeln("    tmpl_class_names = [],")

            if trampolines:
                self.output_buffer.writeln("    trampolines = [")
                with self.output_buffer.indent(4):
                    for trampoline in trampolines:
                        with self.output_buffer.indent(4):
                            self.output_buffer.writeln(
                                f'("{trampoline[0]}", "{trampoline[1]}"),'
                            )
                self.output_buffer.writeln("    ],")
            else:
                self.output_buffer.writeln("    trampolines = [],")

            self.output_buffer.writeln("),")
            # ),""")

        return local_hdrs


def generate_build_info(
    project_file: pathlib.Path, output_file: pathlib.Path, pkgcfgs: T.List[pathlib.Path]
):
    generator = _BuildPlanner(project_file, pkgcfgs)
    generator.generate(output_file)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project_file", type=pathlib.Path, required=True)
    parser.add_argument("--output_file", type=pathlib.Path, required=True)
    parser.add_argument("--pkgcfgs", type=pathlib.Path, nargs="+")
    args = parser.parse_args()

    for pc in args.pkgcfgs:
        if not os.path.exists(pc):
            raise Exception(f"Package config {pc} does not exist")

    generate_build_info(args.project_file.parent, args.output_file, args.pkgcfgs)


BUILD_FILE_TEMPLATE = """load("@rules_semiwrap//:defs.bzl", "copy_extension_library", "create_pybind_library", "make_pyi", "robotpy_library")
load("@rules_semiwrap//rules_semiwrap/private:semiwrap_helpers.bzl", "gen_libinit", "gen_modinit_hpp", "gen_pkgconf", {% if local_caster_targets|length > 0 %}"publish_casters", {% endif %}"resolve_casters", "run_header_gen")
load("//bazel_scripts:file_resolver_utils.bzl", "local_native_libraries_helper", "resolve_caster_file", "resolve_include_root")
{% for extension_module in extension_modules%}
def {{extension_module.name}}_extension(entry_point, deps, header_to_dat_deps, extension_name = None, extra_hdrs = [], extra_srcs = [], includes = []):
    {{extension_module.name|upper}}_HEADER_GEN = [
    {%- for header_cfg in extension_module.header_configs %}
        struct(
            class_name = "{{header_cfg.yml}}",
            yml_file = "{{header_cfg.yml_input}}",
            header_root = {{header_cfg.header_root}},
            header_file = {{header_cfg.header_file}},
            {%- if header_cfg.templates|length > 0 %}
            tmpl_class_names = [
            {%- for tmpl in header_cfg.templates %}
                ("{{ tmpl[0] }}", "{{ tmpl[1] }}"),
            {%- endfor %}
            ],
            {%- else %}
            tmpl_class_names = [],
            {%- endif %}
            {%- if header_cfg.trampolines|length > 0 %}
            trampolines = [
            {%- for trampoline in header_cfg.trampolines %}
                ("{{ trampoline[0] }}", "{{ trampoline[1] }}"),
            {%- endfor %}
            ],
            {%- else %}
            trampolines = [],
            {%- endif %}
        ),
    {%- endfor %}
    ]

    resolve_casters(
        name = "{{extension_module.name}}.resolve_casters",
        {%- if extension_module.caster_files %}
        caster_files = [{%for cf in extension_module.caster_files %}{{cf}}{%endfor%}],
        {%- endif %}
        {%- if extension_module.caster_deps %}
        caster_deps = [{%for cd in extension_module.caster_deps %}{{cd}}{% if not loop.last %}, {% endif %}{%endfor%}],
        {%- endif %}
        casters_pkl_file = "{{extension_module.name}}.casters.pkl",
        dep_file = "{{extension_module.name}}.casters.d",
    )

    gen_libinit(
        name = "{{extension_module.name}}.gen_lib_init",
        output_file = "{{extension_module.package_path}}/{{extension_module.libinit_py}}",
        modules = [{% for module in extension_module.libinit_modules %}"{{module}}"{% if not loop.last %}, {% endif %}{% endfor %}],
    )

    gen_pkgconf(
        name = "{{extension_module.name}}.gen_pkgconf",
        libinit_py = "{{extension_module.parent_package}}.{{extension_module.libinit_py[:-3]}}",
        module_pkg_name = "{{extension_module.package_name}}",
        output_file = "{{extension_module.name}}.pc",
        pkg_name = "{{extension_module.name}}",
        install_path = "{{extension_module.package_path}}",
        project_file = "pyproject.toml",
    )

    gen_modinit_hpp(
        name = "{{extension_module.name}}.gen_modinit_hpp",
        input_dats = [x.class_name for x in {{extension_module.name|upper}}_HEADER_GEN],
        libname = "{{extension_module.module_name}}",
        output_file = "semiwrap_init.{{extension_module.package_name}}.hpp",
    )

    run_header_gen(
        name = "{{extension_module.name}}",
        casters_pickle = "{{extension_module.name}}.casters.pkl",
        header_gen_config = {{extension_module.name|upper}}_HEADER_GEN,
        trampoline_subpath = "{{extension_module.subpackage_name}}",
        deps = header_to_dat_deps{% if extension_module.local_headers %} + [{% for h in extension_module.local_headers %}"{{ h }}"{%endfor%}]{% endif %},
        local_native_libraries = [
        {%- for header_path in extension_module.header_paths|sort %}
            {{header_path}},
        {%- endfor %}
        ],
    )

    native.filegroup(
        name = "{{extension_module.name}}.generated_files",
        srcs = [
            "{{extension_module.name}}.gen_modinit_hpp.gen",
            "{{extension_module.name}}.header_gen_files",
            "{{extension_module.name}}.gen_pkgconf",
            "{{extension_module.name}}.gen_lib_init",
        ],
        tags = ["manual"],
    )
    create_pybind_library(
        name = "{{extension_module.name}}",
        entry_point = entry_point,
        extension_name = extension_name,
        generated_srcs = [":{{extension_module.name}}.generated_srcs"],
        semiwrap_header = [":{{extension_module.name}}.gen_modinit_hpp"],
        deps = deps + [
            ":{{extension_module.name}}.tmpl_hdrs",
            ":{{extension_module.name}}.trampoline_hdrs",
        ],
        extra_hdrs = extra_hdrs,
        extra_srcs = extra_srcs,
        includes = includes,
    )

    make_pyi(
        name = "{{extension_module.name}}.make_pyi",
        extension_package = "{{extension_module.parent_package}}.{{extension_module.module_name}}",
        extension_library = "copy_{{extension_module.name}}",
        interface_files = [
        {%- for pyi_file in extension_module.pyi_files|sort %}
            "{{pyi_file}}",
        {%- endfor %}
        ],
        {%- if extension_modules|length==1 %}
        init_pkgcfgs = ["{{extension_module.parent_package}}/_init_{{extension_module.module_name}}.py"],
        init_packages = ["{{extension_module.parent_package}}"],
        {%- else %}
        init_pkgcfgs = [
        {%- for em in extension_modules %}
            "{{em.subpackage_name}}/_init_{{em.module_name}}.py",
        {%- endfor %}
        ],
        init_packages = [
        {%- for em in extension_modules %}
            "{{em.subpackage_name}}",
        {%- endfor %}
        ],
        {%- endif %}
        install_path = "{{extension_module.pyi_install_path}}",
        python_deps = [
            "//subprojects/robotpy-native-wpinet:import",
            "//subprojects/robotpy-wpiutil:import",
        ],
        {%- if extension_modules|length > 1 %}
        local_extension_deps = [
        {%- for em in extension_modules %}
            ("{{em.subpackage_name}}/{{em.module_name}}", "copy_{{em.name}}"),
        {%- endfor %}
        ],
        {%- endif %}
    )
{% endfor %}
{%- for name, caster_install_path in local_caster_targets|items %}
def publish_library_casters(typecasters_srcs):
    publish_casters(
        name = "publish_casters",
        caster_name = "{{name}}",
        output_json = "{{caster_install_path}}/{{name}}.pybind11.json",
        output_pc = "{{caster_install_path}}/{{name}}.pc",
        project_config = "pyproject.toml",
        typecasters_srcs = typecasters_srcs,
    )
{% endfor %}
def get_generated_data_files():
    {%- for em in extension_modules %}
    copy_extension_library(
        name = "copy_{{em.name}}",
        extension = "{{em.module_name}}",
        output_directory = "{{em.package_path}}/",
    )
    {%- endfor %}

    native.filegroup(
        name = "{{top_level_name}}.generated_data_files",
        srcs = [
            {%- for em in extension_modules %}
            "{{em.package_path}}/{{em.name}}.pc",
            {%- endfor %}
            {%- for name, caster_install_path in local_caster_targets|items %}
            "{{caster_install_path}}/{{name}}.pc",
            "{{caster_install_path}}/{{name}}.pybind11.json",
            {%- endfor %}
        ],
    )

    return [
        ":{{top_level_name}}.generated_data_files",
        {%- for em in extension_modules %}
        ":copy_{{em.name}}",
        {%- endfor %}
        {%- for em in extension_modules %}
        ":{{em.name}}.trampoline_hdr_files",
        {%- endfor %}
    ]

def libinit_files():
    return [
    {%- for em in extension_modules %}
        "{{em.package_path}}/{{em.libinit_py}}",
    {%- endfor %}
    ]

def define_pybind_library(name, version):
    native.filegroup(
        name = "{{top_level_name}}.extra_pkg_files",
        srcs = native.glob(["{{top_level_name}}/**"], exclude = ["{{top_level_name}}/**/*.py"]),
        tags = ["manual"],
    )

    native.filegroup(
        name = "pyi_files",
        srcs = [
        {%- for em in extension_modules %}
            ":{{em.name}}.make_pyi",
        {%- endfor %}
        ],
    )

    robotpy_library(
        name = name,
        srcs = native.glob(["{{top_level_name}}/**/*.py"]) + libinit_files(),
        data = get_generated_data_files() + ["{{top_level_name}}.extra_pkg_files"] + [":pyi_files"],
        imports = ["."],
        robotpy_wheel_deps = ["//subprojects/robotpy-native-wpiutil:import"],
        strip_path_prefixes = ["subprojects/{{raw_project_config.name}}"],
        version = version,
        visibility = ["//visibility:public"],
        entry_points = {
            "pkg_config": [
                {%- for name, caster_install_path in local_caster_targets|items %}
                "{{name}} = {{caster_install_path}}",
                {%- endfor %}
                {%- for em in extension_modules %}
                "{{ em.name }} = {{ em.parent_package }}",
                {%- endfor %}
            ],
        },
        package_name = "{{raw_project_config.name}}",
        package_summary = "{{raw_project_config.description}}",
        package_project_urls = {{raw_project_config.urls}},
        package_author_email = "RobotPy Development Team <robotpy@googlegroups.com>",
        package_requires = {{raw_project_config.dependencies}},
    )

"""

if __name__ == "__main__":
    main()
