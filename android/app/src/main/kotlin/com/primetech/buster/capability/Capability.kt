package com.primetech.buster.capability

/**
 * The capability vocabulary for the Buster APK principal.
 *
 * Least privilege is enforced structurally, not by convention:
 *
 *  * The APK's INITIAL baseline is the six read/present operations. It does
 *    NOT automatically inherit PTT's `service-start` / `service-restart` /
 *    `service-status`, because a concrete Buster workflow has not yet been
 *    shown to need them.
 *  * There is no broad `BUSTER_READ` or `BUSTER_WRITE` capability. Possessing
 *    one of those would mean arbitrary read/write, which is exactly the shape
 *    this model exists to prevent. Authorization resolves to a TYPED OPERATION
 *    plus a BOUNDED TARGET, never to a permission that implies scope.
 *  * No capability anywhere grants execution: there is no `execute`, `shell`,
 *    `run(argv)`, arbitrary-path, generic-filesystem or generic-root entry.
 */
enum class Capability {
    // --- Initial baseline: status, health, ping, services, capabilities, present.
    BUSTER_STATUS,
    BUSTER_SERVICES_READ,
    BUSTER_CAPABILITIES_READ,
    BUSTER_PRESENT,

    // --- Reserved, NOT granted to the APK. Justified separately.
    BUSTER_SERVICES_CONTROL,

    // --- Phase 5B.1: the two read-only operations, granted to this principal.
    BUSTER_DEPLOYMENT_READ,
    BUSTER_READ,

    // --- Still reserved: nothing mutating is authorized.
    BUSTER_RUNTIME_CONTROL,
    BUSTER_SCOPED_WRITE,
    BUSTER_IMPORT,
    BUSTER_EXPORT,
    BUSTER_JOBS_READ,
}

/**
 * A typed operation, resolved against a capability.
 *
 * Every operation is argument-bounded by construction. None accepts a caller
 * supplied path, argv, environment, working directory, URL, package,
 * component or Intent.
 */
enum class Operation(
    val capability: Capability,
    /** Whether this operation may be performed without a prior user action. */
    val requiresUserConsent: Boolean = false,
) {
    // ---- Initial baseline (nine-operation bridge, the six granted) ----
    STATUS(Capability.BUSTER_STATUS),
    HEALTH(Capability.BUSTER_STATUS),
    PING(Capability.BUSTER_STATUS),
    SERVICES(Capability.BUSTER_SERVICES_READ),
    CAPABILITIES(Capability.BUSTER_CAPABILITIES_READ),

    /**
     * Zero-argument by design. The host constructs the Android action; the
     * caller names no URL, package, component or Intent.
     */
    PRESENT(Capability.BUSTER_PRESENT),

    // ---- Reserved: PTT retains these today; Buster does NOT get them yet ----
    SERVICE_START(Capability.BUSTER_SERVICES_CONTROL),
    SERVICE_RESTART(Capability.BUSTER_SERVICES_CONTROL),
    SERVICE_STATUS(Capability.BUSTER_SERVICES_CONTROL),

    // ---- Phase 5B.1: the two read-only operations ----
    DEPLOYMENT(Capability.BUSTER_DEPLOYMENT_READ),
    READ(Capability.BUSTER_READ),

    // ---- Still reserved: no implementation, no authorization ----
    RUNTIME_CONTROL(Capability.BUSTER_RUNTIME_CONTROL, requiresUserConsent = true),
    WRITE(Capability.BUSTER_SCOPED_WRITE, requiresUserConsent = true),
    IMPORT(Capability.BUSTER_IMPORT, requiresUserConsent = true),
    EXPORT(Capability.BUSTER_EXPORT, requiresUserConsent = true),
    ;

    val guestVerb: String get() = name.lowercase().replace('_', '-')
}

/**
 * The capabilities this principal is authorized for in Phase 4.
 *
 * The six baseline operations. The service-control trio and every reserved
 * capability are absent, and [isAuthorized] will refuse them. PTT is unaffected
 * and keeps all nine.
 */
object BusterBaseline {

    val AUTHORIZED: Set<Capability> = setOf(
        Capability.BUSTER_STATUS,
        Capability.BUSTER_SERVICES_READ,
        Capability.BUSTER_CAPABILITIES_READ,
        Capability.BUSTER_PRESENT,
        // Granted in 5B.1: read-only, and nothing beyond it.
        Capability.BUSTER_DEPLOYMENT_READ,
        Capability.BUSTER_READ,
    )

    /** Capabilities that still have no implementation. */
    val RESERVED_CAPABILITIES: Set<Capability> =
        setOf(
            Capability.BUSTER_RUNTIME_CONTROL,
            Capability.BUSTER_SCOPED_WRITE,
            Capability.BUSTER_IMPORT,
            Capability.BUSTER_EXPORT,
            Capability.BUSTER_JOBS_READ,
        )

    /**
     * Operations deliberately withheld from the APK until a concrete workflow
     * justifies them. Exposed so the UI and tests can state the reason rather
     * than silently omitting them.
     */
    val RESERVED_PENDING_JUSTIFICATION: Set<Operation> = setOf(
        Operation.SERVICE_START,
        Operation.SERVICE_RESTART,
        Operation.SERVICE_STATUS,
    )

    /** Operations whose TerminalP implementation does not exist yet. */
    val RESERVED_PENDING_IMPLEMENTATION: Set<Operation> = setOf(
        Operation.RUNTIME_CONTROL,
        Operation.WRITE,
        Operation.IMPORT,
        Operation.EXPORT,
    )
}

/** The closed set of things a scoped read may name. Never a path. */
enum class ReadView {
    GOALS, MEMORY, ATTENTION, ACTIVITY, DEVICE, SETTINGS, JOBS,
}

/** The closed set of logical things a scoped write may name. Never a path. */
enum class WriteTarget {
    PREFERENCES, MEMORY_NOTE, GOAL, FILE_WITHIN_PERSISTENT_ROOT,
}

/**
 * A typed request. There is deliberately no free-form argument bag, and no way
 * to express a path, argv, environment or Intent.
 */
sealed interface OperationRequest {

    /** The argument-free operations. */
    data object None : OperationRequest

    /** `read(view)` — a closed enum, never a path. */
    data class Read(val view: ReadView) : OperationRequest

    /** `write(target, …)` — a closed enum target plus bounded payload. */
    data class Write(
        val target: WriteTarget,
        val payload: String,
    ) : OperationRequest {
        init {
            require(payload.length <= MAX_PAYLOAD) {
                "write payload exceeds the bounded limit"
            }
        }
    }

    /** One-shot token minted by user-mediated document selection. Never a path. */
    data class Transfer(val tokenId: String) : OperationRequest {
        init {
            require(tokenId.isNotBlank() && tokenId.length <= MAX_TOKEN) {
                "transfer token must be a short opaque identifier"
            }
        }
    }

    companion object {
        const val MAX_PAYLOAD: Int = 64 * 1024
        const val MAX_TOKEN: Int = 128
    }
}
