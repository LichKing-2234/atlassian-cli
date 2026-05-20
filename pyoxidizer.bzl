def make_exe():
    dist = default_python_distribution(python_version = "3.10")
    policy = dist.make_python_packaging_policy()
    policy.resources_location = "filesystem-relative:lib"

    python_config = dist.make_python_interpreter_config()
    python_config.filesystem_importer = True
    python_config.run_module = "atlassian_cli.main"
    python_config.sys_frozen = True

    exe = dist.to_python_executable(
        name = "atlassian",
        packaging_policy = policy,
        config = python_config,
    )

    exe.add_python_resources(exe.read_virtualenv(path = VARS["RUNTIME_VENV"]))
    exe.add_python_resources(
        exe.read_package_root(
            path = VARS["SOURCE_ROOT"],
            packages = ["atlassian_cli"],
        )
    )

    return exe


def make_install(exe):
    files = FileManifest()
    files.add_python_resource(".", exe)
    return files


register_target("exe", make_exe)
register_target("install", make_install, depends = ["exe"], default = True)
resolve_targets()
