import os
import pathlib
import shutil


def copy_meson_projects():
    projects = [
        "pyntcore",
        "robotpy-apriltag",
        "robotpy-cscore",
        "robotpy-hal",
        "robotpy-romi",
        "robotpy-wpilib",
        "robotpy-wpimath",
        "robotpy-wpinet",
        "robotpy-wpiutil",
        "robotpy-xrp",
        "robotpy-halsim-gui",
    ]

    for project in projects:
        resolved_project_name = project
        if project == "robotpy-wpilib":
            resolved_project_name = "wpilib"

        for root, _, files in os.walk(f"bazel-bin/subprojects/{project}/generated"):
            for f in files:
                if f.endswith(".dat") or f.endswith(".d") or f.endswith(".pkl"):
                    continue

                full_file = pathlib.Path(os.path.join(root, f))
                print(full_file)

                if "dat_to_trampoline_hdr" in root:
                    dst_file = pathlib.Path(
                        f"/home/pjreiniger/git/robotpy/temp_gen_results/{resolved_project_name.replace('-', '_')}-2025.3.2.2/build/cp310/semiwrap/trampolines/{f}"
                    )
                else:
                    dst_file = pathlib.Path(
                        f"/home/pjreiniger/git/robotpy/temp_gen_results/{resolved_project_name.replace('-', '_')}-2025.3.2.2/build/cp310/semiwrap/{f}"
                    )
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                # os.chmod(dst_file, 0o777)
                shutil.copy(full_file, dst_file)
                os.chmod(dst_file, 0o644)

        for root, dirs, files in os.walk(f"bazel-bin/subprojects/{project}/"):
            ignored_dirs = []
            for d in dirs:
                if "runfiles" in d:
                    ignored_dirs.append(d)
            for d in ignored_dirs:
                dirs.remove(d)

            for f in files:
                full_file = os.path.join(root, f)
                if f.startswith("_init__") and f.endswith(".py"):
                    print("Got one", full_file)

                    dst_file = pathlib.Path(
                        f"/home/pjreiniger/git/robotpy/temp_gen_results/{project.replace('-', '_')}-2025.3.2.2/build/cp310/semiwrap/{f}"
                    )
                    dst_file.parent.mkdir(parents=True, exist_ok=True)
                    print(dst_file)


def copy_other_projects():

    projects = [
        "robotpy-native-apriltag",
        "robotpy-native-datalog",
        "robotpy-native-ntcore",
        "robotpy-native-romi",
        "robotpy-native-wpihal",
        "robotpy-native-wpilib",
        "robotpy-native-wpimath",
        "robotpy-native-wpinet",
        "robotpy-native-wpiutil",
        "robotpy-native-xrp",
    ]

    for project in projects:

        for root, dirs, files in os.walk(f"bazel-bin/subprojects/{project}/"):
            ignored_dirs = []
            for d in dirs:
                if "runfiles" in d:
                    ignored_dirs.append(d)
            for d in ignored_dirs:
                dirs.remove(d)

            for f in files:
                full_file = os.path.join(root, f)
                if f.startswith("_init_robotpy_native_") and f.endswith(".py"):
                    print(f)
                    dst_file = pathlib.Path(
                        f"/home/pjreiniger/git/robotpy/temp_gen_results/{project.replace('-', '_')}-2025.3.2/src/native/{project[15:]}/{f}"
                    )
                    dst_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(full_file, dst_file)
                    os.chmod(dst_file, 0o644)


# robotpy_native_wpimath-2025.3.2/src/native/wpimath/_init_robotpy_native_wpimath.py
# robotpy_native_wpimath-2025.3.2/src/native/robotpy-native-wpimath/_init_robotpy_native_wpimath.py


def main():
    copy_meson_projects()
    copy_other_projects()


if __name__ == "__main__":
    main()
