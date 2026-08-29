// SPDX-License-Identifier: MIT
package io.github.janguenter.bluemap.addon.toolkit.gradle;

import java.util.List;
import org.gradle.api.Plugin;
import org.gradle.api.Project;
import org.gradle.api.plugins.JavaPluginExtension;
import org.gradle.api.plugins.quality.Checkstyle;
import org.gradle.api.plugins.quality.CheckstyleExtension;
import org.gradle.api.tasks.bundling.AbstractArchiveTask;
import org.gradle.api.tasks.compile.JavaCompile;
import org.gradle.api.tasks.testing.Test;
import org.gradle.jvm.toolchain.JavaLanguageVersion;

/** Applies only the build conventions common to independent BlueMap add-ons. */
public final class BlueMapAddonJavaConventionsPlugin implements Plugin<Project> {
    @Override
    public void apply(Project project) {
        project.getPluginManager().withPlugin("java", ignored -> {
            JavaPluginExtension java = project.getExtensions()
                    .getByType(JavaPluginExtension.class);
            java.getToolchain().getLanguageVersion().set(JavaLanguageVersion.of(21));
            java.withSourcesJar();
        });

        project.getTasks().withType(JavaCompile.class).configureEach(task -> {
            task.getOptions().setEncoding("UTF-8");
            task.getOptions().getRelease().set(21);
            addOnce(task.getOptions().getCompilerArgs(), "-Xlint:all");
            addOnce(task.getOptions().getCompilerArgs(), "-Werror");
        });

        project.getTasks().withType(AbstractArchiveTask.class).configureEach(task -> {
            task.setPreserveFileTimestamps(false);
            task.setReproducibleFileOrder(true);
        });

        project.getTasks().withType(Test.class).configureEach(Test::useJUnitPlatform);

        project.getPluginManager().withPlugin("checkstyle", ignored -> {
            CheckstyleExtension checkstyle = project.getExtensions()
                    .getByType(CheckstyleExtension.class);
            checkstyle.setToolVersion("10.18.2");
            checkstyle.setConfigFile(project.file("config/checkstyle/checkstyle.xml"));
            project.getTasks().withType(Checkstyle.class).configureEach(task -> {
                task.getReports().getXml().getRequired().set(true);
                task.getReports().getHtml().getRequired().set(true);
            });
        });
    }

    private static void addOnce(List<String> values, String value) {
        if (!values.contains(value)) {
            values.add(value);
        }
    }
}
