from urllib.parse import quote as parse_url
from urllib.request import Request, urlopen, HTTPError
from xml.etree import ElementTree as ET
from os import getcwd, makedirs
from os import path as os_path

CACHE_DIR = os_path.join(getcwd(), ".mvn_cache")
CACHE_METADATA_DIR = os_path.join(CACHE_DIR, "metadata")
CACHE_POM_DIR = os_path.join(CACHE_DIR, "pom")
CACHE_JAR_DIR = os_path.join(CACHE_DIR, "jar")
DEFAULT_REPO_BASE = "https://repo1.maven.org/maven2"
DEFAULT_VERSION = "release"
DEFAULT_SCOPE = "compile"
DEFAULT_OPTIONAL = False


def get_package_page_url(repo_base: str, groupId: str, artifactId: str) -> str:
    groupId = groupId.replace(".", "/")
    groupId = parse_url(groupId)
    artifactId = parse_url(artifactId)
    return f"{repo_base}/{groupId}/{artifactId}"


def _quote_groupId_path(groupId: str):
    groupId = groupId.replace("..", "")
    groupId = groupId.replace(".", os_path.sep)
    groupId = groupId.replace(":", "").replace("?", "").replace("=", "")
    return groupId


def _quote_artifactId_path(artifactId: str):
    artifactId = artifactId.replace("..", "")
    artifactId = artifactId.replace("/", "").replace("\\", "")
    artifactId = artifactId.replace(":", "").replace("?", "").replace("=", "")
    return artifactId


def _quote_version_path(version: str):
    version = version.replace("..", "").replace("/", "").replace("\\", "")
    version = version.replace(":", "").replace("?", "").replace("=", "")
    return version


def get_metadata_cache_path(groupId: str, artifactId: str):
    groupId = _quote_groupId_path(groupId)
    artifactId = _quote_artifactId_path(artifactId)
    return os_path.join(CACHE_METADATA_DIR, groupId, artifactId, "maven-metadata.xml")


def get_pom_cache_path(groupId: str, artifactId: str, version: str):
    groupId = _quote_groupId_path(groupId)
    artifactId = _quote_artifactId_path(artifactId)
    version = _quote_version_path(version)
    return os_path.join(CACHE_POM_DIR, groupId, artifactId, f"{artifactId}-{version}.pom")


def get_jar_cache_path(groupId: str, artifactId: str, version: str, postfix: str = ""):
    groupId = _quote_groupId_path(groupId)
    artifactId = _quote_artifactId_path(artifactId)
    version = _quote_version_path(version)
    return os_path.join(CACHE_JAR_DIR, f"{artifactId}-{version}{postfix}.jar")


def fetch_url(url: str) -> str:
    req = Request(url)
    with urlopen(req) as resp:
        return resp.read().decode("utf-8")


def fetch_file(url: str) -> bytes:
    req = Request(url)
    with urlopen(req) as resp:
        return resp.read()


def tag_strip_namespace(tag: str):
    if tag.startswith("{"):
        tag = tag.split("}")[1]
    return tag


def parse_property_value(properties: dict[str, str], text: str):
    idx = text.find("${")
    while idx >= 0:
        end = text.find("}")
        name = text[idx + 2:end]
        replacement = properties.get(name, "")
        text_head = text[0:idx]
        text_tail = text[end + 1:]
        text = text_head + replacement + text_tail
        # find next
        idx = text.find("${")
    return text


class MavenPackageMeta:
    def __init__(self, groupId: str, artifactId: str, repo: str = DEFAULT_REPO_BASE) -> None:
        self.groupId = groupId
        self.artifactId = artifactId
        self.repo = repo
        self._base_url = get_package_page_url(repo, groupId, artifactId)
        self._metadata_cache = ""

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, MavenPackageMeta):
            return False
        return (self.groupId == value.groupId) and (self.artifactId == value.groupId)

    def __hash__(self) -> int:
        return hash(self.groupId) + hash(self.artifactId)

    def __repr__(self) -> str:
        if self.repo == DEFAULT_REPO_BASE:
            return f"MavenPackageMeta('{self.groupId}', '{self.artifactId}')"
        else:
            return f"MavenPackageMeta('{self.groupId}', '{self.artifactId}', '{self.repo}')"

    def _get_metadata(self) -> ET.Element:
        cache_path = get_metadata_cache_path(self.groupId, self.artifactId)
        if len(self._metadata_cache) > 0:
            pass  # using cache
        elif os_path.exists(cache_path):
            # load from cache
            with open(cache_path, "rt", encoding="utf-8") as f:
                self._metadata_cache = f.read()
        else:
            # load from remote repo
            url = f"{self._base_url}/maven-metadata.xml"
            content = fetch_url(url)
            if len(content) > 0:
                self._metadata_cache = content
                # save cache
                makedirs(os_path.dirname(cache_path), exist_ok=True)
                with open(cache_path, "wt", encoding="utf-8") as f:
                    f.write(content)
        # process xml
        return ET.fromstring(self._metadata_cache)

    def get_latest_version(self) -> str:
        root = self._get_metadata()
        for elem in root.iterfind(".//{*}latest"):
            return elem.text

    def get_release_version(self) -> str:
        root = self._get_metadata()
        for elem in root.iterfind(".//{*}release"):
            return elem.text

    def get_versions(self) -> list[str]:
        root = self._get_metadata()
        return [elem.text for elem in root.iterfind(".//{*}version")]

    def get_package(self, version: str = DEFAULT_VERSION):
        return MavenPackage(self, version)


