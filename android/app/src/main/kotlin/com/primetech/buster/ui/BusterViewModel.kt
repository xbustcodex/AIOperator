package com.primetech.buster.ui

import androidx.lifecycle.ViewModel
import com.primetech.buster.BusterApplication
import com.primetech.buster.bridge.BridgeResult
import com.primetech.buster.capability.BusterBaseline
import com.primetech.buster.capability.Operation
import com.primetech.buster.capability.OperationRequest
import com.primetech.buster.diagnostics.DiagnosticItem
import com.primetech.buster.state.ApkState
import com.primetech.buster.state.BusterUiState
import com.primetech.buster.state.IntegrationState
import com.primetech.buster.state.RuntimeState
import com.primetech.buster.transfer.TransferDirection
import com.primetech.buster.transfer.TransferState

/**
 * Presentation logic.
 *
 * Two rules hold throughout:
 *
 *  1. An action is only enabled when a real bounded implementation exists
 *     behind it. Start/Restart and Import/Export stay disabled because their
 *     TerminalP operations do not exist yet.
 *  2. No action may report success it did not observe. A refused bridge call
 *     surfaces the refusal.
 */
class BusterViewModel(private val app: BusterApplication) : ViewModel() {

    var state: BusterUiState = app.initialState()
        private set

    var diagnostics: List<DiagnosticItem> = emptyList()
        private set

    var lastTransfer: TransferState = TransferState.Idle
        private set

    /** `present` is a baseline capability, so the action exists. */
    val canOpenBuster: Boolean
        get() = Operation.PRESENT.capability in app.bridge.authorizedCapabilities()

    val canRunDiagnostics: Boolean
        get() = Operation.PING.capability in app.bridge.authorizedCapabilities()

    /**
     * Runtime control is represented but NOT available: the TerminalP
     * operation does not exist. It must not look actionable.
     */
    val canStartOrRestart: Boolean = false

    /**
     * Import/export surfaces exist, but cannot move data until the privileged
     * operations exist. They open user-mediated selection only.
     */
    val canTransfer: Boolean = false

    fun refresh() {
        state = app.initialState().copy(
            integration = app.bridge.integrationState(),
        )
    }

    fun openBuster(): BridgeResult<*> = runOperation(Operation.PRESENT)

    fun runDiagnostics() {
        diagnostics = app.diagnostics.probeOperations().map { op ->
            app.diagnostics.describe(op, app.bridge.perform(op, app.diagnostics.probeRequest()))
        }
    }

    /** Opens the system picker. No document is selected by this call. */
    fun beginUserMediatedSelection(direction: TransferDirection) {
        lastTransfer = TransferState.AwaitingUserSelection
    }

    /**
     * Called once a user-selected document has been converted into a token.
     * The token is opaque and names no location.
     */
    fun onDocumentSelected(tokenId: String, displayName: String, byteSize: Long) {
        lastTransfer = TransferState.Selected(tokenId, displayName, byteSize)
    }

    fun onTransferRefused(reason: String) {
        lastTransfer = TransferState.Refused(reason)
    }

    fun resetTransfer() {
        lastTransfer = TransferState.Idle
    }

    private fun runOperation(op: Operation): BridgeResult<*> =
        app.bridge.perform(op, OperationRequest.None)

    /** The honest summary of what is and is not authorized today. */
    fun authorizationSummary(): String =
        "Baseline capabilities: " +
            BusterBaseline.AUTHORIZED.joinToString(", ") { it.name } +
            ". Withheld pending justification: " +
            BusterBaseline.RESERVED_PENDING_JUSTIFICATION.joinToString(", ") { it.name } +
            "."
}
