package com.primetech.buster.diagnostics

import com.primetech.buster.bridge.BridgeResult
import com.primetech.buster.capability.Operation
import com.primetech.buster.capability.OperationRequest

/**
 * A user-facing diagnostics row.
 *
 * Backed by real state only. There is deliberately no constructor that takes
 * free text, because a fabricated "OK" is the failure mode this surface must
 * not have.
 */
sealed interface DiagnosticItem {

    data class Row(val label: String, val value: String, val ok: Boolean) : DiagnosticItem

    /** An operation was attempted and did not succeed. */
    data class Failure(val operation: Operation, val reason: String) : DiagnosticItem
}

/**
 * The diagnostics surface contract.
 *
 * Reports what was actually observed. It never synthesises a healthy row for
 * something that was not queried, and it never reports an operation as
 * succeeded when the bridge refused it.
 */
interface DiagnosticsContract {

    /** Renders a bridge outcome truthfully. */
    fun <T> describe(operation: Operation, result: BridgeResult<T>): DiagnosticItem =
        when (result) {
            is BridgeResult.Ok -> DiagnosticItem.Row(
                operation.guestVerb, "ok", true,
            )
            is BridgeResult.Failed -> DiagnosticItem.Failure(
                operation, result.failure::class.simpleName ?: "failed",
            )
        }

    /** Operations this surface may probe, all argument-free baseline reads. */
    fun probeOperations(): List<Operation> = listOf(
        Operation.PING, Operation.HEALTH, Operation.STATUS,
        Operation.SERVICES, Operation.CAPABILITIES,
    )

    /** A probe always uses the argument-free request form. */
    fun probeRequest(): OperationRequest = OperationRequest.None
}

object BusterDiagnosticsContract : DiagnosticsContract
