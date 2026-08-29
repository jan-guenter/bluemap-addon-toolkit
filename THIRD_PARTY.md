# Third-party software

The toolkit has no third-party runtime Python dependencies. Release archives
are built with the MIT-licensed Setuptools version pinned in
`requirements/build.txt`.

The source-distributed convention plugin compiles against Gradle's
Apache-2.0-licensed public API supplied by the consumer's Gradle distribution.
No Gradle classes are bundled. Checkstyle is likewise resolved by Gradle in
the consumer build and is not bundled by the toolkit.

Consumer repositories remain responsible for their own dependencies,
licenses, provenance, and candidate-mod artifacts.
