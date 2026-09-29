package com.primetech.buster

import android.app.Application
import com.primetech.buster.bridge.BusterBridgeClient
import com.primetech.buster.bridge.FailClosedBridgeClient
import com.primetech.buster.capability.BusterBaseline
import com.primetech.buster.diagnostics.BusterDiagnosticsContract
import com.primetech.buster.diagnostics.DiagnosticsContract
import com.primetech.buster.identity.BusterIdentity
import com.primetech.buster.state.BusterUiState
import com.primetech.buster.transfer.DocumentTransferContract
import com.primetech.buster.transfer.TransferContract

/**
 * Application wiring.
 *
 * Phase 4 holds NO privileged capability: TerminalP does not yet recognize
 * `com.primetech.buster`, and teaching it to is a Phase 5 security-boundary
 * change. The bridge client therefore fails closed, and the UI renders that
 * truth rather than a placeholder success.
 */
class BusterApplication : Application() {

    val signingFlavor: BusterIdentity.SigningFlavor =
        if (BuildConfig.SIGNING_FLAVOR == "DEBUG") {
            BusterIdentity.SigningFlavor.DEBUG
        } else {
            BusterIdentity.SigningFlavor.RELEASE
        }

    val bridge: BusterBridgeClient = FailClosedBridgeClient()

    val transfer: TransferContract = DocumentTransferContract

    val diagnostics: DiagnosticsContract = BusterDiagnosticsContract

    /** Capabilities this principal is designed around; none are live yet. */
    val baselineCapabilities = BusterBaseline.AUTHORIZED

    fun initialState(): BusterUiState = BusterUiState(
        apk = com.primetech.buster.state.ApkState.INSTALLED,
        apkVersionName = BuildConfig.VERSION_NAME,
        apkVersionCode = BuildConfig.VERSION_CODE,
        signingFlavor = signingFlavor.name,
        runtime = com.primetech.buster.state.RuntimeState.NOT_DEPLOYED,
        runtimeVersion = null,
        integration = bridge.integrationState(),
        consentRequiredForTransfer = true,
    )
}
