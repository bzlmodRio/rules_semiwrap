def gen_libinit(name, lib_name, output_file, modules):
    cmd = "$(locations //bazel_scripts:render_native_libinit) "
    cmd += "  " + lib_name
    cmd += " $(OUTS) "
    for module in modules:
        cmd += " " + module

    native.genrule(
        name = name,
        outs = [output_file],
        cmd = cmd,
        tools = ["//bazel_scripts:render_native_libinit"],
    )
