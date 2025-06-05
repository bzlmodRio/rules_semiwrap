import argparse
import pathlib
import importlib
import sys
import os
import shutil


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--install_path", required=True, type=pathlib.Path)
    parser.add_argument("--extension_package", required=True)
    parser.add_argument("--output_files", nargs="+", type=pathlib.Path)
    parser.add_argument("--remapping_args", nargs="+")
    args = parser.parse_args()

    semiwrap_args = [args.extension_package]

    for output_file in args.output_files:
        semiwrap_args.extend([args.install_path / output_file.name, output_file])

    semiwrap_args.append("--")
    semiwrap_args.extend(args.remapping_args)

    module = importlib.import_module("semiwrap.cmd.make_pyi")
    tool_main = getattr(module, "main")

    sys.argv = [""] + [str(x) for x in semiwrap_args]
    try:
        tool_main()
    except:
        print("-------------------------------------")
        print("Failed to run wrapped tool.")
        print(f"Args:")
        for a in semiwrap_args:
            print("  ", a)
        print("-------------------------------------")
        raise


if __name__ == "__main__":
    main()
