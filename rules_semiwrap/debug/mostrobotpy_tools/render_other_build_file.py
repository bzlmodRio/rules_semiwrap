import pathlib


def render_build_file(project_dir):
    print(project_dir.name)
    if "robotpy-native-" in str(project_dir):
        lib_name = project_dir.name[15:]

    print(lib_name)

    with open(project_dir / "BUILD.bazel", "w") as f:
        f.write(
            f"""load("//bazel_scripts:copy_native_file.bzl", "copy_native_file")
load("//bazel_scripts:hatch_nativelib_helpers.bzl", "gen_libinit")
load("//bazel_scripts:pybind_rules.bzl", "pybind_python_library")

gen_libinit(
    name = "gen_lib_init",
    lib_name = "{lib_name}",
    output_file = "native/{lib_name}/_init_robotpy_native_{lib_name}.py",
    modules = [],
)

copy_native_file(
    name = "{lib_name}",
    base_path = "native/{lib_name}",
    library = "@bzlmodrio-allwpilib//libraries/cpp/{lib_name}:shared_raw",
)

pybind_python_library(
    name = "{lib_name}",
    srcs = [":gen_lib_init"],
    data = [
        ":{lib_name}.copy_lib",
    ],
    imports = ["."],
    visibility = ["//visibility:public"],
)

"""
        )


def main():
    project_files = [
        pathlib.Path(
            "/home/pjreiniger/git/robotpy/mostrobotpy/subprojects/robotpy-native-wpiutil"
        ),
        pathlib.Path(
            "/home/pjreiniger/git/robotpy/mostrobotpy/subprojects/robotpy-native-wpinet"
        ),
        pathlib.Path(
            "/home/pjreiniger/git/robotpy/mostrobotpy/subprojects/robotpy-native-wpilib"
        ),
        pathlib.Path(
            "/home/pjreiniger/git/robotpy/mostrobotpy/subprojects/robotpy-native-wpihal"
        ),
        pathlib.Path(
            "/home/pjreiniger/git/robotpy/mostrobotpy/subprojects/robotpy-native-romi"
        ),
        pathlib.Path(
            "/home/pjreiniger/git/robotpy/mostrobotpy/subprojects/robotpy-native-ntcore"
        ),
        pathlib.Path(
            "/home/pjreiniger/git/robotpy/mostrobotpy/subprojects/robotpy-native-apriltag"
        ),
    ]

    for project_file in project_files:
        print(f"Running for {project_file}")
        render_build_file(project_file)


if __name__ == "__main__":
    main()
