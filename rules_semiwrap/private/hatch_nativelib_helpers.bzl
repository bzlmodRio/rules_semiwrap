def generate_native_lib_files(name, pyproject_toml, libinit_file, pc_file, pc_dep_files, pc_dep_deps):
    cmd = "$(locations @rules_semiwrap//rules_semiwrap/private/hatchlib_native_port:generate_native_lib_files) "
    cmd += "  $(location " + pyproject_toml + ")"
    cmd += " $(OUTS) "
    cmd += " ".join(pc_dep_files)

    native.genrule(
        name = name,
        srcs = [pyproject_toml] + pc_dep_deps,
        outs = [libinit_file, pc_file],
        cmd = cmd,
        tools = ["@rules_semiwrap//rules_semiwrap/private/hatchlib_native_port:generate_native_lib_files"],
    )
