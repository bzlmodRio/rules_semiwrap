import argparse
import sys
import semiwrap
import pathlib
from semiwrap.pyproject import PyProject
import tomli


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project_file", type=pathlib.Path, required=True)
    parser.add_argument("--output_file", type=pathlib.Path, required=True)
    args = parser.parse_args()

    with open(args.project_file, "rb") as fp:
        project_cfg = tomli.load(fp)

    # print(project_cfg)
    for key in project_cfg:
        print(key, "->", project_cfg[key])
    print()

    # project = PyProject().project
    project_name = project_cfg["tool"]["hatch"]["build"]["hooks"]["nativelib"][
        "pcfile"
    ][0]["name"]

    pkgconf_pypi_initpy = f"native.{project_name}._init_robotpy_native_{project_name}"

    requires = []
    if project_name in ["ntcore"]:
        requires.append("robotpy-native-wpinet")
    if project_name in ["ntcore", "wpinet", "wpimath"]:
        requires.append("robotpy-native-wpiutil")

    #     output_file = sys.argv[1]

    with open(args.output_file, "w") as f:
        f.write(
            """prefix=${pcfiledir}
includedir=${prefix}/include
libdir=${prefix}/lib
"""
        )
        f.write(
            f"""pkgconf_pypi_initpy={pkgconf_pypi_initpy}

Name: {project_name}
Description: {project_cfg["project"]["description"]}
Version: {project_cfg["project"]["version"]}"""
        )
        if requires:
            f.write("\nRequires: " + " ".join(requires))
        f.write(
            """
Libs: -L${libdir} """
            + f"-l{project_name}"
            + """
Cflags: -I${includedir}
"""
        )


if __name__ == "__main__":
    main()
