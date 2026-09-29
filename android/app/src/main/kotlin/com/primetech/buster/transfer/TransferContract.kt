package com.primetech.buster.transfer

/**
 * Import/export are USER-MEDIATED. The Android document picker is the only
 * place an external location ever exists.
 *
 * The APK never receives, and never forwards, a filesystem path. It performs
 * selection itself, then mints a one-shot token that names nothing but itself.
 * TerminalP will eventually own privileged transfer validation; Buster OS
 * remains the owner of the guest data. No raw path crosses any boundary.
 */
enum class TransferDirection { IMPORT, EXPORT }

/** What is happening, truthfully. No state implies data moved. */
sealed interface TransferState {

    /** Nothing selected. */
    data object Idle : TransferState

    /** The system picker is open; the user is choosing. */
    data object AwaitingUserSelection : TransferState

    /**
     * A document was selected and a token minted. No bytes have moved.
     * The bridge transfer operation does not exist yet, so this is as far as
     * Phase 4 can truthfully go.
     */
    data class Selected(val tokenId: String, val displayName: String, val byteSize: Long) : TransferState

    /** The token was presented and the host refused. */
    data class Refused(val reason: String) : TransferState

    /** The privileged operation is not implemented yet. */
    data class NotImplemented(val direction: TransferDirection) : TransferState
}

/**
 * The contract the UI is built against.
 *
 * Deliberately has no member that accepts a path, a URI or a destination: the
 * only way to produce a [TransferState.Selected] is a token minted from
 * user-mediated selection.
 */
interface TransferContract {

    /** True when the surface may claim a document is ready for transfer. */
    fun isReadyForTransfer(state: TransferState): Boolean =
        state is TransferState.Selected

    /**
     * True only when data actually moved.
     *
     * No Phase-4 state satisfies this, which is the point: the UI must not be
     * able to show a successful import or export before the privileged
     * operations exist.
     */
    fun hasTransferred(state: TransferState): Boolean = false

    /** Human-readable, truthful summary. */
    fun describe(state: TransferState): String = when (state) {
        is TransferState.Idle -> "No document selected"
        is TransferState.AwaitingUserSelection -> "Choose a document"
        is TransferState.Selected -> "Ready: ${state.displayName}"
        is TransferState.Refused -> "Refused: ${state.reason}"
        is TransferState.NotImplemented ->
            "${state.direction.name.lowercase()} is not available yet"
    }
}

object DocumentTransferContract : TransferContract
