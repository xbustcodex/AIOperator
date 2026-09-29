package com.primetech.buster

import com.primetech.buster.identity.BusterIdentity
import com.primetech.buster.identity.PrincipalKind
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The Buster APK is its own Android application and security principal.
 *
 * TerminalP authenticates a caller as (UID -> package -> pinned certificate).
 * These tests pin the identity facts that model depends on.
 */
class IdentityTest {

    @Test
    fun `buster package identity is distinct`() {
        assertEquals("com.primetech.buster", BusterIdentity.PACKAGE_NAME)
        assertNotEquals(BusterIdentity.PACKAGE_NAME, BusterIdentity.PRIME_TECH_TERMINAL_PACKAGE)
        assertNotEquals(BusterIdentity.PACKAGE_NAME, BusterIdentity.TERMINALP_PACKAGE)
    }

    @Test
    fun `debug build is a separate android identity`() {
        // The `.debug` suffix makes it a different package entirely, so a debug
        // build cannot be mistaken for the release application.
        assertNotEquals(BusterIdentity.PACKAGE_NAME, BusterIdentity.DEBUG_PACKAGE_NAME)
        assertTrue(BusterIdentity.isBusterPackage(BusterIdentity.DEBUG_PACKAGE_NAME))
    }

    @Test
    fun `ptt identity cannot masquerade as buster`() {
        assertFalse(BusterIdentity.isBusterPackage(BusterIdentity.PRIME_TECH_TERMINAL_PACKAGE))
        assertFalse(BusterIdentity.isBusterPackage(BusterIdentity.TERMINALP_PACKAGE))
        assertTrue(BusterIdentity.isOtherPrimeTechPrincipal(BusterIdentity.PRIME_TECH_TERMINAL_PACKAGE))
        assertEquals(PrincipalKind.PRIME_TECH_TERMINAL,
            BusterIdentity.kindOf(BusterIdentity.PRIME_TECH_TERMINAL_PACKAGE))
    }

    @Test
    fun `unknown package resolves to no principal`() {
        assertNull(BusterIdentity.kindOf("com.example.evil"))
        assertFalse(BusterIdentity.isBusterPackage(null))
        assertFalse(BusterIdentity.isOtherPrimeTechPrincipal(null))
    }

    @Test
    fun `signing flavors stay distinguishable`() {
        assertTrue(BusterIdentity.isDebugIdentity(BusterIdentity.SigningFlavor.DEBUG))
        assertFalse(BusterIdentity.isDebugIdentity(BusterIdentity.SigningFlavor.RELEASE))
    }
}
