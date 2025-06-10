
import jinja2
from jinja2 import Environment, PackageLoader, select_autoescape
from jinja2 import Environment, BaseLoader
import pathlib
import tomli
import json
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pyproject", type=pathlib.Path)
    parser.add_argument("--output_file", type=pathlib.Path)
    args = parser.parse_args()

    def double_quotes(data):
        if data:
            return json.dumps(data)
        return None

    def get_subpath(library):
        return library.replace("robotpy-native-", "")

    env = Environment(loader=BaseLoader)
    env.filters['double_quotes'] = double_quotes
    env.filters['get_subpath'] = get_subpath
    template = env.from_string(BUILD_FILE_TEMPLATE)
    
    with open(args.pyproject, "rb") as fp:
        raw_config = tomli.load(fp)
    
    with open(args.output_file, 'w') as f:
        f.write(template.render(
            raw_project_config = raw_config["project"],
            nativelib_config = raw_config["tool"]["hatch"]["build"]["hooks"]["nativelib"]
        ))


BUILD_FILE_TEMPLATE = """load("@rules_cc//cc:cc_library.bzl", "cc_library")
load("@rules_python//python:pip.bzl", "whl_filegroup")
load("@rules_semiwrap//:defs.bzl", "create_native_library")
load("//bazel_scripts:file_resolver_utils.bzl", "local_pc_file_util")

def define_library(name, headers, headers_external_repositories, shared_library, windows_interface_library, version):
    create_native_library(
        name = name,
        package_name = "{{raw_project_config.name}}",
        entry_points = {"pkg_config": ["{{nativelib_config.pcfile[0].name}} = native.{{nativelib_config.pcfile[0].name}}"]},
        headers = headers,
        headers_external_repositories = headers_external_repositories,
        shared_library = shared_library,
        lib_name = "{{nativelib_config.pcfile[0].name}}",
        local_pc_file_info ={% if nativelib_config.pcfile[0].requires | length == 0 %} [],{% else %}
        {%- for dep in nativelib_config.pcfile[0].requires | sort %}
            local_pc_file_util("//subprojects/{{dep}}", ["native/{{dep | get_subpath}}/{{dep}}.pc"]){% if not loop.last %} +{% endif %}
        {%- endfor %},{% endif %}
        package_requires = {{raw_project_config.dependencies|double_quotes}},
        package_summary = "{{raw_project_config.description}}",
        strip_pkg_prefix = ["subprojects/{{raw_project_config.name}}"],
        version = version,
    )

    whl_filegroup(
        name = "header_files",
        pattern = "native/{{nativelib_config.pcfile[0].name}}/include",
        whl = ":{{raw_project_config.name}}-wheel",
        visibility = ["//visibility:public"],
        tags = ["manual"],
    )

    cc_library(
        name = "{{nativelib_config.pcfile[0].name}}",
        srcs = [shared_library],
        hdrs = [":header_files"],
        includes = ["header_files/native/{{nativelib_config.pcfile[0].name}}/include"],
        visibility = ["//visibility:public"],
        deps = [
        {%- for dep in nativelib_config.pcfile[0].requires | sort %}
            "//subprojects/{{dep}}:{{dep | get_subpath}}",
        {%- endfor %}
        ] + select({
            "@bazel_tools//src/conditions:windows": [windows_interface_library],
            "//conditions:default": [],
        }),
        tags = ["manual"],
    )

"""


if __name__ == "__main__":
    main()