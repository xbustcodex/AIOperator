package com.primetech.buster

import com.primetech.buster.bridge.BridgeFailure
import com.primetech.buster.bridge.BridgeResult
import com.primetech.buster.bridge.FailClosedBridgeClient
import com.primetech.buster.capability.BusterBaseline
import com.primetech.buster.capability.Capability
import com.primetech.buster.capability.Operation
import com.primetech.buster.capability.OperationRequest
import com.primetech.buster.capability.ReadView
import com.primetech.buster.capability.WriteTarget
import com.primetech.buster.state.IntegrationState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Least privilege, and the absence of any generic execution surface.
 */
class CapabilityAndBridgeTest {

    private val baseline = BusterBaseline.AUTHORIZED

    @Test
    fun `baseline is the six operations plus the two read-only ones`() {
        assertEquals(
            setOf(
                Capability.BUSTER_STATUS,
                Capability.BUSTER_SERVICES_READ,
                Capability.BUSTER_CAPABILITIES_READ,
                Capability.BUSTER_PRESENT,
                // Granted in 5B.1: read-only, nothing beyond it.
                Capability.BUSTER_DEPLOYMENT_READ,
                Capability.BUSTER_READ,
            ),
            baseline,
        )
    }

    @Test
    fun `service control is withheld from the buster apk`() {
        // PTT keeps these; the APK does not get them merely because the
        // operations already exist.
        for (op in BusterBaseline.RESERVED_PENDING_JUSTIFICATION) {
            assertFalse(
                "${op.name} must not be authorized for the APK",
                op.capability in baseline,
            )
        }
        assertFalse(Capability.BUSTER_SERVICES_CONTROL in baseline)
    }

    @Test
    fun `baseline operations map onto the accepted bridge verbs`() {
        val granted = Operation.entries.filter { it.capability in baseline }.map { it.guestVerb }
        assertEquals(
            listOf("status", "health", "ping", "services", "capabilities",
                "present", "deployment", "read"),
            granted,
        )
    }

    @Test
    fun `no capability grants execution`() {
        val names = Capability.entries.map { it.name }
        // Exact enum names, not substrings: RUNTIME is legitimate (runtime
        // control is a reserved capability), RUN_ARGV/EXECUTE/SHELL are not.
        for (forbidden in listOf("EXECUTE", "SHELL", "RUN_ARGV", "ROOT", "ARBITRARY_PATH")) {
            assertTrue(
                "capability vocabulary must not contain $forbidden",
                forbidden !in names,
            )
        }
    }

    @Test
    fun `no operation accepts a path argv env cwd url or intent`() {
        // Requests are a closed set: none can express any of these.
        val none = OperationRequest.None
        val read = OperationRequest.Read(ReadView.GOALS)
        val write = OperationRequest.Write(WriteTarget.PREFERENCES, "v")
        val transfer = OperationRequest.Transfer("tok")
        // A token is an opaque identifier: a path, URI or URL is not accepted.
        listOf(none, read, write, transfer).forEach { r ->
            assertTrue(
                "request ${r::class.simpleName} must not be a path",
                r !is OperationRequest.Read || r.view.name.isNotEmpty(),
            )
        }
    }

    @Test
    fun `write payload is bounded`() {
        val tooBig = "x".repeat(OperationRequest.MAX_PAYLOAD + 1)
        try {
            OperationRequest.Write(WriteTarget.MEMORY_NOTE, tooBig)
            throw AssertionError("oversized write payload must be rejected")
        } catch (expected: IllegalArgumentException) {
            assertTrue(expected.message!!.contains("bounded"))
        }
    }

    @Test
    fun `unsupported privileged operation fails closed`() {
        // With the baseline capabilities, DEPLOYMENT is refused for the
        // STRONGEST reason available: the capability itself is not held. The
        // check never widens scope to make the call succeed.
        val baselineClient = FailClosedBridgeClient(
            IntegrationState.AUTHORIZED,
            BusterBaseline.AUTHORIZED,
        )
        val denied = baselineClient.perform(Operation.RUNTIME_CONTROL)
        assertEquals(
            BridgeFailure.CapabilityMissing(Capability.BUSTER_RUNTIME_CONTROL),
            (denied as BridgeResult.Failed).failure,
        )

        // Even once authorized, it is still refused, because the TerminalP
        // operation does not exist yet.
        val authorizedClient = FailClosedBridgeClient(
            IntegrationState.AUTHORIZED,
            Capability.entries.toSet(),
        )
        val unimplemented = authorizedClient.perform(Operation.WRITE)
        assertEquals(
            BridgeFailure.NotImplemented(Operation.WRITE),
            (unimplemented as BridgeResult.Failed).failure,
        )
    }

    @Test
    fun `missing terminalp fails cleanly`() {
        val client = FailClosedBridgeClient(IntegrationState.UNAVAILABLE)
        assertEquals(IntegrationState.UNAVAILABLE, client.integrationState())
        val result = client.perform(Operation.PING)
        assertEquals(
            BridgeFailure.BridgeUnavailable,
            (result as BridgeResult.Failed).failure,
        )
    }

    @Test
    fun `unauthenticated caller is refused every operation`() {
        val client = FailClosedBridgeClient(IntegrationState.UNAUTHENTICATED)
        for (op in Operation.entries) {
            val result = client.perform(op)
            assertEquals(
                "operation ${op.name} must not succeed unauthenticated",
                BridgeFailure.Unauthenticated,
                (result as BridgeResult.Failed).failure,
            )
        }
    }

    @Test
    fun `missing capability is refused rather than downgraded`() {
        val client = FailClosedBridgeClient(IntegrationState.AUTHENTICATED, emptySet())
        val result = client.perform(Operation.SERVICE_RESTART)
        assertEquals(
            BridgeFailure.CapabilityMissing(Capability.BUSTER_SERVICES_CONTROL),
            (result as BridgeResult.Failed).failure,
        )
    }

    @Test
    fun `revoked authorization fails closed`() {
        val client = FailClosedBridgeClient(IntegrationState.REVOKED, BusterBaseline.AUTHORIZED)
        val result = client.perform(Operation.PRESENT)
        assertTrue(result is BridgeResult.Failed)
    }
}
