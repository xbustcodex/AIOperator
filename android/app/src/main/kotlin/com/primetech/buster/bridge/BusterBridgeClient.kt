package com.primetech.buster.bridge

import com.primetech.buster.capability.Capability
import com.primetech.buster.capability.Operation
import com.primetech.buster.capability.BusterBaseline
import com.primetech.buster.capability.OperationRequest
import com.primetech.terminal.buster.BusterResult
import com.primetech.terminal.buster.IBusterBridge
import com.primetech.terminal.buster.IBusterBridgeCallback
import com.primetech.buster.state.IntegrationState

/** Why a bridge call could not be completed. Never a silent success. */
sealed interface BridgeFailure {
    /** TerminalP is absent, or its bridge service did not bind. */
    object BridgeUnavailable : BridgeFailure

    /** Reachable, but this caller is not recognized. */
    object Unauthenticated : BridgeFailure

    /** Recognized, but lacks the capability this operation requires. */
    data class CapabilityMissing(val capability: Capability) : BridgeFailure

    /** The operation exists in the model but is not implemented yet. */
    data class NotImplemented(val operation: Operation) : BridgeFailure

    /** The operation needs a user action that has not happened. */
    data class ConsentRequired(val operation: Operation) : BridgeFailure

    /**
     * The authenticated bridge worked, but the deployed Buster runtime is older
     * than this contract and has no such verb.
     *
     * <p>Distinct from [Unauthenticated] and [BridgeUnavailable]: the caller IS
     * recognized; the RUNTIME is simply behind. A surface must report this as
     * "unsupported" — never as broken, empty, success, or unauthorized.</p>
     */
    data class UnsupportedRuntime(val operation: Operation) : BridgeFailure

    /** The structured result exceeded the declared bound; failed closed. */
    data object ResultTooLarge : BridgeFailure

    /** The structured result could not be parsed; failed closed. */
    data object Malformed : BridgeFailure

    /** Arguments failed validation. */
    data class InvalidArguments(val detail: String) : BridgeFailure

    /** The host refused, or the operation failed. */
    data class HostRefused(val status: String) : BridgeFailure
}

/** The outcome of one bridge call. */
sealed interface BridgeResult<out T> {
    data class Ok<T>(val value: T) : BridgeResult<T>
    data class Failed(val failure: BridgeFailure) : BridgeResult<Nothing>
}

/** A typed, bounded result document. */
data class OperationResult(
    val operation: Operation,
    val correlationId: String,
    val document: Map<String, String> = emptyMap(),
) {
    companion object {
        /** Bound applied to any document this client accepts. */
        const val MAX_DOCUMENT_BYTES: Int = 256 * 1024

        /**
         * Parses a guest document. A response beyond the bound, or that is not
         * valid UTF-8 JSON, fails closed with a typed condition rather than
         * being truncated into a misleading partial result.
         */
        fun fromDocument(
            operationId: String,
            correlationId: String,
            json: String,
        ): OperationResult {
            if (json.toByteArray(Charsets.UTF_8).size > MAX_DOCUMENT_BYTES) {
                throw ResultTooLargeException()
            }
            val operation = Operation.entries.firstOrNull { it.guestVerb == operationId }
                ?: throw MalformedResultException("unknown operation in document")
            val fields = LinkedHashMap<String, String>()
            val obj = org.json.JSONObject(json)
            for (key in obj.keys()) {
                val value = obj.get(key)
                if (value != null && value !== org.json.JSONObject.NULL) fields[key] = value.toString()
            }
            return OperationResult(operation, correlationId, fields)
        }
    }
}

class ResultTooLargeException : RuntimeException("RESULT_TOO_LARGE")
class MalformedResultException(message: String) : RuntimeException(message)

/**
 * The typed client surface for the authenticated TerminalP bridge.
 *
 * This is an INTERFACE ONLY in Phase 4. No privileged operation is wired to
 * TerminalP yet: recognising `com.primetech.buster` as a principal is a
 * TerminalP security-boundary change and belongs to Phase 5, after review.
 *
 * The contract that must hold for every implementation:
 *
 *  * authorization resolves to a typed operation AND a bounded target;
 *  * a missing capability fails closed — never a weaker substitute;
 *  * nothing can express a path, argv, environment, cwd, URL, package,
 *    component or Intent.
 */
interface BusterBridgeClient {

    /** The bridge state as this client currently observes it. */
    fun integrationState(): IntegrationState

    /** Capabilities this principal currently holds. */
    fun authorizedCapabilities(): Set<Capability>

    /**
     * Performs one typed operation.
     *
     * Implementations must refuse anything they cannot authorize; they must
     * never widen scope to make a call succeed.
     */
    fun perform(operation: Operation, request: OperationRequest = OperationRequest.None): BridgeResult<OperationResult>
}

/**
 * The Phase-4 client: fails closed for everything.
 *
 * The six baseline operations are modelled but not yet executable, because
 * TerminalP does not yet recognize this principal. Returning
 * [IntegrationState.UNAUTHENTICATED] is the truthful answer, and every call
 * fails rather than pretending.
 *
 * This class is deliberately incapable of executing anything.
 */
