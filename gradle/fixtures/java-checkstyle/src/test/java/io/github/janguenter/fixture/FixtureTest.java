// SPDX-License-Identifier: MIT
package io.github.janguenter.fixture;

import static org.junit.jupiter.api.Assertions.assertNotNull;

import org.junit.jupiter.api.Test;

/** Confirms that the convention selects JUnit Platform for a real test. */
final class FixtureTest {
    @Test
    void executesOnJUnitPlatform() {
        assertNotNull(Fixture.class);
    }
}
