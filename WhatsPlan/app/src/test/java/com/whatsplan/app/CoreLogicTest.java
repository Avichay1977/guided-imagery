package com.whatsplan.app;

import org.junit.Test;

/**
 * Runs the existing standalone core tests (kept in the top-level core-tests
 * directory, in the default package) as part of the Gradle unit-test task.
 * Reflection is required because default-package classes cannot be referenced
 * from a named package.
 */
public final class CoreLogicTest {

    @Test public void parserScenarios() throws Exception {
        runMain("ParserTest");
    }

    @Test public void conversationIdentityScenarios() throws Exception {
        runMain("ConversationIdentityResolverTest");
    }

    private void runMain(String className) throws Exception {
        Class.forName(className)
                .getMethod("main", String[].class)
                .invoke(null, (Object) new String[0]);
    }
}
