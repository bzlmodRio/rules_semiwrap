import sys
import pathlib
import typing as T
import platform

platform_sys = platform.system()
is_windows = platform_sys == "Windows"
is_macos = platform_sys == "Darwin"


# TODO: this belongs in a separate script/api that can be used from multiple tools
def _write_libinit_py(
    libs: T.List[pathlib.Path],
    init_py: pathlib.Path,
    requires: T.List[str],
):

    contents = [
        "# This file is automatically generated, DO NOT EDIT",
        "# fmt: off",
        "",
    ]

    for req in requires:
        contents.append(f"import {req}")

    if contents[-1] != "":
        contents.append("")

    if libs:
        contents += [
            "def __load_library():",
            "    from os.path import abspath, join, dirname, exists",
        ]

        if is_macos:
            contents += ["    from ctypes import CDLL, RTLD_GLOBAL"]
        else:
            contents += ["    from ctypes import cdll", ""]

        if len(libs) > 1:
            contents.append("    libs = []")

        contents.append("    root = abspath(dirname(__file__))")

        for lib in libs:
            # rel = lib.relative_to(init_py.parent)
            # components = ", ".join(map(repr, rel.parts))
            components = f"'lib', '{lib}'"

            contents += [
                "",
                f"    lib_path = join(root, {components})",
                "",
                "    try:",
            ]

            if is_macos:
                load = "CDLL(lib_path, mode=RTLD_GLOBAL)"
            else:
                load = "cdll.LoadLibrary(lib_path)"

            if len(libs) > 1:
                contents.append(f"        libs.append({load})")
            else:
                contents.append(f"        return {load}")

            contents += [
                "    except FileNotFoundError:",
                f"        if not exists(lib_path):",
                f'            raise FileNotFoundError("{lib.name} was not found on your system. Is this package correctly installed?")',
            ]

            if is_windows:
                contents.append(
                    f'        raise Exception("{lib.name} could not be loaded. Do you have Visual Studio C++ Redistributible installed?")'
                )
            else:
                contents.append(
                    f'        raise FileNotFoundError("{lib.name} could not be loaded. There is a missing dependency.")'
                )

        if len(libs) > 1:
            contents += ["    return libs"]

        contents += ["", "__lib = __load_library()", ""]

    content = ("\n".join(contents)) + "\n"

    with open(init_py, "w") as f:
        f.write(content)


def main():
    lib_name = sys.argv[1]

    if is_macos:
        lib_name = f"lib{lib_name}.dylib"
    elif is_windows:
        lib_name = f"{lib_name}.dll"
    else:
        lib_name = f"lib{lib_name}.so"

    _write_libinit_py([pathlib.Path(lib_name)], pathlib.Path(sys.argv[2]), sys.argv[3:])


if __name__ == "__main__":
    main()
