package com.primetech.buster.identity

/**
 * Which security principal this application is.
 *
 * Buster is deliberately NOT Prime Tech Terminal. TerminalP authenticates a
 * caller by resolving its Binder UID to a package name and then to a pinned
 * signing-certificate digest. If the two apps shared a key, the package name
 * would be the only thing separating them, so a mistake on either side would
 * silently grant the wrong product the wrong authority. Keeping the identities
 * distinct is what makes the capability model meaningful.
 */
enum class PrincipalKind {
    /** `com.primetech.buster` — this application. */
    BUSTER,

    /** `com.primetechterminal` — Prime Tech Terminal, a different principal. */
    PRIME_TECH_TERMINAL,

    /** `com.primetech.terminal` — TerminalP, the platform/security broker. */
    TERMINALP,
}

/**
 * This application's own identity, as TerminalP will see it.
 *
 * [packageName] is the applicationId of a release build. A debug build carries
 * the `.debug` suffix and is therefore a DIFFERENT Android identity that
 * TerminalP must pin separately; it must never inherit release authority.
 */
object BusterIdentity {

    const val PACKAGE_NAME: String = "com.primetech.buster"
    const val DEBUG_PACKAGE_NAME: String = "com.primetech.buster.debug"

    const val TERMINALP_PACKAGE: String = "com.primetech.terminal"
    const val PRIME_TECH_TERMINAL_PACKAGE: String = "com.primetechterminal"

    /** The signing identity this build carries. */
    enum class SigningFlavor { DEBUG, RELEASE }

    fun isBusterPackage(candidate: String?): Boolean =
        candidate == PACKAGE_NAME || candidate == DEBUG_PACKAGE_NAME

    /**
     * A package that must never be treated as this application.
     *
     * PTT in particular must not be able to act as Buster, and Buster must not
     * be able to act as PTT: their capability profiles are different, so
     * conflating them would grant one product the other's authority.
     */
    fun isOtherPrimeTechPrincipal(candidate: String?): Boolean =
        candidate == PRIME_TECH_TERMINAL_PACKAGE || candidate == TERMINALP_PACKAGE

    fun kindOf(candidate: String?): PrincipalKind? = when {
        isBusterPackage(candidate) -> PrincipalKind.BUSTER
        candidate == PRIME_TECH_TERMINAL_PACKAGE -> PrincipalKind.PRIME_TECH_TERMINAL
        candidate == TERMINALP_PACKAGE -> PrincipalKind.TERMINALP
        else -> null
    }

    /**
     * Which principal a signing flavor represents.
     *
     * Debug and release are separate Android identities with separate
     * certificates; TerminalP pins them separately so a debug build can never
     * be mistaken for, or promoted to, production authority.
     */
    fun principalOf(flavor: SigningFlavor): PrincipalKind = PrincipalKind.BUSTER

    fun isDebugIdentity(flavor: SigningFlavor): Boolean = flavor == SigningFlavor.DEBUG
}