class FailClosedBridgeClient(
    private val state: IntegrationState = IntegrationState.UNAUTHENTICATED,
    private val capabilities: Set<Capability> = emptySet(),
) : BusterBridgeClient {

    override fun integrationState(): IntegrationState = state

    override fun authorizedCapabilities(): Set<Capability> = capabilities

    override fun perform(
        operation: Operation,
        request: OperationRequest,
    ): BridgeResult<OperationResult> = BridgeResult.Failed(
        when {
            state == IntegrationState.UNAVAILABLE -> BridgeFailure.BridgeUnavailable
            state == IntegrationState.UNAUTHENTICATED -> BridgeFailure.Unauthenticated
            state == IntegrationState.REVOKED -> BridgeFailure.CapabilityMissing(operation.capability)
            operation.capability !in capabilities -> BridgeFailure.CapabilityMissing(operation.capability)
            // Authorized, but the TerminalP operation is not implemented yet.
            else -> BridgeFailure.NotImplemented(operation)
        }
    )
}

/**
 * The real authenticated client for the read-only operations.
 *
 * TerminalP authorizes per principal and per capability; this class never
 * widens scope, and every failure is reported rather than absorbed. The
 * interface is bound through TerminalP's exported bridge service, so this
 * package becomes a distinct, TerminalP-pinned security principal.
 */
class TerminalPBridgeClient(
    private val binder: IBusterBridge,
) : BusterBridgeClient {

    override fun integrationState(): IntegrationState = when {
        capabilities.isEmpty() -> IntegrationState.UNAUTHENTICATED
        // Fully authorized only when the whole baseline this surface needs
        // is present; a partial grant is reported as partial, never as ready.
        capabilities.containsAll(BusterBaseline.AUTHORIZED) -> IntegrationState.AUTHORIZED
        else -> IntegrationState.PARTIALLY_AUTHORIZED
    }

    override fun authorizedCapabilities(): Set<Capability> = capabilities

    /** The baseline plus the two read-only operations authorized in 5B.1. */
    var capabilities: Set<Capability> = emptySet()
        private set

    private val pending = HashMap<String, (BridgeResult<OperationResult>) -> Unit>()
    private val lock = Any()

    private val callback = object : IBusterBridgeCallback.Stub() {
        override fun onResult(result: BusterResult?) {
            val doc = result ?: return
            val handler = synchronized(lock) { pending.remove(doc.correlationId) } ?: return
            handler(
                if (doc.statusCode == 0 && doc.output != null) {
                    BridgeResult.Ok(OperationResult.fromDocument(doc.operationId, doc.correlationId, doc.output))
                } else {
                    BridgeResult.Failed(mapStatus(doc.statusCode, doc.message, currentOperation(doc.operationId)))
                }
            )
        }
    }

    /** Records the capabilities TerminalP has authorized for this principal. */
    fun setCapabilities(granted: Set<Capability>) {
        capabilities = granted
    }

    override fun perform(
        operation: Operation,
        request: OperationRequest,
    ): BridgeResult<OperationResult> {
        if (operation.capability !in capabilities) {
            return BridgeResult.Failed(BridgeFailure.CapabilityMissing(operation.capability))
        }
        return when (operation) {
            Operation.DEPLOYMENT -> call("busterDeployment")
            Operation.READ -> {
                val view = (request as? OperationRequest.Read)?.view
                    ?: return BridgeResult.Failed(
                        BridgeFailure.InvalidArguments("read requires a closed view"))
                call("busterRead", view.name.lowercase())
            }
            else -> BridgeResult.Failed(BridgeFailure.NotImplemented(operation))
        }
    }

    private fun call(method: String, argument: String? = null): BridgeResult<OperationResult> {
        val correlationId = java.util.UUID.randomUUID().toString()
        val latch = java.util.concurrent.CountDownLatch(1)
        var slot: BridgeResult<OperationResult>? = null
        synchronized(lock) { pending[correlationId] = { r -> slot = r; latch.countDown() } }
        try {
            when (method) {
                "busterDeployment" -> binder.busterDeployment(correlationId, callback)
                "busterRead" -> binder.busterRead(correlationId, argument!!, callback)
                else -> return BridgeResult.Failed(BridgeFailure.InvalidArguments("unknown call"))
            }
        } catch (e: android.os.RemoteException) {
            synchronized(lock) { pending.remove(correlationId) }
            return BridgeResult.Failed(BridgeFailure.BridgeUnavailable)
        }
        // An explicit deadline: a runtime that never answers must not hold
        // this call indefinitely.
        if (!latch.await(DEADLINE_SECONDS, java.util.concurrent.TimeUnit.SECONDS)) {
            synchronized(lock) { pending.remove(correlationId) }
            return BridgeResult.Failed(BridgeFailure.HostRefused("TIMEOUT"))
        }
        @Suppress("UNCHECKED_CAST")
        return slot ?: BridgeResult.Failed(BridgeFailure.HostRefused("NO_RESULT"))
    }

    private fun currentOperation(operationId: String): Operation =
        Operation.entries.firstOrNull { it.guestVerb == operationId } ?: Operation.DEPLOYMENT

    private fun mapStatus(
        status: Int,
        message: String?,
        operation: Operation,
    ): BridgeFailure = when {
        status == 2 -> BridgeFailure.Unauthenticated
        status == 9 -> BridgeFailure.ConsentRequired(operation)
        status == 12 -> BridgeFailure.CapabilityMissing(operation.capability)
        status == 13 -> BridgeFailure.ResultTooLarge
        status == 14 -> BridgeFailure.Malformed
        // A guest that does not know the verb answers with a usage refusal.
        // The caller is authorized; the RUNTIME is behind. That is a version
        // difference, not an authorization failure.
        status == 1 && message.orEmpty().contains("supports only") ->
            BridgeFailure.UnsupportedRuntime(operation)
        else -> BridgeFailure.HostRefused(message ?: "status=$status")
    }

    companion object {
        const val DEADLINE_SECONDS: Long = 20
    }
}
