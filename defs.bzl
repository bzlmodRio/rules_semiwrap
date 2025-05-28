
load("//rules_semiwrap/private:copy_native_file.bzl", _copy_extension_library = "copy_extension_library")
load("//rules_semiwrap/private:pybind_rules.bzl", _robotpy_library = "robotpy_library")
load("//rules_semiwrap/private:semiwrap_helpers.bzl", _make_pyi = "make_pyi")
load("//rules_semiwrap/private:pybind_rules.bzl", _create_pybind_library = "create_pybind_library")


copy_extension_library = _copy_extension_library
robotpy_library = _robotpy_library
make_pyi = _make_pyi
create_pybind_library = _create_pybind_library