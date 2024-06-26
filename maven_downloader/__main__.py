import maven


def dump_dependencies(pkg: maven.MavenPackage, indent: int = 0, processed: set[maven.MavenPackage] = set()):
    for dep in pkg.get_dependencies():
        if dep.scope.lower() == "compile" and (not dep.optional) and dep not in processed:
            print("    " * indent, end="")
            print(dep)
            processed.add(dep)
            dump_dependencies(dep, indent + 1)

def walk_dependencies(pkg: maven.MavenPackage, indent: int = 0, processed: set[maven.MavenPackage] = set()):
    for dep in pkg.get_dependencies():
        if dep.scope.lower() == "compile" and (not dep.optional) and dep not in processed:
            processed.add(dep)
            walk_dependencies(dep, indent + 1)


def main():
    pkgmeta = maven.MavenPackageMeta("org.apache.poi", "poi-ooxml")
    pkg = pkgmeta.get_package()
    depset: set[maven.MavenPackage] = set()
    depset.add(pkg)
    depset.add(
        maven.MavenPackageMeta("org.apache.poi", "poi-examples").get_package(
            pkg.version
        )
    )
    dump_dependencies(pkg, 0, depset)
    print("================")
    print("dep count:", len(depset))
    for dep in depset:
        print(dep)
        dep.cache_jar("")
        dep.cache_jar("-javadoc")
        dep.cache_jar("-sources")


if __name__ == "__main__":
    main()
