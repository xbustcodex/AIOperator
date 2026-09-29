package com.primetech.buster.ui

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.primetech.buster.BusterApplication
import com.primetech.buster.diagnostics.DiagnosticItem
import com.primetech.buster.state.ApkState
import com.primetech.buster.state.BusterUiState
import com.primetech.buster.state.IntegrationState
import com.primetech.buster.state.RuntimeState
import com.primetech.buster.transfer.TransferDirection
import com.primetech.buster.transfer.TransferState

/**
 * The Buster launcher surface.
 *
 * Every row renders observed state. An action is enabled only when a real
 * bounded implementation exists; nothing here can manufacture a success.
 */
class BusterActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val app = application as BusterApplication
        val model = BusterViewModel(app)
        model.refresh()

        setContent {
            MaterialTheme {
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .verticalScroll(rememberScrollState())
                        .padding(16.dp)
                ) {
                    Text("Buster", style = MaterialTheme.typography.headlineMedium)
                    Spacer(Modifier.height(12.dp))

                    AppCard(model.state)
                    Spacer(Modifier.height(8.dp))
                    RuntimeCard(model.state)
                    Spacer(Modifier.height(8.dp))
                    IntegrationCard(model.state)
                    Spacer(Modifier.height(16.dp))

                    Text("Actions", style = MaterialTheme.typography.titleMedium)
                    Spacer(Modifier.height(8.dp))

                    val note = remember { mutableStateOf<String?>(null) }

                    Button(
                        enabled = model.canOpenBuster,
                        onClick = { note.value = model.openBuster().toString() },
                        modifier = Modifier.fillMaxWidth(),
                    ) { Text("Open Buster") }

                    Spacer(Modifier.height(8.dp))
                    OutlinedButton(
                        enabled = model.canRunDiagnostics,
                        onClick = { model.runDiagnostics() },
                        modifier = Modifier.fillMaxWidth(),
                    ) { Text("Diagnostics") }

                    // Not actionable yet: the TerminalP operation does not exist.
                    Spacer(Modifier.height(8.dp))
                    OutlinedButton(
                        enabled = model.canStartOrRestart,
                        onClick = { },
                        modifier = Modifier.fillMaxWidth(),
                    ) { Text("Start / Restart — not available yet") }

                    Spacer(Modifier.height(8.dp))
                    OutlinedButton(
                        enabled = true,
                        onClick = { model.beginUserMediatedSelection(TransferDirection.IMPORT) },
                        modifier = Modifier.fillMaxWidth(),
                    ) { Text("Import — choose a document") }

                    Spacer(Modifier.height(8.dp))
                    OutlinedButton(
                        enabled = true,
                        onClick = { model.beginUserMediatedSelection(TransferDirection.EXPORT) },
                        modifier = Modifier.fillMaxWidth(),
                    ) { Text("Export — choose a destination") }

                    note.value?.let { value ->
                        Spacer(Modifier.height(8.dp))
                        Text(value, style = MaterialTheme.typography.bodySmall)
                    }

                    Spacer(Modifier.height(12.dp))
                    Text(
                        model.authorizationSummary(),
                        style = MaterialTheme.typography.bodySmall,
                    )

                    when (val t = model.lastTransfer) {
                        is TransferState.Idle -> Unit
                        is TransferState.AwaitingUserSelection ->
                            Text(app.transfer.describe(t))
                        is TransferState.Selected ->
                            Text(app.transfer.describe(t) + " — transfer not available yet")
                        is TransferState.Refused -> Text(app.transfer.describe(t))
                        is TransferState.NotImplemented -> Text(app.transfer.describe(t))
                    }

                    if (model.diagnostics.isNotEmpty()) {
                        Spacer(Modifier.height(12.dp))
                        Text("Diagnostics", style = MaterialTheme.typography.titleMedium)
                        model.diagnostics.forEach { d ->
                            when (d) {
                                is DiagnosticItem.Row ->
                                    Text("${d.label}: ${d.value}", style = MaterialTheme.typography.bodySmall)
                                is DiagnosticItem.Failure ->
                                    Text("${d.operation.guestVerb}: ${d.reason}", style = MaterialTheme.typography.bodySmall)
                            }
                        }
                    }

                    Spacer(Modifier.height(24.dp))
                    Text(
                        "Buster OS remains the single runtime, hosted by TerminalP " +
                            "and PRootDistro. This app is its Android identity and client.",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
        }
    }
}

@Composable
private fun AppCard(state: BusterUiState) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp)) {
            Text("App", style = MaterialTheme.typography.titleMedium)
            Text("version: ${state.apkVersionName} (${state.apkVersionCode})", style = MaterialTheme.typography.bodySmall)
            Text("identity: ${state.signingFlavor}", style = MaterialTheme.typography.bodySmall)
            Text("state: ${apkLabel(state.apk)}", style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun RuntimeCard(state: BusterUiState) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp)) {
            Text("Runtime", style = MaterialTheme.typography.titleMedium)
            Text("state: ${runtimeLabel(state.runtime)}", style = MaterialTheme.typography.bodySmall)
            Text(
                "version: ${state.deployedRuntimeVersion ?: "none deployed"}",
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

@Composable
private fun IntegrationCard(state: BusterUiState) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp)) {
            Text("Integration", style = MaterialTheme.typography.titleMedium)
            Text("state: ${integrationLabel(state.integration)}", style = MaterialTheme.typography.bodySmall)
        }
    }
}

private fun apkLabel(s: ApkState): String = when (s) {
    ApkState.ABSENT -> "Absent"
    ApkState.INSTALLED -> "Installed"
    ApkState.UPDATE_AVAILABLE -> "Update available"
    ApkState.INCOMPATIBLE -> "Incompatible"
}

private fun runtimeLabel(s: RuntimeState): String = when (s) {
    RuntimeState.NOT_DEPLOYED -> "Not deployed"
    RuntimeState.STOPPED -> "Stopped"
    RuntimeState.STARTING -> "Starting"
    RuntimeState.RUNNING -> "Running"
    RuntimeState.UNHEALTHY -> "Unhealthy"
    RuntimeState.UNAVAILABLE -> "Unavailable"
}

private fun integrationLabel(s: IntegrationState): String = when (s) {
    IntegrationState.UNAVAILABLE -> "Unavailable"
    IntegrationState.UNAUTHENTICATED -> "Unauthenticated"
    IntegrationState.AUTHENTICATED -> "Authenticated"
    IntegrationState.AUTHORIZED -> "Authorized"
    IntegrationState.PARTIALLY_AUTHORIZED -> "Partially authorized"
    IntegrationState.REVOKED -> "Revoked"
}
