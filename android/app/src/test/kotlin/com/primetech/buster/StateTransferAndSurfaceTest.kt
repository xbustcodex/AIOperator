package com.primetech.buster

import com.primetech.buster.bridge.BridgeResult
import com.primetech.buster.bridge.FailClosedBridgeClient
import com.primetech.buster.capability.BusterBaseline
import com.primetech.buster.capability.Capability
import com.primetech.buster.capability.Operation
import com.primetech.buster.diagnostics.BusterDiagnosticsContract
import com.primetech.buster.diagnostics.DiagnosticItem
import com.primetech.buster.state.ApkState
import com.primetech.buster.state.BusterUiState
import com.primetech.buster.state.IntegrationState
import com.primetech.buster.state.RuntimeState
import com.primetech.buster.transfer.DocumentTransferContract
import com.primetech.buster.transfer.TransferState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * State models, user-mediated transfer, diagnostics, and the absences that
 * must hold: no second runtime path, no retired node API, no generic execution.
 */
class StateTransferAndSurfaceTest {

    @Test
    fun `state models distinguish apk runtime and integration`() {
        val state = BusterUiState(
            apk = ApkState.INSTALLED,
            runtime = RuntimeState.RUNNING,
            integration = IntegrationState.PARTIALLY_AUTHORIZED,
        )
        // The three axes are independent: any combination is representable.
        assertEquals(ApkState.INSTALLED, state.apk)
        assertEquals(RuntimeState.RUNNING, state.runtime)
        assertEquals(IntegrationState.PARTIALLY_AUTHORIZED, state.integration)
        // And they are not collapsed: not fully operational.
        assertFalse(state.fullyOperational)
    }

    @Test
    fun `fully operational requires all three axes`() {
        assertTrue(
            BusterUiState(
                apk = ApkState.INSTALLED,
                runtime = RuntimeState.RUNNING,
                integration = IntegrationState.AUTHORIZED,
            ).fullyOperational
        )
        assertFalse(
            BusterUiState(
                apk = ApkState.INSTALLED,
                runtime = RuntimeState.RUNNING,
                integration = IntegrationState.UNAUTHENTICATED,
            ).fullyOperational
        )
    }

    @Test
    fun `runtime version is withheld when nothing is deployed`() {
        val notDeployed = BusterUiState(runtime = RuntimeState.NOT_DEPLOYED, runtimeVersion = "0.4.3")
        assertNull(notDeployed.deployedRuntimeVersion)
    }

    @Test
    fun `import and export require user-mediated state`() {
        val contract = DocumentTransferContract
        // Nothing has been selected yet.
        assertFalse(contract.isReadyForTransfer(TransferState.Idle))
        assertFalse(contract.isReadyForTransfer(TransferState.AwaitingUserSelection))
        // No Phase-4 state can claim data actually moved.
        assertFalse(contract.hasTransferred(TransferState.Selected("tok", "a.txt", 10)))
        assertFalse(contract.hasTransferred(TransferState.Idle))
    }

    @Test
    fun `transfer describes truthfully without claiming success`() {
        val contract = DocumentTransferContract
        assertEquals("No document selected", contract.describe(TransferState.Idle))
        val notImpl = TransferState.NotImplemented(com.primetech.buster.transfer.TransferDirection.IMPORT)
        assertTrue(contract.describe(notImpl).contains("not available yet"))
    }

    @Test
    fun `diagnostics never fabricate a healthy row`() {
        val client = FailClosedBridgeClient(IntegrationState.UNAUTHENTICATED)
        val result = client.perform(Operation.PING)
        val item = BusterDiagnosticsContract.describe(Operation.PING, result)
        assertTrue("unauthenticated ping must not report ok", item is DiagnosticItem.Failure)
    }

    @Test
    fun `diagnostics probes only argument free baseline operations`() {
        val probes = BusterDiagnosticsContract.probeOperations()
        assertTrue(probes.all { it.guestVerb in setOf("ping", "health", "status", "services", "capabilities") })
        assertTrue(probes.none { it.requiresUserConsent })
    }

    // ---- Absences that must hold ----

    @Test
    fun `no second buster runtime path exists in this application`() {
        // This APK holds no kernel, scheduler, agent or capability execution of
        // its own: the only route to Buster is a typed, bounded bridge call.
        val client = FailClosedBridgeClient(IntegrationState.AUTHORIZED, BusterBaseline.AUTHORIZED)
        for (op in Operation.entries) {
            val result = client.perform(op)
            assertTrue(
                "operation ${op.name} must not execute without a real TerminalP implementation",
                result is BridgeResult.Failed,
            )
        }
    }

    @Test
    fun `no retired node api vocabulary exists`() {
        val names = ArrayList<String>()
        for (entry in Capability.entries) names.add(entry.name)
        for (entry in Operation.entries) names.add(entry.name)
        for (retired in listOf("NODE_API", "BUSTER_NODE", "AGENT_STATUS", "RUNIT")) {
            assertTrue(
                "retired vocabulary $retired must not reappear",
                !names.any { candidate -> candidate.contains(retired) },
            )
        }
    }

    @Test
    fun `no generic execution interface exists`() {
        val names = Operation.entries.map { it.name }
        for (forbidden in listOf("EXECUTE", "SHELL", "RUN_ARGV", "FS", "ROOT", "AM_START")) {
            assertTrue(
                "operation vocabulary must not contain $forbidden",
                names.none { it.contains(forbidden) },
            )
        }
    }
}
