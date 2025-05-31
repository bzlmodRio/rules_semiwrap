import os

PYPROJECT_FILE_TMPL = "bazel-mostrobotpy/external/rules_python~~pip~rules_semiwrap_pip_deps_{}_semiwrap/site-packages/semiwrap/pyproject.py"

if os.path.exists(PYPROJECT_FILE_TMPL.format("39")):
    PYPROJECT_FILE = PYPROJECT_FILE_TMPL.format("39")
elif os.path.exists(PYPROJECT_FILE_TMPL.format("310")):
    PYPROJECT_FILE = PYPROJECT_FILE_TMPL.format("310")
elif os.path.exists(PYPROJECT_FILE_TMPL.format("311")):
    PYPROJECT_FILE = PYPROJECT_FILE_TMPL.format("311")
elif os.path.exists(PYPROJECT_FILE_TMPL.format("312")):
    PYPROJECT_FILE = PYPROJECT_FILE_TMPL.format("312")
elif os.path.exists(PYPROJECT_FILE_TMPL.format("313")):
    PYPROJECT_FILE = PYPROJECT_FILE_TMPL.format("313")
else:
    raise Exception("Unknown version")

with open(PYPROJECT_FILE, "r",) as f:
    contents = f.read()

print(contents)

contents = contents.replace(
    "def package_root(self) -> pathlib.Path:",
    "def package_root(self) -> pathlib.Path:\n        self._package_root = self.root",
)

with open(PYPROJECT_FILE, "w") as f:
    f.write(contents)

with open("subprojects/robotpy-hal/hal/version.py", "w") as f:
    f.write('version = __version__ = "2025.3.2.2"')
