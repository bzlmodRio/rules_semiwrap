import os
import shutil
import pathlib


def cp_file(src, dst):
    full_dst = pathlib.Path(os.path.join(dst, os.path.basename(src)))
    full_dst.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy(src, full_dst)
    os.chmod(full_dst, 0o777)


cp_file(
    "bazel-bin/subprojects/robotpy-apriltag/generated/gen_libinit/_init__apriltag.py",
    "subprojects/robotpy-apriltag/robotpy_apriltag",
)
cp_file(
    "bazel-bin/subprojects/pyntcore/generated/gen_libinit/_init__ntcore.py",
    "subprojects/pyntcore/ntcore",
)
cp_file(
    "bazel-bin/subprojects/robotpy-cscore/generated/gen_libinit/_init__cscore.py",
    "subprojects/robotpy-cscore/cscore",
)
cp_file(
    "bazel-bin/subprojects/robotpy-hal/generated/gen_libinit/_init__wpiHal.py",
    "subprojects/robotpy-hal/hal",
)
cp_file(
    "bazel-bin/subprojects/robotpy-hal/generated/gen_libinit/_init__simulation.py",
    "subprojects/robotpy-hal/hal/simulation",
)
cp_file(
    "bazel-bin/subprojects/robotpy-romi/generated/gen_libinit/_init__romi.py",
    "subprojects/robotpy-romi/romi",
)
cp_file(
    "bazel-bin/subprojects/robotpy-wpimath/generated/gen_libinit/_init__wpimath.py",
    "subprojects/robotpy-wpimath/wpimath",
)
cp_file(
    "bazel-bin/subprojects/robotpy-wpimath/generated/gen_libinit/_init__geometry.py",
    "subprojects/robotpy-wpimath/wpimath/geometry",
)
cp_file(
    "bazel-bin/subprojects/robotpy-wpimath/generated/gen_libinit/_init__filter.py",
    "subprojects/robotpy-wpimath/wpimath/filter",
)
cp_file(
    "bazel-bin/subprojects/robotpy-wpimath/generated/gen_libinit/_init__interpolation.py",
    "subprojects/robotpy-wpimath/wpimath/interpolation",
)
cp_file(
    "bazel-bin/subprojects/robotpy-wpimath/generated/gen_libinit/_init__kinematics.py",
    "subprojects/robotpy-wpimath/wpimath/kinematics",
)
cp_file(
    "bazel-bin/subprojects/robotpy-wpimath/generated/gen_libinit/_init__spline.py",
    "subprojects/robotpy-wpimath/wpimath/spline",
)
cp_file(
    "bazel-bin/subprojects/robotpy-wpimath/generated/gen_libinit/_init__controls.py",
    "subprojects/robotpy-wpimath/wpimath/_controls",
)
cp_file(
    "bazel-bin/subprojects/robotpy-wpinet/generated/gen_libinit/_init__wpinet.py",
    "subprojects/robotpy-wpinet/wpinet",
)
cp_file(
    "bazel-bin/subprojects/robotpy-wpiutil/generated/gen_libinit/_init__wpiutil.py",
    "subprojects/robotpy-wpiutil/wpiutil",
)
cp_file(
    "bazel-bin/subprojects/robotpy-xrp/generated/gen_libinit/_init__xrp.py",
    "subprojects/robotpy-xrp/xrp",
)

cp_file(
    "bazel-bin/subprojects/robotpy-wpilib/generated/gen_libinit/_init__wpilib.py",
    "subprojects/robotpy-wpilib/wpilib",
)
cp_file(
    "bazel-bin/subprojects/robotpy-wpilib/generated/gen_libinit/_init__drive.py",
    "subprojects/robotpy-wpilib/wpilib/drive",
)
cp_file(
    "bazel-bin/subprojects/robotpy-wpilib/generated/gen_libinit/_init__event.py",
    "subprojects/robotpy-wpilib/wpilib/event",
)
cp_file(
    "bazel-bin/subprojects/robotpy-wpilib/generated/gen_libinit/_init__interfaces.py",
    "subprojects/robotpy-wpilib/wpilib/interfaces",
)
cp_file(
    "bazel-bin/subprojects/robotpy-wpilib/generated/gen_libinit/_init__simulation.py",
    "subprojects/robotpy-wpilib/wpilib/simulation",
)


cp_file(
    "bazel-bin/subprojects/robotpy-native-apriltag/native/apriltag/_init_robotpy_native_apriltag.py",
    "subprojects/robotpy-native-apriltag/native/apriltag",
)
cp_file(
    "bazel-bin/subprojects/robotpy-native-ntcore/native/ntcore/_init_robotpy_native_ntcore.py",
    "subprojects/robotpy-native-ntcore/native/ntcore",
)
cp_file(
    "bazel-bin/subprojects/robotpy-native-romi/native/romi/_init_robotpy_native_romi.py",
    "subprojects/robotpy-native-romi/native/romi",
)
cp_file(
    "bazel-bin/subprojects/robotpy-native-wpihal/native/wpihal/_init_robotpy_native_wpihal.py",
    "subprojects/robotpy-native-wpihal/native/wpihal",
)
cp_file(
    "bazel-bin/subprojects/robotpy-native-wpilib/native/wpilib/_init_robotpy_native_wpilib.py",
    "subprojects/robotpy-native-wpilib/native/wpilib",
)
cp_file(
    "bazel-bin/subprojects/robotpy-native-wpimath/native/wpimath/_init_robotpy_native_wpimath.py",
    "subprojects/robotpy-native-wpimath/native/wpimath",
)
cp_file(
    "bazel-bin/subprojects/robotpy-native-wpinet/native/wpinet/_init_robotpy_native_wpinet.py",
    "subprojects/robotpy-native-wpinet/native/wpinet",
)
cp_file(
    "bazel-bin/subprojects/robotpy-native-wpiutil/native/wpiutil/_init_robotpy_native_wpiutil.py",
    "subprojects/robotpy-native-wpiutil/native/wpiutil",
)
cp_file(
    "bazel-bin/subprojects/robotpy-native-xrp/native/xrp/_init_robotpy_native_xrp.py",
    "subprojects/robotpy-native-xrp/native/xrp",
)
