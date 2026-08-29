# Gradle Java convention

`io.github.janguenter.bluemap-addon.java-conventions` is a development-only
Gradle plugin introduced in toolkit `0.2.0-alpha.1`. It is loaded from toolkit
source through an exact nested Git submodule and
`pluginManagement.includeBuild`. The plugin is not shipped in a Python wheel,
resolved from GitHub Packages, or installed on a Minecraft server.

The plugin configures only:

- Java 21 toolchains and a sources JAR when the consumer applies `java`;
- UTF-8, Java 21, `-Xlint:all` and `-Werror` on every Java compile task;
- timestamp-free, reproducibly ordered archives;
- JUnit Platform on every test task;
- Checkstyle 10.18.2, the consumer's local configuration, and XML/HTML reports
  when the consumer applies `checkstyle`.

It does not apply `base`, `java`, `java-library`, `checkstyle` or
`maven-publish`. It declares no production or test dependency, repository,
publication, project coordinate, compression policy, manifest or release
task. `withSourcesJar()` intentionally exposes the ordinary Java sources
variant, and Checkstyle's selected tool version intentionally resolves the
consumer's existing Checkstyle tooling dependency.

## Repository contract checker

Toolkit `0.3.0-alpha.1` resolves the `0.2.0-alpha.1` checker limitation that
required the convention-owned settings to remain inline in `build.gradle`.
`bluemap-addon-toolkit conventions check` now accepts the exact applied plugin
declaration in the leading `plugins` block as the provider of Java 21,
compiler, Checkstyle, and reproducible-archive settings.

The checker still requires the consumer to apply `java-library`, `checkstyle`,
and `maven-publish`. A comment, a different plugin ID, a declaration outside
the leading `plugins` block, or `apply false` does not qualify. This remains a
repository-shape check. The consumer-owned `settings.gradle` preflight and the
Gradle build verify the exact plugin source and its effective behavior.

## Consumer loading

The consumer keeps the toolkit at `tooling/bluemap-addon-toolkit`. The
complete preflight belongs directly in the consumer. Replace the all-zero
value with the reviewed toolkit commit. Do not make the path configurable or
fetch/update the submodule from Gradle.

```groovy
pluginManagement {
    def toolkitPath = 'tooling/bluemap-addon-toolkit'
    def expectedToolkitCommit = '0000000000000000000000000000000000000000'
    def consumerRoot = settings.settingsDir
    def toolkit = new File(consumerRoot, toolkitPath)

    if (!(expectedToolkitCommit ==~ /[0-9a-f]{40}/)
            || !new File(consumerRoot, '.git').exists()
            || !toolkit.isDirectory()
            || !new File(toolkit, '.git').exists()) {
        throw new GradleException(
                'Toolkit trust preflight is not configured or initialized. '
                        + "Run: git submodule update --init --recursive -- ${toolkitPath}"
        )
    }

    def gitOutput = { File repository, List<String> arguments, String operation ->
        def execution = settings.providers.exec {
            commandLine(['git', '-C', repository.absolutePath] + arguments)
            ignoreExitValue = true
            environment 'LC_ALL', 'C'
            environment 'GIT_OPTIONAL_LOCKS', '0'
        }
        def result = execution.result.get()
        def output = execution.standardOutput.asText.get().trim()
        def error = execution.standardError.asText.get().trim()
        if (result.exitValue != 0) {
            throw new GradleException(
                    "Unable to ${operation}: ${error ?: 'Git returned no diagnostic.'}"
            )
        }
        output
    }

    if (!gitOutput(consumerRoot, ['rev-parse', '--show-prefix'],
            'verify the consumer root').isEmpty()) {
        throw new GradleException('settings.gradle must be at the Git worktree root')
    }

    def tree = gitOutput(consumerRoot, ['ls-tree', 'HEAD', '--', toolkitPath],
            'read the committed toolkit gitlink').tokenize(' \t')
    def index = gitOutput(consumerRoot, ['ls-files', '--stage', '--', toolkitPath],
            'read the indexed toolkit gitlink').tokenize(' \t')
    if (tree.size() != 4 || tree[0] != '160000' || tree[1] != 'commit'
            || tree[2] != expectedToolkitCommit || tree[3] != toolkitPath
            || index.size() != 4 || index[0] != '160000'
            || index[1] != expectedToolkitCommit || index[2] != '0'
            || index[3] != toolkitPath) {
        throw new GradleException('Committed/indexed toolkit gitlink does not match its pin')
    }

    def toolkitHead = gitOutput(toolkit, ['rev-parse', '--verify', 'HEAD^{commit}'],
            'read toolkit HEAD')
    def toolkitStatus = gitOutput(toolkit,
            ['status', '--porcelain=v1', '--untracked-files=all',
             '--ignore-submodules=none'], 'verify the toolkit worktree')
    if (toolkitHead != expectedToolkitCommit || !toolkitStatus.isEmpty()) {
        throw new GradleException('Toolkit HEAD differs from the gitlink or is dirty')
    }

    def gradleBuild = new File(toolkit, 'gradle')
    if (!new File(gradleBuild, 'settings.gradle').isFile()) {
        throw new GradleException('Pinned toolkit has no Gradle convention build')
    }
    includeBuild(gradleBuild)

    repositories {
        gradlePluginPortal()
        mavenCentral()
    }
}
```

This check is the trust boundary and must not be moved into the plugin that it
authorizes. CI checks out the consumer with `submodules: recursive` and
`persist-credentials: false`; an ordinary clone uses `--recurse-submodules`.

## Validation

The fixture gate builds the plugin twice, compares its binary and sources JARs
byte for byte, runs `validatePlugins`, and audits an exact JAR allowlist. It
also runs Java, JUnit and Checkstyle in a publishing fixture, checks for
repository/dependency/publication/POM/JAR leakage, compares the fixture JARs,
POM and module metadata across two builds, and exercises a consumer without
core plugins. Run it separately with exact Gradle 9.4.0 and 9.6.1 executables:

```bash
python tools/verify_gradle_conventions.py --gradle /path/to/gradle-9.4.0/bin/gradle
python tools/verify_gradle_conventions.py --gradle /path/to/gradle-9.6.1/bin/gradle
```

A wrapper is deliberately absent. One wrapper can select only one Gradle
distribution, while the current consumer portfolio has accepted build paths
on both versions. CI selects each exact distribution independently.