class MavenPackage:
    def __init__(self, meta: MavenPackageMeta, version: str = DEFAULT_VERSION) -> None:
        self._version = version
        self.meta = meta
        self._pom_cache = ""
        self._version_is_unsure = False
        if version == None or version.lower().strip() in ("latest", "release", DEFAULT_VERSION, ""):
            self._version_is_unsure = True
    

    @property
    def version(self) -> str:
        return self._get_version()

    @property
    def version_is_unsure(self):
        return self._version_is_unsure

    def __repr__(self) -> str:
        return f"MavenPackage({repr(self.meta)}, '{self._version}')"

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, MavenPackage):
            return False
        return (self.meta == value.meta) and (self._get_version() == value._get_version())

    def __hash__(self) -> int:
        return hash(self.meta) + hash(self._get_version())

    def _get_version(self):
        if self._version == None or len(self._version.strip()) <= 0:
            self._version = DEFAULT_VERSION
        if self._version == "latest":
            self._version = self.meta.get_latest_version()
        elif self._version == "release":
            self._version = self.meta.get_release_version()
        return self._version

    def _get_package_file_url(self, postfix: str):
        version = self._get_version()
        return f"{self.meta._base_url}/{version}/{self.meta.artifactId}-{version}{postfix}"

    def _get_pom(self):
        cache_path = get_pom_cache_path(
            self.meta.groupId, self.meta.artifactId, self._get_version())
        if len(self._pom_cache) > 0:
            pass  # using cache
        elif os_path.exists(cache_path):
            # load from cache
            with open(cache_path, "rt", encoding="utf-8") as f:
                self._pom_cache = f.read()
        else:
            url = self._get_package_file_url(".pom")
            content = fetch_url(url)
            if len(content) > 0:
                self._pom_cache = content
                # save cache
                makedirs(os_path.dirname(cache_path), exist_ok=True)
                with open(cache_path, "wt", encoding="utf-8") as f:
                    f.write(content)
        # process xml
        return ET.fromstring(self._pom_cache)

    def get_dependencies(self) -> list['MavenDependencyPackage']:
        lst: list['MavenDependencyPackage'] = list()
        root = self._get_pom()
        # parse properties
        properties: dict[str, str] = dict()
        properties["project.version"] = self._version
        properties["project.groupId"] = self.meta.groupId
        properties["project.artifactId"] = self.meta.artifactId
        if root.find(".//{*}properties") != None:
            for prop in root.find(".//{*}properties").iter():
                tag = tag_strip_namespace(prop.tag)
                value = prop.text.strip() if prop.text else ""
                properties[tag] = value
        # parse deps
        for dep in root.iterfind(".//{*}dependencies/{*}dependency"):
            # id
            groupId = dep.find("./{*}groupId").text
            groupId = parse_property_value(properties, groupId)
            artifactId = dep.find("./{*}artifactId").text
            artifactId = parse_property_value(properties, artifactId)
            # version
            version = DEFAULT_VERSION
            if dep.find("./{*}version") != None:
                version = dep.find("./{*}version").text
                version = parse_property_value(properties, version)
            elif groupId == self.meta.groupId:
                version = self._version
            pkg = MavenDependencyPackage(
                MavenPackageMeta(groupId, artifactId, self.meta.repo),
                version
            )
            # scope
            pkg._scope = DEFAULT_SCOPE
            if dep.find("./{*}scope") != None:
                pkg._scope = dep.find("./{*}scope").text
            # optional
            if dep.find("./{*}optional") != None:
                pkg._optional = dep.find(
                    "./{*}optional").text.lower() == "true"
            lst.append(pkg)
        return lst

    def asDependencyPackage(self, optional: bool = DEFAULT_OPTIONAL, scope: str = DEFAULT_SCOPE) -> 'MavenDependencyPackage':
        pkg = MavenDependencyPackage(
            self.meta,
            self._version
        )
        pkg._scope = scope
        pkg._optional = optional
    
    def cache_jar(self, postfix: str = "") -> bool:
        cache_path = get_jar_cache_path(self.meta.groupId, self.meta.artifactId, self._get_version(), postfix)
        if not os_path.exists(cache_path):
            url = self._get_package_file_url(f"{postfix}.jar")
            try:
                data = fetch_file(url)
            except HTTPError:
                return False
            makedirs(os_path.dirname(cache_path), exist_ok=True)
            with open(cache_path, "wb") as f:
                f.write(data)
        return True


class MavenDependencyPackage(MavenPackage):
    def __init__(self, meta: MavenPackageMeta, version: str = DEFAULT_VERSION) -> None:
        super().__init__(meta, version)
        self._scope = DEFAULT_SCOPE
        self._optional = DEFAULT_OPTIONAL

    @property
    def scope(self) -> str:
        return self._scope

    @property
    def optional(self) -> str:
        return self._optional
