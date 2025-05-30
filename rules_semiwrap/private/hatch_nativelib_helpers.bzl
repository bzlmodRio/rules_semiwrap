def gen_libinit(name, lib_name, output_file, modules):
    cmd = "$(locations @rules_semiwrap//rules_semiwrap/private:render_native_libinit) "
    cmd += "  " + lib_name
    cmd += " $(OUTS) "
    for module in modules:
        cmd += " " + module

    native.genrule(
        name = name,
        outs = [output_file],
        cmd = cmd,
        tools = ["@rules_semiwrap//rules_semiwrap/private:render_native_libinit"],
    )
