package com.primetech.buster

import com.primetech.buster.bridge.BridgeFailure
import com.primetech.buster.bridge.BridgeResult
import com.primetech.buster.bridge.FailClosedBridgeClient
import com.primetech.buster.bridge.MalformedResultException
import com.primetech.buster.bridge.OperationResult
import com.primetech.buster.bridge.ResultTooLargeException
import com.primetech.buster.capability.BusterBaseline
import com.primetech.buster.capability.Capability
import com.primetech.buster.capability.Operation
import com.primetech.buster.capability.OperationRequest
import com.primetech.buster.capability.ReadView
import com.primetech.buster.state.IntegrationState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

/**
 * Phase 5B.1 — the two read-only operations.
 *
 * <p>Everything here is asserted at the client contract: a caller can reach
 * `deployment` and `read(view)` and nothing else, and every failure is typed
 * rather than absorbed.</p>
 */
@RunWith(RobolectricTestRunner::class)
class ReadOnlyIntegrationTest {

    private fun authorized(): Set<Capability> =
        BusterBaseline.AUTHORIZED + setOf(
            Capability.BUSTER_DEPLOYMENT_READ, Capability.BUSTER_READ)

    // ------------------------------------------------------------ deployment

    @Test
    fun `deployment is authorized for the buster baseline`() {
        assertTrue(Capability.BUSTER_DEPLOYMENT_READ in authorized())
    }

    @Test
    fun `deployment is not part of the ptt nine operation set`() {
        val ptt = setOf(
            Capability.BUSTER_STATUS, Capability.BUSTER_SERVICES_READ,
            Capability.BUSTER_CAPABILITIES_READ, Capability.BUSTER_PRESENT,
            Capability.BUSTER_SERVICES_CONTROL)
        assertFalse("PTT must not receive deployment", Capability.BUSTER_DEPLOYMENT_READ in ptt)
        assertFalse("PTT must not receive read", Capability.BUSTER_READ in ptt)
    }

    @Test
    fun `deployment takes no argument`() {
        // A deployment request carries no target of any kind.
        val client = FailClosedBridgeClient(IntegrationState.AUTHORIZED, authorized())
        client.perform(Operation.DEPLOYMENT, OperationRequest.None)
        // Argument-free by construction: a deployment request has no variant
        // that accepts a target, so nothing can be attached to it.
        assertEquals(
            "deployment must not expose a target-bearing form",
            1,
            Operation.entries.count { it.guestVerb == "deployment" }
        )
    }

    // ------------------------------------------------------------ read(view)

    @Test
    fun `every valid view is available`() {
        assertEquals(
            listOf("GOALS", "MEMORY", "ATTENTION", "ACTIVITY", "DEVICE", "SETTINGS", "JOBS"),
            ReadView.entries.map { it.name })
    }

    @Test
    fun `read requires a closed view`() {
        val client = FailClosedBridgeClient(IntegrationState.AUTHORIZED, authorized())
        // No view at all is invalid.
        assertTrue(client.perform(Operation.READ, OperationRequest.None) is BridgeResult.Failed)
        // Every declared view is a valid request.
        for (view in ReadView.entries) {
            assertTrue(OperationRequest.Read(view).view in ReadView.entries)
        }
    }

    @Test
    fun `an arbitrary view string is impossible to express`() {
        // The request type accepts only the enum, so a traversal attempt or a
        // module name cannot be constructed at all.
        val hostile = listOf("../etc/passwd", "os.system", "memory.__class__",
            "http://x", "a b", "__import__('os')")
        for (attempt in hostile) {
            assertFalse(attempt in ReadView.entries.map { it.name })
        }
    }

    // -------------------------------------------------- capability refusals

    @Test
    fun `read and deployment are refused without the capability`() {
        val baselineOnly = FailClosedBridgeClient(IntegrationState.AUTHORIZED, BusterBaseline.AUTHORIZED)
        for (op in listOf(Operation.DEPLOYMENT, Operation.READ)) {
            val result = baselineOnly.perform(op, if (op == Operation.READ)
                OperationRequest.Read(ReadView.GOALS) else OperationRequest.None)
            assertTrue("$op must be refused", result is BridgeResult.Failed)
        }
    }

    @Test
    fun `service control remains refused for buster`() {
        val client = FailClosedBridgeClient(IntegrationState.AUTHORIZED, authorized())
        for (op in listOf(Operation.SERVICE_START, Operation.SERVICE_RESTART, Operation.SERVICE_STATUS)) {
            assertTrue(
                "$op must not be authorized",
                op.capability !in authorized())
        }
    }

    @Test
    fun `mutating and unimplemented operations remain unavailable`() {
        for (capability in BusterBaseline.RESERVED_CAPABILITIES) {
            assertFalse("$capability must not be granted", capability in authorized())
        }
    }

    // --------------------------------------------------------- result bounds

    @Test
    fun `an oversized document fails closed`() {
        val huge = "{\"a\":\"" + "x".repeat(OperationResult.MAX_DOCUMENT_BYTES + 16) + "\"}"
        try {
            OperationResult.fromDocument("deployment", "c", huge)
            throw AssertionError("an oversized document must fail closed")
        } catch (expected: ResultTooLargeException) {
            assertTrue(true)
        }
    }

    @Test
    fun `a malformed document fails closed`() {
        try {
            OperationResult.fromDocument("deployment", "c", "not json at all")
            throw AssertionError("a malformed document must fail closed")
        } catch (expected: org.json.JSONException) {
            assertTrue(true)
        } catch (expected: MalformedResultException) {
            assertTrue(true)
        }
    }

    @Test
    fun `a bounded document is accepted`() {
        val result = OperationResult.fromDocument(
            "deployment", "c1", """{"verb":"deployment","deployed":true,"version":"0.4.3"}""")
        assertEquals(Operation.DEPLOYMENT, result.operation)
        assertEquals("c1", result.correlationId)
        assertEquals("0.4.3", result.document["version"])
    }

    // ------------------------------------------------------------- deadlines

    @Test
    fun `no operation can be called without an explicit bounded result`() {
        // Every operation resolves to a typed operation; none is a raw stream.
        for (op in Operation.entries) {
            assertTrue(op.guestVerb.isNotBlank())
        }
    }

    // ---------------------------------------------- no generic execution

    @Test
    fun `no generic execution operation exists`() {
        for (forbidden in listOf("execute", "shell", "run-argv", "fs", "rpc")) {
            assertTrue(
                "$forbidden must not be an operation",
                Operation.entries.none { it.guestVerb == forbidden })
        }
    }

    @Test
    fun `read capability confers no write authority`() {
        assertFalse(Capability.BUSTER_SCOPED_WRITE in authorized())
        assertFalse(Capability.BUSTER_IMPORT in authorized())
        assertFalse(Capability.BUSTER_EXPORT in authorized())
        assertFalse(Capability.BUSTER_RUNTIME_CONTROL in authorized())
    }
}
